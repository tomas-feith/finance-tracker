# finance-tracker

A Python dashboard that reads a personal-finance Google Sheet **live via the
Google Sheets API**, parses the transaction-level data, and exposes analytics the
spreadsheet doesn't — monthly category breakdowns, rolling trends, seasonality,
recurring-cost detection, outliers, and a data-quality check against the sheet's
own totals.

Built with **pandas**, **Plotly**, and **Streamlit**.

## Try it instantly (demo mode)

No Google account needed — with no credentials configured, the app loads a
synthetic sample dataset so you can explore every feature:

```bash
python -m venv .venv && .venv/Scripts/activate   # or: source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/app.py
```

A banner marks demo mode. Force it anytime with `FINANCE_DEMO=1`. To use your own
data, follow **Setup** below.

## Features

- **Overview** — monthly cashflow (income vs. expense, net), spending by category
  over time, year-by-year summary.
- **Trends** — 3- and 12-month rolling spend, seasonality by calendar month,
  savings-rate history.
- **Categories** — donut + Pareto (80/20) breakdown, per-category drill-down.
- **Recurring & Outliers** — subscriptions/fixed costs detected from transaction
  comments, statistical outliers, top single expenses.
- **Data quality** — cross-checks every parsed category total against the sheet's
  own `TOTAL` cells and flags any month where the sheet's `SUM()` range misses
  entries (a common spreadsheet bug that silently undercounts spending).

## How it works

`src/data.py` parses your sheet into a tidy transaction table, and all analytics
build on that single shape:

| year | month | date | category | amount | comment | is_income | month_str |
|------|-------|------|----------|--------|---------|-----------|-----------|

### Sheet layouts

The layout is configured in `config.py` (see `config.example.py`); everything
about *how your sheet is shaped* lives in `src/schema.py`.

- **`flat`** *(recommended for most people)* — one row per transaction, e.g.
  `Date | Category | Amount | Note`. Columns are matched by header name or index;
  income is detected by category name or by amount sign. Number format (decimal,
  thousands, currency) is configurable, so US (`1,234.56`) and European
  (`1.234,56 €`) sheets both work.

- **`block`** *(the layout this project started with)* — each year in a
  `Full YYYY` tab as vertically stacked monthly blocks of `amount | comment`
  column pairs with per-category `TOTAL` rows. `src/validate.py` cross-checks the
  parse against those totals. A monthly figure kept outside the blocks (rent, in
  the original sheet's `Lifetime` → `MONTHLY TIMELINE`) is injected as a monthly
  expense.

Parsers for both layouts are pure functions over a raw value matrix, unit-tested
in `tests/test_parsers.py` (run `python tests/test_parsers.py`). If neither
layout fits, adapt `src/schema.py`/`src/data.py` — or just use **demo mode**
(`src/sample_data.py`, synthetic data, no sheet at all).

## Setup

### 1. Google Cloud service account (free, no billing required)

1. Create a project at <https://console.cloud.google.com/>.
2. **APIs & Services → Library** → enable the **Google Sheets API**.
3. **Credentials → Create Credentials → Service account** → create it (no roles
   needed).
4. On the service account, **Keys → Add Key → JSON** → download it.
5. Save the JSON as `secrets/service_account.json`.
6. Open your sheet → **Share** → add the service account's `client_email` as a
   **Viewer**.

### 2. Configure the sheet ID

```bash
cp config.example.py config.py
# edit config.py and paste your sheet ID (from the sheet URL)
```

### 3. Install & run

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

streamlit run src/app.py
```

Then open <http://localhost:8501>. Data is cached for 10 minutes; use the
**Refresh data** button in the sidebar to pull the latest.

### 4. (Recommended) enable the pre-commit safeguards

```bash
pip install pre-commit
pre-commit install
```

This runs [gitleaks](https://github.com/gitleaks/gitleaks) and related hooks on
every commit to block secrets, private keys, and accidental large data files
before they can be committed.

## Project layout

```
src/
  app.py            Streamlit dashboard
  analytics.py      metrics (pandas, no UI)
  data.py           layout-aware parser -> tidy transactions
  schema.py         sheet-layout config (block / flat, number format)
  sample_data.py    synthetic dataset for demo mode
  sheets_client.py  Google Sheets API wrapper
  validate.py       parse vs. sheet-total integrity check (block layout)
  inspect_sheet.py  print tab structure (dev helper)
tests/test_parsers.py  unit tests for both layouts
config.example.py   template for sheet ID + layout config
requirements.txt
```

> **Note:** this repo contains **no financial data** — everything is read live
> from your private sheet at runtime. Credentials (`secrets/`) and your sheet ID
> (`config.py`) are git-ignored.

## Security

- **No data or credentials in the repo.** `secrets/` (service-account key) and
  `config.py` (sheet ID) are git-ignored; the app reads everything live at runtime.
- **Pre-commit secret scanning** via gitleaks (see setup step 4) blocks secrets
  before they enter history.
- The service account is **read-only** (`spreadsheets.readonly`, `Viewer`) and
  scoped to a single sheet.

## License

MIT — see [LICENSE](LICENSE).
