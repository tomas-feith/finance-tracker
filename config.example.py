# Copy this file to `config.py` and fill in your spreadsheet ID.
# The ID is the long string in the sheet URL between "/d/" and "/edit":
#   https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
#
# config.py is git-ignored so your sheet ID stays local.
SHEET_ID = "your-google-sheet-id-here"


# ---------------------------------------------------------------------------
# OPTIONAL: sheet layout. Omit everything below to use the default "block"
# layout (stacked monthly blocks). Most people will want the "flat" layout:
# one row per transaction. See finance_tracker/schema.py for every option.
#
# Not sure how your sheet is shaped? Print its structure with:
#   uv run python -m finance_tracker.inspect_sheet
# ---------------------------------------------------------------------------

# from finance_tracker.schema import FlatLayout, BlockLayout, NumberFormat

# --- Example A: a simple flat transaction table ---------------------------
# LAYOUT = "flat"
# NUMBER_FORMAT = NumberFormat(decimal=".", thousands=",", currency="$")  # US style
# FLAT = FlatLayout(
#     tabs=("Transactions",),        # which tab(s); omit for every tab
#     date_col="Date",               # column header (or 0-based index)
#     amount_col="Amount",
#     category_col="Category",
#     description_col="Note",
#     dayfirst=False,                # True for DD/MM/YYYY dates
#     # income detection — pick ONE approach:
#     income_categories=("Salary", "Interest"),   # these categories are income
#     # income_if_amount_positive=True,           # ...or: positive amount = income
# )

# --- Example B: override the block layout (different categories/columns) ---
# LAYOUT = "block"
# BLOCK = BlockLayout(
#     tab_prefix="Full ",
#     category_cols={0: "Food", 2: "Fun", 4: "Bills", 6: "Income"},
#     income_category="Income",
# )
