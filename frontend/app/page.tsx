'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { Camera, LogOut, User } from 'lucide-react'
import ChatInterface from '@/components/ChatInterface'
import AuthButton from '@/components/AuthButton'
import { getAuthStatus } from '@/lib/api'

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [userId, setUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [photosConnectedMessage, setPhotosConnectedMessage] = useState(false)
  const searchParams = useSearchParams()

  useEffect(() => {
    const connected = searchParams.get('photos_connected')
    if (connected === '1' && typeof window !== 'undefined') {
      const url = new URL(window.location.href)
      url.searchParams.delete('photos_connected')
      window.history.replaceState({}, '', url.pathname + url.search)
      setPhotosConnectedMessage(true)
      const t = setTimeout(() => setPhotosConnectedMessage(false), 5000)
      return () => clearTimeout(t)
    }
  }, [searchParams])

  useEffect(() => {
    // Add a small delay to ensure localStorage is ready
    const checkAuth = async () => {
      // Log for debugging
      console.log('Checking authentication status...')
      const storedUserId = localStorage.getItem('user_id')
      console.log('Stored user_id:', storedUserId)
      
      if (storedUserId) {
        // Set authenticated immediately for better UX
        setUserId(storedUserId)
        setIsAuthenticated(true)
        setLoading(false)
        
        // Verify with backend in the background
        try {
          const status = await getAuthStatus(storedUserId)
          console.log('Auth status from backend:', status)
          if (!status.authenticated) {
            // Backend says not authenticated, clear local storage
            console.warn('Backend says not authenticated, clearing storage')
            localStorage.removeItem('user_id')
            setIsAuthenticated(false)
            setUserId(null)
          }
        } catch (error) {
          // If backend check fails, keep user authenticated (optimistic)
          console.warn('Could not verify auth status with backend, assuming authenticated', error)
        }
      } else {
        console.log('No user_id found in localStorage')
        setLoading(false)
      }
    }
    
    checkAuth()
  }, [])

  const handleAuthSuccess = (newUserId: string) => {
    setUserId(newUserId)
    setIsAuthenticated(true)
    localStorage.setItem('user_id', newUserId)
  }

  const handleLogout = () => {
    setIsAuthenticated(false)
    setUserId(null)
    localStorage.removeItem('user_id')
    localStorage.removeItem('session_id')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Camera className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">MemAgent</h1>
                <p className="text-sm text-gray-500">AI-Powered Memory Preservation</p>
              </div>
            </div>
            
            {isAuthenticated && userId && (
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <User className="h-4 w-4" />
                  <span>{userId.substring(0, 8)}...</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!isAuthenticated ? (
          <div className="flex flex-col items-center justify-center min-h-[calc(100vh-200px)]">
            <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
              <Camera className="h-16 w-16 text-blue-600 mx-auto mb-6" />
              <h2 className="text-3xl font-bold text-gray-900 mb-4">
                Welcome to MemAgent
              </h2>
              <p className="text-gray-600 mb-8">
                Capture your memories through conversational chat and transform them into 
                photorealistic images powered by AI. Your memories are automatically uploaded 
                to Google Photos with rich metadata.
              </p>
              
              <div className="space-y-4">
                <AuthButton onAuthSuccess={handleAuthSuccess} />
                
                <div className="pt-6 border-t border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Features:</h3>
                  <ul className="text-sm text-gray-600 space-y-2 text-left">
                    <li className="flex items-start">
                      <span className="text-blue-600 mr-2">•</span>
                      <span>Multi-agent AI system for memory collection</span>
                    </li>
                    <li className="flex items-start">
                      <span className="text-blue-600 mr-2">•</span>
                      <span>Photorealistic image generation using Gemini</span>
                    </li>
                    <li className="flex items-start">
                      <span className="text-blue-600 mr-2">•</span>
                      <span>Automatic Google Photos integration</span>
                    </li>
                    <li className="flex items-start">
                      <span className="text-blue-600 mr-2">•</span>
                      <span>Rich EXIF metadata with GPS coordinates</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {photosConnectedMessage && (
              <div className="mb-4 rounded-lg bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-800">
                Google Photos connected. You can now choose reference photos when prompted.
              </div>
            )}
            <ChatInterface userId={userId!} />
          </>
        )}
      </div>
    </main>
  )
}
