"""Summarize and chart launch slip history."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

from .paths import SLIPS_PATH, SNAPSHOT_DIR
from .precision import FLAG_OK, infer_class, precision_flag

# A timed NET has to move by at least this much to count as a slip (or a pull-in).
# Smaller moves are T-0 refinements inside the day (e.g. 17:11:30 -> 17:40:30 on
# launch day), reported separately as "minor adjustments".
DEFAULT_MIN_HOURS = 1.0


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
    return ensure_precision_flags(df)


def ensure_precision_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add precision columns to an older slips frame that predates them.

    Without window fields only the NET itself is available, so this applies the
    midnight/last-day heuristic from :mod:`launch_delay_watch.precision`.
    Run ``ldw rebuild`` to recompute them properly from the snapshots.
    """
    if df.empty or ("precision_flag" in df.columns and (df["precision_flag"] != "").all()):
        return df
    out = df.copy()
    if "net_a" not in out.columns or "net_b" not in out.columns:
        out["precision_flag"] = FLAG_OK
        return out
    out["precision_a"] = [infer_class(v) for v in out["net_a"]]
    out["precision_b"] = [infer_class(v) for v in out["net_b"]]
    out["precision_flag"] = [
        precision_flag(a, b) for a, b in zip(out["precision_a"], out["precision_b"])
    ]
    return out


def filter_slips(df: pd.DataFrame, include_low_precision: bool = False) -> pd.DataFrame:
    """Keep only rows whose two NETs were both timed (hour precision or better).

    Pass ``include_low_precision=True`` to keep placeholder/precision-change rows.
    """
    if include_low_precision or df.empty:
        return df
    data = ensure_precision_flags(df)
    return data[data["precision_flag"] == FLAG_OK].copy()


def summarize_slips(
    df: pd.DataFrame | None = None,
    by: str = "provider",
    include_low_precision: bool = False,
) -> pd.DataFrame:
    """Aggregate slip_days by provider or rocket.

    Returns count, mean, median, and total positive slip (delay mass). Rows whose
    NETs were not both timed are excluded unless ``include_low_precision``.
    """
    if by not in {"provider", "rocket", "pad"}:
        raise ValueError("by must be 'provider', 'rocket', or 'pad'")
    data = load_slips() if df is None else df.copy()
    data = filter_slips(data, include_low_precision=include_low_precision)
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


SOURCE_CREDIT = (
    "Data: Launch Library 2 API by The Space Devs (thespacedevs.com) · "
    "github.com/RadioJupiter/launch-delay-watch"
)


def _period(df: pd.DataFrame) -> str:
    """'snapshots 2026-11-03 to 2026-11-15' from snapshot_a/snapshot_b columns."""
    dates: list[str] = []
    for col in ("snapshot_a", "snapshot_b"):
        if col in df.columns:
            dates += [str(v) for v in df[col] if str(v)]
    if not dates:
        return ""
    return f"daily snapshots {min(dates)} to {max(dates)}"


def _footer(fig, df: pd.DataFrame, note: str) -> None:
    period = _period(df)
    lines = [note] if note else []
    lines.append(SOURCE_CREDIT + (f" · {period}" if period else ""))
    fig.text(0.01, 0.01, "\n".join(lines), ha="left", va="bottom", fontsize=8, color="#555")


def chart_slips(
    df: pd.DataFrame | None = None,
    by: str = "provider",
    out_path: Path | None = None,
    top_n: int = 10,
    include_low_precision: bool = False,
    min_hours: float = DEFAULT_MIN_HOURS,
) -> Path:
    """Bar chart of days of delay (moves later >= min_hours) for the top-N groups."""
    if by not in {"provider", "rocket", "pad"}:
        raise ValueError("by must be 'provider', 'rocket', or 'pad'")
    data = load_slips() if df is None else df
    used = filter_slips(data, include_low_precision=include_low_precision)
    used = used.dropna(subset=["slip_days"]) if not used.empty else used
    thr = min_hours / 24.0
    rows = []
    if not used.empty:
        used = used.copy()
        used[by] = used[by].replace("", "(unknown)")
        for name, g in used.groupby(by):
            late = g[g["slip_days"] >= thr]
            if late.empty:
                continue
            rows.append((name, len(g), len(late), float(late["slip_days"].sum())))
    rows.sort(key=lambda r: r[3], reverse=True)
    rows = rows[:top_n]
    dest = out_path or (SLIPS_PATH.parent / f"slip_by_{by}.png")
    dest.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, max(3.2, 1.2 + 0.7 * len(rows))))
    if not rows:
        ax.text(0.5, 0.5, "No slip data yet", ha="center", va="center")
        ax.set_axis_off()
    else:
        labels = [f"{name}\n{n} comparisons, {k} slip{'s' if k != 1 else ''}"
                  for name, n, k, _ in rows]
        values = [v for *_, v in rows]
        ax.barh(labels[::-1], values[::-1], color="#c0392b", height=0.6)
        for y, v in enumerate(values[::-1]):
            ax.text(v, y, f" {v:.1f} d", va="center", fontsize=10)
        ax.set_xlim(0, max(values) * 1.15)
        ax.set_xlabel(f"Days of delay added (sum of moves later by >= {min_hours:g} h)")
        ax.grid(axis="x", alpha=0.3)
    scope = "all NETs" if include_low_precision else "NETs given to the hour or better"
    ax.set_title(f"Launch NET delay by {by} ({scope})")
    note = (
        "Groups with no slip are omitted. "
        + (
            "Includes month/day placeholder NETs."
            if include_low_precision
            else "Comparisons where either NET was a day/month/year placeholder are excluded."
        )
    )
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    _footer(fig, data, note)
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return dest


