from __future__ import annotations

from pathlib import Path

import pandas as pd

from launch_delay_watch.diff import compare_snapshots, update_slips_history


def test_compare_snapshots_slip_days(snapshot_a: Path, snapshot_b: Path) -> None:
    delta = compare_snapshots(snapshot_a, snapshot_b)
    assert len(delta) == 3  # launch-004 and launch-005 are unmatched
    by_id = delta.set_index("id")["slip_days"].to_dict()
    assert by_id["launch-001"] == 2.0
    assert by_id["launch-002"] == -1.0
    assert by_id["launch-003"] == 7.0
    # Sorted by slip descending → launch-003 first
    assert delta.iloc[0]["id"] == "launch-003"


def test_update_slips_history_idempotent(
    snapshot_a: Path, snapshot_b: Path, tmp_path: Path
) -> None:
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir()
    (snap_dir / "2026-11-01.csv").write_text(snapshot_a.read_text())
    (snap_dir / "2026-11-03.csv").write_text(snapshot_b.read_text())
    slips = tmp_path / "slips.csv"

    d1 = update_slips_history(
        snap_dir / "2026-11-01.csv",
        snap_dir / "2026-11-03.csv",
        slips_path=slips,
        snapshot_dir=snap_dir,
    )
    assert len(d1) == 3
    hist1 = pd.read_csv(slips)
    assert len(hist1) == 3

    d2 = update_slips_history(
        snap_dir / "2026-11-01.csv",
        snap_dir / "2026-11-03.csv",
        slips_path=slips,
        snapshot_dir=snap_dir,
    )
    assert len(d2) == 3
    hist2 = pd.read_csv(slips)
    assert len(hist2) == 3  # no duplicate rows on re-run
