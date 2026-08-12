"""Personal finance dashboard — reads the live Google Sheet, parses the
transaction-level 'Full YYYY' tabs, and exposes analytics the sheet doesn't.

Run:  uv run streamlit run finance_tracker/app.py
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import analytics as A
from finance_tracker.data import load_transactions
from finance_tracker.sample_data import load_sample_transactions
from finance_tracker.sheets_client import has_live_config
from finance_tracker.userconfig import ConfigError

st.set_page_config(page_title="Finances", page_icon="\U0001f4b0", layout="wide")


def EUR(v: float) -> str:
    return f"€{v:,.0f}"


PLOT_TMPL = "plotly_white"

# Demo mode: forced via FINANCE_DEMO=1, or auto when no live sheet is configured.
DEMO = os.getenv("FINANCE_DEMO") == "1" or not has_live_config()


@st.cache_data(ttl=600, show_spinner="Loading data…")
def get_data(demo: bool) -> pd.DataFrame:
    return load_sample_transactions() if demo else load_transactions()


cat_order = A.order_categories

# ------------------------------------------------------------------ load + filter
# Everything below assumes df_all exists, so a load failure has to stop here with
# an explanation. The live path reaches the network and reads a gitignored
# config.py, so the realistic failures are a revoked service-account key, a
# renamed sheet tab, and a typo in config.py -- none of which the reader can
# diagnose from a raw traceback halfway down the page.
try:
    df_all = get_data(DEMO)
except ConfigError as exc:
    st.error(f"**config.py could not be loaded.**\n\n{exc}")
    st.info("Fix `config.py`, or unset it entirely to fall back to demo mode.")
    st.stop()
except Exception as exc:
    st.error(f"**Could not load your data.**\n\n`{type(exc).__name__}: {exc}`")
    st.info(
        "If this is the live sheet: check that `secrets/service_account.json` is "
        "present and still authorised, that the sheet is shared with the service "
        "account, and that the tab names in `config.py` still match. "
        "Set `FINANCE_DEMO=1` to explore with synthetic data instead."
    )
    st.stop()

if df_all.empty:
    st.warning("The sheet parsed cleanly but produced no transactions.")
    st.info(
        "Usually a layout mismatch: check `LAYOUT` and the column names in "
        "`config.py` against your sheet. `uv run python -m finance_tracker.inspect_sheet` "
        "prints each tab's structure."
    )
    st.stop()

years = sorted(df_all["year"].unique())

st.sidebar.title("\U0001f4b0 Finances")
st.sidebar.caption(
    "⚠️ Demo mode — synthetic data"
    if DEMO
    else "Live from Google Sheets · refresh clears the 10-min cache"
)
if st.sidebar.button("\U0001f504 Refresh data"):
    st.cache_data.clear()
    st.rerun()

yr_sel = st.sidebar.multiselect("Years", years, default=years)
# Taken from the loaded data, not from a fixed list: a "flat" layout carries the
# user's own category names, and filtering against the block sheet's names would
# match none of them.
cats_all = A.expense_categories(df_all)
cat_sel = st.sidebar.multiselect("Expense categories", cats_all, default=cats_all)

mask = df_all["year"].isin(yr_sel) & (df_all["is_income"] | df_all["category"].isin(cat_sel))
df = df_all[mask].copy()
exp_df = df[df["category"].isin(cat_sel) & ~df["is_income"]]

if df.empty:
    st.warning("No data for the current filters.")
    st.stop()

# ------------------------------------------------------------------ KPI header
ms = A.monthly_summary(pd.concat([exp_df, A.income(df)]))
total_inc = A.income(df)["amount"].sum()
total_exp = exp_df["amount"].sum()
net = total_inc - total_exp
sav = net / total_inc if total_inc else 0
n_months = df["month_str"].nunique()

st.title("Personal Finance Dashboard")
if DEMO:
    st.info(
        "**Demo mode** — synthetic sample data. To use your own finances, add a "
        "service-account key to `secrets/` and a `config.py` with your sheet ID "
        "(see the README).",
        icon="🧪",
    )
last_full = ms.iloc[-2] if len(ms) >= 2 else ms.iloc[-1]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total income", EUR(total_inc))
c2.metric("Total spend", EUR(total_exp))
c3.metric("Net", EUR(net), delta=f"{sav * 100:.0f}% savings rate")
c4.metric("Avg spend / month", EUR(total_exp / n_months))
c5.metric(
    f"Last full month ({last_full['month_str']})",
    EUR(last_full["expense"]),
    delta=EUR(last_full["expense"] - total_exp / n_months) + " vs avg",
    delta_color="inverse",
)

tab_over, tab_trend, tab_cat, tab_recur, tab_dq = st.tabs(
    ["Overview", "Trends", "Categories", "Recurring & Outliers", "Data quality"]
)

# ------------------------------------------------------------------ OVERVIEW
with tab_over:
    st.subheader("Monthly cashflow")
    fig = go.Figure()
    fig.add_bar(x=ms["date"], y=ms["income"], name="Income", marker_color=A.POS_COLOR)
    fig.add_bar(x=ms["date"], y=-ms["expense"], name="Expense", marker_color=A.NEG_COLOR)
    fig.add_scatter(
        x=ms["date"], y=ms["net"], name="Net", mode="lines", line=dict(color="#0b0b0b", width=2)
    )
    fig.update_layout(
        barmode="relative",
        template=PLOT_TMPL,
        height=420,
        legend=dict(orientation="h", y=1.1),
        yaxis_title="€",
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Spending by category over time")
    st.caption("The view your sheet doesn't have: every category, every month.")
    cm = A.category_month_matrix(exp_df)
    fig2 = px.area(
        cm,
        x="date",
        y="amount",
        color="category",
        category_orders={"category": cat_order(cat_sel)},
        color_discrete_map=A.CATEGORY_COLORS,
        template=PLOT_TMPL,
    )
    fig2.update_layout(height=420, yaxis_title="€", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, width="stretch")

    st.subheader("Year by year")
    ysum = A.yearly_summary(pd.concat([exp_df, A.income(df)]))
    show = ysum.copy()
    for c in ["income", "expense", "net", "avg_month_spend"]:
        show[c] = show[c].map(EUR)
    show["savings_rate"] = (ysum["savings_rate"] * 100).map(lambda v: f"{v:.0f}%")
    st.dataframe(show, width="stretch", hide_index=True)

# ------------------------------------------------------------------ TRENDS
with tab_trend:
    st.subheader("Spending trend & rolling averages")
    rs = A.rolling_spend(exp_df)
    fig = go.Figure()
    fig.add_bar(x=rs["date"], y=rs["expense"], name="Monthly spend", marker_color="#9ec5f4")
    fig.add_scatter(
        x=rs["date"], y=rs["roll_3m"], name="3-mo avg", line=dict(color="#2a78d6", width=2)
    )
    fig.add_scatter(
        x=rs["date"], y=rs["roll_12m"], name="12-mo avg", line=dict(color="#eb6834", width=2)
    )
    fig.update_layout(
        template=PLOT_TMPL, height=430, yaxis_title="€", legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig, width="stretch")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Seasonality")
        st.caption("Average spend by calendar month, across all selected years.")
        seas = A.seasonality(exp_df)
        fig = px.bar(
            seas,
            x="month_name",
            y="expense",
            template=PLOT_TMPL,
            color_discrete_sequence=["#2a78d6"],
        )
        fig.update_layout(height=360, yaxis_title="€ avg", xaxis_title="")
        st.plotly_chart(fig, width="stretch")
    with col_b:
        st.subheader("Savings rate over time")
        st.caption(
            "Clipped to ±100% — early low-income months produce extreme "
            "ratios; hover shows the true value."
        )
        sr = ms["savings_rate"] * 100
        sr_clip = sr.clip(lower=-100, upper=100)
        colors = [A.POS_COLOR if v >= 0 else A.NEG_COLOR for v in sr.fillna(0)]
        fig = go.Figure()
        fig.add_bar(
            x=ms["date"],
            y=sr_clip,
            marker_color=colors,
            customdata=sr.round(0),
            hovertemplate="%{x|%Y-%m}: %{customdata:.0f}% saved<extra></extra>",
        )
        fig.update_layout(
            template=PLOT_TMPL, height=360, yaxis=dict(title="% of income saved", range=[-110, 110])
        )
        st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ CATEGORIES
with tab_cat:
    st.subheader("Where the money goes")
    ct = A.category_totals(exp_df)
    col_a, col_b = st.columns([1, 1])
    with col_a:
        fig = px.pie(
            ct,
            names="category",
            values="amount",
            hole=0.5,
            color="category",
            color_discrete_map=A.CATEGORY_COLORS,
            category_orders={"category": cat_order(cat_sel)},
        )
        fig.update_traces(textposition="outside", textinfo="label+percent")
        fig.update_layout(template=PLOT_TMPL, height=430, showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with col_b:
        st.caption("Pareto — cumulative share of spend")
        fig = go.Figure()
        fig.add_bar(x=ct["category"], y=ct["amount"], marker_color="#2a78d6", name="Spend")
        fig.add_scatter(
            x=ct["category"],
            y=ct["cum_pct"],
            yaxis="y2",
            mode="lines+markers",
            name="Cumulative %",
            line=dict(color="#eb6834", width=2),
        )
        fig.update_layout(
            template=PLOT_TMPL,
            height=430,
            yaxis=dict(title="€"),
            yaxis2=dict(title="cum %", overlaying="y", side="right", range=[0, 100]),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig, width="stretch")

    st.subheader("Category detail")
    pick = st.selectbox("Category", cat_order(cat_sel))
    sub = exp_df[exp_df["category"] == pick]
    st.caption(
        f"{len(sub)} transactions · total {EUR(sub['amount'].sum())} "
        f"· avg {EUR(sub['amount'].mean())}"
    )
    monthly = sub.groupby("date")["amount"].sum().reset_index()
    fig = px.bar(
        monthly,
        x="date",
        y="amount",
        template=PLOT_TMPL,
        color_discrete_sequence=[A.CATEGORY_COLORS[pick]],
    )
    fig.update_layout(height=300, yaxis_title="€")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        sub[["date", "amount", "comment"]]
        .sort_values("amount", ascending=False)
        .head(30)
        .assign(date=lambda d: d["date"].dt.strftime("%Y-%m")),
        width="stretch",
        hide_index=True,
    )

# ------------------------------------------------------------------ RECURRING & OUTLIERS
with tab_recur:
    st.subheader("Recurring costs")
    st.caption(
        "Line items whose description repeats across ≥4 months — "
        "your subscriptions & fixed commitments, detected from comments."
    )
    rec = A.recurring_costs(exp_df, min_months=4)
    rec_show = rec.assign(
        avg_amount=rec["avg_amount"].map(EUR),
        total=rec["total"].map(EUR),
        last_seen=rec["last_seen"].dt.strftime("%Y-%m"),
    )
    st.dataframe(
        rec_show,
        width="stretch",
        hide_index=True,
        column_config={"key": "item", "months": "months seen"},
    )

    st.subheader("Outlier transactions")
    st.caption("Individual expenses far above their category's norm (z ≥ 2.5).")
    out = A.outliers(exp_df).assign(date=lambda d: d["date"].dt.strftime("%Y-%m"))
    st.dataframe(out, width="stretch", hide_index=True)

    st.subheader("Top 25 single expenses")
    top = A.top_expenses(exp_df).assign(
        date=lambda d: d["date"].dt.strftime("%Y-%m"), amount=lambda d: d["amount"].map(EUR)
    )
    st.dataframe(top, width="stretch", hide_index=True)

# ------------------------------------------------------------------ DATA QUALITY
with tab_dq:
    st.subheader("Sheet vs. parsed totals")
    if DEMO:
        st.info(
            "Data-quality checks compare parsed totals against the live sheet's "
            "own `TOTAL` cells — not applicable to synthetic demo data.",
            icon="🧪",
        )
        st.stop()
    st.markdown(
        "During parsing we compare each parsed category total against your sheet's "
        "own `TOTAL` row. Where they differ, your sheet's `SUM()` range doesn't "
        "reach a late entry — so the sheet **undercounts** those months. "
        "The figures in this dashboard use the corrected (parsed) totals."
    )
    # Imported lazily: sheet_totals() hits the Google Sheets API, so it must not
    # run on the demo path above.
    from finance_tracker.validate import sheet_totals

    parsed = df_all.groupby(["year", "month", "category"])["amount"].sum().round(2).to_dict()
    rows = []
    for key, sv in sheet_totals().items():
        mine = round(parsed.get(key, 0.0), 2)
        if abs(mine - sv) > 0.01:
            rows.append(
                {
                    "year": key[0],
                    "month": key[1],
                    "category": key[2],
                    "sheet TOTAL": sv,
                    "true (parsed)": mine,
                    "undercount": round(mine - sv, 2),
                }
            )
    if rows:
        dq = pd.DataFrame(rows).sort_values("undercount", ascending=False)
        st.metric("Total hidden spend (sheet undercount)", EUR(dq["undercount"].sum()))
        st.dataframe(dq, width="stretch", hide_index=True)
    else:
        st.success("No discrepancies — every parsed total matches the sheet.")
