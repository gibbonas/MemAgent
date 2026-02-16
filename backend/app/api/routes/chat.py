"""
Chat Routes - MemAgent

Endpoints for chat interaction with memory agents.
"""

import asyncio
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.team import MemoryTeam, create_memory_team
from app.core.llm_errors import is_retryable_llm_error, parse_llm_error
from app.core.monitoring import logger
from app.core.security import OAuthManager
from app.core.token_tracker import TokenTracker
from app.deps import get_db
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ReferenceSelectionBody, GenerateFromReferencesBody
from app.tools.google_photos import GooglePhotosClient

# Retry config for transient LLM errors (503, 429)
MAX_LLM_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2

router = APIRouter()
oauth_manager = OAuthManager()

# In-memory cache for MemoryTeam instances (persists across requests)
# In production, consider Redis or database-backed storage
_team_cache: Dict[str, MemoryTeam] = {}


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the memory agent team.
    
    This endpoint handles the conversation flow with the multi-agent system.
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
        
        # Get or create memory team (cached per user to maintain conversation state)
        if user_id not in _team_cache:
            _team_cache[user_id] = create_memory_team(google_photos_client, token_tracker)
            logger.info("team_created_for_user", user_id=user_id)
        
        team = _team_cache[user_id]
        
        # Get or create session ID
        session_id = request.session_id or f"session_{user_id}_{int(__import__('time').time())}"
        
        # Process message through team (with retry on 503/429)
        last_error = None
        for attempt in range(MAX_LLM_RETRIES):
            try:
                result = await team.process_memory(
                    user_message=request.message,
                    user_id=user_id,
                    session_id=session_id
                )
                break
            except HTTPException:
                raise
            except Exception as e:
                last_error = e
                if attempt < MAX_LLM_RETRIES - 1 and is_retryable_llm_error(e):
                    logger.warning(
                        "chat_llm_retry",
                        attempt=attempt + 1,
                        max_retries=MAX_LLM_RETRIES,
                        error=str(e)[:200],
                        user_id=user_id,
                    )
                    await asyncio.sleep(LLM_RETRY_DELAY_SECONDS)
                    continue
                raise
        
        # Build metadata with all relevant info
        metadata = {
            "stage": result.get("stage")
        }
        
        # Add reference photos if available (legacy list from search)
        if result.get("reference_photos"):
            metadata["reference_photos"] = result.get("reference_photos")
        # Picker flow: URI and session id for user to open Google Photos
        if result.get("picker_uri"):
            metadata["picker_uri"] = result.get("picker_uri")
        if result.get("picker_session_id"):
            metadata["picker_session_id"] = result.get("picker_session_id")
        if result.get("polling_interval_seconds") is not None:
            metadata["polling_interval_seconds"] = result.get("polling_interval_seconds")
        if result.get("requires_reauth"):
            metadata["requires_reauth"] = True
        
        # Add image info if available - convert local path to backend URL with user_id for auth
        if result.get("image_path"):
            import os
            import time
            filename = os.path.basename(result.get("image_path"))
            # Add cache-busting so browser fetches updated image after edits (filename has timestamp; extra safety)
            metadata["image_url"] = f"http://localhost:8000/api/photos/images/{filename}?user_id={user_id}&t={int(time.time())}"
        
        # Add Google Photos URL if available
        if result.get("google_photos_url"):
            metadata["google_photos_url"] = result.get("google_photos_url")
        
        # Add extraction data if available
        if result.get("extraction"):
            metadata["extraction"] = result.get("extraction")
        
        return ChatMessageResponse(
            message=result.get("message", ""),
            session_id=session_id,
            status=result.get("status", "success"),
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat_message_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=500,
            detail=parse_llm_error(e),
        )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat session history.
    
    Returns conversation history for a session.
    """
    # TODO: Implement session history retrieval from Agno storage
    return {
        "session_id": session_id,
        "user_id": user_id,
        "messages": []
    }


@router.post("/sessions")
async def create_session(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new chat session.
    """
    import time
    session_id = f"session_{user_id}_{int(time.time())}"
    
    logger.info("chat_session_created", session_id=session_id, user_id=user_id)
    
    return {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": __import__('datetime').datetime.utcnow().isoformat()
    }


