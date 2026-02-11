# Reference Photo Selection Flow

## Overview

The memory creation process includes an interactive, multi-step flow where users provide their story, optionally select reference photos, confirm, and then generate the image. Each step happens in a **separate request** to avoid timeouts.

## Flow Stages

### 1. **Collection** (`collecting`)
**Request 1: User shares story**
- User shares their memory story
- Agent asks clarifying questions (minimal - only if critical info is missing)
- Extracts: who, what, when, where, mood
- **Returns immediately** (fast, <5 seconds)

**When ready:**
- If people/pets mentioned → asks "Would you like me to search your Google Photos for reference images?"
- Stage → `ready_for_search`
- If no people/pets → asks "Ready to generate your memory?"
- Stage → `confirm_generation`

### 2. **Ready for Search** (`ready_for_search`)
**Request 2: User decides about photo search**
- User responds: "yes" / "search" → Triggers photo search
- User responds: "skip" / "no" → Goes to confirmation
- **This is a separate request** - avoids timeout

### 3. **Searching & Selecting** (`selecting_references`)
**Request 3: Photo search happens** (only if user said yes)
- Backend searches Google Photos within ±14 days of memory date
- Searches for PEOPLE category (if people mentioned)
- Searches for PETS category (if pets mentioned)
- Returns up to 8 unique reference photos
- **Search takes 5-20 seconds but in its own request**

**User sees:**
- Thumbnail gallery of suggested photos
- Each photo shows: thumbnail, creation date, description
- Options: Select specific photos or skip

### 4. **Confirm Generation** (`confirm_generation`)
**Request 4: User confirms**
- After selection (or skip), asks "Ready to generate your memory?"
- User responds: "yes" / "generate" → Proceeds to generation
- User responds: "no" / "change" → Returns to collection

### 5. **Screening** (`screening`)
**Automatic during generation request**
- Content screening agent reviews for policy compliance
- No user interaction needed

### 6. **Generation** (`generating`)
**Request 5: Image generation**
- Image generated using:
  - Memory details (extracted data)
  - Selected reference photos (if any)
  - Gemini 2.5 Flash Image model
- Takes 10-30 seconds

### 7. **Completed** (`completed`)
- Generated image displayed
- Option to upload to Google Photos
- Memory saved with metadata

## API Endpoints

### POST `/api/chat/message`
Main conversation endpoint. Returns different responses based on stage:

**When stage = `selecting_references`:**
```json
{
  "message": "I found some photos...",
  "session_id": "session_...",
  "status": "selecting_references",
  "metadata": {
    "stage": "selecting_references",
    "reference_photos": [
      {
        "media_item_id": "...",
        "thumbnail_url": "https://...",
        "url": "https://...",
        "creation_time": "2024-08-15T10:30:00",
        "description": "...",
        "relevance_score": 0.95
      }
    ]
  }
}
```

### POST `/api/chat/references/select`
Confirm reference photo selection.

**Query params:**
- `session_id`: Current session
- `user_id`: User ID

**Body:**
```json
{
  "selected_photo_ids": ["media_item_id_1", "media_item_id_2"]
}
```

**Response:**
Continues to next stage (screening → generation → completed)

## Frontend Implementation

### ChatInterface Updates Needed

1. **Detect `selecting_references` stage** in message metadata
2. **Display photo gallery** when reference_photos present
3. **Selection UI:**
   - Checkbox on each photo thumbnail
   - "Continue with selected" button
   - "Skip - generate without references" button
4. **Call `selectReferencePhotos()`** API when user confirms
5. **Handle response** and continue conversation

### Example Frontend Code

```typescript
// In ChatInterface.tsx
if (message.metadata?.stage === 'selecting_references' && 
    message.metadata?.reference_photos) {
  return (
    <ReferencePhotoSelector
      photos={message.metadata.reference_photos}
      onSelect={(selectedIds) => {
        selectReferencePhotos(userId, sessionId, selectedIds)
          .then(handleResponse)
      }}
      onSkip={() => {
        selectReferencePhotos(userId, sessionId, [])
          .then(handleResponse)
      }}
    />
  )
}
```

## Backend Implementation

### Key Files

1. **`backend/app/agents/team.py`:**
   - `_fetch_reference_photos()`: Searches Google Photos
   - `confirm_reference_selection()`: Processes user's selection

2. **`backend/app/api/routes/chat.py`:**
   - `/message`: Main endpoint, includes reference_photos in metadata
   - `/references/select`: New endpoint for confirming selection

