# Memory Collection Flow - Corrected

## Problem You Identified

I was doing Google Photos search + image generation **in the same request** as memory collection, causing 30-second timeouts.

## Your Correct Vision

The flow should be **step-by-step**, with each major operation in its own request:

1. **Collect story** (ask questions if needed)
2. **Search Google Photos** for references (if people/pets mentioned)
3. **Present options** to user
4. **User confirms** they're ready
5. **Then generate** image

## Fixed Flow

### Request 1: Collection
```
User: "My daughter Emma's birthday last summer at the park"
↓ [Agent extracts: Emma, birthday, summer 2024, park]
Bot: "Would you like me to search your Google Photos for reference images?"
```
**Time:** ~3 seconds ✅

### Request 2: Photo Search (if user says yes)
```
User: "yes"
↓ [Searches Google Photos for Emma, summer 2024]
Bot: "I found 5 photos. Select any to use as references."
[Shows thumbnails]
```
**Time:** ~12 seconds ✅

### Request 3: Confirmation
```
User: [Selects 2 photos] → calls /api/chat/references/select
Bot: "Ready to generate your memory?"
```
**Time:** ~1 second ✅

### Request 4: Generation
```
User: "yes"
↓ [Screening + Image Generation]
Bot: "Your memory has been created! Here's your image."
```
**Time:** ~20 seconds ✅

**Total:** ~36 seconds across 4 separate requests (each under 30s)

## Key Changes

1. **Separated photo search**: Now happens in Request 2 (not Request 1)
2. **Added `ready_for_search` stage**: Asks user before searching
3. **Added `confirm_generation` stage**: Confirms before generating
4. **Increased frontend timeout**: 30s → 120s (safety buffer)
5. **Optimized searches**: ±14 days, 5 results each, 10s timeouts

## Why This Works

- **Each request is fast** (under 30s)
- **User controls pace** (confirms each step)
- **Graceful degradation** (can skip photos if search fails)
- **Better UX** (user sees progress, not just waiting)

## Testing

Start a new chat session and try:
```
User: "Emma's birthday last summer"
Bot: [Asks questions if needed]
Bot: "Would you like me to search for photos?"
User: "yes" or "skip"
```

Each response should come back quickly now!
