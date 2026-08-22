"""End-to-end smoke test: run the dashboard headlessly in demo mode.

app.py is top-level Streamlit code, so the only way to exercise it is to run it.
That is worth doing: every import in it moved when `src/` became the
`finance_tracker` package, and a broken import there is invisible to the unit
tests but fatal to the app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "finance_tracker" / "app.py")


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """The dashboard pinned to demo mode, so it never reaches Google Sheets."""
    monkeypatch.setenv("FINANCE_DEMO", "1")
    # get_data is @st.cache_data, and that cache lives in the Streamlit runtime
    # rather than the AppTest session -- so without this a later test reuses an
    # earlier one's DataFrame and never calls the loader it just patched.
    st.cache_data.clear()
    return AppTest.from_file(APP, default_timeout=60)


def test_app_runs_without_exceptions(app: AppTest) -> None:
    app.run()
    assert not app.exception


# --- load-failure boundary -------------------------------------------------
# Everything after the load assumes df_all exists. Without a boundary a revoked
# key or a renamed tab surfaces as a raw traceback partway down the page, which
# says nothing about which of those it was.


def test_a_load_failure_is_explained_rather_than_crashing(
    app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finance_tracker import sample_data

    def boom() -> None:
        raise RuntimeError("the sheet went away")

    # app.py rebinds this name on each AppTest import, so patching the module
    # attribute before run() is what the fresh import picks up.
    monkeypatch.setattr(sample_data, "load_sample_transactions", boom)
    app.run()

    assert not app.exception
    assert any("Could not load your data" in e.value for e in app.error)
    assert any("RuntimeError: the sheet went away" in e.value for e in app.error)


def test_a_broken_config_names_config_py(app: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    """ConfigError gets its own message -- the fix is in a different place."""
    from finance_tracker import sample_data, userconfig

    def boom() -> None:
        raise userconfig.ConfigError("config.py raised SyntaxError: bad")

    monkeypatch.setattr(sample_data, "load_sample_transactions", boom)
    app.run()

    assert not app.exception
    assert any("config.py could not be loaded" in e.value for e in app.error)


def test_an_empty_parse_suggests_the_layout_is_wrong(
    app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean parse yielding nothing is a layout mismatch, not an outage."""
    import pandas as pd

    from finance_tracker import sample_data
    from finance_tracker.data import _COLS

    monkeypatch.setattr(
        sample_data,
        "load_sample_transactions",
        lambda: pd.DataFrame(columns=[*_COLS, "month_str"]),
    )
    app.run()

    assert not app.exception
    assert any("produced no transactions" in w.value for w in app.warning)


def test_demo_banner_is_shown(app: AppTest) -> None:
    app.run()
    assert any("Demo mode" in info.value for info in app.info)


def test_kpi_header_is_populated(app: AppTest) -> None:
    app.run()
    labels = [m.label for m in app.metric]
    assert "Total income" in labels
    assert "Total spend" in labels
    # Every KPI should carry a euro figure, not a placeholder.
    assert all("€" in m.value for m in app.metric)


def test_category_filter_is_derived_from_the_data(app: AppTest) -> None:
    """The sidebar options must be the categories actually present, in order."""
    app.run()
    categories = next(ms for ms in app.multiselect if ms.label == "Expense categories")
    assert categories.options == [
        "Rent",
        "Food",
        "Social Life",
        "House Purchases",
        "Fixed costs",
        "Travels",
        "Others",
    ]
    # All selected by default, so nothing is hidden on first load.
    assert categories.value == categories.options


def test_deselecting_every_category_warns_instead_of_crashing(app: AppTest) -> None:
    app.run()
    categories = next(ms for ms in app.multiselect if ms.label == "Expense categories")
    years = next(ms for ms in app.multiselect if ms.label == "Years")
    categories.set_value([]).run()
    years.set_value([]).run()

    assert not app.exception
    assert any("No data for the current filters" in w.value for w in app.warning)


def test_year_filter_narrows_the_data(app: AppTest) -> None:
    app.run()
    years = next(ms for ms in app.multiselect if ms.label == "Years")
    all_spend = next(m.value for m in app.metric if m.label == "Total spend")

    years.set_value([years.options[0]]).run()
    assert not app.exception
    one_year_spend = next(m.value for m in app.metric if m.label == "Total spend")
    assert one_year_spend != all_spend


# --- data-quality boundary -------------------------------------------------
# The data-quality tab re-reads the sheet live, after the cached load has already
# succeeded, so it fails on its own schedule -- a dropped TLS connection is enough.


def test_a_failed_totals_read_does_not_crash_the_data_quality_tab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sheet_totals() is the one network call after the load boundary."""
    from finance_tracker import data, sheets_client, validate
    from finance_tracker.sample_data import load_sample_transactions

    # Live mode, but with the load itself served from synthetic data: the point is
    # to reach the data-quality tab, which demo mode short-circuits.
    monkeypatch.delenv("FINANCE_DEMO", raising=False)
    monkeypatch.setattr(sheets_client, "has_live_config", lambda: True)
    monkeypatch.setattr(data, "load_transactions", load_sample_transactions)

    def boom() -> dict[tuple[int, int, str], float]:
        raise OSError("[SSL: WRONG_VERSION_NUMBER] wrong version number")

    monkeypatch.setattr(validate, "sheet_totals", boom)
    st.cache_data.clear()

    at = AppTest.from_file(APP, default_timeout=60).run()

    assert not at.exception
    assert any("Could not read the sheet's own totals" in e.value for e in at.error)
    assert any("WRONG_VERSION_NUMBER" in e.value for e in at.error)
    # The rest of the page still rendered -- this is a tab-local failure.
    assert "Total spend" in [m.label for m in at.metric]
