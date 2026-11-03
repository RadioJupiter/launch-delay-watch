"""Repo-relative paths for data artifacts."""

from __future__ import annotations

from pathlib import Path

# Package lives at src/launch_delay_watch/ → repo root is parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SLIPS_PATH = DATA_DIR / "slips.csv"
