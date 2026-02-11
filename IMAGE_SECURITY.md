# Image Security Implementation

## Overview

Generated memory images are now secured so that only the authenticated user who created them can access them.

## Security Measures

### 1. User-Specific Filenames

Images are now saved with the user ID embedded in the filename:
```
memory_{user_id}_{timestamp}.jpg
```

Example: `memory_a6156c30-7699-44f4-92cd-eb9c6cbbdca6_20260209_020530.jpg`

### 2. Authentication Required

The image serving endpoint (`/api/photos/images/{filename}`) now requires:
- `user_id` query parameter
- Valid OAuth credentials in the database

### 3. Ownership Verification

The endpoint verifies:
1. The filename starts with `memory_{user_id}_` (ownership check)
2. The user has valid credentials (authentication check)
3. The file exists on disk

If any check fails, access is denied with appropriate HTTP status codes:
- `401 Unauthorized`: User not authenticated
- `403 Forbidden`: User doesn't own this image
- `404 Not Found`: Image doesn't exist

### 4. Secure Headers

Images are served with:
- `Cache-Control: private, max-age=3600` (not public, user-specific)
- `Access-Control-Allow-Origin`: Restricted to configured CORS origins

## Implementation Details

### Backend Changes

1. **`backend/app/tools/gemini_image.py`**:
   - Added `user_id` parameter to `generate_image()` method
   - Includes user_id in generated filename

2. **`backend/app/agents/team.py`**:
   - Calls image generator directly with `user_id`
   - Bypasses agent tool wrapper for direct control

3. **`backend/app/api/routes/photos.py`**:
   - Added authentication to `/api/photos/images/{filename}` endpoint
   - Verifies user credentials and ownership
   - Logs access attempts (including unauthorized ones)

4. **`backend/app/api/routes/chat.py`**:
   - Includes `user_id` in image URLs as query parameter
   - Example: `http://localhost:8000/api/photos/images/memory_user123_20260209.jpg?user_id=user123`

### Frontend

The frontend automatically includes `user_id` in image requests when displaying images in the chat interface.

## Security Benefits

1. **Authorization**: Users can only access their own generated images
2. **Audit Trail**: All image access attempts are logged
3. **Privacy**: Images are marked as private (not public cache)
4. **CORS Protection**: Only allowed origins can access images
5. **Path Traversal Prevention**: Filename sanitization prevents directory traversal attacks

## Testing

To verify security:

1. Generate an image as User A
2. Copy the image URL
3. Try to access it as User B (different user_id)
4. Access should be denied with 403 Forbidden

## Production Considerations

For production deployment:

1. **Use HTTPS**: All image URLs should use HTTPS in production
2. **Signed URLs**: Consider using time-limited signed URLs for additional security
3. **CDN**: For better performance, consider using a CDN with signed URLs
4. **Storage**: Move from temp directory to persistent storage (S3, Google Cloud Storage)
5. **Cleanup**: Implement automatic cleanup of old generated images
6. **Rate Limiting**: Add rate limiting to prevent abuse
7. **File Size Limits**: Enforce maximum file sizes

## Logging

The following events are logged:

- `image_served`: Successful image access
- `unauthorized_image_access_attempt`: Blocked access attempt
- `serve_image_error`: Any errors during image serving

Monitor these logs to detect potential security issues or abuse attempts.
