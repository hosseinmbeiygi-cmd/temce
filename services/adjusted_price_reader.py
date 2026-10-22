"""Adjusted-price reads for the indicator layer (audit §2, migrations 0108/0109).

Indicators (the nightly ``stock_indicators_snapshot`` precompute and the JIT
read-through) must not see raw TSETMC prices: a capital increase halves the
price overnight, so a raw 200-day MA, RSI or MACD that spans the ex-date is
wrong for the rest of that window. Migration 0061 materialised the cumulative
factor per ``(symbol_id, trade_date)``; this module is the read side —
``vw_daily_history_adjusted`` returns every daily bar plus ``adj_factor`` and
``price_*_adj``.

Two calendars, on purpose (Iranian convention): every candle carries the
Gregorian ``date`` used by the maths **and** ``date_shamsi`` for display.

Two safety properties:

* **Fallback, never a hard failure.** If the view is missing (migration not
  applied yet) or ``INDICATOR_ADJUSTED_PRICES=false``, the reader falls back
  to the raw ``daily_history`` columns. Indicator output is then identical to
  the pre-0108 behaviour (``date_shamsi`` is ``None`` in that mode).
* **Cheap.** The view is not materialised and the query orders by
  ``trade_date_shamsi``, which is the leading edge of
  ``idx_hist_symbol_date`` — so the planner stops the index scan after
  ``LIMIT`` rows and only then derives the Gregorian date. Measured on the
  5.45 M-row dev DB: 13 ms warm for a 320-candle read. Ordering by the
  *derived* Gregorian column instead costs 113 ms because it has to derive a
  date for every row of the symbol before sorting (Jalali ``YYYY-MM-DD``
  strings sort chronologically, so the order is identical).

Deliberate convention: volume/value/count are **not** scaled (matches
``yfinance``'s ``auto_adjust``), and percentage-change columns are left raw
because a constant per-day factor cancels out of an intra-day ratio.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

ADJUSTED_VIEW = "vw_daily_history_adjusted"
RAW_SOURCE = "daily_history"

# Process-level cache of the view-existence probe (one catalog lookup per
# process instead of one per symbol) — mirrors the restart-to-flip behaviour
# of the other rollout dials in this codebase. Ops note: after applying
# migration 0108/0109 to a running API process, call
# ``reset_adjusted_source_cache()`` (or restart) to pick the view up.
_view_available: bool | None = None

# Adjusted mode reads the view (true trade date in both calendars + factor);
# raw mode stays byte-for-byte the pre-0108 loader. Both alias the price
# columns back to the raw names so ``build_candles`` is source-agnostic and
# both return 8 columns in the same order.
_ADJUSTED_CANDLE_SQL = """
SELECT d.trade_date, d.trade_date_shamsi,
       d.price_first_adj, d.price_max_adj, d.price_min_adj, d.price_last_adj,
       d.trade_volume, d.trade_value
FROM vw_daily_history_adjusted d
WHERE d.symbol = :sym
  AND d.price_last IS NOT NULL
  AND d.trade_date_shamsi IS NOT NULL
ORDER BY d.trade_date_shamsi DESC
LIMIT :lim
"""

_RAW_CANDLE_SQL = """
SELECT d.trade_date, NULL AS trade_date_shamsi,
       d.price_first, d.price_max, d.price_min, d.price_last,
       d.trade_volume, d.trade_value
