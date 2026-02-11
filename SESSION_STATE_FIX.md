# Session State Persistence Fix

## Critical Bug Found

### The Problem

Conversation state was being lost between requests. When a user said "search" after being asked "Would you like me to search for photos?", the bot would reset to the initial prompt instead of actually searching.

### Root Cause

**Each request was creating a new MemoryTeam instance:**

```python
# OLD CODE (BROKEN)
team = create_memory_team(google_photos_client, token_tracker)
```

The `MemoryTeam` class stores conversation state in memory:
```python
class MemoryTeam:
    def __init__(self, ...):
        self.sessions: Dict[str, ConversationState] = {}  # In-memory storage
```

**Result:** Every new request created a fresh team with empty `self.sessions = {}`, losing all conversation history!

### Why This Broke the Flow

```
Request 1:
  User: "Emma's birthday last summer"
  Team Instance A: {session_123: {stage: "collecting", extraction: {...}}}
  Bot: "Would you like me to search for photos?"
  ✅ Stage set to "ready_for_search"

Request 2:
  User: "search"
  Team Instance B: {sessions: {}}  ← NEW EMPTY TEAM!
  Bot: Doesn't find session_123, creates new session
  Bot: "I'm ready when you are! Tell me about a memory..."
  ❌ Lost all context!
```

## The Fix

### Module-Level Team Cache

Created a persistent cache that survives across requests:

```python
# In-memory cache for MemoryTeam instances (persists across requests)
_team_cache: Dict[str, MemoryTeam] = {}

@router.post("/message", response_model=ChatMessageResponse)
async def send_message(...):
    # Get or create memory team (cached per user)
    if user_id not in _team_cache:
        _team_cache[user_id] = create_memory_team(google_photos_client, token_tracker)
        logger.info("team_created_for_user", user_id=user_id)
    
    team = _team_cache[user_id]  # Reuse same team for this user
```

### How It Works Now

```
Request 1:
  User: "Emma's birthday last summer"
  _team_cache["user_123"] = Team Instance A
  Team A: {session_abc: {stage: "ready_for_search"}}
  Bot: "Would you like me to search for photos?"
  ✅

Request 2:
  User: "search"
  team = _team_cache["user_123"]  ← REUSES Team Instance A!
  Team A: {session_abc: {stage: "ready_for_search"}}  ← State preserved!
  Bot: [Searches Google Photos]
  Bot: "I found 5 photos..."
  ✅ Context maintained!
```

## Applied to Both Endpoints

1. **`POST /api/chat/message`**: Uses cached team
2. **`POST /api/chat/references/select`**: Uses cached team

Both endpoints now share the same team instance per user, maintaining conversation state.

## Benefits

✅ **Conversation state persists** across requests  
✅ **Multi-turn memory collection** works correctly  
✅ **Reference photo selection** maintains context  
✅ **Stage transitions** work as designed  

## Limitations & Production Considerations

### Current Approach (Development)
- **Storage:** In-memory dictionary in FastAPI process
- **Scope:** Single server instance
- **Persistence:** Lost on server restart
- **Scaling:** Won't work with multiple server instances

### Production Recommendations

For production deployment, replace in-memory cache with:

1. **Redis** (Recommended):
   ```python
   import redis
   import pickle
   
   redis_client = redis.Redis(host='localhost', port=6379)
   
   # Store
   redis_client.setex(
       f"team:{user_id}", 
       3600,  # 1 hour TTL
       pickle.dumps(team)
   )
   
   # Retrieve
   team_data = redis_client.get(f"team:{user_id}")
   team = pickle.loads(team_data) if team_data else create_memory_team(...)
   ```

2. **Database Sessions Table**:
   ```sql
   CREATE TABLE conversation_sessions (
       user_id UUID,
       session_id VARCHAR,
       stage VARCHAR,
       extraction JSONB,
       messages JSONB,
       created_at TIMESTAMP,
       updated_at TIMESTAMP
   );
   ```

3. **FastAPI Dependency with Lifespan**:
   ```python
   from contextlib import asynccontextmanager
   
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # Initialize persistent storage
       yield
       # Cleanup
   ```

### Memory Management

To prevent unbounded memory growth:

```python
from datetime import datetime, timedelta

# Add expiration to cache
_team_cache: Dict[str, tuple[MemoryTeam, datetime]] = {}

def get_or_create_team(user_id: str, ...) -> MemoryTeam:
    now = datetime.utcnow()
    
    # Clean expired entries (older than 1 hour)
    expired = [
        uid for uid, (team, created_at) in _team_cache.items()
        if now - created_at > timedelta(hours=1)
    ]
    for uid in expired:
        del _team_cache[uid]
    
    # Get or create
    if user_id not in _team_cache:
        team = create_memory_team(...)
        _team_cache[user_id] = (team, now)
    
    return _team_cache[user_id][0]
```

## Testing

To verify the fix works:

```bash
# Terminal 1: Watch backend logs
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Look for:
# - "team_created_for_user" (only once per user)
# - "collection_complete" with extraction
# - "pipeline_stage" transitions
```

Then in chat:
```
1. User: "Emma's birthday last summer at the park"
   Expected: Bot asks clarifying questions OR "Would you like me to search for photos?"

2. User: "search" 
   Expected: Bot searches and shows "I found X photos..."
   (NOT: Reset to "I'm ready when you are")

3. Verify logs show same session_id across both requests
```

## Monitoring

Watch for these log events:

```
# Team creation (should only happen once per user per backend session)
team_created_for_user: user_id=...

# Stage transitions (should flow logically)
pipeline_stage: stage=collecting
collection_complete: extraction={...}
pipeline_stage: stage=fetching_references
reference_photos_fetched: count=5

# Should NOT see
collection_complete → team_created_for_user (indicates new team, lost state)
```

## Quick Fix Applied

**Files changed:**
- `backend/app/api/routes/chat.py`: Added `_team_cache` dictionary and logic to reuse team instances

**Result:** Conversation state now persists across requests within the same backend session.
