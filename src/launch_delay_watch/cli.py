"""Command-line interface for Launch Delay Watch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .diff import (
    compare_snapshots,
    list_snapshots,
    rebuild_slips_history,
    update_slips_history,
)
from .paths import SLIPS_PATH, SNAPSHOT_DIR
from .precision import FLAG_OK
from .snapshot import fetch_upcoming, write_snapshot
from .stats import (
    DEFAULT_MIN_HOURS,
    chart_slips,
    chart_timeline,
    filter_slips,
    format_headline,
    headline_numbers,
    load_slips,
    summarize_slips,
)


def _cmd_snapshot(args: argparse.Namespace) -> int:
    df = fetch_upcoming()
    path = write_snapshot(df, date=args.date, directory=Path(args.dir) if args.dir else None)
    print(f"Wrote {path} ({len(df)} launches)")
    preview = df[["name", "provider", "rocket", "net", "status"]].head(args.preview)
    print(preview.to_string(index=False))
    # If at least two snapshots exist, refresh the cumulative slips file.
    snaps = list_snapshots(Path(args.dir) if args.dir else None)
    if len(snaps) >= 2 and not args.no_history:
        delta = update_slips_history(
            snaps[-2],
            snaps[-1],
            slips_path=Path(args.slips) if args.slips else None,
            snapshot_dir=Path(args.dir) if args.dir else None,
        )
        timed = delta[delta["precision_flag"] == FLAG_OK] if not delta.empty else delta
        delayed = timed[timed["slip_days"] >= DEFAULT_MIN_HOURS / 24] if not timed.empty else timed
        print(
            f"Updated slips history: {len(delta)} matched, {len(timed)} with timed NETs, "
            f"{len(delayed)} moved later by >= {DEFAULT_MIN_HOURS:g} h vs prior snapshot"
        )
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    snap_dir = Path(args.dir) if args.dir else SNAPSHOT_DIR
    if args.a and args.b:
        path_a, path_b = Path(args.a), Path(args.b)
    else:
        snaps = list_snapshots(snap_dir)
        if len(snaps) < 2:
            print("Need at least two snapshots to diff.", file=sys.stderr)
            return 1
        path_a, path_b = snaps[-2], snaps[-1]
    if not path_a.is_file():
        path_a = snap_dir / path_a.name
    if not path_b.is_file():
        path_b = snap_dir / path_b.name
    delta = compare_snapshots(path_a, path_b)
    if args.update_history:
        update_slips_history(
            path_a,
            path_b,
            slips_path=Path(args.slips) if args.slips else None,
            snapshot_dir=snap_dir,
        )
    print(f"Compared {path_a.name} → {path_b.name}: {len(delta)} matched launches")
    cols = ["name", "provider", "rocket", "net_a", "net_b", "slip_days"]
    shown = filter_slips(delta, include_low_precision=args.include_low_precision)
    if args.include_low_precision:
        cols.append("precision_flag")
    print(shown[cols].head(args.preview).to_string(index=False))
    flagged = delta[(delta["precision_flag"] == "precision_change")]
    if not flagged.empty and not args.include_low_precision:
        print(f"\nPrecision changes (placeholder set or replaced; not slips): {len(flagged)}")
        print(
            flagged[["name", "net_a", "precision_a", "net_b", "precision_b"]]
            .to_string(index=False)
        )
    skipped = int((delta["precision_flag"] == "low_precision").sum())
    if skipped and not args.include_low_precision:
        print(f"\n{skipped} launches with day/month/year placeholder NETs hidden "
              "(use --include-low-precision).")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    df = load_slips(Path(args.slips) if args.slips else None)
    if df.empty:
        print("No slips.csv yet. Take two snapshots (or run ldw diff --update-history).")
        return 0
    summary = summarize_slips(df, by=args.by, include_low_precision=args.include_low_precision)
    print(summary.head(args.preview).to_string(index=False))
    used = filter_slips(df, include_low_precision=args.include_low_precision)
    overall = used["slip_days"].dropna()
    if not overall.empty:
        thr = args.min_hours / 24
        print(
            f"\nOverall: n={len(overall)}  mean={overall.mean():.2f}d  "
            f"median={overall.median():.2f}d  "
            f"moved later >= {args.min_hours:g} h: {(overall >= thr).sum()}  "
            f"moved earlier >= {args.min_hours:g} h: {(overall <= -thr).sum()}"
        )
    excluded = len(df) - len(used)
    if excluded:
        print(f"Excluded {excluded} comparisons with day/month/year placeholder NETs "
              "(use --include-low-precision to include them).")
    return 0


def _cmd_headline(args: argparse.Namespace) -> int:
    df = load_slips(Path(args.slips) if args.slips else None)
    if df.empty:
        print("No slips.csv yet.")
        return 0
    h = headline_numbers(
        df, snapshot_dir=Path(args.dir) if args.dir else None, min_hours=args.min_hours
    )
    print(format_headline(h))
    return 0


def _cmd_rebuild(args: argparse.Namespace) -> int:
    out = rebuild_slips_history(
        slips_path=Path(args.slips) if args.slips else None,
        snapshot_dir=Path(args.dir) if args.dir else None,
    )
    print(f"Rebuilt slips history: {len(out)} rows")
    return 0


def _cmd_chart(args: argparse.Namespace) -> int:
    df = load_slips(Path(args.slips) if args.slips else None)
    if args.kind == "timeline":
        out = chart_timeline(
            df,
            out_path=Path(args.out) if args.out else None,
            top_n=args.top if args.top != 10 else 4,
            min_hours=args.min_hours,
        )
    else:
        out = chart_slips(
            df,
            by=args.by,
            out_path=Path(args.out) if args.out else None,
            top_n=args.top,
            include_low_precision=args.include_low_precision,
            min_hours=args.min_hours,
        )
    print(f"Wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ldw",
        description="Launch Delay Watch — track rocket launch NET date slip.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("snapshot", help="Fetch upcoming launches into a dated CSV")
    s.add_argument("--date", help="Override snapshot date (YYYY-MM-DD)")
    s.add_argument("--dir", help=f"Snapshot directory (default: {SNAPSHOT_DIR})")
    s.add_argument("--slips", help=f"Slips history path (default: {SLIPS_PATH})")
    s.add_argument("--preview", type=int, default=10, help="Rows to print")
    s.add_argument(
        "--no-history",
        action="store_true",
        help="Do not update data/slips.csv even if two snapshots exist",
    )
    s.set_defaults(func=_cmd_snapshot)

    d = sub.add_parser("diff", help="Compare two snapshots (default: last two)")
    d.add_argument("a", nargs="?", help="Older snapshot path or filename")
    d.add_argument("b", nargs="?", help="Newer snapshot path or filename")
    d.add_argument("--dir", help=f"Snapshot directory (default: {SNAPSHOT_DIR})")
    d.add_argument("--slips", help=f"Slips history path (default: {SLIPS_PATH})")
    d.add_argument("--update-history", action="store_true", help="Append result to slips.csv")
    d.add_argument("--preview", type=int, default=20, help="Rows to print")
    d.add_argument(
        "--include-low-precision",
        action="store_true",
        help="Include comparisons where either NET was a day/month/year placeholder",
    )
    d.set_defaults(func=_cmd_diff)

    t = sub.add_parser("stats", help="Summarize slip days by provider/rocket/pad")
    t.add_argument("--by", choices=["provider", "rocket", "pad"], default="provider")
    t.add_argument("--slips", help=f"Slips history path (default: {SLIPS_PATH})")
    t.add_argument("--preview", type=int, default=20, help="Rows to print")
    t.add_argument(
        "--include-low-precision",
        action="store_true",
        help="Include comparisons where either NET was a day/month/year placeholder",
    )
    t.add_argument(
        "--min-hours",
        type=float,
        default=DEFAULT_MIN_HOURS,
        help="Minimum move (hours) to count as a slip (default: %(default)s)",
    )
    t.set_defaults(func=_cmd_stats)

    c = sub.add_parser("chart", help="Write a PNG bar chart of mean slip by group")
    c.add_argument("--by", choices=["provider", "rocket", "pad"], default="provider")
    c.add_argument("--slips", help=f"Slips history path (default: {SLIPS_PATH})")
    c.add_argument("--out", help="Output PNG path")
    c.add_argument("--top", type=int, default=10, help="Top N groups (timeline: 4)")
    c.add_argument("--kind", choices=["bar", "timeline"], default="bar")
    c.add_argument(
        "--include-low-precision",
        action="store_true",
        help="Include comparisons where either NET was a day/month/year placeholder",
    )
    c.add_argument(
        "--min-hours",
        type=float,
        default=DEFAULT_MIN_HOURS,
        help="Minimum move (hours) to count as a slip (default: %(default)s)",
    )
    c.set_defaults(func=_cmd_chart)

    h = sub.add_parser("headline", help="Print every headline number used in write-ups")
    h.add_argument("--slips", help=f"Slips history path (default: {SLIPS_PATH})")
    h.add_argument("--dir", help=f"Snapshot directory (default: {SNAPSHOT_DIR})")
    h.add_argument(
        "--min-hours",
        type=float,
        default=DEFAULT_MIN_HOURS,
        help="Minimum move (hours) to count as a slip (default: %(default)s)",
    )
    h.set_defaults(func=_cmd_headline)

    r = sub.add_parser("rebuild", help="Recompute slips.csv from all snapshots")
    r.add_argument("--slips", help=f"Slips history path (default: {SLIPS_PATH})")
    r.add_argument("--dir", help=f"Snapshot directory (default: {SNAPSHOT_DIR})")
    r.set_defaults(func=_cmd_rebuild)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
