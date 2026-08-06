"""Parser tests for both sheet layouts. Pure functions over raw value matrices,
so no Google Sheets access is needed.

Run either way:
    python tests/test_parsers.py     # plain asserts
    pytest                            # auto-discovered test_* functions
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from data import parse_block_values, parse_flat_values
from schema import DEFAULT_BLOCK, DEFAULT_NUMBER, FlatLayout, NumberFormat

_US = NumberFormat(decimal=".", thousands=",", currency="$")


# ------------------------------------------------------------------ flat layout
def test_flat_by_category_name():
    values = [
        ["date", "category", "amount", "description"],
        ["2025-01-05", "Food", "12.50", "Lunch"],
        ["2025-01-20", "Salary", "3,000.00", "Jan pay"],
        ["2025-02-03", "Food", "8.00", "Snack"],
        ["bad-date", "Food", "5.00", "skip"],
        ["2025-02-10", "Food", "notnum", "skip"],
    ]
    recs = parse_flat_values(values, FlatLayout(income_categories=("Salary",)), _US)
    assert len(recs) == 3
    assert sorted((r["date"].year, r["date"].month) for r in recs) == [
        (2025, 1),
        (2025, 1),
        (2025, 2),
    ]
    assert all(r["date"].day == 1 for r in recs)  # month-normalised
    sal = next(r for r in recs if r["category"] == "Salary")
    assert sal["is_income"] and sal["amount"] == 3000.0


def test_flat_sign_convention():
    values = [
        ["date", "category", "amount", "description"],
        ["2025-01-05", "Food", "-12.50", "Lunch"],
        ["2025-01-20", "Salary", "3000", "pay"],
    ]
    recs = parse_flat_values(values, FlatLayout(income_if_amount_positive=True), _US)
    food = next(r for r in recs if r["category"] == "Food")
    sal = next(r for r in recs if r["category"] == "Salary")
    assert food["is_income"] is False and food["amount"] == 12.5
    assert sal["is_income"] is True and sal["amount"] == 3000.0


def test_flat_columns_by_index_and_dayfirst():
    values = [
        ["when", "what", "how much", "note"],
        ["05/01/2025", "Rent", "1.000,00", "March"],  # 5 Jan 2025, EU number fmt
    ]
    flat = FlatLayout(date_col=0, category_col=1, amount_col=2, description_col=3, dayfirst=True)
    recs = parse_flat_values(values, flat, NumberFormat())  # euro default
    assert len(recs) == 1
    assert recs[0]["category"] == "Rent" and recs[0]["amount"] == 1000.0
    assert recs[0]["date"].month == 1  # dayfirst -> January


# ----------------------------------------------------------------- block layout
def test_block_basic():
    values = [
        ["JAN 2025"],
        [
            "Food",
            "Comment",
            "Social Life",
            "Comment",
            "House Purchases",
            "Comment",
            "Fixed costs",
            "Comment",
            "Travels",
            "Comment",
            "Others",
            "Comment",
            "Income",
            "Comment",
        ],
        ["12,50", "Lunch", "", "", "", "", "", "", "", "", "", "", "3 000,00", "Salary"],
        ["8,00", "Snack", "", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "20,50",
            "TOTAL",
            "0,00",
            "TOTAL",
            "0,00",
            "TOTAL",
            "0,00",
            "TOTAL",
            "0,00",
            "TOTAL",
            "0,00",
            "TOTAL",
            "3 000,00",
            "TOTAL",
        ],
        ["FULL", "2 979,50"],
        [],
    ]
    recs = parse_block_values(values, DEFAULT_BLOCK, DEFAULT_NUMBER)
    foods = [r for r in recs if r["category"] == "Food"]
    incomes = [r for r in recs if r["category"] == "Income"]
    assert len(foods) == 2 and {r["amount"] for r in foods} == {12.5, 8.0}
    assert len(incomes) == 1 and incomes[0]["is_income"] and incomes[0]["amount"] == 3000.0
    assert all(r["date"].month == 1 and r["date"].year == 2025 for r in recs)
    # TOTAL / FULL / header rows must not become transactions
    assert not any(r["comment"] == "TOTAL" for r in recs)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
