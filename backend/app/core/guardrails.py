"""
Custom Guardrails - MemAgent

Security guardrails for content policy, token budgets, and API key protection.
"""

import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.monitoring import logger
from app.core.token_tracker import TokenBudgetExceeded


class APIKeyGuardrail:
    """
    Prevents agents from exposing API keys in responses.
    """
    
    # Patterns that might indicate API keys
    KEY_PATTERNS = [
        r'sk-[A-Za-z0-9]{20,}',  # OpenAI-style keys
        r'AIza[A-Za-z0-9_-]{35}',  # Google API keys
        r'[A-Za-z0-9]{32,}',  # Generic long alphanumeric strings
    ]
    
    def __call__(self, response: str) -> str:
        """
        Check response for API keys.
        
        Args:
            response: Agent response text
            
        Returns:
            Sanitized response
            
        Raises:
            ValueError: If API key detected
        """
        for pattern in self.KEY_PATTERNS:
            if re.search(pattern, response):
                logger.error(
                    "api_key_exposure_detected",
                    pattern=pattern,
                    response_preview=response[:100]
                )
                # Redact the key
                response = re.sub(pattern, "[REDACTED_API_KEY]", response)
        
        return response


class ContentPolicyGuardrail:
    """
    Pre-validates memory content against image generation policies.
    
    Detects policy violations early to prevent wasted API calls.
    """
    
    # Policy violation keywords/patterns
    VIOLATION_PATTERNS = {
        "violence": [
            r'\b(blood|gore|violent|weapon|gun|knife|murder|kill|death)\b',
            r'\b(fight|attack|assault|injure|wound)\b'
        ],
        "explicit": [
            r'\b(nude|naked|explicit|sexual|xxx)\b',
            r'\b(porn|nsfw|adult content)\b'
        ],
        "copyrighted": [
            r'\b(disney|marvel|dc comics|warner|pixar|dreamworks)\b',
            r'\b(mickey mouse|superman|batman|spiderman|star wars)\b',
            r'\b(harry potter|lord of the rings|pokemon)\b'
        ],
        "hate_speech": [
            r'\b(racist|sexist|homophobic|discriminat)\b',
        ]
    }
    
    def check_content(self, story_text: str, people_tags: List[str] = None) -> Dict[str, Any]:
        """
        Check content for policy violations.
        
        Args:
            story_text: The memory story text
            people_tags: Names of people mentioned
            
        Returns:
            Dict with approved (bool), violations (list), suggestions (list), severity (str)
        """
        violations = []
        suggestions = []
        severity = "none"
        
        text_lower = story_text.lower()
        
        # Check for violation patterns
        for violation_type, patterns in self.VIOLATION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    violations.append(violation_type)
                    severity = "high" if violation_type in ["violence", "explicit"] else "medium"
                    
                    # Provide suggestions
                    if violation_type == "violence":
                        suggestions.append(
                            "Try describing the scene without violent or graphic details. "
                            "Focus on the emotional aspects rather than physical actions."
                        )
                    elif violation_type == "explicit":
                        suggestions.append(
                            "Please keep descriptions family-friendly and appropriate for all audiences."
                        )
                    elif violation_type == "copyrighted":
                        suggestions.append(
                            "Instead of mentioning copyrighted characters, describe original characters "
                            "or use generic descriptors (e.g., 'a magical creature' instead of 'Mickey Mouse')."
                        )
                    elif violation_type == "hate_speech":
                        suggestions.append(
                            "Please revise to remove any discriminatory or hateful content."
                        )
                    
                    break  # Only report each violation type once
        
        approved = len(violations) == 0
        
        if not approved:
            logger.warning(
                "content_policy_violation",
                violations=violations,
                severity=severity,
                story_preview=story_text[:100]
            )
        
        return {
            "approved": approved,
            "violations": list(set(violations)),  # Remove duplicates
            "suggestions": suggestions,
            "severity": severity
        }


