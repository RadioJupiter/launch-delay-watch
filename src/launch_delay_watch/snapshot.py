"""Fetch upcoming launches from Launch Library 2 and write dated CSV snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .paths import SNAPSHOT_DIR

# One page of 100 keeps us well under the free-tier ~15 req/hour limit.
LL2_UPCOMING = (
    "https://ll.thespacedevs.com/2.2.0/launch/upcoming/"
    "?limit=100&mode=normal"
)

SNAPSHOT_COLUMNS = [
    "id",
    "name",
    "provider",
    "rocket",
    "pad",
    "net",
    "status",
    "window_start",
    "window_end",
]


def _nested_name(obj: Any, *keys: str) -> str:
    """Walk nested dicts and return the final string value, or empty."""
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur if isinstance(cur, str) else ""


def normalize_launch(item: dict[str, Any]) -> dict[str, str]:
    """Flatten one Launch Library 2 launch object into a snapshot row."""
    pad = item.get("pad") or {}
    location = pad.get("location") if isinstance(pad, dict) else {}
    pad_name = _nested_name(item, "pad", "name")
    loc_name = location.get("name") if isinstance(location, dict) else ""
    pad_label = pad_name
    if loc_name:
        pad_label = f"{pad_name} ({loc_name})" if pad_name else loc_name

    return {
        "id": str(item.get("id") or ""),
        "name": str(item.get("name") or ""),
        "provider": _nested_name(item, "launch_service_provider", "name"),
        "rocket": _nested_name(item, "rocket", "configuration", "full_name")
        or _nested_name(item, "rocket", "configuration", "name"),
        "pad": pad_label,
        "net": str(item.get("net") or ""),
        "status": _nested_name(item, "status", "abbrev")
        or _nested_name(item, "status", "name"),
        "window_start": str(item.get("window_start") or ""),
        "window_end": str(item.get("window_end") or ""),
    }


def fetch_upcoming(
    url: str = LL2_UPCOMING,
    session: requests.Session | None = None,
    timeout: float = 60.0,
) -> pd.DataFrame:
    """Download one page of upcoming launches and return a normalized DataFrame.

    Uses a single HTTP request (limit=100) to respect Launch Library 2 free-tier
    rate limits. Pass ``session`` in tests to inject a stubbed transport.
    """
    http = session or requests
    resp = http.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    results = payload.get("results") or []
    rows = [normalize_launch(item) for item in results]
    df = pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)
    return df


def write_snapshot(
    df: pd.DataFrame,
    date: str | None = None,
    directory: Path | None = None,
) -> Path:
    """Write ``df`` to ``data/snapshots/YYYY-MM-DD.csv`` and return the path."""
    out_dir = directory or SNAPSHOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    day = date or pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    path = out_dir / f"{day}.csv"
    out = df.copy()
    # Ensure column order and ISO-ish NET strings for stable diffs.
    for col in SNAPSHOT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[SNAPSHOT_COLUMNS]
    out.to_csv(path, index=False)
    return path
