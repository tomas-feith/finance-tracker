# finance-tracker

[![CI](https://github.com/tomas-feith/finance-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/tomas-feith/finance-tracker/actions/workflows/ci.yml)

A Python dashboard that reads a personal-finance Google Sheet **live via the
Google Sheets API**, parses the transaction-level data, and exposes analytics the
spreadsheet doesn't — monthly category breakdowns, rolling trends, seasonality,
recurring-cost detection, outliers, and a data-quality check against the sheet's
own totals.

Built with **pandas**, **Plotly**, and **Streamlit**.

## Try it instantly (demo mode)

No Google account needed — with no credentials configured, the app loads a
synthetic sample dataset so you can explore every feature. Install
[uv](https://docs.astral.sh/uv/) (`pip install uv`), then:

```bash
uv run streamlit run finance_tracker/app.py
```

`uv` creates the environment from the lockfile on first run. A banner marks demo
mode; force it anytime with `FINANCE_DEMO=1`. To use your own data, follow
**Setup** below.

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

`finance_tracker/data.py` parses your sheet into a tidy transaction table, and all analytics
build on that single shape:

| year | month | date | category | amount | comment | is_income | month_str |
|------|-------|------|----------|--------|---------|-----------|-----------|

### Sheet layouts

The layout is configured in `config.py` (see `config.example.py`); everything
about *how your sheet is shaped* lives in `finance_tracker/schema.py`.

- **`flat`** *(recommended for most people)* — one row per transaction, e.g.
  `Date | Category | Amount | Note`. Columns are matched by header name or index;
  income is detected by category name or by amount sign. Number format (decimal,
  thousands, currency) is configurable, so US (`1,234.56`) and European
  (`1.234,56 €`) sheets both work.

- **`block`** *(the layout this project started with)* — each year in a
  `Full YYYY` tab as vertically stacked monthly blocks of `amount | comment`
  column pairs with per-category `TOTAL` rows. `finance_tracker/validate.py` cross-checks the
  parse against those totals. A monthly figure kept outside the blocks (rent, in
  the original sheet's `Lifetime` → `MONTHLY TIMELINE`) is injected as a monthly
  expense.

Parsers for both layouts are pure functions over a raw value matrix, unit-tested
in `tests/test_parsers.py`. If neither
layout fits, adapt `finance_tracker/schema.py` / `finance_tracker/data.py` — or just use **demo mode**
(`finance_tracker/sample_data.py`, synthetic data, no sheet at all).

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

Uses [uv](https://docs.astral.sh/uv/) (`pip install uv` if you don't have it):

```bash
uv sync                         # create the env from pyproject + uv.lock
uv run streamlit run finance_tracker/app.py
```

Then open <http://localhost:8501>. Data is cached for 10 minutes; use the
**Refresh data** button in the sidebar to pull the latest. (No uv? `pip install
-e .` then `streamlit run finance_tracker/app.py` also works.)

If 8501 is already taken by another local dashboard, use `run_dashboard.bat`
(Windows) or `./run_dashboard.sh`, which pick the next free port and print the
URL they settled on.

### 4. (Recommended) enable the pre-commit hooks

```bash
uv run pre-commit install
```

Runs [gitleaks](https://github.com/gitleaks/gitleaks) (blocks secrets/keys/large
data files) plus **ruff** and **mypy** on every commit — the same checks CI runs.

## Project layout

`finance_tracker` is an installed package (`uv sync` puts it on the path), so
every module, test and CLI helper imports it the same way — `from
finance_tracker.data import load_transactions`.

```
finance_tracker/
  __init__.py       module map
  app.py            Streamlit dashboard
  analytics.py      metrics (pandas, no UI)
  data.py           layout-aware parser -> tidy transactions
  schema.py         sheet-layout config (block / flat, number format)
  userconfig.py     loads the gitignored config.py from the project root
  sample_data.py    synthetic dataset for demo mode
  sheets_client.py  Google Sheets API wrapper
  validate.py       parse vs. sheet-total integrity check (block layout)
  inspect_sheet.py  print tab structure (dev helper)
  freeport.py       picks a free port when 8501 is taken
tests/
  test_parsers.py     both sheet layouts
  test_analytics.py   the metrics layer
  test_sample_data.py demo data + the shared schema contract
  test_userconfig.py  config.py loading and its failure modes
  test_freeport.py    port selection (the Windows bind case)
config.example.py   template for sheet ID + layout config
pyproject.toml      deps + ruff / mypy / pytest config (uv.lock pins versions)
.github/workflows/  CI: ruff + mypy + pytest + gitleaks
```

### Command-line helpers

```bash
uv run python -m finance_tracker.inspect_sheet   # print each tab's structure
uv run python -m finance_tracker.validate        # parse vs. the sheet's own TOTALs
uv run python -m finance_tracker.freeport        # print the next free port
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

## Development

```bash
uv sync                       # install runtime + dev tools (ruff, mypy, pytest)
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
uv run mypy                   # type-check
uv run pytest                 # tests, with the coverage floor
```

CI (`.github/workflows/ci.yml`) runs all of these on every push and pull request,
on both Ubuntu and Windows, plus a gitleaks scan over full history. The
pre-commit hooks run the same commands locally through `uv run --no-sync`, so
they use the versions pinned in `uv.lock` rather than a separately-pinned mirror
that can drift out of agreement with CI.

For a targeted run that would otherwise trip the coverage floor:

```bash
uv run pytest -k analytics --no-cov
```

## License

MIT — see [LICENSE](LICENSE).
