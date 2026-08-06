"""Parse a finance spreadsheet into a tidy transaction-level DataFrame.

Supports two layouts (see schema.py): "block" (stacked monthly blocks with
amount|comment pairs — the original sheet) and "flat" (one row per transaction).
Both produce the same schema:

    year | month | date | category | amount | comment | is_income | month_str

The `parse_*_values` functions are pure (take a raw values matrix) so they can be
unit-tested without hitting Google Sheets.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root (config.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))  # src (sheets_client)

import schema as _schema
from schema import DEFAULT_BLOCK, DEFAULT_NUMBER
from sheets_client import get_values, list_tabs

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_MONTH_HEADER = re.compile(r"^\s*([A-Z]{3})[A-Z]*\s+(\d{4})\s*$", re.IGNORECASE)
_TIMELINE_MONTH = re.compile(r"^\s*(\d{4})-([A-Za-z]{3,})\s*$")

# back-compatible export (validate.py reads the active block's category columns)
CATEGORY_COLS = _schema.resolve()[2].category_cols

_COLS = ["year", "month", "date", "category", "amount", "comment", "is_income"]


# --------------------------------------------------------------------- helpers
def parse_amount(raw, nf=DEFAULT_NUMBER) -> float | None:
    """Parse a number in the configured format. Strips the currency symbol,
    spaces / non-breaking spaces, and the thousands separator, then normalises
    the decimal separator. Returns None if not a number."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for c in nf.currency:
        s = s.replace(c, "")
    s = s.replace("\xa0", "").replace(" ", "")  # always drop spaces & nbsp
    for c in nf.thousands:
        s = s.replace(c, "")
    if nf.decimal and nf.decimal != ".":
        s = s.replace(nf.decimal, ".")
    s = s.strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _cell(row: list, idx: int) -> str:
    return row[idx] if (0 <= idx < len(row)) else ""


def _to_df(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records, columns=_COLS)
    df["date"] = pd.to_datetime(df["date"])
    df["month_str"] = df["date"].dt.strftime("%Y-%m") if len(df) else pd.Series(dtype=str)
    if len(df):
        df = df.sort_values(["date", "category"]).reset_index(drop=True)
    return df


def _col_index(spec, header) -> int | None:
    if isinstance(spec, int):
        return spec
    for i, h in enumerate(header):
        if str(h).strip().lower() == str(spec).strip().lower():
            return i
    return None


# ----------------------------------------------------------------- block parser
def parse_block_values(values, block=DEFAULT_BLOCK, nf=DEFAULT_NUMBER) -> list[dict]:
    records: list[dict] = []
    cur_month = cur_year = None
    comment_cols = [c + 1 for c in block.category_cols]
    for row in values:
        first = (_cell(row, 0) or "").strip()
        m = _MONTH_HEADER.match(first) if (first and len([c for c in row if c]) <= 2) else None
        if m and m.group(1).upper()[:3] in MONTHS:
            cur_month = MONTHS[m.group(1).upper()[:3]]
            cur_year = int(m.group(2))
            continue
        if cur_month is None or cur_year is None:
            continue
        if first in (block.header_first_cell, block.net_first_cell):
            continue
        if any((_cell(row, c) or "").strip() == block.total_marker for c in comment_cols):
            continue
        for amt_col, category in block.category_cols.items():
            amount = parse_amount(_cell(row, amt_col), nf)
            if amount is None:
                continue
            records.append(
                {
                    "year": cur_year,
                    "month": cur_month,
                    "date": dt.date(cur_year, cur_month, 1),
                    "category": category,
                    "amount": amount,
                    "comment": (_cell(row, amt_col + 1) or "").strip(),
                    "is_income": category == block.income_category,
                }
            )
    return records


def parse_block_tab(tab, block=DEFAULT_BLOCK, nf=DEFAULT_NUMBER) -> list[dict]:
    return parse_block_values(get_values(tab), block, nf)


parse_full_tab = parse_block_tab  # back-compat alias


