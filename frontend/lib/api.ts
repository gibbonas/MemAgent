/**
 * Frontend API client for MemAgent backend.
 * All requests use NEXT_PUBLIC_API_URL (set in Vercel env or .env.local).
 */

const getBaseUrl = () =>
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '')
    : 'http://localhost:8000'

// --- Auth ---

export function initiateGoogleAuth(): void {
  window.location.href = `${getBaseUrl()}/api/auth/google`
}

export function initiateGooglePhotosConnect(userId: string, returnPath: string = '/'): void {
  const params = new URLSearchParams()
  if (userId) params.set('user_id', userId)
  if (returnPath) params.set('return_path', returnPath)
  window.location.href = `${getBaseUrl()}/api/auth/google/photos?${params.toString()}`
}

export async function getAuthStatus(userId: string): Promise<{ authenticated: boolean; email?: string; expires_at?: string }> {
  const res = await fetch(`${getBaseUrl()}/api/auth/status?user_id=${encodeURIComponent(userId)}`, {
    credentials: 'include',
  })
  if (!res.ok) return { authenticated: false }
  return res.json()
}

// --- Chat ---

export interface SendMessageResponse {
  message: string
  session_id: string
  status: string
  metadata?: Record<string, unknown>
  message_id?: string
}

export async function sendMessage(
  userId: string,
  sessionId: string,
  message: string
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/message?user_id=${encodeURIComponent(userId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ message, session_id: sessionId }),
    }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || res.statusText) as Error & { response?: { status: number; data?: unknown } }
    err.response = { status: res.status, data }
    throw err
  }
  return data
}

export async function createSession(userId: string): Promise<{ session_id: string; user_id: string; created_at?: string }> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/sessions?user_id=${encodeURIComponent(userId)}`,
    {
      method: 'POST',
      credentials: 'include',
    }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

export async function getSession(
  sessionId: string,
  userId: string
): Promise<{ session_id: string; user_id: string; messages?: Array<{ id?: string; role: string; content: string; timestamp?: string; metadata?: unknown }> }> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`,
    { credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

// --- Reference photos (Picker + select/store/generate) ---

export async function selectReferencePhotos(
  userId: string,
  sessionId: string,
  selectedPhotoIds: string[],
  referencePhotoUrls?: string[]
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/references/select?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(sessionId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        selected_photo_ids: selectedPhotoIds,
        reference_photo_urls: referencePhotoUrls ?? undefined,
      }),
    }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || res.statusText) as Error & { response?: { status: number; data?: unknown } }
    err.response = { status: res.status, data }
    throw err
  }
  return data
}

export async function storeReferencePhotos(
  userId: string,
  sessionId: string,
  selectedPhotoIds: string[],
  referencePhotoUrls?: string[]
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/references/store?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(sessionId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        selected_photo_ids: selectedPhotoIds,
        reference_photo_urls: referencePhotoUrls ?? undefined,
      }),
    }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || res.statusText) as Error & { response?: { status: number; data?: unknown } }
    err.response = { status: res.status, data }
    throw err
  }
  return data
}

export async function generateFromReferences(
  userId: string,
  sessionId: string,
  additionalContext?: string
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/references/generate?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(sessionId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ additional_context: additionalContext ?? null }),
    }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || res.statusText) as Error & { response?: { status: number; data?: unknown } }
    err.response = { status: res.status, data }
    throw err
  }
  return data
}

// --- Picker ---

export async function getPickerSession(
  userId: string,
  pickerSessionId: string
): Promise<{
  picker_session_id: string
  media_items_set: boolean
  expire_time?: string
  polling_interval_seconds?: number
}> {
  const res = await fetch(
    `${getBaseUrl()}/api/photos/picker/session/${encodeURIComponent(pickerSessionId)}?user_id=${encodeURIComponent(userId)}`,
    { credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

export async function listPickerMedia(
  userId: string,
  pickerSessionId: string,
  pageSize: number = 50
): Promise<{
  media_items: Array<{
    media_item_id: string
    url?: string
    thumbnail_url?: string
    create_time?: string
  }>
  next_page_token?: string
}> {
  const res = await fetch(
    `${getBaseUrl()}/api/photos/picker/session/${encodeURIComponent(pickerSessionId)}/media?user_id=${encodeURIComponent(userId)}&page_size=${pageSize}`,
    { credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

// --- Images & Google Photos ---

export async function saveToGooglePhotos(
  userId: string,
  imageFilename: string
): Promise<{ status: string; google_photos_url?: string; media_item_id?: string }> {
  const res = await fetch(
    `${getBaseUrl()}/api/photos/save-to-google-photos?user_id=${encodeURIComponent(userId)}&image_filename=${encodeURIComponent(imageFilename)}`,
    { method: 'POST', credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

/**
 * Extract image filename from a backend image URL (e.g. .../images/memory_xxx_123.jpg?user_id=...).
 */
export function getImageFilenameFromUrl(imageUrl: string | undefined): string | null {
  if (!imageUrl) return null
  try {
    const path = new URL(imageUrl, 'http://dummy').pathname
    const segments = path.split('/')
    const last = segments[segments.length - 1]
    return last && last.includes('.') ? last : null
  } catch {
    return null
  }
}

/**
 * URL for the backend reference-thumbnail proxy (requires user_id and session_id for auth).
 */
export function getReferenceThumbnailUrl(userId: string, sessionId: string, index: number): string {
  return `${getBaseUrl()}/api/chat/reference-thumbnail?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(sessionId)}&index=${index}`
}
