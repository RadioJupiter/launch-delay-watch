from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def snapshot_a(fixtures_dir: Path) -> Path:
    return fixtures_dir / "snapshot_a.csv"


@pytest.fixture
def snapshot_b(fixtures_dir: Path) -> Path:
    return fixtures_dir / "snapshot_b.csv"


@pytest.fixture
def upcoming_payload(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "upcoming_sample.json").read_text())
