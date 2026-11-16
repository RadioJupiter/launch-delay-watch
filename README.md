# Launch Delay Watch

[![CI](https://github.com/RadioJupiter/launch-delay-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/RadioJupiter/launch-delay-watch/actions/workflows/ci.yml)
[![Daily snapshot](https://github.com/RadioJupiter/launch-delay-watch/actions/workflows/daily-snapshot.yml/badge.svg)](https://github.com/RadioJupiter/launch-delay-watch/actions/workflows/daily-snapshot.yml)
[![License: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)

**Open dataset + Python library/CLI that tracks how far rocket launch NET dates slip** — by vehicle, provider, and pad.

Every day we freeze the public [no-earlier-than (NET)](https://en.wikipedia.org/wiki/NET_(date)) schedule for the next ~100 upcoming launches. Diffing consecutive snapshots measures schedule pressure: how often, and by how many days, launches move later. It is built only from public data and is meant as an observational record, not an official schedule.

| | |
|---|---|
| **CLI** | `ldw snapshot` · `ldw diff` · `ldw stats` · `ldw chart` · `ldw headline` · `ldw rebuild` |
| **Data** | [`data/snapshots/`](data/snapshots/) (daily) → [`data/slips.csv`](data/slips.csv) (cumulative) · [site downloads](https://radiojupiter.github.io/launch-delay-watch/data/) |
| **Source** | [Launch Library 2](https://thespacedevs.com/llapi) by [The Space Devs](https://thespacedevs.com/) |
| **License** | MIT for the code; launch records are The Space Devs' data under [their terms](#data-source-terms--attribution) |

## Website

Public auto-updating site (GitHub Pages):

**https://radiojupiter.github.io/launch-delay-watch/**

Built from the CSVs in `data/` by `site/build.py` (Python + Jinja2). Redeploys on push to `main`, after the daily snapshot workflow, and on a daily schedule. No Launch Library API calls at build time.

```bash
python site/build.py
# open site/_site/index.html (use --base-path "" for local root links)
```

## Why this exists

Reporters, analysts, and hobbyists can see that launches slip, and some launch-tracking sites show a date history for individual launches. Launch Delay Watch aims to be a plain, versioned, machine-readable **history of those slips across all upcoming launches**, with the method and code in the open. It is deliberately narrow:

1. Snapshot the public NET.
2. Diff it.
3. Publish the CSV so anyone can chart provider/vehicle delay without reinventing the fetch.

## Method

1. **Snapshot.** Once a day, one request to the Launch Library 2 `launch/upcoming` endpoint (`limit=100`) is saved as `data/snapshots/YYYY-MM-DD.csv` (UTC date).
2. **Compare.** Each snapshot is diffed against the previous day's. Every launch present in both files is one *comparison*: `slip_days = NET(new) − NET(old)` in days, positive = later.
3. **Filter placeholder dates.** When Launch Library 2 only knows the day, month, quarter or year of a launch, it publishes a placeholder NET such as `2026-11-30T00:00:00Z` ("sometime in November"). Swapping a placeholder for a real time (or back) can look like a 17-day "slip" that never happened. Each NET is therefore classed as `timed` (hour, minute or second precision), `day`, or `coarse` (month or longer), and each comparison gets a `precision_flag`:
   * `ok`: both NETs timed. **Only these count in slip statistics.**
   * `precision_change`: the class changed (placeholder set or replaced). Listed separately, never counted as a slip.
   * `low_precision`: the same placeholder class on both days (e.g. a launch still listed as "2026" both days).
   `--include-low-precision` on `ldw diff`, `ldw stats` and `ldw chart` puts the excluded rows back.
4. **Count slips.** A *slip* is a timed NET moving later by at least 1 hour (`--min-hours`). Smaller moves are T-0 refinements, such as liftoff late in the launch window, and are reported as minor adjustments.

**Where precision comes from.** Snapshots from 2026-11-16 onward store Launch Library 2's own `net_precision` field. Earlier snapshots did not record it, so a heuristic is used for them: a NET at exactly 00:00:00 UTC with a zero-length launch window is a placeholder (month-or-coarser if it falls on the last day of a month, otherwise day). Checked against the live `net_precision` field on 2026-11-16, the heuristic agreed on all 100 upcoming launches.

**Reproduce every published number:**

```bash
pip install -e .
ldw rebuild      # recompute data/slips.csv from all snapshots (deterministic)
ldw headline     # prints every count, percentage and per-launch slip used in write-ups
ldw chart --kind timeline --top 5 --out net_timeline.png
ldw chart --by rocket --out slip_by_rocket.png
```

## Limitations

* **Daily sampling.** One snapshot per day (the scheduled run usually starts in the afternoon UTC, not at a fixed minute). A date that moves and moves back within a day is missed, and a launch that moves twice in a day counts once, so slip counts are a lower bound.
* **Window of 100.** Only the next 100 upcoming launches are captured; launches further out enter the record when they come into that window.
* **NET is a public target.** It is not an official range schedule. Launch Library 2 is curated by volunteers from public sources and can lag or differ from provider statements; The Space Devs do not guarantee accuracy.
* **Small sample.** The record starts on 2026-11-03; per-provider and per-vehicle numbers are not yet statistically meaningful.
* **Heuristic precision before 2026-11-16** (see Method). A real launch scheduled at exactly 00:00:00 UTC with no window would be misread as a placeholder.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Pull today's upcoming launches (1 API call, limit=100)
ldw snapshot

# After a second snapshot exists (or on the next daily Action run):
ldw diff                          # placeholder-date changes listed separately
ldw stats --by provider           # timed NETs only; add --include-low-precision for all
ldw chart --by rocket --out slip_by_rocket.png
ldw headline                      # all headline numbers
```

Or from a clone without installing editably:

```bash
pip install pandas requests matplotlib
PYTHONPATH=src python -m launch_delay_watch.cli snapshot
```

## Example: real snapshot (2026-11-03)

Taken live against Launch Library 2 (free tier, single request):

```text
$ ldw snapshot --preview 12 --no-history
Wrote data/snapshots/2026-11-03.csv (100 launches)
                                              name                                           provider            rocket                  net  status
            Kinetica 2 | SpaceSail Polar Group #17                                          CAS Space        Kinetica 2 2026-11-03T00:15:00Z Success
                   Long March 2C | Unknown Payload China Aerospace Science and Technology Corporation     Long March 2C 2026-11-05T16:00:00Z      Go
                         Ceres-2 | Unknown Payload                                    Galactic Energy           Ceres-2 2026-11-06T23:35:00Z      Go
                       Falcon 9 Block 5 | USSF-432                                             SpaceX  Falcon 9 Block 5 2026-11-07T00:46:00Z      Go
             Long March 12 | SatNet LEO Group TBD? China Aerospace Science and Technology Corporation     Long March 12 2026-11-08T20:25:00Z      Go
               Falcon 9 Block 5 | USSF-xxx ("R-5")                                             SpaceX  Falcon 9 Block 5 2026-11-10T03:03:00Z     TBC
               Falcon 9 Block 5 | USSF-xxx ("R-6")                                             SpaceX  Falcon 9 Block 5 2026-11-13T04:23:00Z     TBC
                  Vulcan VC6L | Amazon Leo (LV-01)                             United Launch Alliance       Vulcan VC6L 2026-11-13T17:54:00Z      Go
Electron | The Mountain God Rises (iQPS Launch 10)                                         Rocket Lab          Electron 2026-11-14T00:00:00Z     TBD
             Long March 8A | SatNet LEO Group TBD? China Aerospace Science and Technology Corporation     Long March 8A 2026-11-20T11:00:00Z     TBC
            Ariane 64 Block 2 | Amazon Leo (LE-04)                                        Arianespace Ariane 64 Block 2 2026-11-23T00:00:00Z     TBD
                 Soyuz 2.1b | Progress MS-36 (97P)           Russian Federal Space Agency (ROSCOSMOS)        Soyuz 2.1b 2026-11-24T05:03:00Z     TBC
```

Provider mix in that file (top counts): SpaceX 37 · ULA 12 · Rocket Lab 10 · CASC 7 · ISRO 5 · …

`data/slips.csv` starts with headers only until a **second** dated snapshot lands (the daily GitHub Action handles that). Then `ldw snapshot` appends matched launches with `slip_days` (positive = NET moved later).

```text
$ ldw diff                          # last two snapshots
$ ldw stats --by provider           # mean / median / delay mass (timed NETs only)
$ ldw chart --by provider           # writes data/slip_by_provider.png
$ ldw chart --kind timeline         # NET vs snapshot date for the launches that slipped
```

## Dataset schema

### `data/snapshots/YYYY-MM-DD.csv`

| column | meaning |
|--------|---------|
| `id` | Launch Library 2 UUID |
| `name` | Launch name (`Vehicle \| Mission`) |
| `provider` | Launch service provider |
| `rocket` | Vehicle configuration full name |
| `pad` | Pad name plus location |
| `net` | No-earlier-than time (UTC, ISO-8601) |
| `status` | Status abbrev (`Go`, `TBD`, `TBC`, `Success`, …) |
| `window_start` / `window_end` | Launch window bounds (UTC) |
| `net_precision` | LL2 precision of the NET (`Second`, `Minute`, `Hour`, `Day`, `Month`, `Quarter 4`, `Year`, …); empty before 2026-11-16 |

### `data/slips.csv`

| column | meaning |
|--------|---------|
| `id` | Same launch UUID |
| `name`, `provider`, `rocket`, `pad` | From the newer snapshot when present |
| `snapshot_a` / `snapshot_b` | Date stems compared |
| `net_a` / `net_b` | NET before / after |
| `slip_days` | `(net_b − net_a)` in days; **+ = delayed** |
| `status_a` / `status_b` | Status at each snapshot |
| `precision_a` / `precision_b` | `timed`, `day` or `coarse` (see [Method](#method)) |
| `precision_flag` | `ok` (counted), `precision_change` or `low_precision` (excluded by default) |

Launches that appear in only one snapshot (flew, scrubbed from the feed, or newly announced) are omitted from that pair’s diff.

## Library API

```python
from pathlib import Path
from launch_delay_watch import fetch_upcoming, write_snapshot, compare_snapshots, summarize_slips

df = fetch_upcoming()                 # one HTTP call
path = write_snapshot(df)             # data/snapshots/YYYY-MM-DD.csv
delta = compare_snapshots(
    Path("data/snapshots/2026-11-03.csv"),
    Path("data/snapshots/2026-11-04.csv"),
)
print(summarize_slips(delta, by="rocket"))
```

## Automation

* **CI** (`.github/workflows/ci.yml`) — ruff + pytest on Python 3.10 / 3.12 / 3.13.
* **Daily snapshot** (`.github/workflows/daily-snapshot.yml`) — cron `0 14 * * *` UTC (GitHub often starts scheduled runs hours late; the exact capture time of each file is in the commit history), runs `ldw snapshot`, commits under `data/` with `contents: write` via `GITHUB_TOKEN`.
* **Pages** (`.github/workflows/pages.yml`) — rebuilds the site after each snapshot and on push.

Rate limit: we intentionally use **one** `limit=100&mode=normal` request per day, far below the free Launch Library 2 tier of 15 requests per hour, and the site is built from the committed CSVs so visitors never call the API.

## Data source, terms & attribution

Launch records come from **[Launch Library 2](https://thespacedevs.com/llapi)** (API v2.2.0) operated by **[The Space Devs](https://thespacedevs.com/)**, a community-funded nonprofit. This project is not affiliated with The Space Devs.

Their [terms of use](https://github.com/TheSpaceDevs/Tutorials/blob/main/faqs/faq_TSD.md#terms-of-use) allow free use and sharing of the data, ask that it not be forwarded without adding value, encourage attribution, and state that accuracy cannot be guaranteed. This project adds value by keeping a dated history of the schedule and computing day-over-day changes; it credits The Space Devs on every page, chart and export, and stays far under the free-tier rate limit by caching one request per day. If you reuse the CSVs, please credit "Launch Library 2 by The Space Devs" as the source of the launch records. The MIT license covers this repository's code; it does not relicense The Space Devs' data.

NET dates and statuses can change without notice; treat slips as observational, not official range statements.

## How to cite

See [`CITATION.cff`](CITATION.cff) (GitHub shows a "Cite this repository" button). Plain text:

> RadioJupiter (2026). *Launch Delay Watch: daily snapshots of public rocket launch NET dates and their day-over-day changes* [Data set and software]. https://github.com/RadioJupiter/launch-delay-watch. Launch records from Launch Library 2 by The Space Devs.

Please also credit The Space Devs for the underlying launch records.

## Roadmap

- [x] First week of cumulative `slips.csv` from the daily Action
- [x] Static site over the committed CSVs
- [x] Placeholder-date (NET precision) filter
- [ ] Pad-congestion and vehicle-family rollups
- [ ] Optional PyPI release (`pip install launch-delay-watch`)
- [ ] Hold-reason / probability fields once schema-compatible

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Short version: no fabricated launch rows, no network in tests, keep the free-tier polite.

## License

[MIT](LICENSE) © 2026 RadioJupiter
