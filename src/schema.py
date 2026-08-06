"""Sheet-layout configuration.

Everything the parser needs to know about *how a sheet is shaped* lives here,
so `data.py` contains logic, not magic constants. Two layouts are supported:

  - "block": stacked monthly blocks with `amount | comment` column pairs and
    per-category TOTAL rows (the layout this project started with).
  - "flat":  one row per transaction — the common `date | category | amount |
    description` table most people keep.

Defaults reproduce the original block sheet exactly. A project can override any
of this from `config.py` by setting LAYOUT / NUMBER_FORMAT / BLOCK / FLAT.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root (config.py)


@dataclass(frozen=True)
class NumberFormat:
    decimal: str = ","  # decimal separator in the sheet
    thousands: str = "."  # extra char(s) stripped as thousands separators
    currency: str = "€"  # currency symbol(s) to strip (default: euro)
    # spaces and non-breaking spaces are always stripped, regardless of the above


@dataclass
class BlockLayout:
    """Stacked monthly blocks (the original layout)."""

    tab_prefix: str = "Full "  # tabs whose title starts with this hold transactions
    # amount-column index -> category (comment assumed at index+1)
    category_cols: dict = field(
        default_factory=lambda: {
            0: "Food",
            2: "Social Life",
            4: "House Purchases",
            6: "Fixed costs",
            8: "Travels",
            10: "Others",
            12: "Income",
        }
    )
    income_category: str = "Income"
    header_first_cell: str = "Food"  # first cell of the per-block header row
    total_marker: str = "TOTAL"  # comment-cell value marking the totals row
    net_first_cell: str = "FULL"  # first-cell value marking the monthly-net row
    # optional monthly figure that lives outside the blocks (e.g. rent):
    extra_tab: str | None = "Lifetime"
    extra_section: str = "MONTHLY TIMELINE"
    extra_col: int = 7
    extra_category: str = "Rent"


@dataclass
class FlatLayout:
    """One row per transaction. Columns may be given by header name or 0-based index."""

    tabs: tuple = ()  # explicit tab titles; empty = every tab
    header_row: int = 0  # 0-based row holding column headers
    date_col: object = "date"  # header name or int index
    amount_col: object = "amount"
    category_col: object = "category"
    description_col: object = "description"
    date_format: str | None = None  # strptime fmt; None = let pandas infer
    dayfirst: bool = False  # True for DD/MM/YYYY sheets (ignored if date_format set)
    # income detection — either by category name, or by amount sign:
    income_categories: tuple = ("Income",)
    income_if_amount_positive: bool = False  # if True, positive amount = income


def resolve():
    """Return (layout_name, NumberFormat, BlockLayout, FlatLayout), applying any
    overrides found in config.py."""
    layout = "block"
    number, block, flat = NumberFormat(), BlockLayout(), FlatLayout()
    try:
        import config

        layout = getattr(config, "LAYOUT", layout)
        number = getattr(config, "NUMBER_FORMAT", number)
        block = getattr(config, "BLOCK", block)
        flat = getattr(config, "FLAT", flat)
    except Exception:
        pass
    return layout, number, block, flat


# module-level defaults (kept for back-compatible imports)
DEFAULT_NUMBER = NumberFormat()
DEFAULT_BLOCK = BlockLayout()
