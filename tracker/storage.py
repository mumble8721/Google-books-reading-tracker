"""Flat-file persistence: state.json (last-known position per book) and
reading_log.jsonl (append-only history of reading events).

No database — both files are plain JSON, sized for personal-scale reading
history (a few thousand lines a year at most).
"""
import json
import os
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"volumes": {}, "shelf_id_cache": None, "schema_version": SCHEMA_VERSION}
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("volumes", {})
    state.setdefault("shelf_id_cache", None)
    state.setdefault("schema_version", SCHEMA_VERSION)
    return state


def save_state(path: Path, state: dict) -> None:
    """Atomic write: write to a temp file in the same directory, then
    os.replace — avoids a torn/partial state.json if the process is killed
    mid-write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def append_log_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True))
        f.write("\n")
        f.flush()


def read_log_rows(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # skip a corrupted line rather than fail the whole read
