"""Calendar helpers for GoldDesk.

Several BrsApi columns used by GoldDesk store **Shamsi (Jalali)** date strings
(``YYYY-MM-DD``):

* ``brsapi_gold_coin_history.date`` — gold/coin OHLC history
* ``brsapi_nav_records.date`` — fund NAV records
* ``brsapi_historical_real_legal.date`` — daily real/legal volume

Comparing a Gregorian ISO string against those columns silently matches **zero
rows** (audit finding GS-03), which is why every backtest path used to report
"no data". All cutoffs must therefore be built in the same calendar as the
stored data, via :func:`jalali_days_ago`.
"""

from __future__ import annotations

from datetime import timedelta

from core.time import now_tehran


def jalali_days_ago(days: int) -> str:
    """Return the Shamsi date ``days`` days before today as ``YYYY-MM-DD``.

    The result is zero-padded so it can be compared lexicographically against
    the Shamsi ``date`` columns (``'1405-06-23'`` style).
    """
    import jdatetime

    gregorian = now_tehran().date() - timedelta(days=days)
    j = jdatetime.date.fromgregorian(date=gregorian)
    return f"{j.year:04d}-{j.month:02d}-{j.day:02d}"


__all__ = ["jalali_days_ago"]
