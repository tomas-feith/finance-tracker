"""Synthetic dataset for demo mode.

Produces a DataFrame with the exact schema of data.load_transactions()
(year, month, date, category, amount, comment, is_income, month_str) so the
dashboard runs with no Google Sheets access. Deterministic (seeded) so the demo
looks the same every run. This is fake data — any resemblance to real finances
is coincidental.
"""

from __future__ import annotations

import datetime as dt
import random

import pandas as pd

_START = (2023, 1)
_END = (2025, 6)  # inclusive

# recurring fixed costs -> (label, amount, months between occurrences)
_RECURRING = [
    ("Gym", 29.90, 1),
    ("Netflix", 9.99, 1),
    ("Electricity+Gas", 55.00, 1),
    ("Water", 25.00, 1),
    ("Health insurance", 160.00, 3),
]
_GROCERY_WEEKS = ["1st - 7th", "8th - 14th", "15th - 21st", "22nd - 28th"]
_SOCIAL = ["Dinner", "Cinema", "Drinks", "Board games", "Concert", "Lunch out"]
_HOUSE = [
    "Toilet paper",
    "Detergent",
    "Light bulbs",
    "Sponges",
    "Trash bags",
    "Shampoo",
    "Batteries",
]
_OTHERS = ["Books", "Haircut", "Gift", "Clothes", "Phone case", "Charity"]
_TRAVEL_DEST = ["Lisbon", "Berlin", "Rome", "Amsterdam", "Paris", "Prague"]


def _months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def load_sample_transactions() -> pd.DataFrame:
    rng = random.Random(42)
    recs: list[dict] = []

    def add(y, m, category, amount, comment, is_income=False):
        recs.append(
            {
                "year": y,
                "month": m,
                "date": dt.date(y, m, 1),
                "category": category,
                "amount": round(amount, 2),
                "comment": comment,
                "is_income": is_income,
            }
        )

    for i, (y, m) in enumerate(_months(_START, _END)):
        # --- income ---
        add(y, m, "Income", 3200 + rng.uniform(-50, 250), "Salary", is_income=True)
        add(y, m, "Income", rng.uniform(2, 40), "Interest", is_income=True)
        if m == 4:  # annual tax return in April (a legit "outlier" income)
            add(y, m, "Income", rng.uniform(1500, 3200), "Tax returns", is_income=True)

        # --- rent (fixed, like the real sheet's Lifetime timeline) ---
        add(y, m, "Rent", 1000.0, "Rent (monthly)")

        # --- food: weekly groceries + snacks ---
        for wk in _GROCERY_WEEKS:
            add(y, m, "Food", rng.uniform(35, 95), f"Groceries ({wk})")
        add(y, m, "Food", rng.uniform(8, 30), "Snacks")

        # --- fixed costs: recurring subscriptions ---
        for label, amount, every in _RECURRING:
            if i % every == 0:
                add(y, m, "Fixed costs", amount + rng.uniform(-3, 3), label)

        # --- social life ---
        for _ in range(rng.randint(2, 4)):
            add(y, m, "Social Life", rng.uniform(10, 65), rng.choice(_SOCIAL))

        # --- house purchases ---
        for _ in range(rng.randint(1, 3)):
            add(y, m, "House Purchases", rng.uniform(2, 25), rng.choice(_HOUSE))

        # --- others (occasional big one = outlier) ---
        for _ in range(rng.randint(1, 2)):
            add(y, m, "Others", rng.uniform(10, 60), rng.choice(_OTHERS))
        if rng.random() < 0.15:
            add(y, m, "Others", rng.uniform(300, 500), "Dentist")

        # --- travel: seasonal, occasionally large ---
        if m in (4, 7, 8, 12) and rng.random() < 0.8:
            dest = rng.choice(_TRAVEL_DEST)
            add(y, m, "Travels", rng.uniform(120, 350), f"Flights {dest}")
            add(y, m, "Travels", rng.uniform(200, 900), f"Hotel {dest}")
            add(y, m, "Travels", rng.uniform(40, 200), f"Food {dest}")
        else:
            add(y, m, "Travels", rng.uniform(10, 60), "Local transport")

    df = pd.DataFrame(recs)
    df["date"] = pd.to_datetime(df["date"])
    df["month_str"] = df["date"].dt.strftime("%Y-%m")
    return df.sort_values(["date", "category"]).reset_index(drop=True)


if __name__ == "__main__":
    d = load_sample_transactions()
    print(
        f"{len(d):,} synthetic rows, {d['month_str'].nunique()} months "
        f"({d['date'].min():%Y-%m} -> {d['date'].max():%Y-%m})"
    )
    print(d.groupby("category")["amount"].agg(["count", "sum"]).round(2))
