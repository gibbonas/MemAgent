"""
Photo Manager Agent - MemAgent

Persona: Meticulous librarian that preserves memories with perfect metadata.

Tools: EXIF writer, location resolver, Google Photos uploader

Outcome: Google Photos URL + upload confirmation

Token Budget: 500 tokens (minimal LLM usage, mostly API calls)

Usage:
    from app.agents.photo_manager import create_photo_manager_agent
    agent = create_photo_manager_agent(exif_writer, location_resolver, photos_client)
    result = agent.run(image_path, memory_metadata)
"""

from typing import Dict, List, Optional

from agno.agent import Agent

from app.agents.base import BASE_AGENT_CONFIG, get_gemini_model
from app.tools.exif_writer import EXIFWriter
from app.tools.location_resolver import LocationResolver
from app.tools.google_photos import GooglePhotosClient


def create_photo_manager_agent(
    exif_writer: EXIFWriter,
    location_resolver: LocationResolver,
    google_photos_client: GooglePhotosClient
) -> Agent:
    """
    Create the Photo Manager agent.
    
    This agent handles EXIF metadata embedding and upload to Google Photos.
    
    Args:
        exif_writer: EXIF metadata writer
        location_resolver: Location to GPS resolver
        google_photos_client: Google Photos client
        
    Returns:
        Configured Agent instance
    """
    
    instructions = """You are a meticulous photo librarian preserving precious memories.

Your responsibilities:
1. Embed comprehensive EXIF metadata into generated images
2. Resolve location names to GPS coordinates
3. Upload images to Google Photos with proper organization
4. Verify upload success

EXIF metadata to embed:
- DateTime: Memory date/time
- GPS: Coordinates (if location provided)
- ImageDescription: Full memory story (max 2000 chars)
- UserComment: Additional context (location, people, pets)
- Artist: People names
- Software: "MemAgent AI Memory Generator"

Process:
1. Load image from file path (not from memory - token optimization!)
2. Resolve location to GPS if provided
3. Embed all metadata
4. Upload to Google Photos
5. Clean up temp file
6. Return Google Photos URL

Keep responses brief and focused on the upload process."""
    
    async def embed_exif_tool(
        image_path: str,
        memory_date: Optional[str] = None,
        location_name: Optional[str] = None,
        description: Optional[str] = None,
        people_tags: Optional[List[str]] = None,
        pet_tags: Optional[List[str]] = None
    ) -> str:
        """Embed EXIF metadata into image."""
        from datetime import datetime
        
        # Resolve location to GPS
        gps_coords = None
        if location_name and location_resolver.is_available():
            gps_coords = await location_resolver.resolve_location(location_name)
        
        # Parse date
        parsed_date = None
        if memory_date:
            try:
                parsed_date = datetime.fromisoformat(memory_date)
            except:
                pass
        
        # Embed metadata
        output_path = exif_writer.embed_exif_metadata(
            image_path=image_path,
            memory_date=parsed_date,
            gps_coordinates=gps_coords,
            location_name=location_name,
            description=description,
            people_tags=people_tags,
            pet_tags=pet_tags
        )
        
        return output_path
    
    async def upload_to_google_photos_tool(
        image_path: str,
        description: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """Upload image to Google Photos."""
        result = await google_photos_client.upload_photo(
            image_path=image_path,
            description=description
        )
        return result
    
    agent = Agent(
        name="Photo Manager",
        model=get_gemini_model(),
        description="Embeds EXIF metadata and uploads to Google Photos",
        instructions=instructions,
        tools=[embed_exif_tool, upload_to_google_photos_tool],
        **BASE_AGENT_CONFIG
    )
    
    return agent
