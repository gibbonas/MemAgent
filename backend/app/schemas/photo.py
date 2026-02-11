"""
Pydantic Schemas for Photo Operations - MemAgent
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PhotoMetadata(BaseModel):
    """Metadata for a photo."""
    media_item_id: str
    url: str
    filename: Optional[str] = None
    creation_time: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None


class PhotoSuggestion(BaseModel):
    """Suggested photo for reference."""
    media_item_id: str
    url: str
    thumbnail_url: Optional[str] = None
    creation_time: Optional[datetime] = None
    description: Optional[str] = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class PhotoSearchRequest(BaseModel):
    """Request for searching photos."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    content_categories: List[str] = Field(default_factory=list)
    max_results: int = Field(default=5, ge=1, le=20)


class PhotoUploadRequest(BaseModel):
    """Request for uploading a photo."""
    image_path: str
    filename: str
    description: Optional[str] = None
    album_id: Optional[str] = None