def load_block_extra(block=DEFAULT_BLOCK, nf=DEFAULT_NUMBER) -> list[dict]:
    """A monthly figure that lives outside the blocks (rent, in the original
    sheet's Lifetime > MONTHLY TIMELINE). Emits one expense record per month."""
    if not block.extra_tab:
        return []
    started = False
    recs: list[dict] = []
    for row in get_values(block.extra_tab):
        first = (_cell(row, 0) or "").strip()
        if first == block.extra_section:
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
        amount = parse_amount(_cell(row, block.extra_col), nf)
        if amount is None or amount == 0:
            continue
        yr = int(m.group(1))
        recs.append(
            {
                "year": yr,
                "month": mon,
                "date": dt.date(yr, mon, 1),
                "category": block.extra_category,
                "amount": amount,
                "comment": f"{block.extra_category} (monthly)",
                "is_income": False,
            }
        )
    return recs


# ------------------------------------------------------------------ flat parser
def parse_flat_values(values, flat, nf=DEFAULT_NUMBER) -> list[dict]:
    if not values or len(values) <= flat.header_row:
        return []
    header = values[flat.header_row]
    di = _col_index(flat.date_col, header)
    ai = _col_index(flat.amount_col, header)
    ci = _col_index(flat.category_col, header)
    xi = _col_index(flat.description_col, header)
    if di is None or ai is None or ci is None:
        raise ValueError(
            f"Flat layout: could not locate date/amount/category columns in header {header!r}"
        )
    inc_set = {c.strip().lower() for c in flat.income_categories}
    recs: list[dict] = []
    for row in values[flat.header_row + 1 :]:
        raw_date = str(_cell(row, di) or "").strip()
        amount = parse_amount(_cell(row, ai), nf)
        if not raw_date or amount is None:
            continue
        ts = pd.to_datetime(
            raw_date, format=flat.date_format, errors="coerce", dayfirst=flat.dayfirst
        )
        if pd.isna(ts):
            continue
        category = (_cell(row, ci) or "").strip() or "Uncategorized"
        desc = (_cell(row, xi) or "").strip() if xi is not None else ""
        is_income = (
            (amount > 0)
            if flat.income_if_amount_positive
            else (category.strip().lower() in inc_set)
        )
        recs.append(
            {
                "year": int(ts.year),
                "month": int(ts.month),
                "date": dt.date(int(ts.year), int(ts.month), 1),
                "category": category,
                "amount": abs(amount),
                "comment": desc,
                "is_income": is_income,
            }
        )
    return recs


def parse_flat_tab(tab, flat, nf=DEFAULT_NUMBER) -> list[dict]:
    return parse_flat_values(get_values(tab), flat, nf)


# --------------------------------------------------------------------- loaders
@lru_cache(maxsize=1)
def _load_full_transactions() -> pd.DataFrame:
    """Block transactions only (no extra/rent). Used by validate.py."""
    _, nf, block, _ = _schema.resolve()
    recs: list[dict] = []
    for t in list_tabs():
        if t["title"].startswith(block.tab_prefix):
            recs.extend(parse_block_tab(t["title"], block, nf))
    return _to_df(recs)


@lru_cache(maxsize=1)
def load_transactions(include_rent: bool = True) -> pd.DataFrame:
    layout, nf, block, flat = _schema.resolve()

    if layout == "flat":
        tabs = list(flat.tabs) or [t["title"] for t in list_tabs()]
        recs: list[dict] = []
        for tab in tabs:
            recs.extend(parse_flat_tab(tab, flat, nf))
        return _to_df(recs)

    # default: block layout
    df = _load_full_transactions()
    if include_rent and block.extra_tab:
        extra = load_block_extra(block, nf)
        if extra:
            df = pd.concat([df, _to_df(extra)], ignore_index=True)
            df = df.sort_values(["date", "category"]).reset_index(drop=True)
    return df


def load_rent() -> list[dict]:
    """Back-compat: the block layout's extra monthly figure (rent)."""
    _, nf, block, _ = _schema.resolve()
    return load_block_extra(block, nf)


if __name__ == "__main__":
    df = load_transactions()
    print(f"Parsed {len(df):,} transactions across {df['month_str'].nunique()} months")
    print(f"Date range: {df['date'].min():%Y-%m} -> {df['date'].max():%Y-%m}")
    print("\nBy category:")
    print(df.groupby("category")["amount"].agg(["count", "sum"]).round(2))
