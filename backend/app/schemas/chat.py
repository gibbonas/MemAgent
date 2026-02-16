"""
Pydantic Schemas for Chat Operations - MemAgent
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message schema."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: Optional[datetime] = None


class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session."""
    user_id: str


class ChatSessionResponse(BaseModel):
    """Schema for chat session response."""
    session_id: str
    user_id: str
    created_at: datetime
    message_count: int


class ChatMessageRequest(BaseModel):
    """Schema for sending a chat message."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    message: str
    session_id: str
    status: str = Field(default="success")
    metadata: Optional[dict] = None


class ReferenceSelectionBody(BaseModel):
    """Body for reference photo selection (Picker or legacy)."""
    selected_photo_ids: List[str] = Field(default_factory=list)
    reference_photo_urls: Optional[List[str]] = None  # From Picker mediaItems.list (baseUrl)


class GenerateFromReferencesBody(BaseModel):
    """Body for triggering generation from stored references."""
    additional_context: Optional[str] = None  # User notes about the reference photos
