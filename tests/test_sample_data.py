"""Demo-mode data, and the schema contract every analytic depends on.

`data.load_transactions()` and `sample_data.load_sample_transactions()` must
produce the identical shape, because the dashboard swaps one for the other
depending on whether credentials are configured. That shared shape is the thing
worth pinning: change it and everything downstream moves.
"""

from __future__ import annotations

import pandas as pd

from finance_tracker import analytics as A
from finance_tracker.data import _to_df
from finance_tracker.sample_data import load_sample_transactions

EXPECTED_COLUMNS = [
    "year",
    "month",
    "date",
    "category",
    "amount",
    "comment",
    "is_income",
    "month_str",
]


def test_sample_data_matches_the_documented_schema() -> None:
    df = load_sample_transactions()
    assert list(df.columns) == EXPECTED_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert pd.api.types.is_bool_dtype(df["is_income"])
    assert pd.api.types.is_numeric_dtype(df["amount"])


def test_parser_output_has_the_same_columns_as_the_sample() -> None:
    """The real path and the demo path must agree, or the app breaks on switch."""
    parsed = _to_df(
        [
            {
                "year": 2025,
                "month": 1,
                "date": pd.Timestamp(2025, 1, 1).date(),
                "category": "Food",
                "amount": 10.0,
                "comment": "Lunch",
                "is_income": False,
            }
        ]
    )
    assert list(parsed.columns) == EXPECTED_COLUMNS


def test_empty_parse_still_has_the_schema() -> None:
    """An empty sheet must not collapse to a zero-column frame."""
    assert list(_to_df([]).columns) == EXPECTED_COLUMNS


def test_sample_data_is_deterministic() -> None:
    """Seeded, so the demo looks the same on every run."""
    first, second = load_sample_transactions(), load_sample_transactions()
    pd.testing.assert_frame_equal(first, second)


def test_sample_data_is_sorted_by_date() -> None:
    df = load_sample_transactions()
    assert df["date"].is_monotonic_increasing


def test_sample_data_has_both_income_and_expenses() -> None:
    df = load_sample_transactions()
    assert df["is_income"].any()
    assert (~df["is_income"]).any()


def test_analytics_run_end_to_end_on_the_sample() -> None:
    """Smoke test: every analytic must survive the full demo dataset."""
    df = load_sample_transactions()
    assert not A.monthly_summary(df).empty
    assert not A.category_totals(df).empty
    assert not A.yearly_summary(df).empty
    assert not A.rolling_spend(df).empty
    assert len(A.seasonality(df)) == 12
    assert not A.recurring_costs(df).empty
    assert not A.top_expenses(df).empty
    # Outliers may legitimately be empty, but the call must not raise.
    A.outliers(df)


def test_expense_categories_of_the_sample_are_the_known_ones() -> None:
    df = load_sample_transactions()
    assert A.expense_categories(df) == [
        "Rent",
        "Food",
        "Social Life",
        "House Purchases",
        "Fixed costs",
        "Travels",
        "Others",
    ]
