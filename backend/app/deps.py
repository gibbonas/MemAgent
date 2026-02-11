"""
Dependency Injection - MemAgent

Provides FastAPI dependencies for database sessions, authentication, etc.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.storage.database import async_session_maker


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
