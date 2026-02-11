"""
Context Enricher Agent - MemAgent

Persona: Photo archivist that finds relevant reference images from user's library.

Tools: Google Photos search tools

Outcome: List of suggested reference photos with URLs (NO image bytes)

Token Budget: 1,500 tokens/search

Usage:
    from app.agents.context_enricher import create_context_enricher_agent
    agent = create_context_enricher_agent(google_photos_client)
    suggestions = agent.run(memory_details)
"""

from typing import List, Optional

from agno.agent import Agent

from app.agents.base import BASE_AGENT_CONFIG, get_gemini_model
from app.tools.google_photos import GooglePhotosClient


def create_context_enricher_agent(
    google_photos_client: GooglePhotosClient
) -> Agent:
    """
    Create the Context Enricher agent.
    
    CRITICAL TOKEN OPTIMIZATION:
    - Returns photo URLs and metadata only
    - Image bytes never enter LLM context
    - Frontend displays images via URLs
    
    Args:
        google_photos_client: Initialized Google Photos client
        
    Returns:
        Configured Agent instance
    """
    
    instructions = """You are a photo archivist helping users find relevant reference images.

Your goal is to search the user's Google Photos library and suggest photos that could serve as references for generating their memory image.

Search strategy:
1. Start with date-based search (±30 days from memory date)
2. If people/pets mentioned, also search by content categories
3. Present top 5 most relevant suggestions
4. Allow manual upload as fallback

CRITICAL: You will receive photo metadata (IDs, URLs, dates) - NOT image data.
This is for token efficiency. The frontend will display the actual images.

Output format:
- List photo suggestions with: media_item_id, thumbnail_url, creation_date
- Brief explanation of why each photo is relevant
- Option for manual upload

Keep responses concise and focused on photo selection."""
    
    # Define tools for the agent
    async def search_photos_by_date_tool(start_date: str, end_date: str = None) -> List[dict]:
        """Search Google Photos by date range."""
        from datetime import datetime
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date) if end_date else None
        
        suggestions = await google_photos_client.search_photos_by_date(start, end)
        
        # Return only metadata (URLs), not image bytes
        return [
            {
                "media_item_id": s.media_item_id,
                "url": s.url,
                "thumbnail_url": s.thumbnail_url,
                "creation_time": s.creation_time.isoformat() if s.creation_time else None,
                "relevance_score": s.relevance_score
            }
            for s in suggestions
        ]
    
    async def search_photos_by_content_tool(categories: List[str]) -> List[dict]:
        """Search Google Photos by content categories (PEOPLE, PETS, ANIMALS, etc.)."""
        suggestions = await google_photos_client.search_photos_by_content(categories)
        
        return [
            {
                "media_item_id": s.media_item_id,
                "url": s.url,
                "thumbnail_url": s.thumbnail_url,
                "creation_time": s.creation_time.isoformat() if s.creation_time else None,
                "relevance_score": s.relevance_score
            }
            for s in suggestions
        ]
    
    agent = Agent(
        name="Context Enricher",
        model=get_gemini_model(),
        description="Searches Google Photos for relevant reference images",
        instructions=instructions,
        tools=[search_photos_by_date_tool, search_photos_by_content_tool],
        **BASE_AGENT_CONFIG
    )
    
    return agent
