'use client'

import { Chrome } from 'lucide-react'
import { initiateGoogleAuth } from '@/lib/api'

interface AuthButtonProps {
  onAuthSuccess: (userId: string) => void
}

export default function AuthButton({ onAuthSuccess }: AuthButtonProps) {
  const handleAuth = () => {
    // Store a flag to check after redirect
    localStorage.setItem('auth_initiated', 'true')
    initiateGoogleAuth()
  }

  return (
    <button
      onClick={handleAuth}
      className="w-full flex items-center justify-center space-x-3 px-6 py-3 bg-white border-2 border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-400 transition-all shadow-sm hover:shadow"
    >
      <Chrome className="h-5 w-5" />
      <span>Continue with Google</span>
    </button>
  )
}
