"""
Memory Team Orchestrator - MemAgent

Coordinates the multi-agent pipeline for memory preservation.

Pipeline: Collector → Screener → Enricher → Generator → Manager

This orchestrator manages the workflow, handles errors, tracks token usage,
maintains conversation state, and provides progress updates to the user.
"""

from typing import Dict, Optional, List
import asyncio
import json
import os
import re
from datetime import datetime

import httpx
from google.auth.transport.requests import Request

from agno.agent import Agent
from agno.team import Team

from app.agents.base import get_gemini_model
from app.agents.content_screener import create_content_screener_agent
from app.agents.context_enricher import create_context_enricher_agent
from app.agents.image_generator import create_image_generator_agent
from app.agents.memory_collector import create_memory_collector_agent, parse_collected_memory
from app.agents.photo_manager import create_photo_manager_agent
from app.config import settings
from app.core.monitoring import logger
from app.core.token_tracker import TokenTracker, TokenBudgetExceeded
from app.schemas.memory import MemoryExtraction
from app.tools.exif_writer import EXIFWriter
from app.tools.gemini_image import GeminiImageGenerator
from app.tools.google_photos import GooglePhotosClient
from app.tools.google_photos_picker import GooglePhotosPickerClient, PickerUnauthorizedError
from app.tools.location_resolver import LocationResolver


class ConversationState:
    """Maintains conversation state for memory collection."""
    
    def __init__(self):
        self.messages = []
        self.extraction: Optional[MemoryExtraction] = None
        self.stage = "collecting"
        self.reference_photos = []
        self.selected_reference_ids = []
        self.selected_reference_urls: List[str] = []  # URLs from Picker for image generation
        self.photo_context: Optional[str] = None  # Optional context user adds about reference photos
        self.last_generated_image_path: Optional[str] = None  # For edit flow and save
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
    
    def reset(self) -> None:
        """Clear all captured information and return to initial collecting stage."""
        self.messages = []
        self.extraction = None
        self.stage = "collecting"
        self.reference_photos = []
        self.selected_reference_ids = []
        self.selected_reference_urls = []
        self.photo_context = None
        self.last_generated_image_path = None
    
    def get_conversation_context(self) -> str:
        """Get formatted conversation context for the agent."""
        return "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in self.messages[-6:]  # Keep last 3 exchanges
        ])


