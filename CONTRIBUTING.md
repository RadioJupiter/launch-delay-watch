# Contributing to Launch Delay Watch

Thanks for helping track launch schedule pressure in the open.

## Development setup

```bash
git clone https://github.com/RadioJupiter/launch-delay-watch.git
cd launch-delay-watch
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

## Guidelines

1. **Do not fabricate launch data.** Snapshots must come from Launch Library 2 (or another attributed public source). Tests use fixtures only.
2. **Respect the free-tier rate limit** (~15 requests/hour). Prefer a single `limit=100` call; do not scrape or parallelize aggressively.
3. **Keep snapshot schema stable.** If you add columns, document them in the README and keep older CSVs readable.
4. **Tests must not hit the network.** Inject sessions or use `tests/fixtures/`.
5. Run `ruff check` and `pytest` before opening a PR.

## Useful tasks

* Improve slip metrics (pad congestion, vehicle family rollups)
* Add a small static site or notebook that charts `data/slips.csv`
* Mirror additional public schedule fields (probability, hold reason) without breaking diffs
* Packaging / PyPI release automation

## Data license note

Code is MIT. Launch records originate from [The Space Devs Launch Library 2](https://thespacedevs.com/llapi); attribute them and follow their terms when redistributing derived datasets.
