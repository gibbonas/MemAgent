# Quick Reference: Memory Collection System

## 🎯 Design Principles

1. **Fast > Perfect**: 2-3 exchanges, not 6
2. **Smart Defaults**: Accept vague, estimate missing
3. **Visual Focus**: Always ask "what moment?"
4. **Optional Details**: Location/mood are nice-to-have
5. **Auto Progress**: No manual stage transitions

## 📋 Critical vs Optional Fields

### ✅ Critical (Must Have)
- `what_happened` - The scene to visualize
- `when` - Date/time (can be approximate)
- `who_people` - People in the scene

### 🔧 Optional (Nice to Have)
- `where` - Location (only if scene-relevant)
- `who_pets` - Pets present
- `emotions_mood` - Emotional tone
- `additional_details` - Extra context

## 🔄 Pipeline Stages

```
collecting → screening → generating → uploading → completed
           ↓           ↓            ↓            ↓
        (user)    (auto)      (auto)       (auto)
```

## 💬 Agent Response Formats

### Still Collecting
```json
{
  "status": "needs_info",
  "message": "Great! Who was with you?"
}
```

### Ready to Proceed
```json
{
  "status": "ready",
  "extraction": {
    "what_happened": "wedding ceremony at sunset",
    "when": "2020-06-15T18:30:00",
    "who_people": ["Alex"],
    "is_complete": true
  },
  "confirmation_message": "Got it! I'll create..."
}
```

## 📅 Date Calculation Examples

| Input | Output | Note |
|-------|--------|------|
| "last summer" | 2025-07-15 | Mid-July previous year |
| "2 years ago" | 2024-02-07 | Exact calculation |
| "Christmas 2020" | 2020-12-25 | Specific date |
| "my birthday" | Ask clarification | Need birth month |
| "sometime in 2019" | 2019-06-15 | Mid-year estimate |

## 🛠️ Key Files

```
backend/
├── agents/
│   ├── memory_collector.py    # Collection logic & parsing
│   └── team.py                 # Orchestration & state
├── schemas/
│   └── memory.py               # Data models
└── api/routes/
    └── chat.py                 # API endpoint

frontend/
└── components/
    └── ChatInterface.tsx       # UI & message handling
```

## 🐛 Debugging

### Check Agent Response
```python
# In team.py, after collector.run()
logger.info("collector_response", response=response_text)
```

### Check Parsing
```python
# After parse_collected_memory()
logger.info("parsed_result", parsed=parsed)
```

### Check State
```python
# In process_memory()
logger.info("session_state", 
    stage=state.stage,
    messages=len(state.messages),
    has_extraction=bool(state.extraction)
)
```

## 🧪 Quick Test

### Terminal Test (curl)
```bash
# 1. Create session
curl -X POST "http://localhost:8000/api/chat/sessions?user_id=test-123"

# 2. Send message
curl -X POST "http://localhost:8000/api/chat/message?user_id=test-123" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session_test-123_1234567890","message":"My wedding with Alex in 2020"}'

# 3. Follow up
curl -X POST "http://localhost:8000/api/chat/message?user_id=test-123" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session_test-123_1234567890","message":"The ceremony at sunset"}'
```

### Browser Test
1. Go to http://localhost:3002
2. Sign in with Google
3. Type: "My wedding with Alex in 2020"
4. Respond to agent's question
5. Check for auto-progression

## 📊 Expected Metrics

### Per Memory
- **Exchanges**: 2-3 (target)
- **Tokens**: ~3,300 (target)
- **Time**: 10-15 sec (target)

### Per Agent
- Collector: 800-1,200 tokens
- Screener: 300-500 tokens
- Generator: 1,290-2,000 tokens
- Manager: 200-500 tokens

## 🚨 Common Issues

### Frontend shows "I received your message"
**Fix**: Check `ChatInterface.tsx` line 108:
```typescript
content: response.message || 'I received your message.',
```

### Agent never completes collection
**Fix**: Check if agent is returning JSON with `status: "ready"`

### Dates are wrong
**Fix**: Review agent's calculation in logs, adjust prompt examples

### State not persisting
**Fix**: ConversationState is in-memory only, not saved to DB

## 🔐 Session State Structure

```python
class ConversationState:
    messages: List[Dict]          # Last 6 messages (3 exchanges)
    extraction: MemoryExtraction  # Collected data
    stage: str                    # Pipeline stage
```

## 🎨 Response Metadata

### Frontend Receives
```json
{
  "message": "Your memory has been created!",
  "session_id": "session_...",
  "status": "completed",
  "metadata": {
    "stage": "completed",
    "image_url": "/tmp/image.jpg",
    "extraction": { ... }
  }
}
```

## 📝 Example Prompt Flow

### Quick Path (Ideal)
```
User: "My wedding with Alex in 2020"
Agent: "What moment to capture?"
User: "Ceremony at sunset"
→ DONE (2 exchanges)
```

### Normal Path
```
User: "A day at the beach"
Agent: "When was this and who was with you?"
User: "Last summer with my kids"
Agent: "What moment to capture?"
User: "Building sandcastles"
→ DONE (3 exchanges)
```

## 🎓 Best Practices

### For Agent Prompts
1. Ask bundled questions ("When + Who?")
2. Always end with "what moment to capture?"
3. Don't ask for info already provided
4. Accept vague with estimates
5. Keep responses ≤2 sentences

### For Orchestration
1. Check `is_complete` flag
2. Auto-progress on "ready" status
3. Preserve last 3 exchanges only
4. Track tokens per agent
5. Log all stage transitions

### For Error Handling
1. Catch JSON parsing errors
2. Fallback to conversational mode
3. Log unexpected responses
4. Provide clear user messages
5. Don't fail silently

## 🔗 Related Docs

- **Full Details**: `MEMORY_COLLECTION_UPDATES.md`
- **Testing**: `TESTING_GUIDE.md`
- **Examples**: `EXAMPLE_CONVERSATIONS.md`
- **Diagrams**: `FLOW_DIAGRAMS.md`
- **Summary**: `IMPLEMENTATION_SUMMARY.md`

---

**Quick Start**: Read `TESTING_GUIDE.md` → Run manual tests → Review logs → Iterate

**Got Issues?**: Check logs → Review `EXAMPLE_CONVERSATIONS.md` → Debug with logger