class MemoryTeam:
    """
    Memory preservation team orchestrator.
    
    Coordinates agents in sequence with error handling, token tracking,
    and conversation state management.
    """
    
    def __init__(
        self,
        google_photos_client: GooglePhotosClient,
        token_tracker: TokenTracker
    ):
        """
        Initialize the memory team.
        
        Args:
            google_photos_client: Google Photos API client
            token_tracker: Token usage tracker
        """
        self.token_tracker = token_tracker
        self.google_photos_client = google_photos_client
        self.sessions: Dict[str, ConversationState] = {}
        
        # Initialize tools
        self.exif_writer = EXIFWriter()
        self.location_resolver = LocationResolver()
        self.image_generator = GeminiImageGenerator()
        
        # Initialize agents
        self.memory_collector = create_memory_collector_agent()
        self.content_screener = create_content_screener_agent()
        self.context_enricher = create_context_enricher_agent(google_photos_client)
        self.image_generator_agent = create_image_generator_agent(self.image_generator)
        self.photo_manager = create_photo_manager_agent(
            self.exif_writer,
            self.location_resolver,
            google_photos_client
        )
        
        logger.info("memory_team_initialized")
    
    def get_session_state(self, session_id: str) -> ConversationState:
        """Get or create conversation state for a session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationState()
        return self.sessions[session_id]
    
    @staticmethod
    def _user_wants_start_over(message: str) -> bool:
        """True if the user is asking to clear and start over."""
        lower = message.lower().strip()
        phrases = (
            "start over", "start again", "begin again", "clear", "reset",
            "new memory", "different memory", "forget that", "scrub that",
            "cancel", "never mind that",
        )
        return any(p in lower for p in phrases) or lower in ("clear", "reset", "cancel")
    
    @staticmethod
    def _user_wants_change_story(message: str) -> bool:
        """True if the user wants to go back and change the memory story."""
        lower = message.lower().strip()
        phrases = (
            "change my story", "change the story", "change what i said",
            "re-enter", "reenter", "different story", "edit my story",
            "go back", "go back to the story", "change my answer",
        )
        return any(p in lower for p in phrases)
    
    @staticmethod
    def _user_wants_change_references(message: str) -> bool:
        """True if the user wants to go back and pick different reference photos."""
        lower = message.lower().strip()
        phrases = (
            "change photos", "different photos", "pick different",
            "choose different", "other photos", "change references",
            "change reference", "change my reference", "change the reference",
            "go back to photos", "select again", "re-select", "reselect",
            "pick again", "choose again", "new reference", "different reference",
        )
        if any(p in lower for p in phrases):
            return True
        if ("change" in lower or "different" in lower) and ("reference" in lower or "photo" in lower):
            return True
        return False

    @staticmethod
    def _user_wants_add_references(message: str) -> bool:
        """True if the user wants to add reference photos for regeneration."""
        lower = message.lower().strip()
        phrases = (
            "add photos", "add references", "use reference photos", "add reference",
            "pick photos", "select photos", "search photos", "yes", "search",
        )
        return any(p in lower for p in phrases)
    
    @staticmethod
    def _user_wants_go_back(message: str) -> bool:
        """True if the user wants to go back one step (generic)."""
        lower = message.lower().strip()
        return "go back" in lower or "previous step" in lower or "back up" in lower
    
    async def _embed_exif_into_image(self, image_path: str, extraction: MemoryExtraction) -> None:
        """
        Embed EXIF metadata (date, location, description, people, pets) into the image file.
        Overwrites the file in place. Logs and continues on failure so the pipeline is not blocked.
        """
        try:
            memory_date = extraction.when if extraction.when else datetime.utcnow()
            gps_coords = None
            if extraction.where and self.location_resolver.is_available():
                gps_coords = await self.location_resolver.resolve_location(extraction.where)
            description = extraction.what_happened
            if extraction.additional_details:
                description = f"{description}\n\n{extraction.additional_details}"
            EXIFWriter.embed_exif_metadata(
                image_path=image_path,
                output_path=None,
                memory_date=memory_date,
                gps_coordinates=gps_coords,
                location_name=extraction.where,
                description=description,
                people_tags=extraction.who_people or None,
                pet_tags=extraction.who_pets or None,
            )
        except Exception as e:
            logger.warning(
                "exif_embed_skipped",
                image_path=image_path,
                error=str(e),
            )
    
    async def process_memory(
        self,
        user_message: str,
        user_id: str,
        session_id: str,
        memory_id: Optional[str] = None
    ) -> Dict:
        """
        Process a memory through the full pipeline.
        
        Args:
            user_message: User's message/story
            user_id: User ID
            session_id: Session ID
            memory_id: Optional memory ID for tracking
            
        Returns:
            Dict with result status and data
        """
        try:
            # Get session state
            state = self.get_session_state(session_id)
            
            # Start over / clear: reset everything and allow re-input
            if self._user_wants_start_over(user_message):
                state.reset()
                state.add_message("user", user_message)
                state.add_message(
                    "assistant",
                    "I've cleared everything. Tell me about the memory you'd like to save.",
                )
                logger.info("session_reset", session_id=session_id)
                return {
                    "status": "collecting",
                    "message": "I've cleared everything. Tell me about the memory you'd like to save.",
                    "stage": "collecting",
                }
            
            state.add_message("user", user_message)
            
            # Step 1: Memory Collection
            logger.info("pipeline_stage", stage=state.stage, session_id=session_id)
            
            if state.stage == "collecting":
                # Build context-aware prompt
                conversation_context = state.get_conversation_context()
                prompt = f"{conversation_context}\nUSER: {user_message}"
                
                collector_response = self.memory_collector.run(prompt)
                
                # Extract message content from RunOutput
                if hasattr(collector_response, 'content'):
                    response_text = str(collector_response.content)
                elif hasattr(collector_response, 'messages') and collector_response.messages:
                    last_message = collector_response.messages[-1]
                    response_text = str(last_message.content if hasattr(last_message, 'content') else last_message)
                else:
                    response_text = str(collector_response)
                
                # Parse the response
                parsed = parse_collected_memory(response_text)
                
                # Track token usage
                await self.token_tracker.track_usage(
                    user_id=user_id,
                    session_id=session_id,
                    agent_name="memory_collector",
                    tokens_used=1000,  # Estimate
                    memory_id=memory_id,
                    operation="collection"
                )
                
                if parsed["status"] == "ready":
                    # Collection complete! Store extraction and prepare for reference photo search
                    state.extraction = parsed["extraction"]
                    state.stage = "ready_for_search"
                    
                    logger.info("collection_complete", session_id=session_id, extraction=state.extraction.dict())
                    
                    # Build confirmation message with memory details
                    confirmation = parsed.get("confirmation_message", "Great! I have all the details.")
                    
                    # Offer reference photos (optional) - provide the option immediately
                    has_people_or_pets = bool(state.extraction.who_people or state.extraction.who_pets)
                    if has_people_or_pets:
                        ref_message = (
                            f"{confirmation}\n\nReference photos from Google Photos can help match people and pets in your memory. "
                            "Add them below if you'd like, or say 'generate' when ready."
                        )
                        state.add_message("assistant", ref_message)
                        return await self._start_picker_flow(user_id, session_id, state, memory_id, message=ref_message)
                    else:
                        # No people/pets mentioned, skip photo search
                        state.stage = "confirm_generation"
                        message = f"{confirmation}\n\nReady to generate your memory? (Say 'yes' or 'generate' to continue)"
                        state.add_message("assistant", message)
                        return {
                            "status": "ready",
                            "message": message,
                            "stage": state.stage,
                            "extraction": state.extraction.dict()
                        }
                    
                else:
                    # Still collecting - return conversational response
                    message = parsed.get("message", response_text)
                    state.add_message("assistant", message)
                    
                    return {
                        "status": "collecting",
                        "message": message,
                        "stage": "collection"
                    }
            
            # Step 2: Handle reference photo search decision
            elif state.stage == "ready_for_search":
                user_intent = user_message.lower().strip()
                
                # Go back: change the memory story and re-enter details
                if self._user_wants_change_story(user_message) or (
                    self._user_wants_go_back(user_message) and "photo" not in user_intent and "reference" not in user_intent
                ):
                    state.extraction = None
                    state.stage = "collecting"
                    message = "No problem. Tell me again about the memory you'd like to save—who, what, when, and where."
                    state.add_message("assistant", message)
                    return {
                        "status": "collecting",
                        "message": message,
                        "stage": "collecting",
                    }
                
                if any(word in user_intent for word in ['skip', 'no', 'without', 'generate']):
                    # User wants to skip reference photos
                    state.stage = "confirm_generation"
                    message = "Got it! Ready to generate your memory image?"
                    state.add_message("assistant", message)
                    
                    return {
                        "status": "ready",
                        "message": message,
                        "stage": "confirm_generation"
                    }
                else:
                    # User wants to select reference photos via Picker API
                    return await self._start_picker_flow(user_id, session_id, state, memory_id)
            
            # Step 3: Handle photo selection response
            elif state.stage == "selecting_references":
                # Cancel: generate without references
                if self._user_wants_go_back(user_message) or any(
                    w in user_message.lower() for w in ["cancel", "never mind", "skip"]
                ):
                    state.selected_reference_ids = []
                    state.selected_reference_urls = []
                    return await self._process_screening(user_id, session_id, state, memory_id)
                # User ready to generate
                return await self._process_screening(user_id, session_id, state, memory_id)
            
            # Step 4: Handle search_failed (user can retry or skip)
            elif state.stage == "search_failed":
                user_intent = user_message.lower().strip()
                if any(word in user_intent for word in ['skip', 'no', 'without', 'generate']):
                    state.stage = "confirm_generation"
                    message = "Got it! Ready to generate your memory image?"
                    state.add_message("assistant", message)
                    return {
                        "status": "ready",
                        "message": message,
                        "stage": "confirm_generation"
                    }
                # Retry Picker (yes, search, try again, etc.)
                return await self._start_picker_flow(user_id, session_id, state, memory_id)
            
            # Step 5: Handle generation confirmation
            elif state.stage == "confirm_generation":
                user_intent = user_message.lower().strip()
                
                if any(word in user_intent for word in ['yes', 'generate', 'create', 'go', 'proceed']):
                    # User confirmed - proceed to screening and generation
                    return await self._process_screening(user_id, session_id, state, memory_id)
                elif self._user_wants_change_references(user_message):
                    # Go back to choose different reference photos
                    state.selected_reference_ids = []
                    state.selected_reference_urls = []
                    state.stage = "ready_for_search"
                    message = "No problem. Would you like to search for reference photos again, or say 'skip' to generate without them?"
                    state.add_message("assistant", message)
                    return {
                        "status": "ready_for_search",
                        "message": message,
                        "stage": "ready_for_search",
                    }
                else:
                    # User wants to change the story
                    message = "No problem! Tell me what you'd like to change about your memory (who, what, when, where)."
                    state.stage = "collecting"
                    state.add_message("assistant", message)
                    
                    return {
                        "status": "collecting",
                        "message": message,
                        "stage": "collecting"
                    }
            
            # Step 6: After image is generated - user can edit, add/change refs, change story, or restart
            elif state.stage == "completed":
                # Add or change reference photos - go straight to picker
                if self._user_wants_add_references(user_message) or self._user_wants_change_references(user_message):
                    state.selected_reference_ids = []
                    state.selected_reference_urls = []
                    if state.extraction and (state.extraction.who_people or state.extraction.who_pets):
                        return await self._start_picker_flow(
                            user_id, session_id, state, memory_id,
                            message="Here are your reference photos. Add any context below, then click Generate when ready."
                        )
                    state.stage = "confirm_generation"
                    message = "Ready to regenerate your memory image?"
                    state.add_message("assistant", message)
                    return {
                        "status": "ready",
                        "message": message,
                        "stage": state.stage,
                        "extraction": state.extraction.dict() if state.extraction else None,
                    }
                # Change the memory story and re-enter details
                if self._user_wants_change_story(user_message):
                    state.extraction = None
                    state.stage = "collecting"
                    message = "No problem. Tell me what you'd like to change about your memory (who, what, when, where)."
                    state.add_message("assistant", message)
                    return {
                        "status": "collecting",
                        "message": message,
                        "stage": "collecting",
                    }
                # Edit the generated image
                return await self._process_edit_request(user_id, session_id, state, user_message)
            
            # If in unexpected state
            return {
                "status": "error",
                "message": "Session is in an unexpected state. Please start a new session.",
                "stage": state.stage
            }
            
        except TokenBudgetExceeded as e:
            logger.error("token_budget_exceeded", error=str(e), session_id=session_id)
            return {
                "status": "error",
                "message": str(e),
                "stage": "budget_check"
            }
        
        except Exception as e:
            logger.error("pipeline_error", error=str(e), session_id=session_id)
            return {
                "status": "error",
                "message": f"An error occurred: {str(e)}",
                "stage": "unknown"
            }
    
    async def _start_picker_flow(
        self,
        user_id: str,
        session_id: str,
        state: ConversationState,
        memory_id: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict:
        """
        Start Google Photos Picker flow: create a session and return picker_uri for the user.
        Frontend opens the URI, user selects photos, then polls and submits via references/select.
        """
        try:
            logger.info("pipeline_stage", stage="picker_session", session_id=session_id)
            picker = GooglePhotosPickerClient(self.google_photos_client.credentials)
            session = picker.create_session(max_items=8)
            picker_uri = (session.get("pickerUri") or "").rstrip("/") + "/autoclose"
            state.stage = "selecting_references"
            display_message = message or (
                "Open Google Photos to choose reference photos that will guide the image. "
                "When you're done selecting, return here and click \"I've finished selecting\"."
            )
            return {
                "status": "selecting_references",
                "message": display_message,
                "stage": "selecting_references",
                "picker_uri": picker_uri,
                "picker_session_id": session.get("id"),
                "polling_interval_seconds": 3,
            }
        except PickerUnauthorizedError as e:
            logger.warning("picker_unauthorized", error=str(e), session_id=session_id)
            state.stage = "ready_for_search"
            return {
                "status": "search_failed",
                "message": str(e)
                + " You can say 'skip' to generate without reference photos.",
                "stage": "ready_for_search",
                "requires_reauth": True,
            }
        except Exception as e:
            logger.error("picker_start_error", error=str(e), session_id=session_id)
            state.stage = "search_failed"
            return {
                "status": "search_failed",
                "message": "I couldn't open Google Photos for selection. You can try again or say 'skip' to generate without reference photos.",
                "stage": "search_failed",
            }
    
    async def store_reference_selection(
        self,
        session_id: str,
        user_id: str,
        selected_photo_ids: List[str],
        reference_photo_urls: Optional[List[str]] = None
    ) -> Dict:
        """
        Store reference photo selection and return reference_photos for display.
        Does NOT run generation - call process_screening after to generate.
        """
        try:
            state = self.get_session_state(session_id)
            if state.stage != "selecting_references":
                return {
                    "status": "error",
                    "message": "Not currently in reference selection stage",
                    "stage": state.stage
                }
            state.selected_reference_ids = selected_photo_ids
            state.selected_reference_urls = reference_photo_urls or []
            state.stage = "ready_to_generate"
            logger.info(
                "reference_photos_stored",
                session_id=session_id,
                selected_count=len(selected_photo_ids)
            )
            return {
                "status": "ready",
                "message": "Here are your reference photos. Add any context about them below, then click Generate when ready.",
                "stage": "ready_to_generate",
                "reference_photos": [
                    {"media_item_id": selected_photo_ids[i] if i < len(selected_photo_ids) else str(i), "index": i}
                    for i in range(len(state.selected_reference_urls))
                ],
            }
        except Exception as e:
            logger.error("store_reference_selection_error", error=str(e), session_id=session_id)
            return {"status": "error", "message": str(e), "stage": "selecting_references"}

    async def run_generation_from_stored_refs(
        self,
        user_id: str,
        session_id: str,
        memory_id: Optional[str] = None,
        photo_context: Optional[str] = None
    ) -> Dict:
        """Run screening and generation using already-stored reference selection."""
        state = self.get_session_state(session_id)
        if state.stage != "ready_to_generate":
            return {
                "status": "error",
                "message": "Reference selection not stored. Please select photos first.",
                "stage": state.stage
            }
        state.photo_context = (photo_context or "").strip() or None
        state.stage = "screening"
        return await self._process_screening(user_id, session_id, state, memory_id)

    async def confirm_reference_selection(
        self,
        session_id: str,
        user_id: str,
        selected_photo_ids: List[str],
        reference_photo_urls: Optional[List[str]] = None
    ) -> Dict:
        """
        Process user's reference photo selection and continue to screening.
        
        Args:
            session_id: Session ID
            user_id: User ID
            selected_photo_ids: List of selected photo IDs (from Picker or legacy)
            reference_photo_urls: Optional list of image URLs for generation (from Picker)
        """
        try:
            state = self.get_session_state(session_id)
            
            if state.stage != "selecting_references":
                return {
                    "status": "error",
                    "message": "Not currently in reference selection stage",
                    "stage": state.stage
                }
            
            state.selected_reference_ids = selected_photo_ids
            state.selected_reference_urls = reference_photo_urls or []
            state.stage = "screening"
            
            logger.info(
                "reference_photos_selected",
                session_id=session_id,
                selected_count=len(selected_photo_ids)
            )
            
            # Continue to screening
            return await self._process_screening(user_id, session_id, state, None)
            
        except Exception as e:
            logger.error("confirm_reference_selection_error", error=str(e), session_id=session_id)
            return {
                "status": "error",
                "message": f"Failed to process selection: {str(e)}",
                "stage": "selecting_references"
            }
    
    async def _process_screening(
        self,
        user_id: str,
        session_id: str,
        state: ConversationState,
        memory_id: Optional[str] = None
    ) -> Dict:
        """
        Process content screening stage.
        
        Args:
            user_id: User ID
            session_id: Session ID
            state: Conversation state
            memory_id: Optional memory ID
            
        Returns:
            Dict with result status
        """
        try:
            logger.info("pipeline_stage", stage="screening", session_id=session_id)
            
            # Screen the content
            screening_prompt = f"Review this memory for content policy: {state.extraction.what_happened}"
            screening_response = self.content_screener.run(screening_prompt)
            
            # Track tokens
            await self.token_tracker.track_usage(
                user_id=user_id,
                session_id=session_id,
                agent_name="content_screener",
                tokens_used=300,
                memory_id=memory_id,
                operation="screening"
            )
            
            # For now, assume content passes (TODO: parse screening result)
            state.stage = "generating"
            
            # Move to image generation
            return await self._process_generation(user_id, session_id, state, memory_id)
            
        except Exception as e:
            logger.error("screening_error", error=str(e), session_id=session_id)
            return {
                "status": "error",
                "message": f"Content screening failed: {str(e)}",
                "stage": "screening"
            }
    
    async def _process_generation(
        self,
        user_id: str,
        session_id: str,
        state: ConversationState,
        memory_id: Optional[str] = None
    ) -> Dict:
        """
        Process image generation stage.
        
        Args:
            user_id: User ID
            session_id: Session ID
            state: Conversation state
            memory_id: Optional memory ID
            
        Returns:
            Dict with result status and image info
        """
        try:
            logger.info("pipeline_stage", stage="generating", session_id=session_id)
            
            # Build image generation prompt
            extraction = state.extraction
            people_str = ", ".join(extraction.who_people) if extraction.who_people else "no specific people"
            pets_str = f" with {', '.join(extraction.who_pets)}" if extraction.who_pets else ""
            location_str = f" at {extraction.where}" if extraction.where else ""
            mood_str = f", {extraction.emotions_mood} mood" if extraction.emotions_mood else ""
            
            generation_prompt = f"""Generate a photorealistic image: {extraction.what_happened}{location_str}.
