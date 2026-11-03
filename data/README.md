# Data

- `snapshots/YYYY-MM-DD.csv` — daily freeze of upcoming launches from Launch Library 2.
- `slips.csv` — cumulative per-launch NET slip between consecutive snapshots (populated once two or more snapshots exist).

Do not hand-edit these files with invented launches. Regenerate via `ldw snapshot` / `ldw diff --update-history`.
