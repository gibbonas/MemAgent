"""
Dependency Injection - MemAgent

Provides FastAPI dependencies for database sessions, authentication, etc.
"""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from jose import JWTError

from app.core.jwt_utils import ACCESS_TOKEN_COOKIE_NAME, verify_token
from app.storage.database import async_session_maker


class CurrentUser:
    """Authenticated user from JWT (cookie or Bearer)."""

    def __init__(self, user_id: str, email: str | None = None):
        self.user_id = user_id
        self.email = email


def get_current_user(request: Request) -> CurrentUser:
    """
    Require valid JWT from cookie (access_token) or Authorization: Bearer <token>.
    Returns CurrentUser or raises 401.
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not token and request.headers.get("Authorization"):
        auth = request.headers["Authorization"]
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        email = payload.get("email")
        return CurrentUser(user_id=str(user_id), email=email)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_id_for_asset(request: Request, token: str | None = Query(None)) -> str:
    """
    For asset URLs (image, reference-thumbnail): get user_id from token query param
    (short-lived asset token) or from JWT cookie/header. Returns user_id or raises 401.
    """
    if token:
        try:
            payload = verify_token(token)
            uid = payload.get("sub")
            if uid:
                return str(uid)
        except JWTError:
            pass
    # Fall back to full JWT auth
    current = get_current_user(request)
    return current.user_id


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def get_settings():
    """
    Dependency that provides application settings.
    
    Returns:
        Settings: Application settings
    """
    return settings
