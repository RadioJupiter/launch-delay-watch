from __future__ import annotations

from pathlib import Path

from launch_delay_watch.cli import main


def test_cli_diff(snapshot_a: Path, snapshot_b: Path, capsys) -> None:
    code = main(["diff", str(snapshot_a), str(snapshot_b), "--preview", "5"])
    assert code == 0
    out = capsys.readouterr().out
    assert "matched launches" in out
    assert "Vulcan" in out or "launch" in out.lower() or "Sample" in out


def test_cli_stats_empty(tmp_path: Path, capsys) -> None:
    code = main(["stats", "--slips", str(tmp_path / "missing.csv")])
    assert code == 0
    assert "No slips.csv" in capsys.readouterr().out
