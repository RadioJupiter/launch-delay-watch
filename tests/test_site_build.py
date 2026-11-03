"""Tests for the static site generator (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from site_build_helper import import_build_module

build_mod = import_build_module()


def test_slugify():
    assert build_mod.slugify("SpaceX") == "spacex"
    assert build_mod.slugify("Falcon 9 Block 5") == "falcon-9-block-5"
    assert build_mod.slugify("  ") == "unknown"


def test_build_writes_core_pages(tmp_path: Path):
    out = tmp_path / "site"
    summary = build_mod.build(out_dir=out, base_path="/launch-delay-watch")
    assert (out / "index.html").is_file()
    assert (out / "providers" / "index.html").is_file()
    assert (out / "rockets" / "index.html").is_file()
    assert (out / "texas" / "index.html").is_file()
    assert (out / "about" / "index.html").is_file()
    assert (out / "privacy" / "index.html").is_file()
    assert (out / "sitemap.xml").is_file()
    assert (out / "robots.txt").is_file()
    assert (out / "static" / "style.css").is_file()
    assert (out / "build-manifest.json").is_file()
    manifest = json.loads((out / "build-manifest.json").read_text())
    assert manifest["launch_count"] == summary["launch_count"]
    assert summary["launch_count"] >= 1
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Launch Delay Watch" in html
    assert "not enough history yet" in html.lower() or summary["slip_count"] > 0
    assert "The Space Devs" in (out / "about" / "index.html").read_text(encoding="utf-8")
    robots = (out / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap:" in robots
    # Texas page mentions Starbase or Cape
    texas = (out / "texas" / "index.html").read_text(encoding="utf-8")
    assert "Starbase" in texas or "Cape" in texas


def test_provider_and_rocket_pages_exist(tmp_path: Path):
    out = tmp_path / "site"
    build_mod.build(out_dir=out, base_path="")
    providers = list((out / "providers").glob("*/index.html"))
    rockets = list((out / "rockets").glob("*/index.html"))
    assert len(providers) >= 1
    assert len(rockets) >= 1
    # SpaceX should be present in current fixture snapshot
    assert (out / "providers" / "spacex" / "index.html").is_file()
