"""
Google Photos Picker API Client - MemAgent

Uses the Picker API (photospicker.googleapis.com) for user photo selection.
Required after Library API scope changes (March 2025): full-library search
no longer available; Picker is the supported way for users to select photos.
"""

from typing import Any, Dict, List, Optional

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from app.core.monitoring import logger

PICKER_BASE = "https://photospicker.googleapis.com/v1"


class PickerUnauthorizedError(Exception):
    """
    Raised when the Picker API returns 401.
    Usually means the token is missing the Picker scope—user must sign out and sign in again,
    or the Google Photos Picker API is not enabled in Cloud Console.
    """
    pass


class GooglePhotosPickerClient:
    """
    Client for Google Photos Picker API.
    Uses OAuth2 credentials to create sessions and list picked media.
    """

    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def _ensure_token(self) -> str:
        """Refresh credentials if expired and return access token."""
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
        token = self.credentials.token
        if not token:
            raise PickerUnauthorizedError("No access token available.")
        return token

    def create_session(self, max_items: int = 8) -> Dict[str, Any]:
        """
        Create a new Picker session.

        Args:
            max_items: Max number of items the user can pick (default 8).

        Returns:
            Dict with id, pickerUri, pollingConfig, expireTime, mediaItemsSet.

        Raises:
            PickerUnauthorizedError: If the API returns 401 (missing scope or API not enabled).
        """
        token = self._ensure_token()
        url = f"{PICKER_BASE}/sessions"
        body = {}
        if max_items > 0:
            body["pickingConfig"] = {"maxItemCount": str(max_items)}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=body, headers=headers)
            if resp.status_code == 401:
                logger.warning("picker_401_unauthorized", hint="Re-auth or enable Picker API")
                raise PickerUnauthorizedError(
                    "Photo picker access was denied (401). Sign out and sign in again to grant "
                    "photo selection permission. If you manage this app, ensure the Google Photos "
                    "Picker API is enabled in Google Cloud Console."
                )
            resp.raise_for_status()
            data = resp.json()
        logger.info("picker_session_created", session_id=data.get("id"))
        return data

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get session status (for polling). Returns mediaItemsSet when user is done.

        Args:
            session_id: Picker session ID from create_session.

        Returns:
            PickingSession with mediaItemsSet, pickerUri, pollingConfig, etc.
        """
        self._ensure_token()
        url = f"{PICKER_BASE}/sessions/{session_id}"
        headers = {"Authorization": f"Bearer {self._ensure_token()}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def list_media(
        self, session_id: str, page_size: int = 50, page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List media items picked in this session. Call only when mediaItemsSet is true.

        Args:
            session_id: Picker session ID.
            page_size: Max items per page (max 100).
            page_token: Token from previous list call.

        Returns:
            Dict with mediaItems (list of PickedMediaItem) and nextPageToken.
        """
        self._ensure_token()
        params = {"sessionId": session_id, "pageSize": min(page_size, 100)}
        if page_token:
            params["pageToken"] = page_token
        url = f"{PICKER_BASE}/mediaItems"
        headers = {"Authorization": f"Bearer {self._ensure_token()}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def delete_session(self, session_id: str) -> None:
        """Delete a session to free resources."""
        self._ensure_token()
        url = f"{PICKER_BASE}/sessions/{session_id}"
        headers = {"Authorization": f"Bearer {self._ensure_token()}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.delete(url, headers=headers)
            if resp.status_code == 404:
                return
            resp.raise_for_status()
        logger.info("picker_session_deleted", session_id=session_id)

    def get_all_picked_media(self, session_id: str, max_items: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch all picked media items for a session (handles pagination).

        Args:
            session_id: Picker session ID.
            max_items: Maximum total items to return.

        Returns:
            List of PickedMediaItem dicts with id, createTime, type, mediaFile.baseUrl, etc.
        """
        items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while len(items) < max_items:
            page = self.list_media(
                session_id, page_size=min(50, max_items - len(items)), page_token=page_token
            )
            media = page.get("mediaItems") or []
            items.extend(media)
            page_token = page.get("nextPageToken")
            if not page_token or len(media) == 0:
                break
        return items[:max_items]
