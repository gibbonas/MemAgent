"""
Google Photos API Integration - MemAgent

Tools for searching, retrieving, and uploading photos to Google Photos.
CRITICAL: Always returns URLs/metadata only, NEVER base64 image data to LLMs.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.monitoring import logger
from app.schemas.photo import PhotoMetadata, PhotoSuggestion


class GooglePhotosClient:
    """
    Client for interacting with Google Photos Library API.
    
    CRITICAL TOKEN OPTIMIZATION:
    - All methods return URLs and metadata only
    - Image bytes are NEVER included in return values
    - LLM agents only see photo IDs and URLs
    """
    
    def __init__(self, credentials: Credentials):
        """
        Initialize Google Photos client.
        
        Args:
            credentials: Google OAuth2 credentials
        """
        self.credentials = credentials
        self.service = None
        self._init_service()
    
    def _init_service(self):
        """Initialize the Photos Library API service."""
        try:
            self.service = build('photoslibrary', 'v1', credentials=self.credentials, static_discovery=False)
        except Exception as e:
            logger.error("google_photos_init_failed", error=str(e))
            raise
    
    def refresh_credentials_if_needed(self):
        """Refresh OAuth credentials if they've expired."""
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
            self._init_service()
    
    async def search_photos_by_date(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        max_results: int = 5
    ) -> List[PhotoSuggestion]:
        """
        Search for photos within a date range.
        
        Args:
            start_date: Start date for search
            end_date: End date for search (defaults to start_date + 60 days)
            max_results: Maximum number of results to return
            
        Returns:
            List of PhotoSuggestion objects with URLs and metadata (NO image bytes)
        """
        try:
            self.refresh_credentials_if_needed()
            
            if end_date is None:
                end_date = start_date + timedelta(days=60)
            
            # Build date filter
            date_filter = {
                "ranges": [{
                    "startDate": {
                        "year": start_date.year,
                        "month": start_date.month,
                        "day": start_date.day
                    },
                    "endDate": {
                        "year": end_date.year,
                        "month": end_date.month,
                        "day": end_date.day
                    }
                }]
            }
            
            request_body = {
                "filters": {
                    "dateFilter": date_filter,
                    "mediaTypeFilter": {
                        "mediaTypes": ["PHOTO"]
                    }
                },
                "pageSize": min(max_results, 100)
            }
            
            response = self.service.mediaItems().search(body=request_body).execute()
            
            media_items = response.get('mediaItems', [])
            
            suggestions = []
            for item in media_items[:max_results]:
                suggestion = PhotoSuggestion(
                    media_item_id=item['id'],
                    url=item['baseUrl'],
                    thumbnail_url=f"{item['baseUrl']}=w200-h200",
                    creation_time=datetime.fromisoformat(item['mediaMetadata']['creationTime'].replace('Z', '+00:00')),
                    description=item.get('description', None),
                    relevance_score=0.8  # Simple scoring for now
                )
                suggestions.append(suggestion)
            
            logger.info(
                "photos_search_by_date",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                results_count=len(suggestions)
            )
            
            return suggestions
            
        except Exception as e:
            logger.error(
                "photos_search_failed",
                start_date=start_date.isoformat(),
                error=str(e)
            )
            return []
    
    async def search_photos_by_content(
        self,
        categories: List[str],
        max_results: int = 5
    ) -> List[PhotoSuggestion]:
        """
        Search for photos by content category (people, animals, etc.).
        
        Args:
            categories: List of content categories to search for
            max_results: Maximum number of results
            
        Returns:
            List of PhotoSuggestion objects with URLs and metadata (NO image bytes)
        """
        try:
            self.refresh_credentials_if_needed()
            
            # Google Photos API content categories
            # Available: NONE, LANDSCAPES, RECEIPTS, CITYSCAPES, LANDMARKS,
            # SELFIES, PEOPLE, PETS, WEDDINGS, BIRTHDAYS, DOCUMENTS, TRAVEL,
            # ANIMALS, FOOD, SPORT, NIGHT, PERFORMANCES, WHITEBOARDS, SCREENSHOTS,
            # UTILITY, ARTS, CRAFTS, FASHION, HOUSES, GARDENS, FLOWERS, HOLIDAYS
            
            request_body = {
                "filters": {
                    "contentFilter": {
                        "includedContentCategories": [cat.upper() for cat in categories]
                    },
                    "mediaTypeFilter": {
                        "mediaTypes": ["PHOTO"]
                    }
                },
                "pageSize": min(max_results, 100)
            }
            
            response = self.service.mediaItems().search(body=request_body).execute()
            
            media_items = response.get('mediaItems', [])
            
            suggestions = []
            for item in media_items[:max_results]:
                suggestion = PhotoSuggestion(
                    media_item_id=item['id'],
                    url=item['baseUrl'],
                    thumbnail_url=f"{item['baseUrl']}=w200-h200",
                    creation_time=datetime.fromisoformat(item['mediaMetadata']['creationTime'].replace('Z', '+00:00')),
                    description=item.get('description', None),
                    relevance_score=0.7
                )
                suggestions.append(suggestion)
            
            logger.info(
                "photos_search_by_content",
                categories=categories,
                results_count=len(suggestions)
            )
            
            return suggestions
            
        except Exception as e:
            logger.error(
                "photos_content_search_failed",
                categories=categories,
                error=str(e)
            )
            return []
    
    async def get_photo_details(self, media_item_id: str) -> Optional[PhotoMetadata]:
        """
        Get details about a specific photo.
        
        Args:
            media_item_id: Google Photos media item ID
            
        Returns:
            PhotoMetadata with URL and details (NO image bytes)
        """
        try:
            self.refresh_credentials_if_needed()
            
            item = self.service.mediaItems().get(mediaItemId=media_item_id).execute()
            
            metadata = PhotoMetadata(
                media_item_id=item['id'],
                url=item['baseUrl'],
                filename=item.get('filename'),
                creation_time=datetime.fromisoformat(item['mediaMetadata']['creationTime'].replace('Z', '+00:00')),
                width=int(item['mediaMetadata'].get('width', 0)),
                height=int(item['mediaMetadata'].get('height', 0)),
                mime_type=item.get('mimeType')
            )
            
            return metadata
            
        except Exception as e:
            logger.error(
                "photo_details_failed",
                media_item_id=media_item_id,
                error=str(e)
            )
            return None
    
    async def upload_photo(
        self,
        image_path: str,
        description: Optional[str] = None,
        album_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Upload a photo to Google Photos.
        
        Args:
            image_path: Path to image file
            description: Optional description
            album_id: Optional album ID to add photo to
            
        Returns:
            Dict with media_item_id and url, or None if failed
        """
        try:
            self.refresh_credentials_if_needed()
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            access_token = self.credentials.token

            # Step 1: Upload bytes to uploads endpoint (not mediaItems.upload)
            # See https://developers.google.com/photos/library/guides/upload-media
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            mime_type = 'image/jpeg'
            if image_path.lower().endswith('.png'):
                mime_type = 'image/png'
            elif image_path.lower().endswith('.webp'):
                mime_type = 'image/webp'

            async with httpx.AsyncClient(timeout=60.0) as client:
                upload_response = await client.post(
                    'https://photoslibrary.googleapis.com/v1/uploads',
                    content=image_bytes,
                    headers={
                        'Content-type': 'application/octet-stream',
                        'X-Goog-Upload-Content-Type': mime_type,
                        'X-Goog-Upload-Protocol': 'raw',
                        'Authorization': f'Bearer {access_token}',
                    },
                )
            upload_response.raise_for_status()
            upload_token = upload_response.text.strip()
            if not upload_token:
                raise ValueError("Failed to get upload token")
            
            # Step 2: Create media item
            new_media_item = {
                "simpleMediaItem": {
                    "uploadToken": upload_token,
                    "fileName": os.path.basename(image_path)
                }
            }
            
            if description:
                # API restricts description to 1000 characters
                new_media_item["description"] = description[:1000]
            
            create_body = {
                "newMediaItems": [new_media_item]
            }
            
            if album_id:
                create_body["albumId"] = album_id
            
            create_response = self.service.mediaItems().batchCreate(body=create_body).execute()
            
            results = create_response.get('newMediaItemResults', [])
            if results and results[0].get('status', {}).get('message') == 'Success':
                media_item = results[0]['mediaItem']
                
                logger.info(
                    "photo_uploaded",
                    image_path=image_path,
                    media_item_id=media_item['id'],
                    has_album=album_id is not None
                )
                
                return {
                    "media_item_id": media_item['id'],
                    "url": media_item['productUrl']
                }
            else:
                logger.error(
                    "photo_upload_failed",
                    image_path=image_path,
                    status=results[0].get('status') if results else None
                )
                return None
            
        except Exception as e:
            logger.error(
                "photo_upload_exception",
                image_path=image_path,
                error=str(e)
            )
            return None
