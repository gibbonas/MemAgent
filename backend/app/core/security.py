"""
Security and OAuth Helpers - MemAgent

OAuth 2.0 flow for Google Photos API access with token storage and refresh.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.monitoring import logger
from app.storage.models import OAuthToken, User


class OAuthManager:
    """
    Manages OAuth 2.0 flow for Google Photos API.
    
    Handles authorization, token storage, and automatic refresh.
    """
    
    # Google Photos API scopes
    # Note: As of March 31, 2025, photoslibrary.readonly was removed. Full-library
    # search (mediaItems.search with date/content filters) now returns 403.
    # Use photospicker.mediaitems.readonly for user photo selection (Picker API).
    SCOPES = [
        'https://www.googleapis.com/auth/photospicker.mediaitems.readonly',  # Picker: user selects from library
        'https://www.googleapis.com/auth/photoslibrary.appendonly',          # Upload / create media
        'https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata',  # List/search app-created only
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]
    
    REDIRECT_URI = "http://localhost:8000/api/auth/callback"
    
    def __init__(self):
        """Initialize OAuth manager."""
        self.client_config = {
            "web": {
                "client_id": settings.google_auth_client_id,
                "client_secret": settings.google_auth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.REDIRECT_URI]
            }
        }
    
    def get_authorization_url(self, state: str) -> str:
        """
        Generate OAuth authorization URL.
        
        Args:
            state: CSRF state token
            
        Returns:
            Authorization URL to redirect user to
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            redirect_uri=self.REDIRECT_URI
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='false',  # Only request our SCOPES; avoids "Scope has changed" when user had older scopes
            state=state,
            prompt='consent'  # Force consent to get refresh token
        )
        
        logger.info("oauth_authorization_url_generated", state=state)
        return auth_url
    
    async def exchange_code_for_tokens(
        self,
        code: str,
        db: AsyncSession
    ) -> Optional[Dict[str, str]]:
        """
        Exchange authorization code for access/refresh tokens.
        
        Args:
            code: Authorization code from callback
            db: Database session
            
        Returns:
            Dict with user_id and email, or None if failed
        """
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=self.SCOPES,
                redirect_uri=self.REDIRECT_URI
            )
            
            flow.fetch_token(code=code)
            
            credentials = flow.credentials
            
            # Get user info from ID token
            from google.auth.transport.requests import Request
            import google.auth.transport.requests
            import json
            from jose import jwt
            
            # Decode ID token to get user info
            id_info = jwt.get_unverified_claims(credentials.id_token)
            
            google_user_id = id_info.get('sub')
            email = id_info.get('email')
            
            # Find or create user
            result = await db.execute(
                select(User).where(User.google_user_id == google_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    google_user_id=google_user_id,
                    email=email
                )
                db.add(user)
                await db.flush()
            
            # Store or update tokens
            result = await db.execute(
                select(OAuthToken).where(OAuthToken.user_id == user.id)
            )
            token_record = result.scalar_one_or_none()
            
            expires_at = datetime.utcnow() + timedelta(seconds=credentials.expiry.timestamp() - datetime.utcnow().timestamp())
            
            if token_record:
                token_record.access_token = credentials.token
                token_record.refresh_token = credentials.refresh_token or token_record.refresh_token
                token_record.expires_at = expires_at
                token_record.updated_at = datetime.utcnow()
            else:
                token_record = OAuthToken(
                    user_id=user.id,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    expires_at=expires_at
                )
                db.add(token_record)
            
            await db.commit()
            
            logger.info(
                "oauth_tokens_stored",
                user_id=str(user.id),
                email=email
            )
            
            return {
                "user_id": str(user.id),
                "email": email
            }
            
        except Exception as e:
            logger.error("oauth_token_exchange_failed", error=str(e))
            return None
    
    async def get_credentials(
        self,
        user_id: str,
        db: AsyncSession
    ) -> Optional[Credentials]:
        """
        Get OAuth credentials for a user, refreshing if needed.
        
        Args:
            user_id: User UUID (as string)
            db: Database session
            
        Returns:
            Google OAuth2 Credentials, or None if not found
        """
        try:
            # Convert string UUID to UUID object
            import uuid as uuid_lib
            user_uuid = uuid_lib.UUID(user_id)
            
            # Get token from database
            result = await db.execute(
                select(OAuthToken).where(OAuthToken.user_id == user_uuid)
            )
            token_record = result.scalar_one_or_none()
            
            if not token_record:
                logger.warning("oauth_token_not_found", user_id=user_id)
                return None
            
            # Create credentials
            credentials = Credentials(
                token=token_record.access_token,
                refresh_token=token_record.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_auth_client_id,
                client_secret=settings.google_auth_client_secret,
                scopes=self.SCOPES
            )
            
            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                
                # Update tokens in database
                token_record.access_token = credentials.token
                token_record.expires_at = credentials.expiry
                token_record.updated_at = datetime.utcnow()
                await db.commit()
                
                logger.info("oauth_token_refreshed", user_id=user_id)
            
            return credentials
            
        except Exception as e:
            logger.error("oauth_credentials_retrieval_failed", user_id=user_id, error=str(e))
            return None
    
    async def revoke_tokens(self, user_id: str, db: AsyncSession) -> bool:
        """
        Revoke OAuth tokens for a user.
        
        Args:
            user_id: User UUID (as string)
            db: Database session
            
        Returns:
            True if successful
        """
        try:
            # Convert string UUID to UUID object
            import uuid as uuid_lib
            user_uuid = uuid_lib.UUID(user_id)
            
            result = await db.execute(
                select(OAuthToken).where(OAuthToken.user_id == user_uuid)
            )
            token_record = result.scalar_one_or_none()
            
            if token_record:
                await db.delete(token_record)
                await db.commit()
                logger.info("oauth_tokens_revoked", user_id=user_id)
            
            return True
            
        except Exception as e:
            logger.error("oauth_revoke_failed", user_id=user_id, error=str(e))
            return False
