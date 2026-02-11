'use client'

import { useState, useEffect, useRef } from 'react'
import { Send, Loader2, Image as ImageIcon, CheckCircle2, XCircle, ExternalLink, Download, Save } from 'lucide-react'
import {
  sendMessage,
  createSession,
  getSession,
  selectReferencePhotos,
  getPickerSession,
  listPickerMedia,
  saveToGooglePhotos,
  getImageFilenameFromUrl,
} from '@/lib/api'
import { format } from 'date-fns'
import ReferencePhotoSelector from './ReferencePhotoSelector'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  metadata?: {
    agent?: string
    status?: string
    image_url?: string
    google_photos_url?: string
    stage?: string
    picker_uri?: string
    picker_session_id?: string
    polling_interval_seconds?: number
    reference_photos?: Array<{
      media_item_id: string
      thumbnail_url: string
      url: string
      creation_time: string | null
      description: string | null
      relevance_score: number
    }>
  }
}

interface ChatInterfaceProps {
  userId: string
}

export default function ChatInterface({ userId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [selectingReferences, setSelectingReferences] = useState(false)
  const [savingPhotoMessageId, setSavingPhotoMessageId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    initializeSession()
  }, [userId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const initializeSession = async () => {
    try {
      // Check for existing session
      const storedSessionId = localStorage.getItem('session_id')
      
      if (storedSessionId) {
        // Try to load existing session
        try {
          const session = await getSession(storedSessionId, userId)
          setSessionId(storedSessionId)
          
          // Load message history if available
          if (session.messages && session.messages.length > 0) {
            const formattedMessages = session.messages.map((msg: any) => ({
              id: msg.id || Math.random().toString(36),
              role: msg.role,
              content: msg.content,
              timestamp: new Date(msg.timestamp || Date.now()),
              metadata: msg.metadata,
            }))
            setMessages(formattedMessages)
            return
          }
        } catch (error) {
          console.log('Could not load existing session, creating new one')
        }
      }
      
      // Create new session
      const session = await createSession(userId)
      setSessionId(session.session_id)
      localStorage.setItem('session_id', session.session_id)
      
      // Add welcome message
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        content: "Hi! I'm MemAgent. I help you capture and preserve your memories by turning them into beautiful, photorealistic images. Just share a memory with me - tell me about a special moment, place, or experience you'd like to remember. I'll ask you a few questions to understand the details, then create an image that brings your memory to life. Ready to start?",
        timestamp: new Date(),
      }])
    } catch (error) {
      console.error('Failed to initialize session:', error)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !sessionId || loading) return

    const userMessage: Message = {
      id: Math.random().toString(36),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await sendMessage(userId, sessionId, userMessage.content)
      
      const assistantMessage: Message = {
        id: response.message_id || Math.random().toString(36),
        role: 'assistant',
        content: response.message || 'I received your message.',
        timestamp: new Date(),
        metadata: response.metadata,
      }

      setMessages(prev => [...prev, assistantMessage])
      
      // Picker flow or legacy grid: enable reference selection state
      if (response.metadata?.stage === 'selecting_references') {
        setSelectingReferences(true)
      }
    } catch (error: any) {
      console.error('Failed to send message:', error)
      
      const errorMessage: Message = {
        id: Math.random().toString(36),
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}. Please try again.`,
        timestamp: new Date(),
      }
      
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleReferenceSelection = async (selectedIds: string[]) => {
    if (!sessionId) return
    
    setSelectingReferences(false)
    setLoading(true)

    try {
      const response = await selectReferencePhotos(userId, sessionId, selectedIds)
      
      const systemMessage: Message = {
        id: Math.random().toString(36),
        role: 'assistant',
        content: response.message || 'Processing your selection...',
        timestamp: new Date(),
        metadata: response.metadata,
      }

      setMessages(prev => [...prev, systemMessage])
    } catch (error: any) {
      console.error('Failed to process reference selection:', error)
      
      const errorMessage: Message = {
        id: Math.random().toString(36),
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}. Please try again.`,
        timestamp: new Date(),
      }
      
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleSkipReferences = async () => {
    await handleReferenceSelection([])
  }

  const handlePickerFinished = async (pickerSessionId: string) => {
    if (!sessionId || !userId) return
    setSelectingReferences(false)
    setLoading(true)
    const pollIntervalMs = 3000
    const timeoutMs = 120000
    const start = Date.now()
    try {
      while (Date.now() - start < timeoutMs) {
        const session = await getPickerSession(userId, pickerSessionId)
        if (session.media_items_set) {
          const { media_items } = await listPickerMedia(userId, pickerSessionId)
          const ids = media_items.map((m: { media_item_id: string }) => m.media_item_id)
          const urls = media_items.map((m: { url: string }) => m.url).filter(Boolean)
          const response = await selectReferencePhotos(userId, sessionId, ids, urls)
          const systemMessage: Message = {
            id: Math.random().toString(36),
            role: 'assistant',
            content: response.message || 'Processing your selection...',
            timestamp: new Date(),
            metadata: response.metadata,
          }
          setMessages((prev) => [...prev, systemMessage])
          return
        }
        await new Promise((r) => setTimeout(r, pollIntervalMs))
      }
      const errorMessage: Message = {
        id: Math.random().toString(36),
        role: 'assistant',
        content: "Selection timed out. Please open Google Photos again, complete your selection, and click \"I've finished selecting\" within a few minutes.",
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } catch (error: any) {
      console.error('Picker finished error:', error)
      const errMsg = error.response?.data?.detail || error.message
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36),
          role: 'assistant',
          content: `Sorry, something went wrong: ${errMsg}. You can try again or say "skip" to generate without references.`,
          timestamp: new Date(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadImage = (imageUrl: string) => {
    const downloadUrl = imageUrl.includes('?')
      ? `${imageUrl}&download=1`
      : `${imageUrl}?download=1`
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = getImageFilenameFromUrl(imageUrl) || 'memory.jpg'
    a.rel = 'noopener noreferrer'
    a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const handleSaveToGooglePhotos = async (imageUrl: string, messageId: string) => {
    if (!userId) return
    const filename = getImageFilenameFromUrl(imageUrl)
    if (!filename) return
    setSavingPhotoMessageId(messageId)
    try {
      const data = await saveToGooglePhotos(userId, filename)
      if (data?.google_photos_url) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId
              ? { ...m, metadata: { ...m.metadata, google_photos_url: data.google_photos_url } }
              : m
          )
        )
      }
    } catch (e) {
      console.error('Save to Google Photos failed:', e)
    } finally {
      setSavingPhotoMessageId(null)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col" style={{ height: 'calc(100vh - 180px)' }}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <div className="whitespace-pre-wrap break-words">{message.content}</div>
              
              {/* Google Photos Picker: open link + "I've finished selecting" */}
              {message.metadata?.stage === 'selecting_references' &&
                message.metadata?.picker_uri &&
                message.metadata?.picker_session_id && (
                  <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
                    <p className="text-sm text-gray-700">
                      Choose reference photos in Google Photos, then return here.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <a
                        href={message.metadata.picker_uri}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
                      >
                        <ExternalLink className="h-4 w-4" />
                        Open Google Photos to select
                      </a>
                      <button
                        type="button"
                        onClick={() =>
                          handlePickerFinished(message.metadata!.picker_session_id!)
                        }
                        disabled={loading}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                      >
                        {loading ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Checking...
                          </>
                        ) : (
                          "I've finished selecting"
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={handleSkipReferences}
                        disabled={loading}
                        className="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm"
                      >
                        Skip
                      </button>
                    </div>
                  </div>
                )}
              {/* Legacy: reference photo grid (when backend returned reference_photos list) */}
              {message.metadata?.stage === 'selecting_references' &&
                message.metadata?.reference_photos &&
                message.metadata.reference_photos.length > 0 && (
                  <div className="mt-3">
                    <ReferencePhotoSelector
                      photos={message.metadata.reference_photos}
                      onConfirm={handleReferenceSelection}
                      onSkip={handleSkipReferences}
                      loading={loading}
                    />
                  </div>
                )}
              
              {/* Show image if available */}
              {message.metadata?.image_url && (
                <div className="mt-3 space-y-2">
                  <div className="rounded-lg overflow-hidden border border-gray-200">
                    <img
                      src={message.metadata.image_url}
                      alt="Generated memory"
                      className="w-full h-auto"
                      onError={(e) => {
                        console.error('Image failed to load:', message.metadata?.image_url)
                        e.currentTarget.style.display = 'none'
                        const errorDiv = document.createElement('div')
                        errorDiv.className = 'p-4 bg-red-50 text-red-600 text-sm'
                        errorDiv.textContent = 'Image failed to load. The image may be processing or unavailable.'
                        e.currentTarget.parentElement?.appendChild(errorDiv)
                      }}
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleDownloadImage(message.metadata!.image_url!)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4" />
                      Download
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSaveToGooglePhotos(message.metadata!.image_url!, message.id)}
                      disabled={savingPhotoMessageId === message.id}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                    >
                      {savingPhotoMessageId === message.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      Save to Google Photos
                    </button>
                  </div>
                  {message.metadata?.stage === 'completed' && (
                    <p className="text-xs text-gray-500">
                      Want changes? Describe them in the box below and send (e.g. &quot;make the sky more dramatic&quot;).
                    </p>
                  )}
                </div>
              )}
              
              {/* Show Google Photos link if available */}
              {message.metadata?.google_photos_url && (
                <a
                  href={message.metadata.google_photos_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center text-sm text-blue-600 hover:text-blue-700"
                >
                  <ImageIcon className="h-4 w-4 mr-1" />
                  View in Google Photos
                </a>
              )}
              
              {/* Show status indicator */}
              {message.metadata?.status && (
                <div className="mt-2 flex items-center space-x-2 text-xs">
                  {message.metadata.status === 'completed' ? (
                    <>
                      <CheckCircle2 className="h-3 w-3" />
                      <span>Memory saved to Google Photos</span>
                    </>
                  ) : message.metadata.status === 'failed' ? (
                    <>
                      <XCircle className="h-3 w-3" />
                      <span>Failed to process</span>
                    </>
                  ) : (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" />
                      <span>Processing...</span>
                    </>
                  )}
                </div>
              )}
              
              <div
                className={`text-xs mt-2 ${
                  message.role === 'user' ? 'text-blue-200' : 'text-gray-500'
                }`}
              >
                {format(message.timestamp, 'h:mm a')}
              </div>
            </div>
          </div>
        ))}
        
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-3">
              <Loader2 className="h-5 w-5 animate-spin text-gray-500" />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <div className="flex items-end space-x-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={
              messages.some(
                (m) => m.role === 'assistant' && m.metadata?.stage === 'completed' && m.metadata?.image_url
              )
                ? "Ask for changes to your image... (e.g. make the sky more dramatic)"
                : "Share your memory... (Press Enter to send, Shift+Enter for new line)"
            }
            disabled={loading || selectingReferences}
            rows={4}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500 resize-none font-sans"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading || selectingReferences}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center space-x-2 self-stretch"
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <>
                <Send className="h-5 w-5" />
                <span>Send</span>
              </>
            )}
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          💡 Tip: The more details you share, the better your memory image will be!
        </p>
      </div>
    </div>
  )
}
