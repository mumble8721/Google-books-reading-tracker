# Auth setup

This directory produces the one credential file (`token.json`) the tracker
container needs — everything here is meant to be run **once, on your own
computer**, never inside Docker.

## 1. Create Google Cloud credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/), create
   or select a project.
2. **APIs & Services > Library** — enable **Books API**.
3. **APIs & Services > OAuth consent screen** — configure it (User type:
   External is fine for personal use). Add your own Google account under
   **Test users**.
4. **APIs & Services > Credentials > Create Credentials > OAuth client ID** —
   Application type: **Desktop app**. Download the resulting JSON and save it
   as `client_secret.json` in this `auth/` directory (it's gitignored).

> **Note on token lifetime:** while the consent screen is in "Testing"
> publishing status, Google expires refresh tokens after **7 days**. For
> uninterrupted long-term polling, either publish the OAuth consent screen
> (still fine for personal single-user use) or plan to re-run `authorize.py`
> periodically.

## 2. Get a token

```bash
cd auth
pip install -r requirements.txt
python authorize.py
```

This opens your browser, has you sign in and consent, and writes
`auth/token.json`. Treat it like a password — it's gitignored and must never
be committed.

## 3. Sanity-check the API response for your account (recommended)

Google's Books API doesn't fully document the exact shape of a book's reading
position for every format. Before trusting the tracker's page estimates,
open/continue a book in the **Google Play Books app** so it's on your
"Reading now" shelf, then run:

```bash
python inspect_volume.py
```

This prints the raw JSON for every book on that shelf, including
`userInfo.readingPosition` and `volumeInfo.pageCount`, so you can see exactly
what your account's API responses look like. Re-run it any time (it's
read-only) if reading-progress numbers ever look off.

## 4. Deploy the token to your NAS

Copy `token.json` to the NAS, alongside `docker-compose.yml`, e.g.:

```bash
scp token.json nas:/path/to/Google-books-reading-tracker/secrets/token.json
```

See the root `README.md` for the rest of the Docker setup.
