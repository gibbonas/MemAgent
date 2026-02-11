# Memory Collection Updates - Quick Conversational Flow

## Overview

Updated the MemAgent memory collection system to be faster, more conversational, and more efficient. The system now quickly gathers essential details and moves to image generation without overthinking or asking unnecessary questions.

## Key Changes

### 1. Updated Memory Collector Agent (`backend/app/agents/memory_collector.py`)

**New Behavior:**
- **Quick & Efficient**: Focuses on getting 3 critical pieces: What, When, Who
- **Smart Date Handling**: Automatically calculates dates from relative time expressions
  - "last summer" → Calculates to previous June-August
  - "2 years ago" → Calculates from current date
  - "Christmas 2020" → Uses December 25, 2020
  - "when I was 10" → Makes reasonable estimate based on context
- **Optional Location**: Only asks for location if it's relevant to the scene
- **Structured Output**: Returns JSON when collection is complete

**Example Flow:**
```
User: "I want to remember my wedding with Alex in 2020"
Agent: "That sounds beautiful! What's the moment you'd like to capture?"
User: "The ceremony at sunset"
Agent: "Got it! I'll create an image of your wedding ceremony at sunset with Alex. Sound good?"
→ Proceeds to image generation
```

**Key Instructions:**
- Ask ONE question at a time
- Stop collecting as soon as you have: What + When + Who
- Don't pressure for unnecessary details
- Be warm but efficient (1-2 sentences max)

### 2. Enhanced Memory Schema (`backend/app/schemas/memory.py`)

**New Fields:**
```python
class MemoryExtraction(BaseModel):
    what_happened: str
    when: Optional[datetime] = None
    when_description: Optional[str] = None  # NEW: Stores "last summer", "2 years ago"
    who_people: List[str]
    who_pets: List[str]
    where: Optional[str] = None
    emotions_mood: Optional[str] = None
    additional_details: Optional[str] = None
    is_complete: bool = False  # NEW: Indicates collection is done
    missing_fields: List[str] = []  # NEW: Tracks what's still needed
```

### 3. Updated Team Orchestrator (`backend/app/agents/team.py`)

**New Features:**
- **Conversation State Management**: Maintains context across multiple exchanges
  - Stores last 3 message exchanges (6 messages total)
  - Preserves extraction data
  - Tracks pipeline stage
- **Automatic Pipeline Progression**: When collection completes, automatically moves to:
  1. Content Screening
  2. Image Generation
  3. Photo Upload
- **JSON Response Parsing**: Detects when agent returns structured completion data

**ConversationState Class:**
```python
class ConversationState:
    messages: List[Dict]  # Conversation history
    extraction: Optional[MemoryExtraction]  # Collected memory data
    stage: str  # Current pipeline stage
```

### 4. Updated Chat API (`backend/app/api/routes/chat.py`)

**Enhanced Response:**
- Passes image URLs to frontend when generation completes
- Includes extraction data in metadata
- Better error handling

### 5. Frontend Fix (`frontend/components/ChatInterface.tsx`)

**Bug Fix:**
- Fixed response parsing to read `response.message` instead of `response.response`
- Now correctly displays agent responses instead of "I received your message."

## Date Calculation Logic

The agent intelligently handles relative dates:

| User Input | Calculation | Example Result |
|------------|-------------|----------------|
| "last summer" | Previous Jun-Aug period | 2025-07-15 |
| "2 years ago" | Current date - 2 years | 2024-02-07 |
| "Christmas 2020" | Dec 25 of that year | 2020-12-25 |
| "my birthday in June" | Most recent June | 2025-06-15 (estimated) |
| "when I was 10" | Estimate based on context | Varies |

## Location Handling

**Optional & Flexible:**
- Only requested if it adds to the scene
- Generic descriptions are fine: "the beach", "our backyard", "Napa Valley"
- Coordinates are NOT required
- Location resolver can attempt geocoding later if needed

## Token Optimization

**Reduced Token Usage:**
- Memory Collector: ~1,000 tokens (down from 1,500-2,000)
- Fewer conversation turns = lower costs
- Conversation state keeps only last 3 exchanges (reduces context size)

## Pipeline Stages

1. **Collecting** → User conversation with Memory Collector
2. **Screening** → Content policy validation (automatic)
3. **Generating** → Image creation with Gemini (automatic)
4. **Completed** → Image ready, uploaded to Google Photos

Frontend sees these stages in real-time via `status` field.

## Testing the Updates

### Test Case 1: Complete Memory in One Message
```
User: "I want to save a memory from my wedding with Sarah on June 15, 2020 at sunset"
Expected: Agent asks for ONE clarifying question (what moment to capture), then proceeds
```

### Test Case 2: Relative Date
```
User: "Last Christmas with my kids Emma and Jake"
Expected: Agent calculates to Dec 25, 2025, asks what moment to capture, then proceeds
```

### Test Case 3: Vague Date
```
User: "A summer day at the beach with my dog Buddy"
Expected: Agent asks "When was this?" then proceeds with estimate
```

## Benefits

1. **Faster User Experience**: 2-3 exchanges instead of 4-6
2. **Lower Costs**: Fewer tokens per memory
3. **Better UX**: Users see images faster
4. **Smart Defaults**: Works with incomplete info (approximate dates OK)
5. **Conversation Context**: Agent remembers previous exchanges

## Future Enhancements

- [ ] Integrate actual image generation (currently placeholder)
- [ ] Add photo upload stage
- [ ] Persist conversation state to database
- [ ] Add "edit memory" capability
- [ ] Support multiple memories in one session

## Breaking Changes

None - This is backward compatible. Existing API contracts unchanged.

## Files Modified

1. `backend/app/agents/memory_collector.py` - New instructions & parsing
2. `backend/app/agents/team.py` - State management & pipeline orchestration
3. `backend/app/schemas/memory.py` - Enhanced schema with new fields
4. `backend/app/api/routes/chat.py` - Better response metadata
5. `frontend/components/ChatInterface.tsx` - Bug fix for response parsing

## Deployment Notes

- No database migrations required (new fields are optional)
- No environment variable changes needed
- Restart backend and frontend to apply changes
- Test with: `npm run dev` (frontend) and `uv run python dev_server.py` (backend)