def per_launch_slips(
    df: pd.DataFrame,
    min_hours: float = DEFAULT_MIN_HOURS,
) -> pd.DataFrame:
    """One row per launch over timed comparisons: slip count and net NET change."""
    data = filter_slips(df).dropna(subset=["slip_days"])
    if data.empty:
        return pd.DataFrame(
            columns=["id", "name", "rocket", "pad", "slips", "net_change_days",
                     "first_net", "last_net", "last_status"]
        )
    thr = min_hours / 24.0
    data = data.sort_values("snapshot_b")
    rows = []
    for lid, g in data.groupby("id", sort=False):
        last = g.iloc[-1]
        rows.append(
            {
                "id": lid,
                "name": last["name"],
                "rocket": last["rocket"],
                "pad": last["pad"],
                "slips": int((g["slip_days"] >= thr).sum()),
                "net_change_days": float(g["slip_days"].sum()),
                "first_net": g.iloc[0]["net_a"],
                "last_net": last["net_b"],
                "last_status": last["status_b"],
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["net_change_days", "slips"], ascending=False).reset_index(drop=True)


def headline_numbers(
    df: pd.DataFrame,
    snapshot_dir: Path | None = None,
    min_hours: float = DEFAULT_MIN_HOURS,
) -> dict:
    """Every number used in public write-ups, computed from slips + snapshots."""
    data = ensure_precision_flags(df).dropna(subset=["slip_days"])
    snap_dir = snapshot_dir or SNAPSHOT_DIR
    snaps = sorted(p.stem for p in snap_dir.glob("????-??-??.csv")) if snap_dir.is_dir() else []
    thr = min_hours / 24.0
    timed = data[data["precision_flag"] == FLAG_OK]
    pc = data[data["precision_flag"] == "precision_change"]
    lp = data[data["precision_flag"] == "low_precision"]
    later = timed[timed["slip_days"] >= thr]
    earlier = timed[timed["slip_days"] <= -thr]
    minor = timed[(timed["slip_days"].abs() < thr) & (timed["slip_days"] != 0)]
    per = per_launch_slips(data, min_hours=min_hours)
    return {
        "snapshots": len(snaps),
        "first_snapshot": snaps[0] if snaps else "",
        "last_snapshot": snaps[-1] if snaps else "",
        "pairs": int(data[["snapshot_a", "snapshot_b"]].drop_duplicates().shape[0]),
        "launches_matched": int(data["id"].nunique()),
        "comparisons_all": int(len(data)),
        "comparisons_low_precision": int(len(lp)),
        "comparisons_precision_change": int(len(pc)),
        "launches_precision_change": int(pc["id"].nunique()),
        "comparisons_timed": int(len(timed)),
        "launches_timed": int(timed["id"].nunique()),
        "min_hours": min_hours,
        "moved_later": int(len(later)),
        "moved_earlier": int(len(earlier)),
        "minor_adjustments": int(len(minor)),
        "unchanged": int((timed["slip_days"] == 0).sum()),
        "pct_moved_later": (100.0 * len(later) / len(timed)) if len(timed) else 0.0,
        "median_change_days": float(timed["slip_days"].median()) if len(timed) else 0.0,
        "launches_slipped": int(later["id"].nunique()),
        "delay_days_total": float(later["slip_days"].sum()),
        "per_launch": per,
        "slip_rows": later.sort_values(["snapshot_b", "name"]),
        "precision_changes": pc,
    }


def format_headline(h: dict) -> str:
    """Plain-text report of :func:`headline_numbers` (what `ldw headline` prints)."""
    thr = h["min_hours"]
    lines = [
        f"Snapshots: {h['snapshots']} ({h['first_snapshot']} to {h['last_snapshot']}), "
        f"{h['pairs']} day-over-day pairs",
        f"All comparisons: {h['comparisons_all']} across {h['launches_matched']} launches",
        f"  excluded, same placeholder precision both days (day/month/quarter/year): "
        f"{h['comparisons_low_precision']}",
        f"  excluded, precision changed (placeholder set or replaced): "
        f"{h['comparisons_precision_change']} ({h['launches_precision_change']} launches)",
        f"Timed comparisons (both NETs to the hour or better): {h['comparisons_timed']} "
        f"across {h['launches_timed']} launches",
        f"  moved later by >= {thr:g} h: {h['moved_later']} "
        f"({h['pct_moved_later']:.1f}%) across {h['launches_slipped']} launches, "
        f"{h['delay_days_total']:.1f} days of delay in total",
        f"  moved earlier by >= {thr:g} h: {h['moved_earlier']}",
        f"  minor T-0 adjustments (< {thr:g} h): {h['minor_adjustments']}",
        f"  unchanged: {h['unchanged']}",
        f"  median change: {h['median_change_days']:+.2f} days",
        "",
        "Launches that slipped (timed comparisons):",
    ]
    per = h["per_launch"]
    for r in per[per["slips"] > 0].itertuples(index=False):
        lines.append(
            f"  {r.name} | {r.pad} | slips={r.slips} | net change {r.net_change_days:+.2f} d "
            f"| {r.first_net} -> {r.last_net} | last status {r.last_status}"
        )
    steps = h.get("slip_rows")
    if steps is not None and not steps.empty:
        lines += ["", "Slips by pad:"]
        by_pad = steps.groupby("pad")["slip_days"].agg(["count", "sum"])
        for pad, row in by_pad.sort_values("count", ascending=False).iterrows():
            lines.append(f"  {pad}: {int(row['count'])} slips, {row['sum']:.1f} days")
        lines += ["", "Each slip (snapshot pair, launch, size):"]
        for r in steps.itertuples(index=False):
            minutes = int(round(r.slip_days * 24 * 60))
            lines.append(
                f"  {r.snapshot_a} -> {r.snapshot_b} {r.name}: +{minutes // 60} h "
                f"{minutes % 60:02d} min ({r.net_a} -> {r.net_b})"
            )
    lines += ["", "Precision changes (not counted as slips):"]
    for r in h["precision_changes"].itertuples(index=False):
        lines.append(
            f"  {r.snapshot_b} {r.name}: {r.net_a} ({r.precision_a}) -> "
            f"{r.net_b} ({r.precision_b})"
        )
    return "\n".join(lines)


def chart_timeline(
    df: pd.DataFrame | None = None,
    out_path: Path | None = None,
    top_n: int = 4,
    min_hours: float = DEFAULT_MIN_HOURS,
) -> Path:
    """Step chart of published NET vs snapshot date for the launches that slipped most."""
    import matplotlib.dates as mdates

    data = load_slips() if df is None else df
    timed = filter_slips(data).dropna(subset=["slip_days"])
    per = per_launch_slips(data, min_hours=min_hours)
    per = per[per["slips"] > 0].head(top_n)
    dest = out_path or (SLIPS_PATH.parent / "net_timeline.png")
    dest.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11, 6.2))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    all_x: list[pd.Timestamp] = []
    for i, r in enumerate(per.itertuples(index=False)):
        g = timed[timed["id"] == r.id].sort_values("snapshot_b")
        xs = [pd.Timestamp(g.iloc[0]["snapshot_a"])] + [pd.Timestamp(v) for v in g["snapshot_b"]]
        ys = [pd.Timestamp(g.iloc[0]["net_a"]).tz_convert(None)] + [
            pd.Timestamp(v).tz_convert(None) for v in g["net_b"]
        ]
        all_x += xs
        short = r.name.split("|", 1)[-1].strip()
        status = str(r.last_status)
        end = {"Success": ", launched", "Failure": ", launch failed"}.get(status, "")
        if "precision_flag" in data.columns:
            later = data[(data["id"] == r.id) & (data["precision_flag"] == "precision_change")
                         & (data["snapshot_b"] > g["snapshot_b"].max())]
            if not later.empty and later.iloc[-1]["precision_b"] != "timed":
                end += f", then reset to a month placeholder ({later.iloc[-1]['snapshot_b']})"
        label = (
            f"{short} ({r.rocket}): {r.slips} slip{'s' if r.slips != 1 else ''}, "
            f"{r.net_change_days:+.1f} d{end}"
        )
        c = colors[i % len(colors)]
        ax.step(xs, ys, where="post", color=c, linewidth=2, label=label)
        ax.plot(xs, ys, "o", color=c, markersize=5)
        if status in ("Success", "Failure"):
            ax.plot(xs[-1], ys[-1], marker="*" if status == "Success" else "X",
                    color=c, markersize=13, markeredgecolor="black")
    if all_x:
        lo, hi = min(all_x), max(all_x)
        diag = pd.date_range(lo, hi, freq="D")
        ax.plot(diag, diag, "--", color="#888", linewidth=1, label="NET = snapshot date")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_xlabel("Snapshot date (one Launch Library 2 snapshot per day, UTC)")
    ax.set_ylabel("Published NET (UTC)")
    period = _period(data).replace("daily snapshots ", "")
    ax.set_title(f"Launches whose published NET slipped, by total delay ({period})")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.95)
    note = (
        f"Slip = NET moved later by at least {min_hours:g} h between consecutive daily "
        "snapshots; only NETs given to the hour or better. ★ launched  ✕ launch failed."
    )
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _footer(fig, data, note)
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return dest
