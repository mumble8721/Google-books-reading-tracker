#!/usr/bin/env python3
"""One-time local OAuth helper for the Google Books reading tracker.

Run this ONCE on your own PC/laptop (never inside the Docker container).
It opens a browser, has you sign in and consent, then writes a token file
containing a long-lived refresh token. That token file is what gets copied
onto the NAS so the container can authenticate headlessly, without ever
needing a browser itself.

Prerequisites:
  1. In Google Cloud Console, create/select a project and enable the
     "Books API".
  2. Configure the OAuth consent screen (External is fine for personal use;
     add your own Google account as a test user).
  3. Create an OAuth Client ID of type "Desktop app" and download its JSON
     — save it as client_secret.json next to this script (or pass a path).

Usage:
  pip install -r requirements.txt   # (this directory's requirements.txt)
  python authorize.py [path/to/client_secret.json] [--out token.json]
"""
import argparse
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/books"]

DEFAULT_CLIENT_SECRET = Path(__file__).parent / "client_secret.json"
DEFAULT_TOKEN_OUT = Path(__file__).parent / "token.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "client_secret",
        nargs="?",
        default=str(DEFAULT_CLIENT_SECRET),
        help="Path to the OAuth Desktop client JSON downloaded from Google "
        "Cloud Console (default: client_secret.json next to this script).",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_TOKEN_OUT),
        help="Where to write the resulting token file (default: token.json "
        "next to this script).",
    )
    args = parser.parse_args()

    client_secret_path = Path(args.client_secret)
    if not client_secret_path.exists():
        print(
            f"ERROR: client secret file not found: {client_secret_path}\n"
            "Download it from Google Cloud Console (APIs & Services > "
            "Credentials > your Desktop app OAuth client) and place it "
            "there, or pass its path as an argument.",
            file=sys.stderr,
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    # Opens a local redirect server + your system browser. Sign in, consent,
    # and control returns here automatically.
    creds = flow.run_local_server(port=0)

    out_path = Path(args.out)
    out_path.write_text(creds.to_json())

    print(f"\nSuccess! Token written to: {out_path.resolve()}")
    print(
        "\nThis file contains a long-lived credential (a refresh token). "
        "Treat it like a password:\n"
        "  - Never commit it to git (it's already covered by .gitignore).\n"
        "  - Copy it to your NAS out-of-band (scp/rsync/USB), e.g. into "
        "./secrets/token.json next to docker-compose.yml.\n"
        "  - If the OAuth consent screen is still in 'Testing' publishing "
        "status, Google expires refresh tokens after 7 days — either "
        "publish the app or re-run this script periodically."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
