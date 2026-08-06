"""Validate the parser: compare my per-month, per-category parsed sums against
the sheet's own TOTAL rows in each Full tab. Any mismatch > 1 cent is flagged."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import re

from data import CATEGORY_COLS, MONTHS, _cell, _load_full_transactions, parse_amount
from sheets_client import get_values, list_tabs

_MONTH_HEADER = re.compile(r"^\s*([A-Z]{3})[A-Z]*\s+(\d{4})\s*$", re.IGNORECASE)


def sheet_totals():
    """Extract the sheet's own TOTAL row per (year, month, category)."""
    out = {}
    for t in list_tabs():
        if not t["title"].startswith("Full "):
            continue
        cur = None
        for row in get_values(t["title"]):
            first = (_cell(row, 0) or "").strip()
            m = _MONTH_HEADER.match(first) if (first and len([c for c in row if c]) <= 2) else None
            if m and m.group(1).upper()[:3] in MONTHS:
                cur = (int(m.group(2)), MONTHS[m.group(1).upper()[:3]])
                continue
            total_cols = (1, 3, 5, 7, 9, 11, 13)
            if cur and any((_cell(row, c) or "").strip() == "TOTAL" for c in total_cols):
                for amt_col, cat in CATEGORY_COLS.items():
                    if (_cell(row, amt_col + 1) or "").strip() == "TOTAL":
                        val = parse_amount(_cell(row, amt_col))
                        if val is not None:
                            out[(cur[0], cur[1], cat)] = val
    return out


def main():
    df = _load_full_transactions()
    parsed = df.groupby(["year", "month", "category"])["amount"].sum().round(2).to_dict()
    totals = sheet_totals()

    mismatches = []
    checked = 0
    for key, sheet_val in totals.items():
        checked += 1
        my_val = round(parsed.get(key, 0.0), 2)
        if abs(my_val - sheet_val) > 0.01:
            mismatches.append((key, my_val, sheet_val))

    print(f"Checked {checked} (year, month, category) totals against the sheet.")
    if not mismatches:
        print("PERFECT MATCH — every parsed category total equals the sheet's TOTAL row.")
    else:
        print(f"{len(mismatches)} mismatch(es):")
        for key, mine, theirs in sorted(mismatches)[:40]:
            print(f"  {key}: parsed {mine:.2f}  vs sheet {theirs:.2f}  (diff {mine - theirs:+.2f})")


if __name__ == "__main__":
    main()
