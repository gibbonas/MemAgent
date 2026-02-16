"""
Base Agent Configuration - MemAgent

Common configuration and utilities for all Agno agents.
"""

from agno.agent import Agent
from agno.models.google import Gemini

from app.config import settings


def get_gemini_model(model_name: str = "gemini-2.5-flash") -> Gemini:
    """
    Get configured Gemini model instance.
    
    Args:
        model_name: Gemini model name
        
    Returns:
        Configured Gemini model
    """
    return Gemini(
        id=model_name,
        api_key=settings.google_api_key
    )


# Common agent configuration
# Only use parameters supported by Agno Agent
BASE_AGENT_CONFIG = {
    "markdown": True,  # Use markdown for clean UI rendering
}
