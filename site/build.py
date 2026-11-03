#!/usr/bin/env python3
"""Build the Launch Delay Watch static site from local snapshot/slips CSVs.

No Launch Library 2 API calls — only committed data under data/.
Output: site/_site/ (GitHub Pages artifact root).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

SITE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SITE_DIR.parent
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"
SLIPS_PATH = REPO_ROOT / "data" / "slips.csv"
TEMPLATE_DIR = SITE_DIR / "templates"
STATIC_DIR = SITE_DIR / "static"
OUT_DIR = SITE_DIR / "_site"

# Public site URL (GitHub Pages project site).
SITE_BASE = "https://radiojupiter.github.io/launch-delay-watch"
SITE_PATH_PREFIX = "/launch-delay-watch"  # relative asset/base for project pages

# Pad classification for Texas visibility page (keyword match on pad label).
TEXAS_PAD_KEYWORDS = ("starbase", "boca chica", "tx, usa", "texas")
CAPE_PAD_KEYWORDS = (
    "cape canaveral",
    "kennedy space center",
    "kennedy space",
    "canaveral",
)

MIN_SLIP_SAMPLES = 3  # below this, show "not enough history yet"


def slugify(text: str) -> str:
    """URL-safe slug from a provider/rocket name."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "unknown"


def parse_net(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def read_latest_snapshot() -> tuple[Path | None, list[dict[str, str]]]:
    if not SNAPSHOT_DIR.is_dir():
        return None, []
    files = sorted(SNAPSHOT_DIR.glob("????-??-??.csv"))
    if not files:
        return None, []
    path = files[-1]
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return path, rows


def read_slips() -> list[dict[str, Any]]:
    if not SLIPS_PATH.is_file():
        return []
    with SLIPS_PATH.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out: list[dict[str, Any]] = []
    for row in rows:
        if not any(str(v).strip() for k, v in row.items() if k != "id"):
            continue
        slip = row.get("slip_days", "")
        try:
            slip_f = float(slip) if slip not in ("", None) else None
        except ValueError:
            slip_f = None
        item = dict(row)
        item["slip_days"] = slip_f
        out.append(item)
    return out


def enrich_launches(rows: list[dict[str, str]], now: datetime) -> list[dict[str, Any]]:
    launches: list[dict[str, Any]] = []
    for row in rows:
        net = parse_net(row.get("net", ""))
        days_out = None
        countdown = ""
        if net is not None:
            delta = net - now
            days_out = delta.total_seconds() / 86400.0
            if days_out < 0:
                countdown = "NET passed / in progress"
            elif days_out < 1:
                hours = int(delta.total_seconds() // 3600)
                countdown = f"{hours}h"
            elif days_out < 14:
                countdown = f"{days_out:.1f} days"
            else:
                countdown = f"{int(days_out)} days"
        pad = row.get("pad") or ""
        pad_l = pad.lower()
        is_texas = any(k in pad_l for k in TEXAS_PAD_KEYWORDS)
        is_cape = any(k in pad_l for k in CAPE_PAD_KEYWORDS)
        launches.append(
            {
                **row,
                "net_dt": net,
                "net_display": (
                    net.strftime("%Y-%m-%d %H:%M UTC") if net else (row.get("net") or "—")
                ),
                "days_out": days_out,
                "countdown": countdown,
                "provider_slug": slugify(row.get("provider") or "unknown"),
                "rocket_slug": slugify(row.get("rocket") or "unknown"),
                "is_texas": is_texas,
                "is_cape": is_cape,
                "is_texas_visible": is_texas or is_cape,
            }
        )
    launches.sort(key=lambda x: x["net_dt"] or datetime.max.replace(tzinfo=timezone.utc))
    return launches


def slip_stats(slips: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    """Aggregate slip_days by provider or rocket."""
    groups: dict[str, list[float]] = defaultdict(list)
    for row in slips:
        name = (row.get(key) or "").strip() or "(unknown)"
        val = row.get("slip_days")
        if val is None:
            continue
        groups[name].append(float(val))

    stats: dict[str, dict[str, Any]] = {}
    for name, vals in groups.items():
        n = len(vals)
        mean = sum(vals) / n if n else 0.0
        ordered = sorted(vals)
        mid = n // 2
        median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2 if n else 0.0
        delayed = sum(1 for v in vals if v > 0)
        delay_sum = sum(v for v in vals if v > 0)
        enough = n >= MIN_SLIP_SAMPLES
        stats[name] = {
            "name": name,
            "slug": slugify(name),
            "n": n,
            "mean": mean,
            "median": median,
            "delayed": delayed,
            "delay_sum": delay_sum,
            "enough": enough,
        }
    return stats


def latest_slips_for_home(slips: list[dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    """Most recent snapshot_b slips, delayed first."""
    if not slips:
        return []
    # Prefer rows from the newest snapshot_b
    by_b: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in slips:
        by_b[str(row.get("snapshot_b") or "")].append(row)
    if not by_b:
        return []
    newest = sorted(by_b.keys())[-1]
    rows = [r for r in by_b[newest] if r.get("slip_days") is not None]
    rows.sort(key=lambda r: float(r["slip_days"]), reverse=True)
    out = []
    for r in rows[:limit]:
        item = dict(r)
        item["slip_display"] = f"{float(r['slip_days']):+.2f}"
        out.append(item)
    return out


def make_env(base_path: str) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["base_path"] = base_path
    env.globals["site_base"] = SITE_BASE
    env.globals["slugify"] = slugify
    return env


def write_page(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def build_sitemap(paths: list[str], out: Path) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for p in paths:
        loc = f"{SITE_BASE}/{p}" if p else f"{SITE_BASE}/"
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(loc)}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_robots(out: Path) -> None:
    out.write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {SITE_BASE}/sitemap.xml\n",
        encoding="utf-8",
    )


def copy_static(dest: Path) -> None:
    if STATIC_DIR.is_dir():
        target = dest / "static"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(STATIC_DIR, target)


def build(out_dir: Path | None = None, base_path: str | None = None) -> dict[str, Any]:
    """Generate the static site. Returns a small summary dict."""
    dest = out_dir or OUT_DIR
    prefix = SITE_PATH_PREFIX if base_path is None else base_path
    # For local preview without Pages path, pass base_path=""
    now = datetime.now(timezone.utc)

    snap_path, raw_rows = read_latest_snapshot()
    launches = enrich_launches(raw_rows, now)
    slips = read_slips()
    provider_stats = slip_stats(slips, "provider")
    rocket_stats = slip_stats(slips, "rocket")
    recent_slips = latest_slips_for_home(slips)

    # Index maps for detail pages
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_rocket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for launch in launches:
        by_provider[launch["provider"] or "Unknown"].append(launch)
        by_rocket[launch["rocket"] or "Unknown"].append(launch)

    texas = [L for L in launches if L["is_texas"]]
    cape = [L for L in launches if L["is_cape"]]

    snapshot_date = snap_path.stem if snap_path else "none"
    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    env = make_env(prefix)
    common = {
        "generated_at": generated_at,
        "snapshot_date": snapshot_date,
        "launch_count": len(launches),
        "slip_count": len(slips),
        "has_slip_history": len(slips) > 0,
        "min_slip_samples": MIN_SLIP_SAMPLES,
    }

    sitemap_paths: list[str] = [
        "",
        "providers/",
        "rockets/",
        "texas/",
        "about/",
        "privacy/",
    ]

    # Home
    home = env.get_template("index.html").render(
        **common,
        page_title="Launch Delay Watch — rocket schedule slips, open data",
        meta_description=(
            "Free auto-updating tracker of upcoming rocket launches and how far "
            "NET dates slip, by provider and vehicle. Open dataset from Launch Library 2."
        ),
        canonical_path="",
        upcoming=launches[:40],
        recent_slips=recent_slips,
        top_providers=sorted(
            by_provider.items(), key=lambda kv: len(kv[1]), reverse=True
        )[:12],
        provider_stats=provider_stats,
        rocket_stats=rocket_stats,
    )
    write_page(dest / "index.html", home)

    # Providers index + detail
    providers_sorted = sorted(by_provider.keys(), key=str.lower)
    providers_index = env.get_template("providers.html").render(
        **common,
        page_title="Providers — Launch Delay Watch",
        meta_description="Upcoming launches and slip stats by launch service provider.",
        canonical_path="providers/",
        providers=providers_sorted,
        by_provider=by_provider,
        provider_stats=provider_stats,
    )
    write_page(dest / "providers" / "index.html", providers_index)

    for name, items in by_provider.items():
        slug = slugify(name)
        sitemap_paths.append(f"providers/{slug}/")
        stats = provider_stats.get(name)
        page = env.get_template("provider.html").render(
            **common,
            page_title=f"{name} launches & slip stats — Launch Delay Watch",
            meta_description=f"Upcoming {name} launches and NET date slip statistics.",
            canonical_path=f"providers/{slug}/",
            provider_name=name,
            launches=items,
            stats=stats,
        )
        write_page(dest / "providers" / slug / "index.html", page)

    # Rockets index + detail
    rockets_sorted = sorted(by_rocket.keys(), key=str.lower)
    rockets_index = env.get_template("rockets.html").render(
        **common,
        page_title="Rockets — Launch Delay Watch",
        meta_description="Upcoming launches and slip stats by rocket configuration.",
        canonical_path="rockets/",
        rockets=rockets_sorted,
        by_rocket=by_rocket,
        rocket_stats=rocket_stats,
    )
    write_page(dest / "rockets" / "index.html", rockets_index)

    for name, items in by_rocket.items():
        slug = slugify(name)
        sitemap_paths.append(f"rockets/{slug}/")
        stats = rocket_stats.get(name)
        page = env.get_template("rocket.html").render(
            **common,
            page_title=f"{name} launches & slip stats — Launch Delay Watch",
            meta_description=f"Upcoming {name} launches and NET date slip statistics.",
            canonical_path=f"rockets/{slug}/",
            rocket_name=name,
            launches=items,
            stats=stats,
        )
        write_page(dest / "rockets" / slug / "index.html", page)

    # Texas visibility
    texas_page = env.get_template("texas.html").render(
        **common,
        page_title="Launches visible from Texas — Launch Delay Watch",
        meta_description=(
            "Starbase / Boca Chica Starship launches plus Cape Canaveral and Kennedy "
            "launches that Texas skywatchers often track."
        ),
        canonical_path="texas/",
        texas_launches=texas,
        cape_launches=cape,
    )
    write_page(dest / "texas" / "index.html", texas_page)

    # About / data
    about = env.get_template("about.html").render(
        **common,
        page_title="About & data — Launch Delay Watch",
        meta_description=(
            "How Launch Delay Watch works, dataset download links, and attribution "
            "to The Space Devs Launch Library 2."
        ),
        canonical_path="about/",
        snapshot_filename=snap_path.name if snap_path else None,
    )
    write_page(dest / "about" / "index.html", about)

    # Privacy
    privacy = env.get_template("privacy.html").render(
        **common,
        page_title="Privacy — Launch Delay Watch",
        meta_description="Privacy policy for the Launch Delay Watch static site.",
        canonical_path="privacy/",
    )
    write_page(dest / "privacy" / "index.html", privacy)

    copy_static(dest)
    build_sitemap(sitemap_paths, dest / "sitemap.xml")
    build_robots(dest / "robots.txt")

    # Manifest for debugging / CI
    manifest = {
        "generated_at": generated_at,
        "snapshot_date": snapshot_date,
        "launch_count": len(launches),
        "slip_count": len(slips),
        "provider_pages": len(by_provider),
        "rocket_pages": len(by_rocket),
        "texas_count": len(texas),
        "cape_count": len(cape),
        "pages": len(sitemap_paths),
        "content_hash": hashlib.sha256(
            (snapshot_date + str(len(launches)) + str(len(slips))).encode()
        ).hexdigest()[:12],
    }
    (dest / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Build Launch Delay Watch static site")
    p.add_argument(
        "--out",
        type=Path,
        default=OUT_DIR,
        help="Output directory (default: site/_site)",
    )
    p.add_argument(
        "--base-path",
        default=None,
        help='URL path prefix (default: /launch-delay-watch). Use "" for local root.',
    )
    args = p.parse_args()
    summary = build(out_dir=args.out, base_path=args.base_path)
    print(f"Built site → {args.out}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
