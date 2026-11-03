# Launch Delay Watch

**Open dataset + Python library/CLI that tracks how far rocket launch NET dates slip** — by vehicle, provider, and pad.

Every day we freeze the public [no-earlier-than (NET)](https://en.wikipedia.org/wiki/NET_(date)) schedule for the next ~100 upcoming launches. Diffing consecutive snapshots measures schedule pressure: how often, and by how many days, launches move later. That is a concrete signal for pad congestion, vehicle backlog, and the broader “rocket shortage” conversation — built only from public data.

| | |
|---|---|
| **CLI** | `ldw snapshot` · `ldw diff` · `ldw stats` · `ldw chart` |
| **Data** | [`data/snapshots/`](data/snapshots/) (daily) → [`data/slips.csv`](data/slips.csv) (cumulative) |
| **Source** | [Launch Library 2](https://thespacedevs.com/llapi) by [The Space Devs](https://thespacedevs.com/) |
| **License** | MIT (code); attribute The Space Devs for launch records |

## Website

Public auto-updating site (GitHub Pages):

**https://radiojupiter.github.io/launch-delay-watch/**

Built from the CSVs in `data/` by `site/build.py` (Python + Jinja2). Redeploys on push to `main`, after the daily snapshot workflow, and on a daily schedule. No Launch Library API calls at build time.

```bash
python site/build.py
# open site/_site/index.html (use --base-path "" for local root links)
```

## Why this exists

Reporters, analysts, and hobbyists can see that launches slip — but there has not been a small, open, machine-readable **history of those slips**. Proprietary schedule tools are closed; one-off scrapes go stale. Launch Delay Watch is deliberately narrow:

1. Snapshot the public NET.
2. Diff it.
3. Publish the CSV so anyone can chart provider/vehicle delay without reinventing the fetch.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Pull today's upcoming launches (1 API call, limit=100)
ldw snapshot

# After a second snapshot exists (or on the next daily Action run):
ldw diff
ldw stats --by provider
ldw chart --by rocket --out slip_by_rocket.png
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
$ ldw stats --by provider           # mean / median / delay mass
$ ldw chart --by provider           # writes data/slip_by_provider.png
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

### `data/slips.csv`

| column | meaning |
|--------|---------|
| `id` | Same launch UUID |
| `name`, `provider`, `rocket`, `pad` | From the newer snapshot when present |
| `snapshot_a` / `snapshot_b` | Date stems compared |
| `net_a` / `net_b` | NET before / after |
| `slip_days` | `(net_b − net_a)` in days; **+ = delayed** |
| `status_a` / `status_b` | Status at each snapshot |

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
* **Daily snapshot** (`.github/workflows/daily-snapshot.yml`) — cron `0 14 * * *` UTC, runs `ldw snapshot`, commits under `data/` with `contents: write` via `GITHUB_TOKEN`.

Rate limit: we intentionally use **one** `limit=100&mode=normal` request per snapshot so the free Launch Library 2 tier (~15 req/hour) stays happy.

## Data source & attribution

Launch records come from **[Launch Library 2](https://ll.thespacedevs.com/2.2.0)** operated by **[The Space Devs](https://thespacedevs.com/)**. This project is not affiliated with The Space Devs. Please follow their API terms and attribute them when you republish derived data. NET dates and statuses can change without notice; treat slips as observational, not official range statements.

## Roadmap

- [ ] First week of cumulative `slips.csv` from the daily Action
- [ ] Pad-congestion and vehicle-family rollups
- [ ] Optional PyPI release (`pip install launch-delay-watch`)
- [ ] Small static chart page over the committed CSVs
- [ ] Hold-reason / probability fields once schema-compatible

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Short version: no fabricated launch rows, no network in tests, keep the free-tier polite.

## License

[MIT](LICENSE) © 2026 RadioJupiter