class TokenBudgetGuardrail:
    """
    Monitors and enforces token budget limits.
    
    Wraps TokenTracker functionality as a guardrail.
    """
    
    def __init__(self, token_tracker):
        """
        Initialize token budget guardrail.
        
        Args:
            token_tracker: TokenTracker instance
        """
        self.token_tracker = token_tracker
    
    async def check_budget(
        self,
        user_id: str,
        session_id: str,
        estimated_tokens: int
    ) -> Dict[str, Any]:
        """
        Check if operation is within token budget.
        
        Args:
            user_id: User ID
            session_id: Session ID
            estimated_tokens: Estimated tokens for the operation
            
        Returns:
            Dict with allowed (bool), session_total, daily_total, message
        """
        session_total = await self.token_tracker.get_session_total(session_id)
        daily_total = await self.token_tracker.get_daily_total(user_id)
        
        # Check if estimated tokens would exceed limits
        projected_session = session_total + estimated_tokens
        projected_daily = daily_total + estimated_tokens
        
        session_limit = settings.max_tokens_per_session
        daily_limit = settings.max_tokens_per_user_daily
        
        if projected_session > session_limit:
            return {
                "allowed": False,
                "session_total": session_total,
                "daily_total": daily_total,
                "message": f"Operation would exceed session token limit ({projected_session}/{session_limit})"
            }
        
        if projected_daily > daily_limit:
            return {
                "allowed": False,
                "session_total": session_total,
                "daily_total": daily_total,
                "message": f"Operation would exceed daily token limit ({projected_daily}/{daily_limit})"
            }
        
        # Warn if approaching limit
        session_ratio = projected_session / session_limit
        if session_ratio >= settings.token_warning_threshold:
            logger.warning(
                "approaching_token_limit",
                user_id=user_id,
                session_id=session_id,
                projected_session=projected_session,
                limit=session_limit,
                ratio=session_ratio
            )
        
        return {
            "allowed": True,
            "session_total": session_total,
            "daily_total": daily_total,
            "message": "Within budget"
        }


class ImageDataGuardrail:
    """
    Ensures image content is never passed to LLM context.
    
    Validates that tools return URLs/paths, not base64 data.
    """
    
    @staticmethod
    def validate_response(response: Any) -> bool:
        """
        Validate that response doesn't contain image data.
        
        Args:
            response: Response from tool/agent
            
        Returns:
            True if valid (no image data), False if image data detected
        """
        # Convert to string if possible
        response_str = str(response)
        
        # Check for base64 image data patterns
        if "data:image" in response_str:
            logger.error(
                "image_data_in_response",
                message="Base64 image data detected in response"
            )
            return False
        
        # Check for very long strings that might be base64
        if len(response_str) > 10000 and not response_str.startswith("http"):
            logger.warning(
                "suspicious_long_response",
                length=len(response_str),
                message="Response contains suspiciously long data"
            )
        
        return True


class RateLimitGuardrail:
    """
    Prevents abuse by rate limiting memory creation.
    """
    
    async def check_rate_limit(self, user_id: str, db_session) -> Dict[str, Any]:
        """
        Check if user is within rate limits.
        
        Args:
            user_id: User ID
            db_session: Database session
            
        Returns:
            Dict with allowed (bool), memories_today (int), limit (int), message
        """
        from datetime import datetime
        from sqlalchemy import func, select
        from app.storage.models import Memory
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await db_session.execute(
            select(func.count(Memory.id))
            .where(Memory.user_id == user_id)
            .where(Memory.created_at >= today_start)
        )
        memories_today = result.scalar() or 0
        
        limit = settings.max_memories_per_day
        
        if memories_today >= limit:
            return {
                "allowed": False,
                "memories_today": memories_today,
                "limit": limit,
                "message": f"Daily memory limit reached ({memories_today}/{limit})"
            }
        
        return {
            "allowed": True,
            "memories_today": memories_today,
            "limit": limit,
            "message": "Within rate limit"
        }
