"""
Authentication Routes - MemAgent

OAuth 2.0 flow for Google Photos API access.
Handles authorization, callback, and token management.
"""

import secrets
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.monitoring import logger
from app.core.security import OAuthManager
from app.deps import get_db

router = APIRouter()
oauth_manager = OAuthManager()

# Store CSRF state tokens (in production, use Redis)
state_tokens: Dict[str, bool] = {}


@router.get("/google")
async def google_auth():
    """
    Initiate Google OAuth flow.
    
    Redirects user to Google consent screen.
    """
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    state_tokens[state] = True
    
    # Get authorization URL
    auth_url = oauth_manager.get_authorization_url(state)
    
    logger.info("oauth_flow_initiated", state=state)
    
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback handler.
    
    Exchanges authorization code for tokens and stores them.
    """
    # Verify CSRF state
    if state not in state_tokens:
        logger.error("oauth_invalid_state", state=state)
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Remove used state token
    state_tokens.pop(state)
    
    # Exchange code for tokens
    result = await oauth_manager.exchange_code_for_tokens(code, db)
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    
    logger.info("oauth_callback_success", user_id=result["user_id"])
    
    # Redirect to frontend with success
    # In production, include user_id in a secure way (JWT, session, etc.)
    return RedirectResponse(url=f"{settings.frontend_url}/auth/success?user_id={result['user_id']}")


@router.get("/status")
async def auth_status(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Check authentication status for a user.
    """
    credentials = await oauth_manager.get_credentials(user_id, db)
    
    if not credentials:
        return {"authenticated": False}
    
    # Safely get email from id_token if it exists
    email = ""
    if hasattr(credentials, 'id_token') and credentials.id_token:
        if isinstance(credentials.id_token, dict):
            email = credentials.id_token.get("email", "")
    
    return {
        "authenticated": True,
        "email": email,
        "expires_at": credentials.expiry.isoformat() if credentials.expiry else None
    }


@router.post("/logout")
async def logout(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke OAuth tokens and log out user.
    """
    success = await oauth_manager.revoke_tokens(user_id, db)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to revoke tokens")
    
    logger.info("user_logged_out", user_id=user_id)
    
    return {"status": "logged_out"}
