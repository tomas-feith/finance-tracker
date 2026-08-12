"""Print the structure of the spreadsheet, for working out how to configure it.

For each tab: dimensions, detected header row, and a few sample rows. Use it to
fill in the column names/indices that config.py's FLAT or BLOCK layout needs.

Run:  uv run python -m finance_tracker.inspect_sheet
"""

from __future__ import annotations

from finance_tracker.sheets_client import get_values, list_tabs


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
