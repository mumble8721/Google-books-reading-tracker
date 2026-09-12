"""Parse a Google Books `volumes.get(projection=full)` response into a
best-effort reading-progress estimate.

This module is deliberately pure (no network calls) so it can be tested
against sample JSON captured with auth/inspect_volume.py.

Google's Books API does not publicly guarantee a clean page-number field for
every book format. What's observed in practice:

  - PDF and scanned-image books: `userInfo.readingPosition.pdfPosition` /
    `gbImagePosition` are strings that often embed a page-like integer
    (historically of the form "PP<n>" or similar). We try to extract one
    with a regex and sanity-check it against `volumeInfo.pageCount`.
  - EPUB books: `userInfo.readingPosition.epubCfiPosition` is a CFI
    (EPUB Canonical Fragment Identifier) addressing a DOM offset in the
    book's markup, not a print page. There is no reliable, documented way
    to convert a CFI to a page number without the book's actual spine/
    pagination data, which the API does not expose.

HARD RULE: this module must never invent a precise page number when only a
"the position token changed" signal is available. When we can't derive a
number, we say so explicitly (confidence="unknown") rather than guessing.
"""
import re
from dataclasses import dataclass

_PAGE_NUMBER_RE = re.compile(r"(\d+)")


@dataclass
class ProgressResult:
    volume_id: str
    title: str
    page_count: int | None
    estimated_page: int | None
    raw_position_token: str | None
    position_format: str  # "pdf" | "gb_image" | "epub_cfi" | "none"
    position_changed: bool
    confidence: str  # "exact" | "estimated" | "unknown"
    note: str | None = None


def _try_extract_page_number(token: str, page_count: int | None) -> int | None:
    """Best-effort: pull an integer out of a position token and sanity-check
    it against the book's total page count. Returns None if nothing
    plausible is found."""
    match = _PAGE_NUMBER_RE.search(token)
    if not match:
        return None
    candidate = int(match.group(1))
    if page_count is not None and (candidate < 0 or candidate > page_count):
        return None
    return candidate


def extract_progress(
    volume: dict,
    previous_raw_token: str | None = None,
) -> ProgressResult:
    """Parse one volume's API response into a ProgressResult.

    `previous_raw_token` is the last raw position token we stored for this
    volume (from state.json), used purely to detect "something changed"
    even when no numeric page can be derived (e.g. EPUBs).
    """
    volume_id = volume.get("id", "")
    volume_info = volume.get("volumeInfo", {}) or {}
    user_info = volume.get("userInfo", {}) or {}
    title = volume_info.get("title", volume_id)
    page_count = volume_info.get("pageCount")

    reading_position = user_info.get("readingPosition") or {}

    if "pdfPosition" in reading_position:
        token = reading_position["pdfPosition"]
        position_format = "pdf"
    elif "gbImagePosition" in reading_position:
        token = reading_position["gbImagePosition"]
        position_format = "gb_image"
    elif "epubCfiPosition" in reading_position:
        token = reading_position["epubCfiPosition"]
        position_format = "epub_cfi"
    else:
        return ProgressResult(
            volume_id=volume_id,
            title=title,
            page_count=page_count,
            estimated_page=None,
            raw_position_token=None,
            position_format="none",
            position_changed=False,
            confidence="unknown",
            note="no reading position reported yet for this book",
        )

    position_changed = token != previous_raw_token

    if position_format in ("pdf", "gb_image"):
        page = _try_extract_page_number(token, page_count)
        if page is not None:
            return ProgressResult(
                volume_id=volume_id,
                title=title,
                page_count=page_count,
                estimated_page=page,
                raw_position_token=token,
                position_format=position_format,
                position_changed=position_changed,
                confidence="exact",
            )
        # Couldn't confidently parse a page number even though this is a
        # page-oriented format — don't guess, just report the change.
        return ProgressResult(
            volume_id=volume_id,
            title=title,
            page_count=page_count,
            estimated_page=None,
            raw_position_token=token,
            position_format=position_format,
            position_changed=position_changed,
            confidence="unknown",
            note=f"could not parse a page number from position token: {token!r}",
        )

    # EPUB CFI: no reliable page conversion without the book's spine data.
    return ProgressResult(
        volume_id=volume_id,
        title=title,
        page_count=page_count,
        estimated_page=None,
        raw_position_token=token,
        position_format="epub_cfi",
        position_changed=position_changed,
        confidence="unknown",
        note=(
            "epub position token changed; no page-equivalent derivable "
            "from a CFI without the book's spine data"
            if position_changed
            else None
        ),
    )
