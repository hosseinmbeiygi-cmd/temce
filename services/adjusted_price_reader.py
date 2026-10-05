"""Adjusted-price reads for the indicator layer (audit §2, migration 0108).

Indicators (the nightly ``stock_indicators_snapshot`` precompute and the JIT
read-through) must not see raw TSETMC prices: a capital increase halves the
price overnight, so a raw 200-day MA, RSI or MACD that spans the ex-date is
wrong for the rest of that window. Migration 0061 materialised the cumulative
factor per ``(symbol_id, trade_date)``; this module is the read side —
``vw_daily_history_adjusted`` returns every ``daily_history`` row plus
``adj_factor`` and ``price_*_adj``.

Two safety properties:

* **Fallback, never a hard failure.** If the view is missing (migration not
  applied yet) or ``INDICATOR_ADJUSTED_PRICES=false``, the reader silently
  falls back to the raw ``daily_history`` column names. Indicator output is
  then identical to the pre-0108 behaviour.
* **Cheap.** The view is a non-materialised view, so the planner pushes
  ``symbol = :sym`` + ``ORDER BY trade_date DESC LIMIT n`` down to
  ``idx_hist_symbol_gregorian``; the factor lookup is one primary-key probe
  per returned row. Measured on the 5.45 M-row dev DB: 2 ms raw vs 2–9 ms
  adjusted for a 260-candle read.

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
# migration 0108 to a running API process, call
# ``reset_adjusted_source_cache()`` (or restart) to pick the view up.
_view_available: bool | None = None

# Raw price columns and their adjusted counterparts in the view.
_PRICE_COLUMNS = {
    "open": ("price_first", "price_first_adj"),
    "high": ("price_max", "price_max_adj"),
    "low": ("price_min", "price_min_adj"),
    "close": ("price_last", "price_last_adj"),
}

# One statement shape for both sources: the price columns are aliased back to
# the raw names so ``build_candles`` never has to branch.
_CANDLE_SQL = """
SELECT d.trade_date,
       {open} AS price_first,
       {high} AS price_max,
       {low}  AS price_min,
       {close} AS price_last,
       d.trade_volume, d.trade_value
FROM {source} d
WHERE d.symbol = :sym AND {close} IS NOT NULL
ORDER BY d.trade_date DESC LIMIT :lim
"""


def adjustment_enabled() -> bool:
    """Operator dial: ``INDICATOR_ADJUSTED_PRICES`` (default on)."""
    return bool(getattr(settings, "indicator_adjusted_prices", True))


def price_column(name: str, adjusted: bool) -> str:
    """``('close', True)`` → ``'price_last_adj'``, ``False`` → ``'price_last'``."""
    raw, adj = _PRICE_COLUMNS[name]
    return adj if adjusted else raw


def build_candle_query(source: str, adjusted: bool) -> str:
    """Render the candle SQL for a source (view) and adjustment mode."""
    return _CANDLE_SQL.format(
        source=source,
        open=price_column("open", adjusted),
        high=price_column("high", adjusted),
        low=price_column("low", adjusted),
        close=price_column("close", adjusted),
    )


def build_candles(rows: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    """Shape ``(date, open, high, low, close, volume, value)`` rows → candles.

    Same contract as the pre-0108 loaders: rows arrive newest-first and are
    returned oldest-first; a missing OHLC leg falls back to the close.
    """
    return [
        {
            "date": str(r[0]),
            "open": float(r[1] or r[4]),
            "high": float(r[2] or r[4]),
            "low": float(r[3] or r[4]),
            "close": float(r[4]),
            "volume": float(r[5] or 0),
            "value": float(r[6] or 0),
        }
        for r in reversed(rows)
    ]


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
    rows = (
        await session.execute(text(sql), {"sym": symbol, "lim": limit})
    ).fetchall()
    return build_candles(rows)


__all__ = [
    "ADJUSTED_VIEW",
    "RAW_SOURCE",
    "adjusted_view_available",
    "adjustment_enabled",
    "build_candle_query",
    "build_candles",
    "load_daily_candles",
    "price_column",
    "reset_adjusted_source_cache",
    "resolve_price_source",
]
