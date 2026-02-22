"""
Authentication Routes - MemAgent

OAuth 2.0 flow for Google Photos API access.
Handles authorization, callback, and token management.
"""

import secrets
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.jwt_utils import (
    ACCESS_TOKEN_COOKIE_NAME,
    create_access_token,
    create_asset_token,
)
from app.core.monitoring import logger
from app.core.security import OAuthManager
from app.deps import get_db, get_current_user, CurrentUser

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


@router.get("/google/photos")
async def google_photos_auth(
    user_id: str = Query(None),
    return_path: str = Query("/"),
):
    """
    Initiate Google OAuth flow for Photos (reconnect flow).
    Same as /google - used when "Connect Google Photos" is clicked for re-auth.
    """
    return await google_auth()


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
    
    # Issue JWT and set httpOnly cookie. SameSite=none so cookie is sent on cross-origin
    # requests (frontend on Vercel -> backend on Railway); Secure required when SameSite=none.
    access_token = create_access_token(result["user_id"], result.get("email"))
    redirect_url = f"{settings.frontend_url}/auth/success?user_id={result['user_id']}"
    response = RedirectResponse(url=redirect_url, status_code=302)
    max_age = settings.jwt_expire_minutes * 60
    is_https = settings.backend_url.strip().lower().startswith("https")
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="none" if is_https else "lax",
        secure=is_https,
    )
    return response


@router.get("/status")
async def auth_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check authentication status for the current user (from JWT).
    """
    credentials = await oauth_manager.get_credentials(current_user.user_id, db)
    
    if not credentials:
        return {"authenticated": False}
    
    # Safely get email from id_token if it exists
    email = current_user.email or ""
    if not email and hasattr(credentials, 'id_token') and credentials.id_token:
        if isinstance(credentials.id_token, dict):
            email = credentials.id_token.get("email", "")
    
    return {
        "authenticated": True,
        "user_id": current_user.user_id,
        "email": email,
        "expires_at": credentials.expiry.isoformat() if credentials.expiry else None
    }


@router.get("/asset-token")
async def get_asset_token(current_user: CurrentUser = Depends(get_current_user)):
    """
    Return a short-lived token for image/thumbnail URLs (img src cannot send cookies cross-origin).
    """
    token = create_asset_token(current_user.user_id)
    return {"token": token}


@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke OAuth tokens and clear auth cookie.
    """
    success = await oauth_manager.revoke_tokens(current_user.user_id, db)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to revoke tokens")
    
    logger.info("user_logged_out", user_id=current_user.user_id)
    
    response = JSONResponse(content={"status": "logged_out"})
    is_https = settings.backend_url.strip().lower().startswith("https")
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="none" if is_https else "lax",
        secure=is_https,
    )
    return response
