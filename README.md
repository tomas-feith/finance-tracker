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

The source spreadsheet stores each year in a `Full YYYY` tab as vertically
stacked monthly blocks, with seven `amount | comment` column pairs (Food, Social
Life, House Purchases, Fixed costs, Travels, Others, Income). `src/data.py`
reverse-engineers that layout into a tidy transaction table:

| year | month | date | category | amount | comment | is_income |
|------|-------|------|----------|--------|---------|-----------|

European number formats (comma decimal, non-breaking-space thousands, `€`) are
handled during parsing. `src/validate.py` verifies the parse against the sheet's
own totals.

Rent is not in the `Full` tabs — it's read separately from the `Lifetime` tab's
`MONTHLY TIMELINE` and injected as a monthly expense.

> **The parser is specific to this sheet layout.** If your spreadsheet has a
> different shape, either adapt `src/data.py` or just use **demo mode**, which
> loads `src/sample_data.py` (same schema, synthetic data) with no sheet at all.

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
  data.py           parser: Full YYYY tabs -> tidy transactions
  sample_data.py    synthetic dataset for demo mode
  sheets_client.py  Google Sheets API wrapper
  validate.py       parse vs. sheet-total integrity check
  inspect_sheet.py  print tab structure (dev helper)
config.example.py   template for your sheet ID
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
