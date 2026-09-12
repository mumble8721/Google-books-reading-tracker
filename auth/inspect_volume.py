#!/usr/bin/env python3
"""Diagnostic script: print real Google Books API responses.

Run this ONCE (locally, with the token.json produced by authorize.py) before
trusting tracker/progress.py's parsing logic. Google's API does not fully
document the exact shape of `userInfo.readingPosition` for every book format
(PDF vs. EPUB vs. scanned image), so this script lets you inspect the real
JSON for a book you are actively reading in Google Play Books, on your own
account, before writing/trusting any parsing rules against it.

It is read-only and safe to re-run any time — keep it in the repo as a
permanent way to re-check field shapes if Google changes something.

Usage:
  python inspect_volume.py [--token token.json] [--shelf-id ID] [volume_id ...]

With no volume_id given, it lists all bookshelves, then lists and inspects
every volume currently on whichever shelf looks like "Reading now" (falling
back to legacy shelf id 3 if no title match is found).
"""
import argparse
import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DEFAULT_TOKEN = Path(__file__).parent / "token.json"
FALLBACK_READING_NOW_SHELF_ID = 3


def load_credentials(token_path: Path) -> Credentials:
    if not token_path.exists():
        print(
            f"ERROR: token file not found: {token_path}\n"
            "Run authorize.py first to produce it.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def resolve_reading_now_shelf_id(service) -> int:
    resp = service.mylibrary().bookshelves().list().execute()
    shelves = resp.get("items", [])
    print("All bookshelves for this account:")
    for shelf in shelves:
        print(f"  id={shelf.get('id')!r:>4} title={shelf.get('title')!r} "
              f"volumeCount={shelf.get('volumeCount')}")
    for shelf in shelves:
        if str(shelf.get("title", "")).strip().lower() == "reading now":
            return int(shelf["id"])
    print(
        f"\nNo shelf titled 'Reading now' found; falling back to legacy "
        f"shelf id {FALLBACK_READING_NOW_SHELF_ID}."
    )
    return FALLBACK_READING_NOW_SHELF_ID


def list_shelf_volume_ids(service, shelf_id: int) -> list[str]:
    resp = service.mylibrary().bookshelves().volumes().list(shelf=shelf_id).execute()
    items = resp.get("items", [])
    return [item["id"] for item in items if "id" in item]


def inspect_volume(service, volume_id: str) -> None:
    resp = service.volumes().get(volumeId=volume_id, projection="full").execute()
    print(f"\n{'=' * 70}\nFull response for volume_id={volume_id}\n{'=' * 70}")
    print(json.dumps(resp, indent=2))

    volume_info = resp.get("volumeInfo", {})
    user_info = resp.get("userInfo", {})
    reading_position = user_info.get("readingPosition")
    print(f"\n--- Highlights for volume_id={volume_id} ---")
    print(f"title: {volume_info.get('title')!r}")
    print(f"pageCount: {volume_info.get('pageCount')!r}")
    print(f"userInfo.readingPosition: {json.dumps(reading_position, indent=2)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", default=str(DEFAULT_TOKEN))
    parser.add_argument("--shelf-id", type=int, default=None)
    parser.add_argument("volume_ids", nargs="*")
    args = parser.parse_args()

    creds = load_credentials(Path(args.token))
    service = build("books", "v1", credentials=creds)

    if args.volume_ids:
        for vid in args.volume_ids:
            inspect_volume(service, vid)
        return 0

    shelf_id = args.shelf_id if args.shelf_id is not None else resolve_reading_now_shelf_id(service)
    print(f"\nUsing shelf id={shelf_id}")
    volume_ids = list_shelf_volume_ids(service, shelf_id)
    if not volume_ids:
        print("No volumes found on that shelf. Open/continue a book in Google "
              "Play Books so it appears on 'Reading now', then re-run.")
        return 0

    print(f"Volumes on shelf: {volume_ids}")
    for vid in volume_ids:
        inspect_volume(service, vid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
