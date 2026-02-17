"""
Photos Routes - MemAgent

Endpoints for photo suggestions, Picker API (reference photo selection), and memory management.
"""

from typing import List
import os
import re
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.monitoring import logger
from app.core.security import OAuthManager
from app.core.token_tracker import TokenTracker
from app.deps import get_db
from app.schemas.photo import PhotoSuggestion
from app.storage.models import Memory
from app.tools.exif_writer import EXIFWriter
from app.tools.google_photos import GooglePhotosClient
from app.tools.google_photos_picker import GooglePhotosPickerClient, PickerUnauthorizedError

router = APIRouter()
oauth_manager = OAuthManager()


def _parse_poll_interval(duration_str: str) -> int:
    """Parse Google duration string (e.g. '3.5s') to seconds. Default 3."""
    if not duration_str:
        return 3
    m = re.match(r"^(\d+(?:\.\d+)?)s$", duration_str.strip())
    return int(float(m.group(1))) if m else 3


# ---- Google Photos Picker API (reference photo selection) ----

@router.post("/picker/session")
async def create_picker_session(
    user_id: str = Query(...),
    max_items: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Picker session so the user can select reference photos in Google Photos.
    Returns picker_uri (open in new tab) and picker_session_id for polling.
    """
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        picker = GooglePhotosPickerClient(credentials)
        session = picker.create_session(max_items=max_items)
        picker_uri = session.get("pickerUri") or ""
        if picker_uri and not picker_uri.endswith("/autoclose"):
            picker_uri = picker_uri.rstrip("/") + "/autoclose"
        polling = session.get("pollingConfig") or {}
        poll_interval = _parse_poll_interval(polling.get("pollInterval"))
        return {
            "picker_uri": picker_uri,
            "picker_session_id": session.get("id"),
            "expire_time": session.get("expireTime"),
            "polling_interval_seconds": poll_interval,
        }
    except PickerUnauthorizedError as e:
        logger.warning("picker_unauthorized", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=401,
            detail="Google Photos is not connected. Connect Google Photos in the chat to select reference photos.",
        )
    except Exception as e:
        logger.error("picker_create_session_error", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/picker/session/{session_id}")
async def get_picker_session(
    session_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Poll Picker session status. When media_items_set is true, call list media and then select-references."""
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        picker = GooglePhotosPickerClient(credentials)
        session = picker.get_session(session_id)
        polling = session.get("pollingConfig") or {}
        poll_interval = _parse_poll_interval(polling.get("pollInterval"))
        return {
            "picker_session_id": session.get("id"),
            "media_items_set": session.get("mediaItemsSet", False),
            "expire_time": session.get("expireTime"),
            "polling_interval_seconds": poll_interval,
        }
    except Exception as e:
        logger.error("picker_get_session_error", error=str(e), session_id=session_id, user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/picker/session/{session_id}/media")
async def list_picker_media(
    session_id: str,
    user_id: str = Query(...),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List media items picked in this session. Call only after media_items_set is true."""
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        picker = GooglePhotosPickerClient(credentials)
        page = picker.list_media(session_id, page_size=page_size)
        items = page.get("mediaItems") or []
        # Normalize to shape frontend and backend expect: id, url (baseUrl), thumbnail_url, create_time
        out = []
        for it in items:
            mf = it.get("mediaFile") or {}
            base = mf.get("baseUrl") or ""
            out.append({
                "media_item_id": it.get("id"),
                "url": base,
                "thumbnail_url": f"{base}=w200-h200" if base else None,
                "create_time": it.get("createTime"),
            })
        return {"media_items": out, "next_page_token": page.get("nextPageToken")}
    except Exception as e:
        logger.error("picker_list_media_error", error=str(e), session_id=session_id, user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/picker/session/{session_id}")
async def delete_picker_session(
    session_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Delete a Picker session to free resources (optional, recommended after use)."""
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        picker = GooglePhotosPickerClient(credentials)
        picker.delete_session(session_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error("picker_delete_session_error", error=str(e), session_id=session_id, user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


# ---- Generated image serving and legacy suggestions ----

@router.get("/images/{image_filename}")
async def serve_generated_image(
    image_filename: str,
    user_id: str = Query(..., description="User ID for authentication"),
    download: int = Query(0, description="If 1, serve with Content-Disposition: attachment to trigger download"),
    db: AsyncSession = Depends(get_db)
):
    """
    Serve a generated image file with authentication.
    
    This endpoint serves images from the temporary storage directory.
    Only the user who owns the image can access it.
    Add ?download=1 to force the browser to download the file instead of displaying it.
    
    Image filename format: memory_{user_id}_{timestamp}.jpg
    """
    try:
        # Sanitize filename to prevent directory traversal
        if '..' in image_filename or '/' in image_filename or '\\' in image_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Verify user owns this image by checking user_id in filename
        if not image_filename.startswith(f"memory_{user_id}_"):
            logger.warning(
                "unauthorized_image_access_attempt",
                user_id=user_id,
                filename=image_filename
            )
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Verify user credentials exist (basic auth check)
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        image_path = os.path.join(settings.temp_image_dir, image_filename)
        
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        logger.info(
            "image_served",
            user_id=user_id,
            filename=image_filename
        )
        
        headers = {
            "Cache-Control": "private, max-age=3600",
            "Access-Control-Allow-Origin": settings.cors_origins[0] if settings.cors_origins else "*"
        }
        if download == 1:
            headers["Content-Disposition"] = f'attachment; filename="{image_filename}"'
        
        return FileResponse(
            path=image_path,
            media_type="image/jpeg",
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("serve_image_error", error=str(e), filename=image_filename, user_id=user_id)
        raise HTTPException(status_code=500, detail="Failed to serve image")


@router.post("/save-to-google-photos")
async def save_image_to_google_photos(
    image_filename: str = Query(..., description="Filename of the image to save (e.g. memory_xxx_123.jpg)"),
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload the generated memory image to the user's Google Photos library.
    """
    try:
        if ".." in image_filename or "/" in image_filename or "\\" in image_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        if not image_filename.startswith(f"memory_{user_id}_"):
            raise HTTPException(status_code=403, detail="Access denied")
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        image_path = os.path.join(settings.temp_image_dir, image_filename)
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        exif_meta = EXIFWriter.read_exif_metadata(image_path)
        description = (exif_meta.get("description") or "MemAgent memory").strip() or "MemAgent memory"
        client = GooglePhotosClient(credentials)
        result = await client.upload_photo(image_path=image_path, description=description)
        if not result:
            raise HTTPException(status_code=500, detail="Upload to Google Photos failed")
        return {"status": "ok", "google_photos_url": result.get("url"), "media_item_id": result.get("media_item_id")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("save_to_google_photos_error", error=str(e), user_id=user_id, image_filename=image_filename)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions", response_model=List[PhotoSuggestion])
async def get_photo_suggestions(
    user_id: str = Query(...),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get photo suggestions from Google Photos.
    
    Returns URLs and metadata only (NO image bytes).
    """
    try:
        # Get user's OAuth credentials
        credentials = await oauth_manager.get_credentials(user_id, db)
        
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Initialize Google Photos client
        client = GooglePhotosClient(credentials)
        
        # Search by date if provided
        if start_date:
            from datetime import datetime
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date) if end_date else None
            
            suggestions = await client.search_photos_by_date(start, end)
        else:
            # Return empty list if no search criteria
            suggestions = []
        
        logger.info(
            "photo_suggestions_retrieved",
            user_id=user_id,
            count=len(suggestions)
        )
        
        return suggestions
        
    except Exception as e:
        logger.error("photo_suggestions_error", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories")
async def list_memories(
    user_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List user's saved memories.
    """
    try:
        try:
            user_uuid = uuid_lib.UUID(user_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid user_id")
        result = await db.execute(
            select(Memory)
            .where(Memory.user_id == user_uuid)
            .order_by(Memory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        memories = result.scalars().all()
        
        return {
            "memories": [
                {
                    "id": str(m.id),
                    "story_text": m.story_text,
                    "memory_date": m.memory_date.isoformat() if m.memory_date else None,
                    "location": m.location,
                    "people_tags": m.people_tags,
                    "pet_tags": m.pet_tags,
                    "google_photos_url": m.google_photos_url,
                    "status": m.status.value,
                    "created_at": m.created_at.isoformat()
                }
                for m in memories
            ],
            "total": len(memories),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error("list_memories_error", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_photo(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a photo manually (for reference photos).
    """
    # TODO: Implement manual upload handling
    return {"status": "not_implemented"}


@router.post("/select-references")
async def select_reference_photos(
    selected_photo_ids: List[str] = Body(...),
    session_id: str = Query(...),
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit selected reference photos and continue to image generation.
    
    Args:
        selected_photo_ids: List of selected Google Photos media item IDs (in request body)
        session_id: Chat session ID
        user_id: User ID
        
    Returns:
        Result of continuing the pipeline with selected references
    """
    try:
        # Get user's OAuth credentials
        credentials = await oauth_manager.get_credentials(user_id, db)
        
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Initialize Google Photos client
        google_photos_client = GooglePhotosClient(credentials)
        
        # Initialize token tracker
        token_tracker = TokenTracker(db)
        
        # Get the memory team instance (ideally this should be cached/shared)
        from app.agents.team import create_memory_team
        team = create_memory_team(google_photos_client, token_tracker)
        
        # Process the reference selection (pass request-scoped tracker and client)
        result = await team.confirm_reference_selection(
            session_id,
            user_id,
            selected_photo_ids,
            token_tracker=token_tracker,
            google_photos_client=google_photos_client,
        )
        
        # Build response similar to chat message response
        metadata = {
            "stage": result.get("stage")
        }
        
        # Add image info if generation completed
        if result.get("image_path"):
            import os
            filename = os.path.basename(result.get("image_path"))
            metadata["image_url"] = f"{settings.backend_url.rstrip('/')}/api/photos/images/{filename}?user_id={user_id}"
        
        if result.get("google_photos_url"):
            metadata["google_photos_url"] = result.get("google_photos_url")
        
        if result.get("extraction"):
            metadata["extraction"] = result.get("extraction")
        
        return {
            "message": result.get("message", ""),
            "status": result.get("status", "success"),
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error("select_references_error", error=str(e), user_id=user_id, session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))
