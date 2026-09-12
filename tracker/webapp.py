"""Small Flask app serving the reading-history dashboard.

Runs in the same process as the poller (started on a background thread by
main.py). Reads reading_log.jsonl fresh on every request — personal-scale
log sizes make this trivially fast, no caching layer needed.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template

from tracker import storage

logger = logging.getLogger(__name__)

RECENT_LIMIT = 50


def create_app(log_path: Path) -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/daily")
    def api_daily():
        totals: dict[str, int] = defaultdict(int)
        for row in storage.read_log_rows(log_path):
            ts = row.get("ts")
            delta = row.get("pages_delta") or 0
            if not ts:
                continue
            try:
                date = datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                continue
            # Clamp negative deltas (re-reads/rewinds) to 0 for the chart —
            # raw values are preserved in /api/recent for fidelity.
            totals[date] += max(delta, 0)

        # Fill in the last 30 days (including zero-read days) so the chart
        # shows real gaps rather than only the days something happened.
        today = datetime.now(timezone.utc).date()
        days = [today - timedelta(days=i) for i in range(29, -1, -1)]
        series = [{"date": d.isoformat(), "pages": totals.get(d.isoformat(), 0)} for d in days]
        return jsonify(series)

    @app.get("/api/recent")
    def api_recent():
        rows = list(storage.read_log_rows(log_path))
        rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
        return jsonify(rows[:RECENT_LIMIT])

    return app
