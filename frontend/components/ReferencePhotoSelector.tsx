'use client'

import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { format } from 'date-fns'

interface ReferencePhoto {
  media_item_id: string
  thumbnail_url: string
  url: string
  creation_time: string | null
  description: string | null
  relevance_score: number
}

interface ReferencePhotoSelectorProps {
  photos: ReferencePhoto[]
  onConfirm: (selectedIds: string[]) => void
  onSkip: () => void
  loading?: boolean
}

export default function ReferencePhotoSelector({
  photos,
  onConfirm,
  onSkip,
  loading = false
}: ReferencePhotoSelectorProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const togglePhoto = (photoId: string) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(photoId)) {
      newSelected.delete(photoId)
    } else {
      newSelected.add(photoId)
    }
    setSelectedIds(newSelected)
  }

  const handleConfirm = () => {
    onConfirm(Array.from(selectedIds))
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <div className="space-y-2">
        <h3 className="font-semibold text-gray-900">
          Select Reference Photos
        </h3>
        <p className="text-sm text-gray-600">
          Choose photos that can help guide the image generation. These photos might include the people, pets, or places from your memory.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 max-h-96 overflow-y-auto">
        {photos.map((photo) => (
          <button
            key={photo.media_item_id}
            onClick={() => togglePhoto(photo.media_item_id)}
            disabled={loading}
            className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
              selectedIds.has(photo.media_item_id)
                ? 'border-blue-500 ring-2 ring-blue-200'
                : 'border-gray-200 hover:border-gray-300'
            } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            <img
              src={photo.thumbnail_url || photo.url}
              alt={photo.description || 'Reference photo'}
              className="w-full h-full object-cover"
              loading="lazy"
            />
            
            {selectedIds.has(photo.media_item_id) && (
              <div className="absolute inset-0 bg-blue-500 bg-opacity-20 flex items-center justify-center">
                <div className="bg-blue-500 rounded-full p-1">
                  <Check className="h-4 w-4 text-white" />
                </div>
              </div>
            )}
            
            {photo.creation_time && (
              <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 text-center">
                {format(new Date(photo.creation_time), 'MMM d, yyyy')}
              </div>
            )}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-gray-200">
        <div className="text-sm text-gray-600">
          {selectedIds.size} photo{selectedIds.size !== 1 ? 's' : ''} selected
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={onSkip}
            disabled={loading}
            className="px-4 py-2 text-gray-700 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Skip
          </button>
          
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Processing...</span>
              </>
            ) : (
              <span>Continue</span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
