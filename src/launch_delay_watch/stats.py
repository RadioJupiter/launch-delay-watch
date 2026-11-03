"""Summarize and chart launch slip history."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

from .paths import SLIPS_PATH


def load_slips(path: Path | None = None) -> pd.DataFrame:
    """Load slips.csv; return empty frame if missing."""
    p = path or SLIPS_PATH
    if not p.is_file():
        return pd.DataFrame(
            columns=["id", "name", "provider", "rocket", "pad", "slip_days", "snapshot_b"]
        )
    df = pd.read_csv(p, dtype={"id": str}).fillna("")
    if "slip_days" in df.columns:
        df["slip_days"] = pd.to_numeric(df["slip_days"], errors="coerce")
    return df


def summarize_slips(df: pd.DataFrame | None = None, by: str = "provider") -> pd.DataFrame:
    """Aggregate slip_days by provider or rocket.

    Returns count, mean, median, and total positive slip (delay mass).
    """
    if by not in {"provider", "rocket", "pad"}:
        raise ValueError("by must be 'provider', 'rocket', or 'pad'")
    data = load_slips() if df is None else df.copy()
    if data.empty or "slip_days" not in data.columns:
        return pd.DataFrame(
            columns=[by, "n", "mean_slip_days", "median_slip_days", "delay_days_sum"]
        )
    data = data.dropna(subset=["slip_days"])
    if by not in data.columns:
        data[by] = ""
    data[by] = data[by].replace("", "(unknown)")
    grouped = data.groupby(by, dropna=False)["slip_days"]
    out = pd.DataFrame(
        {
            by: grouped.mean().index,
            "n": grouped.count().values,
            "mean_slip_days": grouped.mean().values,
            "median_slip_days": grouped.median().values,
            "delay_days_sum": grouped.apply(lambda s: s[s > 0].sum()).values,
        }
    )
    return out.sort_values("mean_slip_days", ascending=False).reset_index(drop=True)


def chart_slips(
    df: pd.DataFrame | None = None,
    by: str = "provider",
    out_path: Path | None = None,
    top_n: int = 10,
) -> Path:
    """Bar chart of mean slip days for the top-N groups; write a PNG."""
    summary = summarize_slips(df, by=by).head(top_n)
    dest = out_path or (SLIPS_PATH.parent / f"slip_by_{by}.png")
    dest.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    if summary.empty:
        ax.text(0.5, 0.5, "No slip data yet", ha="center", va="center")
        ax.set_axis_off()
    else:
        labels = summary[by].tolist()
        values = summary["mean_slip_days"].tolist()
        colors = ["#c0392b" if v > 0 else "#27ae60" for v in values]
        ax.barh(labels[::-1], values[::-1], color=colors[::-1])
        ax.axvline(0, color="#333", linewidth=0.8)
        ax.set_xlabel("Mean NET slip (days; + = delayed)")
        ax.set_title(f"Launch NET slip by {by}")
    fig.tight_layout()
    fig.savefig(dest, dpi=120)
    plt.close(fig)
    return dest
