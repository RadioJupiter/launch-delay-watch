"""Classify how precise a published NET is, so placeholder dates are not read as slips.

Launch Library 2 (LL2) publishes a ``net_precision`` object (``Second``, ``Minute``,
``Hour``, ``Day``, ``Month``, ``Quarter 1``-``4``, ``Half 1``/``2``, ``Year`` ...).
Snapshots taken before 2026-11-16 did not record it, so for those rows we fall
back to a documented heuristic that mirrors how LL2 encodes low-precision NETs:

* A NET at exactly ``00:00:00Z`` whose launch window has zero length
  (``window_start == window_end``, or no window) is a placeholder.
* If that placeholder falls on the last day of a month, it is a month (or
  coarser: quarter, half, year) placeholder; otherwise it is a day placeholder.
* Everything else is treated as a timed NET (hour precision or better).

Checked against the live LL2 ``net_precision`` field on 2026-11-16 (100 upcoming
launches), the heuristic agreed with LL2 on all 100 rows.

Every NET is reduced to one of three classes, which can be compared whether the
label came from LL2 or from the heuristic:

``timed``   hour, minute or second precision
``day``     the date is known, the time is not
``coarse``  month, quarter, half or year placeholder
"""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

TIMED = "timed"
DAY = "day"
COARSE = "coarse"
UNKNOWN = "unknown"

_TIMED_NAMES = {"second", "minute", "hour"}
_DAY_NAMES = {"day"}

# precision_flag values on each slips.csv row
FLAG_OK = "ok"  # both NETs timed: counted as a real schedule move
FLAG_PRECISION_CHANGE = "precision_change"  # precision class differs between snapshots
FLAG_LOW_PRECISION = "low_precision"  # same non-timed class in both snapshots


def _parse(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def class_from_ll2(name: object) -> str:
    """Map an LL2 ``net_precision`` name to timed/day/coarse ('' if absent)."""
    text = str(name or "").strip().lower()
    if not text or text == "nan":
        return ""
    if text in _TIMED_NAMES:
        return TIMED
    if text in _DAY_NAMES:
        return DAY
    return COARSE


def infer_class(net: object, window_start: object = "", window_end: object = "") -> str:
    """Heuristic precision class for a NET when LL2's ``net_precision`` is missing."""
    dt = _parse(net)
    if dt is None:
        return UNKNOWN
    midnight = dt.hour == 0 and dt.minute == 0 and dt.second == 0
    ws = _parse(window_start) or dt
    we = _parse(window_end) or dt
    if midnight and ws == we:
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        return COARSE if dt.day == last_day else DAY
    return TIMED


def resolve_class(
    net: object,
    window_start: object = "",
    window_end: object = "",
    net_precision: object = "",
) -> tuple[str, str]:
    """Return ``(class, source)`` where source is ``ll2`` or ``heuristic``."""
    from_ll2 = class_from_ll2(net_precision)
    if from_ll2:
        return from_ll2, "ll2"
    return infer_class(net, window_start, window_end), "heuristic"


def precision_flag(class_a: str, class_b: str) -> str:
    """Flag one day-over-day comparison by the precision of its two NETs."""
    if class_a == TIMED and class_b == TIMED:
        return FLAG_OK
    if class_a != class_b:
        return FLAG_PRECISION_CHANGE
    return FLAG_LOW_PRECISION
