"""Import site/build.py as a module without packaging it."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BUILD = _REPO / "site" / "build.py"


def import_build_module():
    spec = importlib.util.spec_from_file_location("ldw_site_build", _BUILD)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
