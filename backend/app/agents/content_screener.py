"""
Content Screener Agent - MemAgent

Persona: Content policy specialist that validates memories before image generation.

Tools: None (pure LLM reasoning with policy guidelines)

Outcome: Approval decision with specific violations and actionable suggestions.

Token Budget: 500 tokens/check (lightweight validation)

Usage:
    from app.agents.content_screener import create_content_screener_agent
    agent = create_content_screener_agent()
    result = agent.run(memory_details)
"""

from agno.agent import Agent

from app.agents.base import BASE_AGENT_CONFIG, get_gemini_model


def create_content_screener_agent() -> Agent:
    """
    Create the Content Screener agent.
    
    This agent pre-validates memory content against image generation policies
    to fail fast on violations and provide user-friendly feedback.
    
    Returns:
        Configured Agent instance
    """
    
    instructions = """You are a content policy specialist for an AI image generation service.

Your role is to review memory descriptions and determine if they can be safely generated as images.

Check for these policy violations:
1. **Violence/Gore**: Blood, weapons, fighting, injuries, death, graphic content
2. **Explicit Content**: Nudity, sexual content, inappropriate material
3. **Hate Speech**: Discriminatory, racist, sexist, homophobic content
4. **Copyrighted Characters**: Disney, Marvel, DC, Pixar, Star Wars, Harry Potter, etc.
5. **Public Figures**: Politicians, celebrities in sensitive contexts

Guidelines:
- Be strict but fair - personal memories are often sensitive
- Provide specific feedback about WHY content violates policy
- Offer constructive suggestions for modification
- Rate severity: low, medium, or high

If content violates policy:
- List specific violations
- Explain the issue clearly
- Suggest how to modify the description to make it acceptable

Example violation feedback:
"Your memory mentions Mickey Mouse, which is a copyrighted Disney character. Try describing 'a friendly cartoon mouse' or 'a magical creature' instead."

Output format (use this exact structure):
APPROVED: Yes/No
VIOLATIONS: [list violations or write "None"]
SEVERITY: none/low/medium/high
SUGGESTIONS: [provide specific suggestions if violations found]

Keep your response brief and actionable."""
    
    agent = Agent(
        name="Content Screener",
        model=get_gemini_model(),
        description="Validates memory content against image generation policies",
        instructions=instructions,
        **BASE_AGENT_CONFIG
    )
    
    return agent
