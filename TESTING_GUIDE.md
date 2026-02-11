# Testing Guide: Updated Memory Collection

## Quick Start Testing

### 1. Start the Services

```bash
# Terminal 1: Backend
cd backend
uv run python dev_server.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 2. Access the Application

- Frontend: http://localhost:3002
- Backend API Docs: http://localhost:8000/docs
- Backend Health: http://localhost:8000/health

## Test Scenarios

### Scenario 1: Complete Memory (Fast Path)
**Goal**: Test that the agent can collect memory in 2-3 exchanges

**Steps:**
1. Navigate to http://localhost:3002
2. Click "Sign in with Google" and authenticate
3. In the chat, type:
   ```
   I want to remember my wedding with Sarah on June 15, 2020
   ```
4. Agent should ask: "What moment would you like to capture?"
5. Respond:
   ```
   The ceremony at sunset
   ```
6. Agent should confirm and proceed to image generation

**Expected:**
- 2-3 total exchanges
- Agent confirms with summary
- Status moves from "collecting" → "screening" → "generating" → "completed"
- Response time < 10 seconds

### Scenario 2: Relative Date Handling
**Goal**: Test date calculation from natural language

**Test Cases:**

#### 2a: "Last Summer"
```
User: "I want to save a memory from last summer at the beach with my kids"
Expected: Agent calculates to July 2025, asks who was there
User: "Emma and Jake, and our dog Buddy"
Expected: Agent confirms and proceeds
```

#### 2b: "Years Ago"
```
User: "I want to remember when I graduated 3 years ago"
Expected: Agent calculates to 2023, asks for more details
User: "Graduation ceremony with my parents"
Expected: Agent confirms and proceeds
```

#### 2c: "Holiday"
```
User: "Last Christmas with my family"
Expected: Agent calculates to December 25, 2025
User: "Opening presents with Mom, Dad, and my sister Emily"
Expected: Agent confirms and proceeds
```

### Scenario 3: Missing Information
**Goal**: Test that agent efficiently asks for missing info

```
User: "I want to save a memory from the beach"
Expected: Agent asks "When was this?" and "Who was with you?"
User: "Last summer with my friends Alex and Jordan"
Expected: Agent asks "What moment would you like to capture?"
User: "Us playing volleyball at sunset"
Expected: Agent confirms and proceeds
```

### Scenario 4: Optional Location
**Goal**: Test that location is optional

```
User: "I want to remember my daughter's first birthday"
Expected: Agent asks "When was this?" and possibly "What moment?"
User: "June 2024, blowing out her candle"
Expected: Agent confirms WITHOUT asking for location
```

### Scenario 5: Vague is OK
**Goal**: Test that agent accepts approximate information

```
User: "I want to save a memory from a summer day, not sure exactly when"
Expected: Agent asks who was there and what happened
User: "Just me and my dog Luna at a park"
Expected: Agent confirms with estimated date (e.g., "summer 2025")
```

## Backend API Testing (Direct)

### Using curl or Postman:

#### 1. Create Session
```bash
curl -X POST "http://localhost:8000/api/chat/sessions?user_id=test-user-123"
```

Response:
```json
{
  "session_id": "session_test-user-123_1234567890",
  "user_id": "test-user-123",
  "created_at": "2026-02-07T12:00:00"
}
```

#### 2. Send Message
```bash
curl -X POST "http://localhost:8000/api/chat/message?user_id=test-user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_test-user-123_1234567890",
    "message": "I want to remember my wedding with Alex in 2020"
  }'
```

Expected Response:
```json
{
  "message": "That sounds beautiful! What moment would you like to capture?",
  "session_id": "session_test-user-123_1234567890",
  "status": "collecting",
  "metadata": {
    "stage": "collection"
  }
}
```

#### 3. Continue Conversation
```bash
curl -X POST "http://localhost:8000/api/chat/message?user_id=test-user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_test-user-123_1234567890",
    "message": "The ceremony at sunset"
  }'
```

Expected Response (when complete):
```json
{
  "message": "Your memory has been created! Here's your image.",
  "session_id": "session_test-user-123_1234567890",
  "status": "completed",
  "metadata": {
    "stage": "completed",
    "image_url": "/tmp/generated_image.jpg",
    "extraction": {
      "what_happened": "wedding ceremony at sunset",
      "when": "2020-06-15T18:30:00",
      "when_description": "2020",
      "who_people": ["Alex"],
      "who_pets": [],
      "where": null,
      "emotions_mood": "joyful, romantic",
      "is_complete": true
    }
  }
}
```

## Debugging

### Check Logs

Backend logs will show pipeline stages:
```
INFO: pipeline_stage stage=collection session_id=...
INFO: collection_complete session_id=... extraction={...}
INFO: pipeline_stage stage=screening session_id=...
INFO: pipeline_stage stage=generating session_id=...
```

### Common Issues

#### Issue: "I received your message" still appears
**Solution**: Frontend not updated. Check that `ChatInterface.tsx` line 108 reads:
```typescript
content: response.message || 'I received your message.',
```

#### Issue: Agent doesn't stop collecting
**Solution**: Check backend logs. Agent should return JSON with `"status": "ready"`. If not, the agent prompt may need adjustment.

#### Issue: Date calculation is wrong
**Solution**: Check the agent's interpretation in logs. The DateCalculator utility is for reference; the agent uses its own logic based on the prompt.

#### Issue: Token budget exceeded
**Solution**: Check `.env.local` settings:
```
MAX_TOKENS_PER_SESSION=15000
MAX_TOKENS_PER_USER_DAILY=50000
```

## Performance Benchmarks

Expected timings:
- Memory collection: 2-3 exchanges, ~5-8 seconds total
- Content screening: ~1 second
- Image generation: ~3-5 seconds
- Total end-to-end: ~10-15 seconds

Token usage:
- Collection: ~1,000 tokens
- Screening: ~300 tokens
- Generation: ~2,000 tokens (includes image generation)
- Total: ~3,300 tokens per memory (down from 4,000-8,000)

## Success Criteria

✅ Memory collected in ≤3 exchanges
✅ Relative dates calculated correctly
✅ Location is optional
✅ Agent confirms before proceeding
✅ Image generation triggers automatically
✅ Frontend displays responses correctly
✅ Total time < 15 seconds per memory
✅ Token usage < 3,500 tokens per memory

## Regression Testing

Test that existing functionality still works:
- [ ] Google OAuth login
- [ ] Session persistence
- [ ] Token tracking
- [ ] Error handling
- [ ] Multiple sessions per user

## Automated Testing (Future)

Create pytest tests:
```python
# tests/test_memory_collection.py
async def test_quick_collection():
    team = create_memory_team(...)
    
    # First message
    result1 = await team.process_memory(
        "My wedding with Alex in 2020",
        user_id="test",
        session_id="test-session"
    )
    assert result1["status"] == "collecting"
    
    # Second message
    result2 = await team.process_memory(
        "The ceremony at sunset",
        user_id="test",
        session_id="test-session"
    )
    assert result2["status"] == "completed"
    assert "image_path" in result2
```
