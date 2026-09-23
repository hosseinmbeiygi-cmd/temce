"""Shared helpers for converting BrsApi snapshot data into screener inputs.

Both the screener endpoint and the unified assistant build the same
``instruments`` / ``market_watch`` structures.  This module keeps that
logic in one place so the two callers never drift apart.
"""

from __future__ import annotations

from typing import Any, Protocol

from core.logging import get_logger

logger = get_logger(__name__)


class _SnapshotService(Protocol):
    """Minimal protocol for services that can provide market snapshots."""

    async def get_enriched_snapshots(self, limit: int) -> list[dict[str, Any]] | None:
        ...

    async def get_latest_snapshots(self, limit: int) -> list[dict[str, Any]] | None:
        ...


def build_market_watch_from_snapshots(
    snapshots: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert raw BrsApi snapshots into ``(instruments, market_watch)``.

    ``instruments`` is the minimal instrument list passed to
    ``ScreenerService.screen`` / ``screen_with_filters``.
    ``market_watch`` is the enriched per-symbol dict used for filter lookups.

    Args:
        snapshots: raw snapshot dicts from ``get_enriched_snapshots`` or
            ``get_latest_snapshots``.  ``None`` is treated as an empty list.

    Returns:
        A tuple of ``(instruments, market_watch)``.
    """
    if snapshots is None:
        snapshots = []

    instruments: list[dict[str, Any]] = []
    market_watch: list[dict[str, Any]] = []

    for s in snapshots:
        sym = s.get("symbol", "")
        if not sym:
            continue

        instruments.append({
            "symbol": sym,
            "name": s.get("name", sym),
            "market": s.get("market", ""),
            "industry": s.get("sector", ""),
        })

        market_watch.append({
            "symbol": sym,
            "name": s.get("name", sym),
            "last_price": s.get("price_last", 0) or 0,
            "close": s.get("price_close", 0) or 0,
            "change": s.get("price_last_change_pct", 0) or 0,
            "change_value": s.get("price_last_change", 0) or 0,
            "volume": s.get("trade_volume", 0) or 0,
            "value": s.get("trade_value", 0) or 0,
            "high": s.get("price_max", 0) or 0,
            "low": s.get("price_min", 0) or 0,
            "sector": s.get("sector", ""),
            "market": s.get("market", ""),
            "pe_ratio": s.get("pe_ratio"),
            "eps": s.get("eps"),
            "market_value": s.get("market_value"),
            "trade_count": s.get("trade_count"),
            "price_first": s.get("price_first"),
            "price_yesterday": s.get("price_yesterday"),
            "price_min": s.get("price_min"),
            "price_max": s.get("price_max"),
            "shares_count": s.get("shares_count"),
            # Keep the raw snapshot available for callers that need it.
            "_snapshot": s,
        })

    return instruments, market_watch


async def fetch_market_watch(
    service: _SnapshotService,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch snapshots from ``service`` and convert them to screener inputs.

    Tries the enriched endpoint first and falls back to the latest-snapshots
    endpoint if the first call fails.  This keeps the fallback logic in one
    place.

    Args:
        service: a service providing ``get_enriched_snapshots`` and
            ``get_latest_snapshots`` (e.g. ``BrsApiQueryService``).
        limit: maximum number of rows to request.

    Returns:
        ``(instruments, market_watch)`` built from the fetched snapshots.
    """
    try:
        snapshots = await service.get_enriched_snapshots(limit=limit)
    except Exception as primary_exc:  # pragma: no cover - depends on external service
        logger.warning("get_enriched_snapshots failed, falling back: %s", primary_exc)
        try:
            snapshots = await service.get_latest_snapshots(limit=limit)
        except Exception as fallback_exc:  # pragma: no cover - depends on external service
            logger.error("get_latest_snapshots fallback also failed: %s", fallback_exc)
            raise primary_exc from fallback_exc
    return build_market_watch_from_snapshots(snapshots)


class _HistoryService(Protocol):
    """Minimal protocol for services that can provide batched daily OHLCV history."""

    async def get_batch_historical_daily(self, limit: int = 61) -> list[dict[str, Any]]: ...


#: Candles per symbol for the screeners. Above the analytics compute window (20) with room
#: for the 50-bar windows the smart-money layers use.
DAILY_HISTORY_DAYS = 61


def candles_from_daily_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map BrsApi daily rows to the candle keys the screeners compute on, oldest first.

    ``historical_daily`` stores ``price_first``/``price_max``/``price_min``/``trade_volume``
    and its queries return rows newest-first, while the analytics engine and the smart-money
    layers read ``price_open``/``price_high``/``price_low``/``volume`` and treat the *last*
    element as today. Passing one convention as the other left every high, low and volume at
    zero and computed the indicators backwards in time.
    """
    candles: list[dict[str, Any]] = []
    for r in rows:
        close = r.get("price_close") or 0
        if not close:
            # A day with no closing price is not a candle; padding one would invent a bar.
            continue
        candles.append({
            "date": r.get("date") or r.get("trade_date"),
            "price_close": close,
            "price_open": r.get("price_open") or r.get("price_first") or close,
            "price_high": r.get("price_high") or r.get("price_max") or close,
            "price_low": r.get("price_low") or r.get("price_min") or close,
            "price_last": r.get("price_last") or close,
            "volume": r.get("volume") or r.get("trade_volume") or 0,
            "value": r.get("value") or r.get("trade_value") or 0,
        })
    candles.reverse()
    return candles


async def fetch_history_map(
    service: _HistoryService,
    symbols: set[str] | None = None,
    days: int = DAILY_HISTORY_DAYS,
) -> dict[str, list[dict[str, Any]]]:
    """Build ``symbol -> candles`` from one batched daily-history query.

    A symbol with no usable rows is simply absent from the mapping — the caller then reports
    its analytics as not measured rather than scoring an empty series.
    """
    rows = await service.get_batch_historical_daily(limit=days)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows or []:
        sym = r.get("symbol")
        if not sym or (symbols is not None and sym not in symbols):
            continue
        grouped.setdefault(sym, []).append(r)
    return {sym: candles for sym in grouped if (candles := candles_from_daily_rows(grouped[sym]))}


__all__ = [
    "DAILY_HISTORY_DAYS",
    "build_market_watch_from_snapshots",
    "candles_from_daily_rows",
    "fetch_history_map",
    "fetch_market_watch",
]
