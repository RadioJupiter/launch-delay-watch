"""Compare launch snapshots and maintain a cumulative slips history."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .paths import SLIPS_PATH, SNAPSHOT_DIR

SLIP_COLUMNS = [
    "id",
    "name",
    "provider",
    "rocket",
    "pad",
    "snapshot_a",
    "snapshot_b",
    "net_a",
    "net_b",
    "slip_days",
    "status_a",
    "status_b",
]


def _read_snapshot(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "id" not in df.columns:
        raise ValueError(f"Snapshot missing id column: {path}")
    for col in ("name", "provider", "rocket", "pad", "net", "status"):
        if col not in df.columns:
            df[col] = ""
    df["net_dt"] = pd.to_datetime(df["net"], utc=True, errors="coerce")
    return df


def compare_snapshots(path_a: Path, path_b: Path) -> pd.DataFrame:
    """Return per-launch slip days between two snapshots.

    Positive ``slip_days`` means the NET moved later (delay). Launches present
    in only one file are dropped (they usually flew or were newly announced).
    """
    a = _read_snapshot(path_a)
    b = _read_snapshot(path_b)

    left = a[["id", "name", "provider", "rocket", "pad", "net", "status", "net_dt"]].rename(
        columns={
            "name": "name_a",
            "provider": "provider_a",
            "rocket": "rocket_a",
            "pad": "pad_a",
            "net": "net_a",
            "status": "status_a",
            "net_dt": "net_dt_a",
        }
    )
    right = b[["id", "name", "provider", "rocket", "pad", "net", "status", "net_dt"]].rename(
        columns={
            "name": "name_b",
            "provider": "provider_b",
            "rocket": "rocket_b",
            "pad": "pad_b",
            "net": "net_b",
            "status": "status_b",
            "net_dt": "net_dt_b",
        }
    )
    merged = left.merge(right, on="id", how="inner")

    def prefer_b(col: str) -> pd.Series:
        b_vals = merged[f"{col}_b"].astype(str)
        a_vals = merged[f"{col}_a"].astype(str)
        return b_vals.where(b_vals != "", a_vals)

    out = pd.DataFrame(
        {
            "id": merged["id"],
            "name": prefer_b("name"),
            "provider": prefer_b("provider"),
            "rocket": prefer_b("rocket"),
            "pad": prefer_b("pad"),
            "snapshot_a": path_a.stem,
            "snapshot_b": path_b.stem,
            "net_a": merged["net_a"],
            "net_b": merged["net_b"],
            "slip_days": (merged["net_dt_b"] - merged["net_dt_a"]).dt.total_seconds() / 86400.0,
            "status_a": merged["status_a"],
            "status_b": merged["status_b"],
        }
    )
    return out.sort_values("slip_days", ascending=False, na_position="last").reset_index(drop=True)


def list_snapshots(directory: Path | None = None) -> list[Path]:
    """Return snapshot CSV paths sorted by date stem ascending."""
    d = directory or SNAPSHOT_DIR
    if not d.is_dir():
        return []
    return sorted(d.glob("????-??-??.csv"))


def update_slips_history(
    path_a: Path | None = None,
    path_b: Path | None = None,
    slips_path: Path | None = None,
    snapshot_dir: Path | None = None,
) -> pd.DataFrame:
    """Diff two snapshots (default: last two on disk) and append to slips.csv.

    Rows for the same (id, snapshot_a, snapshot_b) key are replaced so re-runs
    stay idempotent.
    """
    snaps = list_snapshots(snapshot_dir)
    if path_a is None or path_b is None:
        if len(snaps) < 2:
            return pd.DataFrame(columns=SLIP_COLUMNS)
        path_a, path_b = snaps[-2], snaps[-1]

    delta = compare_snapshots(path_a, path_b)
    dest = slips_path or SLIPS_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.is_file():
        hist = pd.read_csv(dest, dtype={"id": str}).fillna("")
        if "slip_days" in hist.columns:
            hist["slip_days"] = pd.to_numeric(hist["slip_days"], errors="coerce")
        for col in SLIP_COLUMNS:
            if col not in hist.columns:
                hist[col] = "" if col != "slip_days" else float("nan")
        hist = hist[SLIP_COLUMNS]
        key_cols = ["id", "snapshot_a", "snapshot_b"]
        old_index = pd.MultiIndex.from_frame(hist[key_cols].astype(str))
        new_index = pd.MultiIndex.from_frame(delta[key_cols].astype(str))
        hist = hist.loc[~old_index.isin(new_index)].copy()
        combined = pd.concat([hist, delta[SLIP_COLUMNS]], ignore_index=True)
    else:
        combined = delta[SLIP_COLUMNS].copy()

    combined = combined.sort_values(
        ["snapshot_b", "slip_days"], ascending=[True, False], na_position="last"
    ).reset_index(drop=True)
    combined.to_csv(dest, index=False)
    return delta
