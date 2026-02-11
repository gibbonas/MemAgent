"""
Pydantic Schemas for Memory Operations - MemAgent

Data models for API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryStatusEnum(str, Enum):
    """Status of memory processing."""
    COLLECTING = "collecting"
    SCREENING = "screening"
    ENRICHING = "enriching"
    GENERATING = "generating"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    POLICY_VIOLATION = "policy_violation"


class GPSCoordinates(BaseModel):
    """GPS coordinates for a location."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class MemoryCreate(BaseModel):
    """Schema for creating a new memory."""
    story_text: str = Field(..., min_length=10, max_length=5000)
    memory_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=500)
    gps_coordinates: Optional[GPSCoordinates] = None
    people_tags: List[str] = Field(default_factory=list)
    pet_tags: List[str] = Field(default_factory=list)


class MemoryUpdate(BaseModel):
    """Schema for updating a memory."""
    story_text: Optional[str] = Field(None, min_length=10, max_length=5000)
    memory_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=500)
    gps_coordinates: Optional[GPSCoordinates] = None
    people_tags: Optional[List[str]] = None
    pet_tags: Optional[List[str]] = None
    status: Optional[MemoryStatusEnum] = None


class MemoryResponse(BaseModel):
    """Schema for memory response."""
    id: UUID
    user_id: UUID
    session_id: str
    story_text: str
    memory_date: Optional[datetime]
    location: Optional[str]
    gps_coordinates: Optional[dict]
    people_tags: List[str]
    pet_tags: List[str]
    google_photos_url: Optional[str]
    media_item_id: Optional[str]
    generated_image_path: Optional[str]
    image_prompt: Optional[str]
    status: MemoryStatusEnum
    tokens_used: int
    content_violations: List[str]
    retry_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ContentScreeningResult(BaseModel):
    """Result of content policy screening."""
    approved: bool
    violations: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    severity: str = Field(default="none")  # none, low, medium, high


class MemoryExtraction(BaseModel):
    """Extracted memory details from user story."""
    what_happened: str
    when: Optional[datetime] = None
    when_description: Optional[str] = None  # Store relative time like "last summer", "2 years ago"
    who_people: List[str] = Field(default_factory=list)
    who_pets: List[str] = Field(default_factory=list)
    where: Optional[str] = None
    emotions_mood: Optional[str] = None
    additional_details: Optional[str] = None
    is_complete: bool = Field(default=False, description="Whether enough information has been collected")
    missing_fields: List[str] = Field(default_factory=list, description="Critical fields still needed")
