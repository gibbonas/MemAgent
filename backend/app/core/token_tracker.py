"""
Token Usage Tracking - MemAgent

Middleware and utilities for tracking and budgeting token usage across agents.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.monitoring import logger
from app.storage.models import TokenUsage


class TokenBudgetExceeded(Exception):
    """Exception raised when token budget is exceeded."""
    pass


class TokenTracker:
    """
    Tracks token usage across all agent calls and enforces budgets.
    
    Per-agent budgets, per-session limits, and per-user daily limits are enforced.
    """
    
    # Per-agent token budgets
    AGENT_BUDGETS = {
        "memory_collector": 2000,
        "content_screener": 500,
        "context_enricher": 1500,
        "image_generator": 5000,
        "photo_manager": 500,
        "orchestrator": 1000,
    }
    
    def __init__(self, db: AsyncSession):
        """
        Initialize token tracker.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def track_usage(
        self,
        user_id: str,
        session_id: str,
        agent_name: str,
        tokens_used: int,
        memory_id: Optional[str] = None,
        operation: str = "unknown"
    ) -> Dict[str, int]:
        """
        Track token usage for an agent operation.
        
        Args:
            user_id: User ID
            session_id: Session ID
            agent_name: Name of the agent
            tokens_used: Number of tokens used
            memory_id: Optional memory ID
            operation: Operation name
            
        Returns:
            Dict with session_total and daily_total
            
        Raises:
            TokenBudgetExceeded: If any budget limit is exceeded
        """
        # Store in database
        usage = TokenUsage(
            user_id=user_id,
            session_id=session_id,
            memory_id=memory_id,
            agent_name=agent_name,
            tokens_used=tokens_used,
            operation=operation,
            timestamp=datetime.utcnow()
        )
        self.db.add(usage)
        await self.db.commit()
        
        # Check budgets
        session_total = await self.get_session_total(session_id)
        daily_total = await self.get_daily_total(user_id)
        
        # Log usage
        logger.info(
            "token_usage",
            user_id=user_id,
            session_id=session_id,
            agent=agent_name,
            tokens=tokens_used,
            session_total=session_total,
            daily_total=daily_total,
            operation=operation
        )
        
        # Check session limit
        if session_total > settings.max_tokens_per_session:
            logger.error(
                "token_budget_exceeded",
                user_id=user_id,
                session_id=session_id,
                session_total=session_total,
                limit=settings.max_tokens_per_session
            )
            raise TokenBudgetExceeded(
                f"Session token limit exceeded: {session_total}/{settings.max_tokens_per_session}"
            )
        
        # Check daily limit
        if daily_total > settings.max_tokens_per_user_daily:
            logger.error(
                "daily_token_budget_exceeded",
                user_id=user_id,
                daily_total=daily_total,
                limit=settings.max_tokens_per_user_daily
            )
            raise TokenBudgetExceeded(
                f"Daily token limit exceeded: {daily_total}/{settings.max_tokens_per_user_daily}"
            )
        
        # Warn if approaching limits
        session_ratio = session_total / settings.max_tokens_per_session
        if session_ratio >= settings.token_warning_threshold:
            logger.warning(
                "token_budget_warning",
                user_id=user_id,
                session_id=session_id,
                session_total=session_total,
                limit=settings.max_tokens_per_session,
                ratio=session_ratio
            )
        
        return {
            "session_total": session_total,
            "daily_total": daily_total
        }
    
    async def get_session_total(self, session_id: str) -> int:
        """
        Get total tokens used in a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Total tokens used
        """
        result = await self.db.execute(
            select(func.sum(TokenUsage.tokens_used))
            .where(TokenUsage.session_id == session_id)
        )
        total = result.scalar() or 0
        return total
    
    async def get_daily_total(self, user_id: str) -> int:
        """
        Get total tokens used by user today.
        
        Args:
            user_id: User ID
            
        Returns:
            Total tokens used today
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await self.db.execute(
            select(func.sum(TokenUsage.tokens_used))
            .where(TokenUsage.user_id == user_id)
            .where(TokenUsage.timestamp >= today_start)
        )
        total = result.scalar() or 0
        return total
    
    async def get_agent_usage(self, session_id: str, agent_name: str) -> int:
        """
        Get total tokens used by a specific agent in a session.
        
        Args:
            session_id: Session ID
            agent_name: Agent name
            
        Returns:
            Total tokens used by agent
        """
        result = await self.db.execute(
            select(func.sum(TokenUsage.tokens_used))
            .where(TokenUsage.session_id == session_id)
            .where(TokenUsage.agent_name == agent_name)
        )
        total = result.scalar() or 0
        return total
    
    def check_agent_budget(self, agent_name: str, tokens_used: int) -> None:
        """
        Check if agent is within its token budget.
        
        Args:
            agent_name: Agent name
            tokens_used: Tokens used
            
        Raises:
            TokenBudgetExceeded: If agent budget exceeded
        """
        budget = self.AGENT_BUDGETS.get(agent_name, 10000)
        if tokens_used > budget:
            raise TokenBudgetExceeded(
                f"Agent {agent_name} exceeded budget: {tokens_used}/{budget}"
            )