People: {people_str}{pets_str}.
Style: Natural, candid photography{mood_str}.
High quality, detailed, realistic lighting."""

            # Add reference photo context if photos were selected
            if state.selected_reference_ids:
                reference_note = f"\n\nReference photos selected: {len(state.selected_reference_ids)} photos to guide style, people, and setting."
                generation_prompt += reference_note
            # Add optional user context about the photos
            if state.photo_context:
                generation_prompt += f"\n\nUser notes about the reference photos: {state.photo_context}"
            
            # Fetch reference image bytes (Picker baseUrl needs OAuth + dimension params)
            reference_image_bytes: Optional[List[bytes]] = None
            if state.selected_reference_urls:
                creds = self.google_photos_client.credentials
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                token = creds.token
                reference_image_bytes = []
                for url in state.selected_reference_urls[:8]:  # Limit to 8
                    try:
                        # Google baseUrl requires =wN-hN for images; use 1024 for reference quality
                        fetch_url = url if "=" in url else f"{url.rstrip('/')}=w1024-h1024"
                        with httpx.Client(timeout=15.0) as client:
                            r = client.get(
                                fetch_url,
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            r.raise_for_status()
                            reference_image_bytes.append(r.content)
                    except Exception as e:
                        logger.warning("reference_image_fetch_failed", url=url[:80], error=str(e))
                if not reference_image_bytes:
                    reference_image_bytes = None
            
            # Generate image with reference images for likeness when available
            image_path = await self.image_generator.generate_image(
                prompt=generation_prompt,
                user_id=user_id,
                reference_image_urls=None,
                reference_image_bytes=reference_image_bytes
            )
            
            # Track tokens (includes generation cost)
            await self.token_tracker.track_usage(
                user_id=user_id,
                session_id=session_id,
                agent_name="image_generator",
                tokens_used=2000,  # Estimate including generation
                memory_id=memory_id,
                operation="generation"
            )
            
            if not image_path:
                logger.warning("image_generation_failed", user_id=user_id)
            
            state.stage = "completed"
            if image_path:
                state.last_generated_image_path = image_path
                await self._embed_exif_into_image(image_path, extraction)
            
            return {
                "status": "completed",
                "message": "Your memory has been created! Here's your image. You can ask for changes (e.g. 'make the sky more dramatic') or download/save it." if image_path else "Your memory has been created!",
                "stage": "completed",
                "image_path": image_path,
                "extraction": extraction.dict()
            }
            
        except Exception as e:
            logger.error("generation_error", error=str(e), session_id=session_id)
            return {
                "status": "error",
                "message": f"Image generation failed: {str(e)}",
                "stage": "generating"
            }
    
    async def _process_edit_request(
        self,
        user_id: str,
        session_id: str,
        state: ConversationState,
        edit_instruction: str
    ) -> Dict:
        """Handle user request to change the generated image. Re-run image generation with edit."""
        if not state.last_generated_image_path or not os.path.isfile(state.last_generated_image_path):
            state.add_message("assistant", "I don't have the previous image to edit. Start a new memory to create one.")
            return {
                "status": "completed",
                "message": "I don't have the previous image to edit. Start a new memory to create one.",
                "stage": "completed"
            }
        try:
            logger.info("pipeline_stage", stage="editing", session_id=session_id)
            new_path = await self.image_generator.edit_image(
                image_path=state.last_generated_image_path,
                edit_instruction=edit_instruction,
                user_id=user_id
            )
            if new_path:
                state.last_generated_image_path = new_path
                if state.extraction:
                    await self._embed_exif_into_image(new_path, state.extraction)
                state.add_message("assistant", "Here's your updated image. Ask for more changes or download/save when you're happy.")
                return {
                    "status": "completed",
                    "message": "Here's your updated image. Ask for more changes or download/save when you're happy.",
                    "stage": "completed",
                    "image_path": new_path,
                    "extraction": state.extraction.dict() if state.extraction else None
                }
            state.add_message("assistant", "I couldn't apply those changes. Try describing the edit differently.")
            return {
                "status": "completed",
                "message": "I couldn't apply those changes. Try describing the edit differently.",
                "stage": "completed"
            }
        except Exception as e:
            logger.error("edit_request_error", error=str(e), session_id=session_id)
            return {
                "status": "error",
                "message": f"Edit failed: {str(e)}",
                "stage": "completed"
            }


def create_memory_team(
    google_photos_client: GooglePhotosClient,
    token_tracker: TokenTracker
) -> MemoryTeam:
    """
    Factory function to create a configured MemoryTeam.
    
    Args:
        google_photos_client: Google Photos client
        token_tracker: Token tracker
        
    Returns:
        Configured MemoryTeam instance
    """
    return MemoryTeam(
        google_photos_client=google_photos_client,
        token_tracker=token_tracker
    )
