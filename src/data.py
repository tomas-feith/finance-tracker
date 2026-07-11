"""Parse the 'Full YYYY' tabs into a tidy transaction-level DataFrame.

Each Full tab is a vertical stack of monthly blocks:
    <MONTH YYYY>                         (single-cell header)
    Food|Comment|Social Life|Comment|House Purchases|Comment|Fixed costs|Comment|
        Travels|Comment|Others|Comment|Income|Comment
    <amount>|<comment>|...   (transaction rows, category = fixed column pair)
    ...
    <total>|TOTAL|...        (per-category monthly totals)
    FULL|<net>               (monthly net cashflow)
    <blank>

We read each (amount, comment) column pair as a category and emit one row per
non-empty amount: {year, month, date, category, amount, comment, is_income}.
"""
from __future__ import annotations

import re
import sys
import datetime as dt
from pathlib import Path
from functools import lru_cache

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root (config.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))         # src (sheets_client)

from sheets_client import list_tabs, get_values

# column offset -> category label (amount col, comment col = amount col + 1)
CATEGORY_COLS = {
    0: "Food",
    2: "Social Life",
    4: "House Purchases",
    6: "Fixed costs",
    8: "Travels",
    10: "Others",
    12: "Income",
}

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_MONTH_HEADER = re.compile(r"^\s*([A-Z]{3})[A-Z]*\s+(\d{4})\s*$", re.IGNORECASE)


def parse_amount(raw: str) -> float | None:
    """European number format: ',' decimal, non-breaking-space/dot thousands,
    optional '€' and sign. Returns None if not a number."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("€", "").replace("€", "")           # euro sign
    s = s.replace("\xa0", "").replace(" ", "")              # thousands sep
    s = s.replace(".", "").replace(",", ".") if ("," in s) else s.replace(" ", "")
    s = s.strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _cell(row: list, idx: int) -> str:
    return row[idx] if idx < len(row) else ""


def parse_full_tab(tab: str, year_hint: int | None = None) -> list[dict]:
    rows = get_values(tab)
    records: list[dict] = []
    cur_month = None
    cur_year = None
    for row in rows:
        first = (_cell(row, 0) or "").strip()

        # month header?
        m = _MONTH_HEADER.match(first) if (first and len([c for c in row if c]) <= 2) else None
        if m and m.group(1).upper()[:3] in MONTHS:
            cur_month = MONTHS[m.group(1).upper()[:3]]
            cur_year = int(m.group(2))
            continue

        if cur_month is None:
            continue
        # skip the header row and total/net rows
        if first in ("Food", "FULL"):
            continue
        if any((_cell(row, c) or "").strip() == "TOTAL" for c in (1, 3, 5, 7, 9, 11, 13)):
            continue

        for amt_col, category in CATEGORY_COLS.items():
            amount = parse_amount(_cell(row, amt_col))
            comment = (_cell(row, amt_col + 1) or "").strip()
            if amount is None:
                continue
            records.append(
                {
                    "year": cur_year,
                    "month": cur_month,
                    "date": dt.date(cur_year, cur_month, 1),
                    "category": category,
                    "amount": amount,
                    "comment": comment,
                    "is_income": category == "Income",
                }
            )
    return records


_TIMELINE_MONTH = re.compile(r"^\s*(\d{4})-([A-Za-z]{3,})\s*$")


def load_rent() -> list[dict]:
    """Rent isn't in the Full tabs — it lives only as a monthly figure in the
    Lifetime tab's MONTHLY TIMELINE (column 'Rent', index 7). Pull it and emit
    one synthetic expense record per month so every view can include it."""
    rows = get_values("Lifetime")
    started = False
    recs: list[dict] = []
    for row in rows:
        first = (_cell(row, 0) or "").strip()
        if first == "MONTHLY TIMELINE":
            started = True
            continue
        if not started:
            continue
        m = _TIMELINE_MONTH.match(first)
        if not m:
            continue
        mon = MONTHS.get(m.group(2).upper()[:3])
        if mon is None:
            continue
        amount = parse_amount(_cell(row, 7))  # 'Rent' column
        if amount is None or amount == 0:
            continue
        yr = int(m.group(1))
        recs.append({
            "year": yr, "month": mon, "date": dt.date(yr, mon, 1),
            "category": "Rent", "amount": amount, "comment": "Rent (monthly)",
            "is_income": False,
        })
    return recs


@lru_cache(maxsize=1)
def _load_full_transactions() -> pd.DataFrame:
    """Full-tab transactions only (no rent). Used by validate.py."""
    full_tabs = [t["title"] for t in list_tabs() if t["title"].startswith("Full ")]
    all_recs: list[dict] = []
    for tab in full_tabs:
        all_recs.extend(parse_full_tab(tab))
    df = pd.DataFrame(all_recs)
    df["date"] = pd.to_datetime(df["date"])
    df["month_str"] = df["date"].dt.strftime("%Y-%m")
    return df.sort_values(["date", "category"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def load_transactions(include_rent: bool = True) -> pd.DataFrame:
    df = _load_full_transactions()
    if include_rent:
        rent = pd.DataFrame(load_rent())
        rent["date"] = pd.to_datetime(rent["date"])
        rent["month_str"] = rent["date"].dt.strftime("%Y-%m")
        df = pd.concat([df, rent], ignore_index=True)
    return df.sort_values(["date", "category"]).reset_index(drop=True)


if __name__ == "__main__":
    df = load_transactions()
    print(f"Parsed {len(df):,} transactions across {df['month_str'].nunique()} months")
    print(f"Date range: {df['date'].min():%Y-%m} -> {df['date'].max():%Y-%m}")
    print("\nBy category:")
    print(df.groupby("category")["amount"].agg(["count", "sum"]).round(2))
