"""Load the user's ``config.py`` from the project root.

``config.py`` is gitignored and lives beside ``pyproject.toml``, not inside this
package, so a plain ``import config`` only works when the project root happens
to be on ``sys.path``. That used to be arranged by ``sys.path.insert`` calls at
the top of five modules -- which broke as soon as anything was launched from a
different directory, because ``streamlit run`` puts the *script's* directory on
the path, not the project root.

Importing it by file path instead makes the location explicit and independent
of the working directory or how the process was started.
"""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.py"


class ConfigError(Exception):
    """config.py exists but could not be imported."""


@cache
def load() -> ModuleType | None:
    """Return the user's config module, or ``None`` if they have not made one.

    A missing ``config.py`` is normal -- the app falls back to demo mode. A
    *broken* one is not, and raises: the previous behaviour swallowed every
    exception, so a typo in the sheet layout silently reverted to the defaults
    and showed plausible-looking wrong numbers with nothing to explain them.
    """
    if not CONFIG_PATH.exists():
        return None

    spec = importlib.util.spec_from_file_location("finance_tracker._user_config", CONFIG_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ConfigError(f"Could not load {CONFIG_PATH}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ConfigError(f"{CONFIG_PATH} raised {type(exc).__name__}: {exc}") from exc
    return module


def get(name: str, default: object = None) -> object:
    """Read a single setting from config.py, falling back to ``default``."""
    module = load()
    return default if module is None else getattr(module, name, default)
