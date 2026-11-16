"""Placeholder / low-precision NET handling (no network)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from launch_delay_watch.cli import main
from launch_delay_watch.diff import compare_snapshots, rebuild_slips_history
from launch_delay_watch.precision import (
    COARSE,
    DAY,
    TIMED,
    class_from_ll2,
    infer_class,
    precision_flag,
    resolve_class,
)
from launch_delay_watch.snapshot import normalize_launch
from launch_delay_watch.stats import (
    filter_slips,
    headline_numbers,
    load_slips,
    summarize_slips,
)

HEADER = "id,name,provider,rocket,pad,net,status,window_start,window_end"
HEADER_P = HEADER + ",net_precision"


def _write(path: Path, header: str, rows: list[str]) -> Path:
    path.write_text("\n".join([header, *rows]) + "\n")
    return path


def test_ll2_names_map_to_classes() -> None:
    assert class_from_ll2("Second") == TIMED
    assert class_from_ll2("Minute") == TIMED
    assert class_from_ll2("Hour") == TIMED
    assert class_from_ll2("Day") == DAY
    for name in ("Month", "Quarter 4", "Half 1", "Year", "Fiscal Year"):
        assert class_from_ll2(name) == COARSE
    assert class_from_ll2("") == ""
    assert class_from_ll2(None) == ""


def test_heuristic_month_day_and_timed() -> None:
    # Month placeholder: last day of month, midnight, zero-length window
    z = "2026-11-30T00:00:00Z"
    assert infer_class(z, z, z) == COARSE
    assert infer_class("2026-12-31T00:00:00Z") == COARSE  # year placeholder
    # Day placeholder: midnight, zero window, not month end
    d = "2026-11-13T00:00:00Z"
    assert infer_class(d, d, d) == DAY
    # Midnight but real window -> timed (a launch can open at 00:00 UTC)
    assert infer_class(d, d, "2026-11-13T04:00:00Z") == TIMED
    assert infer_class("2026-11-12T19:50:00Z", "", "") == TIMED
    assert infer_class("not a date") == "unknown"


def test_resolve_prefers_ll2_field() -> None:
    z = "2026-11-30T00:00:00Z"
    assert resolve_class(z, z, z, "Minute") == (TIMED, "ll2")
    assert resolve_class(z, z, z, "") == (COARSE, "heuristic")


def test_flags() -> None:
    assert precision_flag(TIMED, TIMED) == "ok"
    assert precision_flag(TIMED, COARSE) == "precision_change"
    assert precision_flag(COARSE, COARSE) == "low_precision"
    assert precision_flag(DAY, DAY) == "low_precision"


def test_normalize_captures_net_precision() -> None:
    row = normalize_launch(
        {"id": "x", "name": "A | B", "net": "2026-11-30T00:00:00Z",
         "net_precision": {"id": 7, "name": "Month", "abbrev": "MON"}}
    )
    assert row["net_precision"] == "Month"
    assert normalize_launch({"id": "y"})["net_precision"] == ""


def _placeholder_pair(tmp_path: Path) -> tuple[Path, Path]:
    a = _write(
        tmp_path / "2026-11-11.csv",
        HEADER,
        [
            # real slip: timed -> timed, +1 day
            "s1,Falcon 9 | Real,SpaceX,Falcon 9,SLC-4E,2026-11-15T03:55:00Z,Go,"
            "2026-11-15T03:55:00Z,2026-11-15T07:55:00Z",
            # timed -> month placeholder (like Kuaizhou 11): not a 17-day slip
            "k1,Kuaizhou 11 | X,ExPace,Kuaizhou 11,Jiuquan,2026-11-12T19:50:00Z,Go,"
            "2026-11-12T19:50:00Z,2026-11-12T20:20:00Z",
            # month placeholder -> day placeholder (like Starship Flight 15)
            "f1,Starship | Flight,SpaceX,Starship,Starbase,2026-11-30T00:00:00Z,TBD,"
            "2026-11-30T00:00:00Z,2026-11-30T00:00:00Z",
            # year placeholder both days
            "y1,Vulcan | Y,ULA,Vulcan,SLC-41,2026-12-31T00:00:00Z,TBD,"
            "2026-12-31T00:00:00Z,2026-12-31T00:00:00Z",
            # minor T-0 tweak on launch day
            "m1,Vulcan | M,ULA,Vulcan,SLC-41,2026-11-15T17:11:30Z,Go,"
            "2026-11-15T17:11:30Z,2026-11-15T17:31:00Z",
        ],
    )
    b = _write(
        tmp_path / "2026-11-12.csv",
        HEADER_P,
        [
            "s1,Falcon 9 | Real,SpaceX,Falcon 9,SLC-4E,2026-11-16T03:55:00Z,Go,"
            "2026-11-16T03:55:00Z,2026-11-16T07:55:00Z,Minute",
            "k1,Kuaizhou 11 | X,ExPace,Kuaizhou 11,Jiuquan,2026-11-30T00:00:00Z,TBD,"
            "2026-11-30T00:00:00Z,2026-11-30T00:00:00Z,Month",
            "f1,Starship | Flight,SpaceX,Starship,Starbase,2026-11-13T00:00:00Z,TBD,"
            "2026-11-13T00:00:00Z,2026-11-13T00:00:00Z,Day",
            "y1,Vulcan | Y,ULA,Vulcan,SLC-41,2026-12-31T00:00:00Z,TBD,"
            "2026-12-31T00:00:00Z,2026-12-31T00:00:00Z,Year",
            "m1,Vulcan | M,ULA,Vulcan,SLC-41,2026-11-15T17:40:30Z,Failure,"
            "2026-11-15T17:11:30Z,2026-11-15T17:40:30Z,Second",
        ],
    )
    return a, b


def test_compare_flags_placeholders(tmp_path: Path) -> None:
    a, b = _placeholder_pair(tmp_path)
    delta = compare_snapshots(a, b).set_index("id")
    assert delta.loc["s1", "precision_flag"] == "ok"
    assert delta.loc["k1", "precision_flag"] == "precision_change"
    assert delta.loc["k1", "precision_a"] == TIMED
    assert delta.loc["k1", "precision_b"] == COARSE
    assert round(delta.loc["k1", "slip_days"], 2) == 17.17  # raw value kept, but flagged
    assert delta.loc["f1", "precision_flag"] == "precision_change"
    assert delta.loc["y1", "precision_flag"] == "low_precision"
    assert delta.loc["m1", "precision_flag"] == "ok"


def test_stats_exclude_placeholders_by_default(tmp_path: Path) -> None:
    a, b = _placeholder_pair(tmp_path)
    delta = compare_snapshots(a, b)
    kept = filter_slips(delta)
    assert set(kept["id"]) == {"s1", "m1"}
    assert len(filter_slips(delta, include_low_precision=True)) == 5
    by_rocket = summarize_slips(delta, by="rocket").set_index("rocket")
    assert "Kuaizhou 11" not in by_rocket.index
    assert "Starship" not in by_rocket.index
    with_all = summarize_slips(delta, by="rocket", include_low_precision=True)
    assert "Kuaizhou 11" in set(with_all["rocket"])


def test_headline_numbers(tmp_path: Path) -> None:
    a, b = _placeholder_pair(tmp_path)
    slips = tmp_path / "slips.csv"
    rebuild_slips_history(slips_path=slips, snapshot_dir=tmp_path)
    h = headline_numbers(load_slips(slips), snapshot_dir=tmp_path)
    assert h["snapshots"] == 2
    assert h["comparisons_all"] == 5
    assert h["comparisons_timed"] == 2
    assert h["comparisons_precision_change"] == 2
    assert h["comparisons_low_precision"] == 1
    assert h["moved_later"] == 1  # s1 only; m1's 29 min is a minor adjustment
    assert h["minor_adjustments"] == 1
    per = h["per_launch"].set_index("id")
    assert per.loc["s1", "slips"] == 1
    assert per.loc["m1", "slips"] == 0


def test_legacy_slips_without_flags_get_heuristic(tmp_path: Path) -> None:
    legacy = pd.DataFrame(
        {
            "id": ["k1", "s1"],
            "net_a": ["2026-11-12T19:50:00Z", "2026-11-15T03:55:00Z"],
            "net_b": ["2026-11-30T00:00:00Z", "2026-11-16T03:55:00Z"],
            "slip_days": [17.17, 1.0],
            "rocket": ["Kuaizhou 11", "Falcon 9"],
        }
    )
    kept = filter_slips(legacy)
    assert list(kept["id"]) == ["s1"]


def test_cli_headline_and_flags(tmp_path: Path, capsys) -> None:
    a, b = _placeholder_pair(tmp_path)
    slips = tmp_path / "slips.csv"
    assert main(["rebuild", "--slips", str(slips), "--dir", str(tmp_path)]) == 0
    assert main(["headline", "--slips", str(slips), "--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Timed comparisons (both NETs to the hour or better): 2" in out
    assert "Kuaizhou 11 | X" in out  # listed under precision changes
    assert main(["stats", "--slips", str(slips), "--by", "rocket"]) == 0
    out = capsys.readouterr().out
    assert "Kuaizhou" not in out.split("Overall")[0]
    assert "Excluded 3 comparisons" in out
    assert main(["stats", "--slips", str(slips), "--by", "rocket",
                 "--include-low-precision"]) == 0
    assert "Kuaizhou" in capsys.readouterr().out
    assert main(["diff", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "Precision changes" in out
    png = tmp_path / "t.png"
    assert main(["chart", "--slips", str(slips), "--kind", "timeline", "--out", str(png)]) == 0
    assert png.stat().st_size > 1000
