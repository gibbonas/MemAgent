"""
JWT utilities for MemAgent.

Create and verify access tokens (cookie) and short-lived asset tokens (image/thumbnail URLs).
Uses python-jose with HS256 and settings.secret_key.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_COOKIE_NAME = "access_token"


def create_access_token(user_id: str, email: str | None = None) -> str:
    """Create a signed JWT for the access cookie. Payload: sub=user_id, email (optional), exp, iat."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_asset_token(user_id: str) -> str:
    """Create a short-lived JWT for image/thumbnail URLs (no cookie sent)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_asset_token_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "asset",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify JWT; return payload. Raises JWTError on invalid/expired."""
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
