"""The polling loop: every POLL_INTERVAL_SECONDS, check the 'Reading now'
shelf and log any reading progress since the last check.

Error-handling policy (see plan): a failure anywhere in a cycle is logged
and the loop continues at the next interval — it must never crash the
container. Each book is additionally isolated in its own try/except so one
bad volume response doesn't abort the rest of the shelf.
"""
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from tracker import storage
from tracker.books_client import AuthError, BooksClient
from tracker.progress import extract_progress

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_one_cycle(client: BooksClient, state: dict, log_path: Path) -> None:
    if not state.get("shelf_id_cache"):
        state["shelf_id_cache"] = client.resolve_reading_now_shelf_id()
    shelf_id = state["shelf_id_cache"]

    volume_ids = client.list_shelf_volume_ids(shelf_id)
    volumes_state = state.setdefault("volumes", {})
    seen_ids = set(volume_ids)

    for volume_id in volume_ids:
        try:
            _process_volume(client, volume_id, volumes_state, log_path)
        except Exception:  # noqa: BLE001 - one bad volume must not abort the cycle
            logger.exception("failed processing volume_id=%s; skipping", volume_id)

    # Books previously tracked but no longer on the shelf (finished/removed
    # in Play Books). Keep their history — mark inactive rather than delete —
    # so a later re-read computes a sane delta instead of a bogus jump.
    for volume_id, entry in volumes_state.items():
        if volume_id not in seen_ids and entry.get("status") != "inactive":
            entry["status"] = "inactive"
            entry["last_checked_at"] = _now_iso()


def _process_volume(client: BooksClient, volume_id: str, volumes_state: dict, log_path: Path) -> None:
    volume = client.get_volume_full(volume_id)
    previous = volumes_state.get(volume_id, {})
    previous_token = previous.get("last_raw_position_token")

    result = extract_progress(volume, previous_raw_token=previous_token)

    previous_page = previous.get("last_estimated_page")
    pages_delta = 0
    if result.estimated_page is not None and previous_page is not None:
        pages_delta = result.estimated_page - previous_page
    elif result.estimated_page is not None and previous_page is None:
        # First time we've ever seen a numeric position for this book —
        # nothing to diff against yet, so no delta (avoids a fake huge
        # "pages read" spike on first sight of an in-progress book).
        pages_delta = 0

    now = _now_iso()
    should_log = pages_delta != 0 or (
        result.position_changed and result.confidence == "unknown"
    )
    if should_log:
        storage.append_log_row(
            log_path,
            {
                "ts": now,
                "volume_id": result.volume_id,
                "title": result.title,
                "pages_delta": pages_delta,
                "page_estimate": result.estimated_page,
                "page_count": result.page_count,
                "confidence": result.confidence,
                "position_format": result.position_format,
                "note": result.note,
            },
        )

    volumes_state[volume_id] = {
        "title": result.title,
        "last_estimated_page": result.estimated_page if result.estimated_page is not None else previous_page,
        "last_raw_position_token": result.raw_position_token,
        "position_format": result.position_format,
        "page_count": result.page_count,
        "status": "active",
        "last_checked_at": now,
        "last_delta_logged_at": now if should_log else previous.get("last_delta_logged_at"),
    }


def run_forever(
    token_path: Path,
    state_path: Path,
    log_path: Path,
    poll_interval_seconds: int,
) -> None:
    client = BooksClient(token_path)
    state = storage.load_state(state_path)

    logger.info(
        "reading tracker poller starting (interval=%ss, state=%s, log=%s)",
        poll_interval_seconds,
        state_path,
        log_path,
    )

    while True:
        cycle_started = time.monotonic()
        try:
            run_one_cycle(client, state, log_path)
            storage.save_state(state_path, state)
        except AuthError:
            logger.exception(
                "AUTH ERROR: token refresh failed — re-run auth/authorize.py "
                "on your PC and re-mount a fresh token.json"
            )
        except Exception:  # noqa: BLE001 - a bad cycle must never kill the loop
            logger.exception("poll cycle failed; will retry next interval")

        elapsed = time.monotonic() - cycle_started
        time.sleep(max(0.0, poll_interval_seconds - elapsed))
