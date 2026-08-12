"""Tests for loading the user's gitignored config.py.

The behaviour that matters here is the failure mode. The previous implementation
wrapped `import config` in `except Exception: pass`, so a broken config silently
reverted to the built-in defaults and the dashboard showed confident, wrong
numbers with nothing to explain them. A missing config is fine; a broken one
must be loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finance_tracker import schema, userconfig


@pytest.fixture(autouse=True)
def _clear_caches():
    """load() and resolve() are cached, so each test needs a clean slate."""
    userconfig.load.cache_clear()
    schema.resolve.cache_clear()
    yield
    userconfig.load.cache_clear()
    schema.resolve.cache_clear()


def _point_at(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(userconfig, "CONFIG_PATH", path)


def test_missing_config_is_not_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _point_at(monkeypatch, tmp_path / "config.py")
    assert userconfig.load() is None
    assert userconfig.get("SHEET_ID") is None
    assert userconfig.get("SHEET_ID", "fallback") == "fallback"


def test_values_are_read_from_the_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config.py"
    cfg.write_text("SHEET_ID = 'abc123'\nLAYOUT = 'flat'\n", encoding="utf-8")
    _point_at(monkeypatch, cfg)

    assert userconfig.get("SHEET_ID") == "abc123"
    assert schema.resolve().layout == "flat"


def test_a_broken_config_raises_instead_of_silently_defaulting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.py"
    cfg.write_text("SHEET_ID = 'abc'\nthis is not valid python\n", encoding="utf-8")
    _point_at(monkeypatch, cfg)

    with pytest.raises(userconfig.ConfigError) as exc:
        userconfig.load()
    assert "SyntaxError" in str(exc.value)


def test_a_config_that_raises_at_import_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.py"
    cfg.write_text("raise ValueError('bad sheet id')\n", encoding="utf-8")
    _point_at(monkeypatch, cfg)

    with pytest.raises(userconfig.ConfigError) as exc:
        userconfig.load()
    assert "bad sheet id" in str(exc.value)


def test_config_can_import_the_package_schema_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """config.example.py tells users to import FlatLayout; make sure that works."""
    cfg = tmp_path / "config.py"
    cfg.write_text(
        "from finance_tracker.schema import FlatLayout, NumberFormat\n"
        "LAYOUT = 'flat'\n"
        "NUMBER_FORMAT = NumberFormat(decimal='.', thousands=',', currency='$')\n"
        "FLAT = FlatLayout(tabs=('Transactions',), date_col='Date')\n",
        encoding="utf-8",
    )
    _point_at(monkeypatch, cfg)

    resolved = schema.resolve()
    assert resolved.layout == "flat"
    assert resolved.number.currency == "$"
    assert resolved.flat.tabs == ("Transactions",)
    assert resolved.flat.date_col == "Date"


def test_resolve_falls_back_to_block_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _point_at(monkeypatch, tmp_path / "config.py")
    resolved = schema.resolve()
    assert resolved.layout == "block"
    assert resolved.number.decimal == ","
    assert resolved.block.income_category == "Income"
