"""Analytics layer: turns the tidy transaction table into the metrics the
dashboard shows. Pure pandas, no Streamlit here so it stays testable."""
from __future__ import annotations

import re

import pandas as pd

EXPENSE_CATEGORIES = [
    "Rent", "Food", "Social Life", "House Purchases", "Fixed costs", "Travels", "Others",
]

# Fixed color per entity (dataviz: assign categorical hues in fixed order, never cycled)
CATEGORY_COLORS = {
    "Rent": "#e34948",             # red (largest expense)
    "Food": "#2a78d6",             # blue
    "Social Life": "#1baf7a",      # aqua
    "House Purchases": "#eda100",  # yellow
    "Fixed costs": "#4a3aa7",      # violet
    "Travels": "#eb6834",          # orange
    "Others": "#e87ba4",           # magenta
    "Income": "#008300",           # green
}
POS_COLOR = "#0ca30c"   # good / surplus
NEG_COLOR = "#d03b3b"   # critical / deficit


def expenses(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["is_income"]]


def income(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["is_income"]]


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-month income, expense, net, savings rate."""
    exp = expenses(df).groupby("date")["amount"].sum().rename("expense")
    inc = income(df).groupby("date")["amount"].sum().rename("income")
    out = pd.concat([inc, exp], axis=1).fillna(0.0).sort_index()
    out["net"] = out["income"] - out["expense"]
    out["savings_rate"] = out["net"] / out["income"].where(out["income"] != 0)
    out = out.reset_index()
    out["month_str"] = out["date"].dt.strftime("%Y-%m")
    return out


def category_month_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """date x category expense matrix (long form)."""
    e = expenses(df)
    m = e.groupby(["date", "category"])["amount"].sum().reset_index()
    return m


def category_totals(df: pd.DataFrame) -> pd.DataFrame:
    e = expenses(df)
    tot = e.groupby("category")["amount"].sum().sort_values(ascending=False)
    out = tot.reset_index()
    out["pct"] = out["amount"] / out["amount"].sum() * 100
    out["cum_pct"] = out["pct"].cumsum()
    return out


def rolling_spend(df: pd.DataFrame, windows=(3, 12)) -> pd.DataFrame:
    ms = monthly_summary(df)[["date", "expense"]].set_index("date").sort_index()
    for w in windows:
        ms[f"roll_{w}m"] = ms["expense"].rolling(w, min_periods=1).mean()
    return ms.reset_index()


def seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """Average monthly spend by calendar month (across years)."""
    ms = monthly_summary(df)
    ms["cal_month"] = ms["date"].dt.month
    s = ms.groupby("cal_month")["expense"].mean().reset_index()
    names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    s["month_name"] = s["cal_month"].map(lambda m: names[m - 1])
    return s


def _normalize_comment(text: str) -> str:
    """Strip trailing date ordinals / week ranges so 'Gym', 'Groceries (5th-11th)'
    collapse to a stable recurring key."""
    t = (text or "").strip().lower()
    t = re.sub(r"\(.*?\)", "", t)                          # remove (5th - 11th)
    t = re.sub(r"\b\d+(st|nd|rd|th)\b", "", t)             # remove 7th, 24th
    t = re.sub(r"\b\d{1,4}\b", "", t)                       # stray numbers
    t = re.sub(r"\s+", " ", t).strip(" -")
    return t


def recurring_costs(df: pd.DataFrame, min_months: int = 4) -> pd.DataFrame:
    """Detect recurring line items: same normalized comment appearing in many
    distinct months. Returns key, months seen, avg amount, total, category."""
    e = expenses(df).copy()
    e["key"] = e["comment"].map(_normalize_comment)
    e = e[e["key"] != ""]
    g = e.groupby("key").agg(
        category=("category", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
        months=("month_str", "nunique"),
        occurrences=("amount", "size"),
        avg_amount=("amount", "mean"),
        total=("amount", "sum"),
        last_seen=("date", "max"),
    ).reset_index()
    g = g[g["months"] >= min_months].sort_values("total", ascending=False)
    num = g.select_dtypes("number").columns
    g[num] = g[num].round(2)
    return g


def outliers(df: pd.DataFrame, z: float = 2.5) -> pd.DataFrame:
    """Per-category outlier transactions (amount well above the category mean)."""
    e = expenses(df).copy()
    stats = e.groupby("category")["amount"].agg(["mean", "std"])
    e = e.join(stats, on="category")
    e["z"] = (e["amount"] - e["mean"]) / e["std"].replace(0, pd.NA)
    out = e[e["z"] >= z].sort_values("amount", ascending=False)
    out = out[["date", "category", "amount", "comment", "z"]].copy()
    out[["amount", "z"]] = out[["amount", "z"]].round(2)
    return out


def top_expenses(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    e = expenses(df).sort_values("amount", ascending=False).head(n)
    return e[["date", "category", "amount", "comment"]]


def yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    ms = monthly_summary(df)
    ms["year"] = ms["date"].dt.year
    y = ms.groupby("year").agg(
        income=("income", "sum"),
        expense=("expense", "sum"),
        months=("date", "nunique"),
    ).reset_index()
    y["net"] = y["income"] - y["expense"]
    y["savings_rate"] = y["net"] / y["income"].where(y["income"] != 0)
    y["avg_month_spend"] = y["expense"] / y["months"]
    return y.round(2)
