"""Thin wrapper around the Google Sheets API using a service account.

Reads the spreadsheet ID from config.py (or the SHEET_ID env var) and the
service-account credentials from secrets/service_account.json.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = ROOT / "secrets" / "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheet_id() -> str:
    sid = os.environ.get("SHEET_ID")
    if sid:
        return sid
    try:
        from config import SHEET_ID  # type: ignore
        return SHEET_ID
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "No spreadsheet ID found. Set SHEET_ID env var or create config.py "
            "with SHEET_ID = '...'."
        ) from exc


def has_live_config() -> bool:
    """True only if both a service-account key and a sheet ID are available.
    When False, the app falls back to synthetic demo data."""
    if not CREDENTIALS_PATH.exists():
        return False
    try:
        sid = get_sheet_id()
    except Exception:
        return False
    return bool(sid) and sid != "your-google-sheet-id-here"


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
    meta = _service().spreadsheets().get(spreadsheetId=get_sheet_id()).execute()
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
        .execute()
    )
    return resp.get("values", [])
