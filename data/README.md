# Data

- `snapshots/YYYY-MM-DD.csv` — daily freeze of the next 100 upcoming launches from Launch Library 2 (The Space Devs). From 2026-11-16 the files include LL2's `net_precision`.
- `slips.csv` — one row per launch per consecutive snapshot pair: `slip_days` (+ = later) plus `precision_a`, `precision_b` and `precision_flag`. Only `precision_flag == ok` rows (both NETs given to the hour or better) count in slip statistics; see the README's Method section.

Launch records are The Space Devs' data, used under their [terms of use](https://github.com/TheSpaceDevs/Tutorials/blob/main/faqs/faq_TSD.md#terms-of-use); please credit "Launch Library 2 by The Space Devs" when reusing them.

Do not hand-edit these files with invented launches. Regenerate via `ldw snapshot` / `ldw rebuild`.
