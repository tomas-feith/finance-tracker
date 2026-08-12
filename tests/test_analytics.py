"""Tests for the analytics layer.

These are pure pandas over the one tidy transaction table
(``year | month | date | category | amount | comment | is_income | month_str``),
so nothing here touches Google Sheets.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from finance_tracker import analytics as A


def _txn(date: str, category: str, amount: float, comment: str = "", income: bool = False) -> dict:
    d = dt.date.fromisoformat(date)
    return {
        "year": d.year,
        "month": d.month,
        "date": pd.Timestamp(d.year, d.month, 1),
        "category": category,
        "amount": amount,
        "comment": comment,
        "is_income": income,
    }


@pytest.fixture
def df() -> pd.DataFrame:
    rows = [
        _txn("2025-01-01", "Income", 3000.0, "Salary", income=True),
        _txn("2025-01-01", "Food", 200.0, "Groceries (1st-7th)"),
        _txn("2025-01-01", "Rent", 900.0, "Rent (monthly)"),
        _txn("2025-02-01", "Income", 3000.0, "Salary", income=True),
        _txn("2025-02-01", "Food", 250.0, "Groceries (8th-14th)"),
        _txn("2025-02-01", "Rent", 900.0, "Rent (monthly)"),
        _txn("2025-03-01", "Income", 3000.0, "Salary", income=True),
        _txn("2025-03-01", "Food", 180.0, "Groceries 21st"),
        _txn("2025-03-01", "Rent", 900.0, "Rent (monthly)"),
        _txn("2025-03-01", "Travels", 1500.0, "Flights"),
    ]
    out = pd.DataFrame(rows)
    out["month_str"] = out["date"].dt.strftime("%Y-%m")
    return out


# ------------------------------------------------------------------- categories
def test_order_categories_puts_known_first_then_the_rest() -> None:
    got = A.order_categories(["Zebra", "Food", "Alpha", "Rent"])
    assert got == ["Rent", "Food", "Alpha", "Zebra"]


def test_order_categories_keeps_unknown_names() -> None:
    """A flat-layout sheet has the user's own category names, not the block ones."""
    got = A.order_categories(["Groceries", "Transport"])
    assert sorted(got) == ["Groceries", "Transport"]


def test_expense_categories_reads_the_data_not_a_fixed_list(df: pd.DataFrame) -> None:
    """The regression: filtering against a hardcoded list dropped every expense
    for any sheet whose categories are not the original block sheet's."""
    custom = df.copy()
    custom.loc[~custom["is_income"], "category"] = "Groceries"
    assert A.expense_categories(custom) == ["Groceries"]


def test_expense_categories_excludes_income(df: pd.DataFrame) -> None:
    assert "Income" not in A.expense_categories(df)
    assert A.expense_categories(df) == ["Rent", "Food", "Travels"]


# ---------------------------------------------------------------------- summary
def test_monthly_summary_computes_net_and_savings_rate(df: pd.DataFrame) -> None:
    ms = A.monthly_summary(df)
    assert list(ms["month_str"]) == ["2025-01", "2025-02", "2025-03"]
    jan = ms.iloc[0]
    assert jan["income"] == 3000.0
    assert jan["expense"] == 1100.0
    assert jan["net"] == 1900.0
    assert jan["savings_rate"] == pytest.approx(1900 / 3000)


def test_monthly_summary_savings_rate_is_nan_without_income() -> None:
    rows = pd.DataFrame([_txn("2025-01-01", "Food", 50.0)])
    rows["month_str"] = rows["date"].dt.strftime("%Y-%m")
    ms = A.monthly_summary(rows)
    assert pd.isna(ms.iloc[0]["savings_rate"])


def test_category_totals_shares_sum_to_100(df: pd.DataFrame) -> None:
    tot = A.category_totals(df)
    assert tot["pct"].sum() == pytest.approx(100.0)
    assert tot.iloc[0]["category"] == "Rent"  # 2700 is the largest expense block
    assert tot["cum_pct"].iloc[-1] == pytest.approx(100.0)


def test_yearly_summary_aggregates_months(df: pd.DataFrame) -> None:
    y = A.yearly_summary(df)
    assert len(y) == 1
    row = y.iloc[0]
    assert row["year"] == 2025
    assert row["months"] == 3
    assert row["income"] == 9000.0
    assert row["expense"] == 4830.0
    assert row["avg_month_spend"] == pytest.approx(4830.0 / 3, abs=0.01)


def test_rolling_spend_windows(df: pd.DataFrame) -> None:
    rs = A.rolling_spend(df, windows=(2,))
    assert "roll_2m" in rs.columns
    # min_periods=1, so the first month's rolling mean is just that month.
    assert rs["roll_2m"].iloc[0] == rs["expense"].iloc[0]


def test_seasonality_averages_by_calendar_month(df: pd.DataFrame) -> None:
    s = A.seasonality(df)
    assert set(s["month_name"]) == {"Jan", "Feb", "Mar"}
    assert len(s) == 3


# --------------------------------------------------------- recurring & outliers
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Groceries (5th - 11th)", "groceries"),
        ("Gym 7th", "gym"),
        ("  Rent (monthly) ", "rent"),
        ("Coffee", "coffee"),
        ("", ""),
    ],
)
def test_normalize_comment_collapses_date_noise(raw: str, expected: str) -> None:
    assert A._normalize_comment(raw) == expected


def test_recurring_costs_finds_items_seen_in_many_months(df: pd.DataFrame) -> None:
    rec = A.recurring_costs(df, min_months=3)
    keys = set(rec["key"])
    assert "rent" in keys  # 3 months
    assert "groceries" in keys  # 3 months, after the date suffixes are stripped
    assert "flights" not in keys  # only one month
    rent = rec[rec["key"] == "rent"].iloc[0]
    assert rent["months"] == 3
    assert rent["total"] == 2700.0


def test_recurring_costs_respects_min_months(df: pd.DataFrame) -> None:
    assert A.recurring_costs(df, min_months=4).empty


def test_outliers_flags_the_unusual_transaction() -> None:
    rows = [_txn("2025-01-01", "Food", 20.0) for _ in range(10)]
    rows.append(_txn("2025-02-01", "Food", 500.0, "Big dinner"))
    frame = pd.DataFrame(rows)
    frame["month_str"] = frame["date"].dt.strftime("%Y-%m")
    out = A.outliers(frame, z=2.0)
    assert list(out["comment"]) == ["Big dinner"]


def test_outliers_handles_a_category_with_zero_variance() -> None:
    """std of 0 would divide by zero; it must produce no outliers, not an error."""
    frame = pd.DataFrame([_txn("2025-01-01", "Food", 20.0) for _ in range(5)])
    frame["month_str"] = frame["date"].dt.strftime("%Y-%m")
    assert A.outliers(frame).empty


def test_top_expenses_is_sorted_and_capped(df: pd.DataFrame) -> None:
    top = A.top_expenses(df, n=2)
    assert len(top) == 2
    assert list(top["amount"]) == [1500.0, 900.0]
    assert "is_income" not in top.columns
