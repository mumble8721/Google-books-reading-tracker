# Google Books Reading Tracker

Tracks how many pages you read in the **Google Play Books** app, over time,
and shows it as a graph. It runs as a small Docker container — designed to
live on a home NAS — that polls the Google Books API every few minutes,
logs any reading progress since the last check to a flat file, and serves a
one-page dashboard with a chart of pages read per day.

## How it works

- A one-time local script (`auth/`) signs you in via Google OAuth once and
  produces a `token.json`. That's the only credential the container needs —
  it refreshes itself silently from then on, with no browser interaction.
- The container polls your **"Reading now"** bookshelf every
  `POLL_INTERVAL_SECONDS` (default 300 = 5 minutes), reads each book's
  reading position, and appends any change to `data/reading_log.jsonl`
  (plain JSON Lines — no database).
- A built-in web server (Flask) serves a dashboard at
  `http://<your-nas-ip>:8080` — a bar chart of pages read per day, plus a
  recent-activity table.

## Important caveat: page estimates are approximate

Google's Books API reports a reading *position*, not literally "pages read,"
and its shape differs by book format:

- **PDF books**: the tracker can usually extract a real page number.
- **EPUB books**: the API only exposes a CFI (an internal markup-offset
  token), not a page number. There's no reliable way to convert that to a
  page count without the book's actual pagination data, so the tracker
  **never guesses a fake page number** for EPUBs — it logs that you kept
  reading (with a note), but with `pages_delta: 0` unless a real number was
  derivable. See `tracker/progress.py` for the exact rules.

## Setup

### 1. Get a Google OAuth token (one-time, on your own PC)

See [`auth/README.md`](auth/README.md) for the full walkthrough:

```bash
cd auth
pip install -r requirements.txt
python authorize.py          # opens a browser, produces token.json
python inspect_volume.py     # optional: sanity-check the API response for your account
```

> **Note:** while your OAuth consent screen is in "Testing" publishing
> status, Google expires the refresh token after **7 days**. Either publish
> the consent screen (fine for personal use) or re-run `authorize.py`
> periodically if the tracker's dashboard stops updating.

### 2. Deploy to your NAS

Copy this repo (or just `docker-compose.yml`, `Dockerfile`, `requirements.txt`,
and `tracker/`) to the NAS, and copy your token alongside it:

```bash
mkdir -p secrets data
cp /path/to/token.json secrets/token.json
```

Then start it:

```bash
docker compose up -d --build
```

### 3. View your reading history

Open `http://<nas-ip>:8080` in a browser. It auto-refreshes every minute.

## Configuration

Set these via `.env` (see `.env.example`) or directly in `docker-compose.yml`:

| Variable | Default | Meaning |
|---|---|---|
| `POLL_INTERVAL_SECONDS` | `300` | How often to check for reading progress |
| `WEB_PORT` | `8080` | Port the dashboard listens on |

## Data & files

- `data/reading_log.jsonl` — append-only history, one line per reading event.
- `data/state.json` — last-known position per book (so deltas survive
  restarts) and the resolved "Reading now" shelf id.

Both are bind-mounted from `./data` so they persist across
`docker compose up`/rebuilds, and are gitignored (this is your personal
reading data, not something to commit).

## Troubleshooting

- **Dashboard shows no data**: make sure you've actually opened/continued a
  book in the Google Play Books app so it appears on your "Reading now"
  shelf, then wait one poll interval.
- **Logs**: `docker compose logs -f`
- **"AUTH ERROR: token refresh failed"** in the logs: your refresh token was
  revoked or expired (see the 7-day Testing-mode caveat above) — re-run
  `auth/authorize.py` and replace `secrets/token.json`.
- **Sanity-checking the API**: `auth/inspect_volume.py` is safe to re-run
  any time and prints the raw API response for books on your shelf.
