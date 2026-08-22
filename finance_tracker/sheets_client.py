"""Thin wrapper around the Google Sheets API using a service account.

Reads the spreadsheet ID from config.py (or the SHEET_ID env var) and the
service-account credentials from secrets/service_account.json.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from finance_tracker import userconfig

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = ROOT / "secrets" / "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
# The value config.example.py ships with; treat it as "not configured yet".
PLACEHOLDER_SHEET_ID = "your-google-sheet-id-here"
# googleapiclient defaults to num_retries=0, so a single transient TLS or socket
# blip (SSLError WRONG_VERSION_NUMBER, ECONNRESET, timeout) propagates straight out
# of execute() and takes the page with it. Non-zero re-runs those with exponential
# backoff; it does not retry HTTP 4xx, so a revoked key still fails fast.
NUM_RETRIES = 3


def get_sheet_id() -> str:
    """The spreadsheet ID, from the SHEET_ID env var or config.py."""
    sid = os.environ.get("SHEET_ID")
    if sid:
        return sid
    from_config = userconfig.get("SHEET_ID")
    if not from_config:
        raise RuntimeError(
            "No spreadsheet ID found. Set the SHEET_ID env var, or copy "
            "config.example.py to config.py and fill in SHEET_ID."
        )
    return str(from_config)


def has_live_config() -> bool:
    """True only if both a service-account key and a sheet ID are available.
    When False, the app falls back to synthetic demo data."""
    if not CREDENTIALS_PATH.exists():
        return False
    try:
        sid = get_sheet_id()
    except (RuntimeError, userconfig.ConfigError):
        return False
    return bool(sid) and sid != PLACEHOLDER_SHEET_ID


@lru_cache(maxsize=1)
def _service():
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Service-account key not found at {CREDENTIALS_PATH}. "
            "Download it from Google Cloud and place it there."
        )
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def list_tabs() -> list[dict]:
    """Return metadata for each tab: title, rows, cols, index."""
    meta = (
        _service().spreadsheets().get(spreadsheetId=get_sheet_id()).execute(num_retries=NUM_RETRIES)
    )
    out = []
    for s in meta.get("sheets", []):
        p = s["properties"]
        grid = p.get("gridProperties", {})
        out.append(
            {
                "title": p["title"],
                "index": p.get("index"),
                "rows": grid.get("rowCount"),
                "cols": grid.get("columnCount"),
            }
        )
    return out


def get_values(tab: str, cell_range: str | None = None) -> list[list]:
    """Return raw cell values for a tab (optionally a specific A1 range)."""
    rng = f"'{tab}'!{cell_range}" if cell_range else f"'{tab}'"
    resp = (
        _service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=get_sheet_id(), range=rng)
        .execute(num_retries=NUM_RETRIES)
    )
    return resp.get("values", [])