FROM daily_history d
WHERE d.symbol = :sym AND d.price_last IS NOT NULL
ORDER BY d.trade_date DESC
LIMIT :lim
"""

_SQL_BY_SOURCE = {
    (ADJUSTED_VIEW, True): _ADJUSTED_CANDLE_SQL,
    (RAW_SOURCE, False): _RAW_CANDLE_SQL,
}


def adjustment_enabled() -> bool:
    """Operator dial: ``INDICATOR_ADJUSTED_PRICES`` (default on)."""
    return bool(getattr(settings, "indicator_adjusted_prices", True))


def build_candle_query(source: str, adjusted: bool) -> str:
    """Render the candle SQL for a source (view/table) and adjustment mode."""
    try:
        return _SQL_BY_SOURCE[(source, adjusted)]
    except KeyError:  # pragma: no cover - programming error
        raise ValueError(f"no candle query for source={source!r} adjusted={adjusted}") from None


def build_candles(rows: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    """Shape rows → candles, oldest first.

    Row shape (both sources): ``(trade_date, trade_date_shamsi, first, max,
    min, last, volume, value)``, newest first. A missing OHLC leg falls back
    to the close; a row whose Gregorian trade date could not be derived from
    its Jalali counterpart is dropped (cannot be placed on a time axis).
    """
    candles: list[dict[str, Any]] = []
    for r in reversed(rows):
        if r[0] is None:
            continue
        candles.append(
            {
                "date": str(r[0]),
                "date_shamsi": str(r[1]) if r[1] else None,
                "open": float(r[2] or r[5]),
                "high": float(r[3] or r[5]),
                "low": float(r[4] or r[5]),
                "close": float(r[5]),
                "volume": float(r[6] or 0),
                "value": float(r[7] or 0),
            }
        )
    return candles


async def adjusted_view_available(session: AsyncSession) -> bool:
    """Is ``vw_daily_history_adjusted`` present? Cached per process."""
    global _view_available
    if _view_available is None:
        try:
            found = (
                await session.execute(text(f"SELECT to_regclass('public.{ADJUSTED_VIEW}')"))
            ).scalar()
            _view_available = found is not None
        except Exception as exc:  # noqa: BLE001 — never block indicator reads
            logger.warning("adjusted-price view probe failed (%s); using raw prices", exc)
            return False
        if not _view_available:
            logger.warning(
                "%s not found — indicators fall back to RAW prices until "
                "migration 0108 is applied and the process restarts",
                ADJUSTED_VIEW,
            )
    return _view_available


def reset_adjusted_source_cache() -> None:
    """Forget the cached probe (tests / after applying migration 0108)."""
    global _view_available
    _view_available = None


async def resolve_price_source(session: AsyncSession) -> tuple[str, bool]:
    """Return ``(source_table_or_view, adjusted)`` for the indicator read path."""
    if adjustment_enabled() and await adjusted_view_available(session):
        return ADJUSTED_VIEW, True
    return RAW_SOURCE, False


async def load_daily_candles(
    session: AsyncSession,
    symbol: str,
    limit: int = 260,
    *,
    adjusted: bool | None = None,
) -> list[dict[str, Any]]:
    """OHLCV candles for one symbol, corporate-action adjusted by default.

    ``adjusted`` overrides the dial (used by backtests/parity checks to read
    the raw series deliberately).
    """
    if adjusted is None:
        source, use_adjusted = await resolve_price_source(session)
    else:
        use_adjusted = bool(adjusted)
        source = ADJUSTED_VIEW if use_adjusted else RAW_SOURCE

    sql = build_candle_query(source, use_adjusted)
    rows = (await session.execute(text(sql), {"sym": symbol, "lim": limit})).fetchall()
    return build_candles(rows)


async def load_daily_candles_range(
    session: AsyncSession,
    symbol: str,
    start: str,
    end: str,
    *,
    adjusted: bool | None = None,
) -> list[dict[str, Any]]:
    """OHLCV candles for one symbol over a date range, corporate-action adjusted by default.

    Args:
        session: Async DB session
        symbol: Symbol/ticker to load
        start: Start date (inclusive) as 'YYYY-MM-DD'
        end: End date (inclusive) as 'YYYY-MM-DD'
        adjusted: Override the adjustment dial. None = use dial.

    Returns:
        List of candle dicts with keys: date, date_shamsi, open, high, low, close, volume, value
    """
    if adjusted is None:
        source, use_adjusted = await resolve_price_source(session)
    else:
        use_adjusted = bool(adjusted)
        source = ADJUSTED_VIEW if use_adjusted else RAW_SOURCE

    sql = build_range_query(source, use_adjusted)
    rows = (await session.execute(text(sql), {"sym": symbol, "start": start, "end": end})).fetchall()
    return build_candles(rows)


def build_range_query(source: str, adjusted: bool) -> str:
    """Render the candle SQL for a source (view/table) and adjustment mode with date range."""
    if adjusted and source == ADJUSTED_VIEW:
        return """
        SELECT d.trade_date, d.trade_date_shamsi,
               d.price_first_adj, d.price_max_adj, d.price_min_adj, d.price_last_adj,
               d.trade_volume, d.trade_value
        FROM vw_daily_history_adjusted d
        WHERE d.symbol = :sym
          AND d.price_last IS NOT NULL
          AND d.trade_date_shamsi IS NOT NULL
          AND d.trade_date >= :start AND d.trade_date <= :end
        ORDER BY d.trade_date ASC
        """
    elif not adjusted and source == RAW_SOURCE:
        return """
        SELECT d.trade_date, NULL AS trade_date_shamsi,
               d.price_first, d.price_max, d.price_min, d.price_last,
               d.trade_volume, d.trade_value
        FROM daily_history d
        WHERE d.symbol = :sym AND d.price_last IS NOT NULL
          AND d.trade_date >= :start AND d.trade_date <= :end
        ORDER BY d.trade_date ASC
        """
    else:
        raise ValueError(f"no candle query for source={source!r} adjusted={adjusted}")


__all__ = [
    "ADJUSTED_VIEW",
    "RAW_SOURCE",
    "adjusted_view_available",
    "adjustment_enabled",
    "build_candle_query",
    "build_range_query",
    "build_candles",
    "load_daily_candles",
    "load_daily_candles_range",
    "reset_adjusted_source_cache",
    "resolve_price_source",
]
