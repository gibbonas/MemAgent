/**
 * Frontend API client for MemAgent backend.
 * Auth: JWT in httpOnly cookie (credentials: 'include').
 * All requests use NEXT_PUBLIC_API_URL.
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

export interface AuthStatusResponse {
  authenticated: boolean
  user_id?: string
  email?: string
  expires_at?: string
}

export async function getAuthStatus(): Promise<AuthStatusResponse> {
  const res = await fetch(`${getBaseUrl()}/api/auth/status`, {
    credentials: 'include',
  })
  if (!res.ok) return { authenticated: false }
  return res.json()
}

export async function getAssetToken(): Promise<string> {
  const res = await fetch(`${getBaseUrl()}/api/auth/asset-token`, {
    credentials: 'include',
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data.token as string
}

export async function logout(): Promise<void> {
  const res = await fetch(`${getBaseUrl()}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || res.statusText)
  }
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
  sessionId: string,
  message: string
): Promise<SendMessageResponse> {
  const res = await fetch(`${getBaseUrl()}/api/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || res.statusText) as Error & { response?: { status: number; data?: unknown } }
    err.response = { status: res.status, data }
    throw err
  }
  return data
}

export async function createSession(): Promise<{ session_id: string; user_id: string; created_at?: string }> {
  const res = await fetch(`${getBaseUrl()}/api/chat/sessions`, {
    method: 'POST',
    credentials: 'include',
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

export async function getSession(
  sessionId: string
): Promise<{ session_id: string; user_id: string; messages?: Array<{ id?: string; role: string; content: string; timestamp?: string; metadata?: unknown }> }> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/sessions/${encodeURIComponent(sessionId)}`,
    { credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

// --- Reference photos (Picker + select/store/generate) ---

export async function selectReferencePhotos(
  sessionId: string,
  selectedPhotoIds: string[],
  referencePhotoUrls?: string[]
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/references/select?session_id=${encodeURIComponent(sessionId)}`,
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
  sessionId: string,
  selectedPhotoIds: string[],
  referencePhotoUrls?: string[]
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/references/store?session_id=${encodeURIComponent(sessionId)}`,
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
  sessionId: string,
  additionalContext?: string
): Promise<SendMessageResponse> {
  const res = await fetch(
    `${getBaseUrl()}/api/chat/references/generate?session_id=${encodeURIComponent(sessionId)}`,
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
  pickerSessionId: string
): Promise<{
  picker_session_id: string
  media_items_set: boolean
  expire_time?: string
  polling_interval_seconds?: number
}> {
  const res = await fetch(
    `${getBaseUrl()}/api/photos/picker/session/${encodeURIComponent(pickerSessionId)}`,
    { credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

export async function listPickerMedia(
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
    `${getBaseUrl()}/api/photos/picker/session/${encodeURIComponent(pickerSessionId)}/media?page_size=${pageSize}`,
    { credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

// --- Images & Google Photos ---

export async function saveToGooglePhotos(
  imageFilename: string
): Promise<{ status: string; google_photos_url?: string; media_item_id?: string }> {
  const res = await fetch(
    `${getBaseUrl()}/api/photos/save-to-google-photos?image_filename=${encodeURIComponent(imageFilename)}`,
    { method: 'POST', credentials: 'include' }
  )
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

/**
 * Extract image filename from a backend image URL (path only; query may be token=...).
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
 * URL for the backend reference-thumbnail proxy. Uses short-lived token (from getAssetToken) for img src.
 */
export function getReferenceThumbnailUrl(sessionId: string, index: number, token: string): string {
  return `${getBaseUrl()}/api/chat/reference-thumbnail?session_id=${encodeURIComponent(sessionId)}&index=${index}&token=${encodeURIComponent(token)}`
}
