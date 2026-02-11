"""
Image Generator Agent - MemAgent

Persona: Creative photographer that generates photorealistic memory images.

Tools: Gemini image generation

Outcome: Generated image file path + metadata

Token Budget: 5,000 tokens/generation (includes prompt crafting + 1,290 for image gen)

Usage:
    from app.agents.image_generator import create_image_generator_agent
    agent = create_image_generator_agent(image_generator)
    result = agent.run(memory_details, reference_photos)
"""

from typing import List, Optional

from agno.agent import Agent

from app.agents.base import BASE_AGENT_CONFIG, get_gemini_model
from app.tools.gemini_image import GeminiImageGenerator


def create_image_generator_agent(
    image_generator: GeminiImageGenerator
) -> Agent:
    """
    Create the Image Generator agent.
    
    CRITICAL TOKEN OPTIMIZATION:
    - Reference images passed as URLs (not bytes)
    - Generated image returned as file path
    - Only metadata stored in agent memory
    
    Args:
        image_generator: Initialized Gemini image generator
        
    Returns:
        Configured Agent instance
    """
    
    instructions = """You are a creative photographer specializing in photorealistic memory images.

Your goal is to craft detailed prompts and generate images that authentically capture users' precious moments.

Prompt crafting guidelines:
1. Style: Always use "photorealistic, high-quality photograph" as base
2. Scene: Describe the main event with vivid, specific details
3. People: Include descriptions of people (without using names in the image prompt)
4. Setting: Describe location, time of day, lighting conditions
5. Mood: Capture the emotional atmosphere
6. Quality tags: Add "35mm film aesthetic, natural lighting, authentic details"

Example prompt structure:
"A photorealistic, high-quality photograph of a wedding ceremony with a couple and their dog at sunset in Napa Valley during golden hour with a romantic, joyful atmosphere, captured with natural lighting, authentic details, 35mm film aesthetic."

Token optimization:
- Reference photos are provided as URLs (you won't see the actual images)
- Your generated image will be saved to a file
- Return only the file path and generation metadata

Content policy handling:
- If generation fails with policy violation, report it immediately
- DO NOT retry without content modification
- Provide user-friendly error message

Keep your responses focused and concise."""
    
    async def generate_image_tool(
        prompt: str,
        reference_image_urls: Optional[List[str]] = None
    ) -> Optional[str]:
        """Generate a photorealistic image from prompt."""
        image_path = await image_generator.generate_image(
            prompt=prompt,
            reference_image_urls=reference_image_urls
        )
        return image_path
    
    def craft_prompt_tool(
        what_happened: str,
        location: Optional[str] = None,
        time_of_day: Optional[str] = None,
        people_descriptions: Optional[List[str]] = None,
        mood: Optional[str] = None
    ) -> str:
        """Craft a detailed prompt for image generation."""
        return image_generator.craft_prompt(
            what_happened=what_happened,
            location=location,
            time_of_day=time_of_day,
            people_descriptions=people_descriptions,
            mood=mood
        )
    
    agent = Agent(
        name="Image Generator",
        model=get_gemini_model(),
        description="Generates photorealistic memory images using Gemini",
        instructions=instructions,
        tools=[generate_image_tool, craft_prompt_tool],
        **BASE_AGENT_CONFIG
    )
    
    return agent