3. **`backend/app/tools/google_photos.py`:**
   - `search_photos_by_date()`: Date-based search
   - `search_photos_by_content()`: Category-based search (PEOPLE, PETS)

### Error Handling

**If no photos found:**
- Automatically skips to screening stage
- User sees normal flow (no photo selection)

**If Google Photos API fails:**
- Logs warning
- Continues without reference photos
- Doesn't block memory creation

**If user has 403 PERMISSION_DENIED:**
- Need to re-authenticate with proper Google Photos scopes
- User should log out and log back in

## Google Photos Scopes Required

```python
SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.readonly',  # Read photos
    'https://www.googleapis.com/auth/photoslibrary.appendonly', # Upload photos
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]
```

## Example Conversation Flow

### Scenario: Memory with people

```
👤 User: "I want to remember my daughter Emma's 5th birthday party last summer"

🤖 Bot: "That sounds wonderful! Can you tell me a bit more about what happened at the party?"
[Stage: collecting]

👤 User: "It was at the park, she blew out candles on her unicorn cake"

🤖 Bot: "Perfect! I have all the details. Would you like me to search your Google Photos 
        for reference images of Emma? This can help make the generated image more accurate."
[Stage: ready_for_search]
[REQUEST 1 COMPLETE - took ~3 seconds]

👤 User: "yes"

🤖 Bot: "I found 5 photos of Emma from around that time. Would you like to select any 
        as references?"
[Shows photo thumbnails]
[Stage: selecting_references]
[REQUEST 2 COMPLETE - took ~12 seconds for photo search]

👤 User: [Clicks to select 2 photos of Emma]
      [Calls /api/chat/references/select endpoint]

🤖 Bot: "Great! Ready to generate your memory image?"
[Stage: confirm_generation]
[REQUEST 3 COMPLETE - took ~1 second]

👤 User: "yes"

🤖 Bot: [Generates image using Emma's photos + memory details]
        "Your memory has been created! Here's your image."
        [Shows generated image]
[Stage: completed]
[REQUEST 4 COMPLETE - took ~20 seconds for image generation]

Total: ~36 seconds across 4 separate requests ✅
```

### Scenario: Skip reference photos

```
👤 User: "I want to remember my daughter Emma's birthday last summer"

🤖 Bot: "Great! Would you like me to search your Google Photos for reference images?"
[Stage: ready_for_search]

👤 User: "skip"

🤖 Bot: "Got it! Ready to generate your memory image?"
[Stage: confirm_generation]

👤 User: "yes"

🤖 Bot: [Generates image]
        "Your memory has been created! Here's your image."
[Stage: completed]

Total: ~25 seconds across 3 requests ✅
```

### Scenario: No people mentioned

```
👤 User: "The sunset at Yosemite was incredible"

🤖 Bot: "Beautiful! When was this?"
[Stage: collecting]

👤 User: "Last July"

🤖 Bot: "Perfect! Ready to generate your memory?"
[Stage: confirm_generation - skips photo search since no people/pets]

👤 User: "yes"

🤖 Bot: [Generates image]
        "Your memory has been created! Here's your image."
[Stage: completed]

Total: ~22 seconds across 3 requests ✅
```

## Testing

### Prerequisites
1. User must have photos in Google Photos
2. User must re-authenticate if they get 403 errors
3. `python-dateutil` must be installed (`uv sync`)

### Test Scenario
```
User: "I want to remember my daughter Emma's 5th birthday party last summer"

Bot: "That sounds like a wonderful memory! Can you tell me more about what 
      happened at the party?"

User: "It was at the park, she blew out candles on her unicorn cake"

Bot: [EXTRACTS: who=Emma, what=birthday party with unicorn cake, when=summer 2024]
     [SEARCHES: Photos of Emma ±30 days from August 2024]
     [RETURNS: 8 reference photos]
     
     "I found some photos from your Google Photos that might be helpful as 
      references. Would you like to select any to help guide the image 
      generation?"
     
     [Shows 8 photo thumbnails]

User: [Selects 2 photos of Emma]

Bot: [GENERATES image using Emma's reference photos + memory details]
     "Your memory has been created! Here's your image."
```

## Benefits

1. **Better image accuracy** - Real photos of people/pets guide generation
2. **Character consistency** - Same people look similar across memories
3. **User engagement** - Interactive, nostalgic browsing
4. **Smart suggestions** - Automatic relevance-based filtering
5. **Optional** - Can always skip and generate without references