@router.get("/reference-thumbnail")
async def get_reference_thumbnail(
    user_id: str = Query(...),
    session_id: str = Query(...),
    index: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Proxy Google Photos reference thumbnail. Fetches with user's OAuth and returns image bytes.
    Used for displaying reference photo thumbnails (Google baseUrl requires auth).
    """
    try:
        if user_id not in _team_cache:
            raise HTTPException(status_code=404, detail="Session not found")
        team = _team_cache[user_id]
        state = team.get_session_state(session_id)
        urls = state.selected_reference_urls or []
        if index >= len(urls):
            raise HTTPException(status_code=404, detail="Reference photo not found")
        url = urls[index]
        # Append dimension for thumbnail if not present
        fetch_url = url if "=" in url else f"{url.rstrip('/')}=w200-h200"
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = credentials.token
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                fetch_url,
                headers={"Authorization": f"Bearer {token}"},
            )
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg")
        return Response(content=r.content, media_type=content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("reference_thumbnail_proxy_failed", error=str(e), index=index)
        raise HTTPException(status_code=500, detail="Failed to load thumbnail")


async def _fetch_thumbnail_as_data_url(url: str, token: str) -> Optional[str]:
    """Fetch image from Google Photos URL and return as data URL for inline display."""
    try:
        fetch_url = url if "=" in url else f"{url.rstrip('/')}=w200-h200"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(fetch_url, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        ct = r.headers.get("content-type", "image/jpeg")
        import base64
        b64 = base64.b64encode(r.content).decode("utf-8")
        return f"data:{ct};base64,{b64}"
    except Exception:
        return None


@router.post("/references/store")
async def store_reference_photos(
    body: ReferenceSelectionBody,
    session_id: str = Query(...),
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Store reference photo selection and return reference_photos for display.
    Call /references/generate next to run generation.
    """
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        if user_id not in _team_cache:
            raise HTTPException(status_code=400, detail="No active session found. Please start over.")
        team = _team_cache[user_id]
        result = await team.store_reference_selection(
            session_id=session_id,
            user_id=user_id,
            selected_photo_ids=body.selected_photo_ids,
            reference_photo_urls=body.reference_photo_urls
        )
        if result.get("status") == "error":
            return ChatMessageResponse(
                message=result.get("message", "Error"),
                session_id=session_id,
                status="error",
                metadata={"stage": result.get("stage")}
            )
        refs = result.get("reference_photos", [])
        urls = body.reference_photo_urls or []
        token = credentials.token
        for i, ref in enumerate(refs):
            if i < len(urls):
                data_url = await _fetch_thumbnail_as_data_url(urls[i], token)
                if data_url:
                    ref["thumbnail_data_url"] = data_url
        return ChatMessageResponse(
            message=result.get("message", ""),
            session_id=session_id,
            status=result.get("status", "success"),
            metadata={
                "stage": result.get("stage"),
                "reference_photos": refs,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("store_reference_photos_error", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=parse_llm_error(e))


@router.post("/references/generate")
async def generate_from_references(
    body: Optional[GenerateFromReferencesBody] = Body(default=None),
    session_id: str = Query(...),
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Run screening and generation using stored reference selection."""
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        if user_id not in _team_cache:
            raise HTTPException(status_code=400, detail="No active session found. Please start over.")
        team = _team_cache[user_id]
        photo_context = body.additional_context if body else None
        result = await team.run_generation_from_stored_refs(
            user_id=user_id,
            session_id=session_id,
            photo_context=photo_context
        )
        metadata = {"stage": result.get("stage")}
        state = team.get_session_state(session_id)
        ref_urls = state.selected_reference_urls or []
        if ref_urls:
            refs = [{"media_item_id": str(i), "index": i} for i in range(len(ref_urls))]
            token = credentials.token
            for i, ref in enumerate(refs):
                if i < len(ref_urls):
                    data_url = await _fetch_thumbnail_as_data_url(ref_urls[i], token)
                    if data_url:
                        ref["thumbnail_data_url"] = data_url
            metadata["reference_photos"] = refs
        if result.get("image_path"):
            import os
            import time
            filename = os.path.basename(result.get("image_path"))
            metadata["image_url"] = f"http://localhost:8000/api/photos/images/{filename}?user_id={user_id}&t={int(time.time())}"
        if result.get("google_photos_url"):
            metadata["google_photos_url"] = result.get("google_photos_url")
        if result.get("extraction"):
            metadata["extraction"] = result.get("extraction")
        return ChatMessageResponse(
            message=result.get("message", ""),
            session_id=session_id,
            status=result.get("status", "success"),
            metadata=metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_from_references_error", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=parse_llm_error(e))


@router.post("/references/select")
async def select_reference_photos(
    body: ReferenceSelectionBody,
    session_id: str = Query(...),
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm user's reference photo selection and continue to generation.
    
    Body: selected_photo_ids (list), optional reference_photo_urls (from Picker).
    """
    try:
        credentials = await oauth_manager.get_credentials(user_id, db)
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        google_photos_client = GooglePhotosClient(credentials)
        token_tracker = TokenTracker(db)
        
        if user_id not in _team_cache:
            raise HTTPException(status_code=400, detail="No active session found. Please start over.")
        
        team = _team_cache[user_id]
        
        result = await team.confirm_reference_selection(
            session_id=session_id,
            user_id=user_id,
            selected_photo_ids=body.selected_photo_ids,
            reference_photo_urls=body.reference_photo_urls
        )
        
        # Build metadata
        metadata = {
            "stage": result.get("stage")
        }
        
        # Add reference photos for thumbnail display (proxy URL uses index)
        state = team.get_session_state(session_id)
        ref_urls = state.selected_reference_urls or []
        ref_ids = state.selected_reference_ids or []
        if ref_urls:
            metadata["reference_photos"] = [
                {
                    "media_item_id": ref_ids[i] if i < len(ref_ids) else str(i),
                    "index": i,
                }
                for i in range(len(ref_urls))
            ]
        
        if result.get("image_path"):
            import os
            import time
            filename = os.path.basename(result.get("image_path"))
            metadata["image_url"] = f"http://localhost:8000/api/photos/images/{filename}?user_id={user_id}&t={int(time.time())}"
        
        if result.get("google_photos_url"):
            metadata["google_photos_url"] = result.get("google_photos_url")
        
        return ChatMessageResponse(
            message=result.get("message", ""),
            session_id=session_id,
            status=result.get("status", "success"),
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("select_reference_photos_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=500,
            detail=parse_llm_error(e),
        )
