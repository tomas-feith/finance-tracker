"""End-to-end smoke test: run the dashboard headlessly in demo mode.

app.py is top-level Streamlit code, so the only way to exercise it is to run it.
That is worth doing: every import in it moved when `src/` became the
`finance_tracker` package, and a broken import there is invisible to the unit
tests but fatal to the app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "finance_tracker" / "app.py")


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """The dashboard pinned to demo mode, so it never reaches Google Sheets."""
    monkeypatch.setenv("FINANCE_DEMO", "1")
    return AppTest.from_file(APP, default_timeout=60)


def test_app_runs_without_exceptions(app: AppTest) -> None:
    app.run()
    assert not app.exception


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
