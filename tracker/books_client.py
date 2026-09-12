"""Thin wrapper around the Google Books API (mylibrary + volumes endpoints).

All network calls to books.googleapis.com are centralized here so callers
(poller.py, and auth/inspect_volume.py) never touch the googleapiclient
service object directly.
"""
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Historical/legacy default shelf id for "Reading now" — used only if a
# title-based lookup can't find the shelf (e.g. a differently localized
# title). Not guaranteed stable, but widely observed in practice.
FALLBACK_READING_NOW_SHELF_ID = 3

READING_NOW_TITLE = "reading now"


class AuthError(Exception):
    """Raised when the stored OAuth token can't be refreshed/used."""


class BooksClient:
    def __init__(self, token_path: Path):
        self._token_path = token_path
        self._service = None

    def _build_service(self):
        if not self._token_path.exists():
            raise AuthError(
                f"token file not found at {self._token_path}; run "
                f"auth/authorize.py and mount the resulting token.json"
            )
        try:
            creds = Credentials.from_authorized_user_file(str(self._token_path))
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001 - re-raised as a clear AuthError
            raise AuthError(f"failed to load/refresh OAuth token: {exc}") from exc
        return build("books", "v1", credentials=creds, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def resolve_reading_now_shelf_id(self) -> str:
        """Find the 'Reading now' shelf id by title, falling back to the
        legacy numeric id if no title match is found."""
        resp = self.service.mylibrary().bookshelves().list().execute()
        shelves = resp.get("items", [])
        for shelf in shelves:
            if str(shelf.get("title", "")).strip().lower() == READING_NOW_TITLE:
                return str(shelf["id"])
        logger.warning(
            "no bookshelf titled 'Reading now' found; falling back to shelf id %s",
            FALLBACK_READING_NOW_SHELF_ID,
        )
        return str(FALLBACK_READING_NOW_SHELF_ID)

    def list_shelf_volume_ids(self, shelf_id: str) -> list[str]:
        resp = (
            self.service.mylibrary()
            .bookshelves()
            .volumes()
            .list(shelf=shelf_id)
            .execute()
        )
        items = resp.get("items", [])
        return [item["id"] for item in items if "id" in item]

    def get_volume_full(self, volume_id: str) -> dict:
        return self.service.volumes().get(volumeId=volume_id, projection="full").execute()
