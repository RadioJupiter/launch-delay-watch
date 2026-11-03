from __future__ import annotations

from pathlib import Path

import pandas as pd

from launch_delay_watch.diff import compare_snapshots, update_slips_history
from launch_delay_watch.stats import chart_slips, summarize_slips


def _seed_slips(snapshot_a: Path, snapshot_b: Path, tmp_path: Path) -> Path:
    slips = tmp_path / "slips.csv"
    update_slips_history(snapshot_a, snapshot_b, slips_path=slips)
    return slips


def test_summarize_by_provider(snapshot_a: Path, snapshot_b: Path, tmp_path: Path) -> None:
    slips = _seed_slips(snapshot_a, snapshot_b, tmp_path)
    df = pd.read_csv(slips)
    summary = summarize_slips(df, by="provider")
    assert "provider" in summary.columns
    assert set(summary["provider"]) >= {"SpaceX", "Rocket Lab", "United Launch Alliance"}
    ula = summary.set_index("provider").loc["United Launch Alliance"]
    assert ula["mean_slip_days"] == 7.0
    spacex = summary.set_index("provider").loc["SpaceX"]
    assert spacex["mean_slip_days"] == 2.0


def test_chart_writes_png(snapshot_a: Path, snapshot_b: Path, tmp_path: Path) -> None:
    slips = _seed_slips(snapshot_a, snapshot_b, tmp_path)
    df = pd.read_csv(slips)
    out = tmp_path / "chart.png"
    path = chart_slips(df, by="rocket", out_path=out, top_n=5)
    assert path == out
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_compare_used_by_stats(snapshot_a: Path, snapshot_b: Path) -> None:
    # Smoke: compare returns expected columns used downstream
    delta = compare_snapshots(snapshot_a, snapshot_b)
    for col in ("provider", "rocket", "pad", "slip_days"):
        assert col in delta.columns
