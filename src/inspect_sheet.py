"""Print the structure of the spreadsheet so we can design the dashboard.

For each tab: dimensions, detected header row, and a few sample rows.
Run:  .venv\\Scripts\\python.exe src\\inspect_sheet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for config.py
sys.path.insert(0, str(Path(__file__).resolve().parent))         # for sheets_client

from sheets_client import get_values, list_tabs  # noqa: E402


def main() -> None:
    tabs = list_tabs()
    print(f"Spreadsheet has {len(tabs)} tab(s):\n")
    for t in tabs:
        print(f"  [{t['index']}] {t['title']}  ({t['rows']} rows x {t['cols']} cols)")
    print("\n" + "=" * 70)

    for t in tabs:
        title = t["title"]
        print(f"\n### TAB: {title}")
        values = get_values(title, "A1:Z12")  # top-left preview
        if not values:
            print("  (empty)")
            continue
        header = values[0]
        print(f"  Columns ({len(header)}): {header}")
        print("  Sample rows:")
        for row in values[1:8]:
            print(f"    {row}")


if __name__ == "__main__":
    main()
