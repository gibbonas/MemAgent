'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'

export default function AuthSuccess() {
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('Completing authentication...')

  useEffect(() => {
    const userId = searchParams.get('user_id')
    
    console.log('Auth callback received, user_id:', userId)
    
    if (userId) {
      try {
        // Store user_id in localStorage
        localStorage.setItem('user_id', userId)
        console.log('Stored user_id in localStorage')
        
        setStatus('success')
        setMessage('Authentication successful! Redirecting...')
        
        // Wait a moment then redirect with full page reload to ensure state updates
        setTimeout(() => {
          window.location.href = '/'
        }, 1500)
      } catch (error) {
        console.error('Failed to store user_id:', error)
        setStatus('error')
        setMessage('Failed to complete authentication. Redirecting...')
        
        setTimeout(() => {
          window.location.href = '/'
        }, 2000)
      }
    } else {
      console.error('No user_id in callback URL')
      setStatus('error')
      setMessage('Authentication incomplete. Redirecting...')
      
      setTimeout(() => {
        window.location.href = '/'
      }, 2000)
    }
  }, [searchParams])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="bg-white rounded-2xl shadow-xl p-8 text-center max-w-md">
        {status === 'loading' && (
          <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto mb-4" />
        )}
        {status === 'success' && (
          <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto mb-4" />
        )}
        {status === 'error' && (
          <XCircle className="h-12 w-12 text-red-600 mx-auto mb-4" />
        )}
        
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          {status === 'success' ? 'Success!' : status === 'error' ? 'Oops!' : 'Processing...'}
        </h2>
        <p className="text-gray-600">
          {message}
        </p>
        
        {status === 'error' && (
          <button
            onClick={() => window.location.href = '/'}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go to Home
          </button>
        )}
      </div>
    </div>
  )
}
