"""
Database Models - MemAgent

SQLAlchemy models for users, memories, OAuth tokens, and token usage tracking.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class MemoryStatus(str, Enum):
    """Status of a memory processing job."""
    COLLECTING = "collecting"
    SCREENING = "screening"
    ENRICHING = "enriching"
    GENERATING = "generating"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    POLICY_VIOLATION = "policy_violation"


class PhotoSource(str, Enum):
    """Source of a reference photo."""
    GOOGLE_PHOTOS = "google_photos"
    MANUAL_UPLOAD = "manual_upload"


class User(Base):
    """User model for authentication and tracking."""
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_users_google_user_id", "google_user_id"),
    )


class OAuthToken(Base):
    """OAuth tokens for Google Photos API access."""
    __tablename__ = "oauth_tokens"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    access_token: Mapped[str] = mapped_column(Text)  # Should be encrypted in production
    refresh_token: Mapped[str] = mapped_column(Text)  # Should be encrypted in production
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_oauth_tokens_user_id", "user_id"),
    )


class Memory(Base):
    """Memory record with all metadata and processing status."""
    __tablename__ = "memories"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    
    # Story content
    story_text: Mapped[str] = mapped_column(Text)
    memory_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gps_coordinates: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {lat: float, lng: float}
    people_tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    pet_tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    
    # Generated content
    google_photos_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generated_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Status and tracking
    status: Mapped[MemoryStatus] = mapped_column(SQLEnum(MemoryStatus), default=MemoryStatus.COLLECTING)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    content_violations: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("idx_memories_user_id", "user_id"),
        Index("idx_memories_session_id", "session_id"),
        Index("idx_memories_status", "status"),
        Index("idx_memories_created_at", "created_at"),
    )


class ReferencePhoto(Base):
    """Reference photos used for image generation."""
    __tablename__ = "reference_photos"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    media_item_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    source: Mapped[PhotoSource] = mapped_column(SQLEnum(PhotoSource))
    photo_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Store photo metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_reference_photos_memory_id", "memory_id"),
    )


class TokenUsage(Base):
    """Token usage tracking for budgeting and monitoring."""
    __tablename__ = "token_usage"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("idx_token_usage_user_timestamp", "user_id", "timestamp"),
        Index("idx_token_usage_session", "session_id"),
    )
