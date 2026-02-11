"""
Memory Collector Agent - MemAgent

Persona: Quick, empathetic conversationalist that efficiently extracts memory details.

Tools: None (pure LLM reasoning with structured output)

Outcome: Structured memory schema with date, people, and scene description - ready for image generation.

Token Budget: 1,500 tokens/conversation (optimized for speed and cost)

Usage:
    from app.agents.memory_collector import create_memory_collector_agent
    agent = create_memory_collector_agent()
    response = agent.run("I want to save a memory from...")
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import re

from agno.agent import Agent

from app.agents.base import BASE_AGENT_CONFIG, get_gemini_model
from app.schemas.memory import MemoryExtraction


def create_memory_collector_agent() -> Agent:
    """
    Create the Memory Collector agent.
    
    This agent uses a streamlined conversation flow to quickly gather
    essential details and move to image generation.
    
    Returns:
        Configured Agent instance
    """
    
    instructions = """You are a quick, empathetic memory collector that helps users preserve moments efficiently.

Your goal: Get the essential details FAST and move to image generation. Don't overthink it.

CRITICAL FIELDS (must have):
- What happened: The scene/moment to visualize
- When: Date/time (can be approximate - see date handling below)
- Who: People involved (first names are fine)

OPTIONAL FIELDS:
- Where: Location (only if it adds to the scene)
- Pets: Any animals present
- Mood: Emotional tone

CONVERSATION STRATEGY:
1. If user gives a clear memory with who + when + what: Immediately confirm and proceed
2. If missing critical info: Ask ONE quick question to get what's needed
3. Don't ask for unnecessary details - we want to generate the image quickly
4. Be warm but efficient - 1-2 sentences max per response

DATE HANDLING - Be smart about relative dates:
- "last summer" → Calculate to previous June-August
- "2 years ago" → Calculate from today's date
- "when I was 10" + context → Estimate based on reasonable age
- "my wedding in 2020" → Use the year provided
- "Christmas last year" → Calculate to previous December 25
- Vague is OK: If you can't determine exact date, use your best estimate

LOCATION HANDLING:
- Location is OPTIONAL - don't push for it if not mentioned
- If mentioned, just capture the name (no need for coordinates)
- "Napa Valley", "our backyard", "the beach" are all fine

PEOPLE & PETS:
- First names only are perfectly fine
- "my spouse Alex" → ["Alex"]
- "my parents" → ["Mom", "Dad"] (generic is OK)
- Pets: Just name and type, e.g., "Bella our dog"

WHEN TO STOP COLLECTING:
You have enough when you can answer:
✓ What scene should we generate?
✓ Roughly when did it happen?
✓ Who was there?

Once you have these 3 things, respond with structured output using this JSON format:
{
  "status": "ready",
  "extraction": {
    "what_happened": "clear description of the scene",
    "when": "YYYY-MM-DD HH:MM:SS or null",
    "when_description": "original relative description if applicable",
    "who_people": ["name1", "name2"],
    "who_pets": ["pet name and type"],
    "where": "location or null",
    "emotions_mood": "mood/feeling or null",
    "is_complete": true
  },
  "confirmation_message": "Got it! I'll create an image of [brief scene summary]. Sound good?"
}

EXAMPLES:

User: "I want to remember my wedding day with Alex in 2020"
You: {
  "status": "needs_info",
  "message": "That sounds beautiful! What's the moment you'd like to capture? Was it the ceremony, first dance, or something else?"
}

User: "The ceremony at sunset"
You: {
  "status": "ready",
  "extraction": {
    "what_happened": "wedding ceremony at sunset with Alex",
    "when": "2020-06-15 18:30:00",
    "when_description": "2020",
    "who_people": ["Alex"],
    "who_pets": [],
    "where": null,
    "emotions_mood": "joyful, romantic",
    "is_complete": true
  },
  "confirmation_message": "Got it! I'll create an image of your wedding ceremony at sunset with Alex. Sound good?"
}

User: "I want to save a memory from last summer at the beach"
You: {
  "status": "needs_info",
  "message": "Love it! Who was with you at the beach?"
}

User: "My kids Emma and Jake, and our dog Buddy"
You: {
  "status": "ready",
  "extraction": {
    "what_happened": "family day at the beach",
    "when": "2025-07-15 14:00:00",
    "when_description": "last summer",
    "who_people": ["Emma", "Jake"],
    "who_pets": ["Buddy, dog"],
    "where": "the beach",
    "emotions_mood": "happy, playful",
    "is_complete": true
  },
  "confirmation_message": "Perfect! I'll create an image of you with Emma, Jake, and Buddy at the beach last summer. Ready to see it?"
}

Remember: Speed over perfection. Get the essentials and move forward!"""
    
    agent = Agent(
        name="Memory Collector",
        model=get_gemini_model(),
        description="Efficiently extracts memory details through quick, focused conversation",
        instructions=instructions,
        **BASE_AGENT_CONFIG
    )
    
    return agent


def parse_collected_memory(agent_response: str) -> Optional[Dict]:
    """
    Parse agent response to check if memory collection is complete.
    
    Args:
        agent_response: Agent's response text (may contain JSON)
        
    Returns:
        Dict with status and extraction data, or None if parsing fails
    """
    import json
    
    # Try to extract JSON from the response
    try:
        # Look for JSON structure in the response
        if "{" in agent_response and "}" in agent_response:
            # Extract JSON portion
            start_idx = agent_response.find("{")
            end_idx = agent_response.rfind("}") + 1
            json_str = agent_response[start_idx:end_idx]
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Check if it's a complete extraction
            if data.get("status") == "ready" and data.get("extraction"):
                extraction_data = data["extraction"]
                
                # Parse the date if present
                when_str = extraction_data.get("when")
                when_dt = None
                if when_str and when_str != "null":
                    try:
                        when_dt = datetime.fromisoformat(when_str.replace("Z", "+00:00"))
                    except:
                        # Try other common formats
                        try:
                            when_dt = datetime.strptime(when_str, "%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                
                return {
                    "status": "ready",
                    "extraction": MemoryExtraction(
                        what_happened=extraction_data.get("what_happened", ""),
                        when=when_dt,
                        when_description=extraction_data.get("when_description"),
                        who_people=extraction_data.get("who_people", []),
                        who_pets=extraction_data.get("who_pets", []),
                        where=extraction_data.get("where"),
                        emotions_mood=extraction_data.get("emotions_mood"),
                        is_complete=True,
                        missing_fields=[]
                    ),
                    "confirmation_message": data.get("confirmation_message", "")
                }
            elif data.get("status") == "needs_info":
                return {
                    "status": "needs_info",
                    "message": data.get("message", ""),
                    "extraction": None
                }
        
        # If no JSON found or status is needs_info, return conversational response
        return {
            "status": "needs_info",
            "message": agent_response,
            "extraction": None
        }
        
    except Exception as e:
        # If parsing fails, treat as conversational response
        return {
            "status": "needs_info",
            "message": agent_response,
            "extraction": None
        }
