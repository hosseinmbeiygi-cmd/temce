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

    async def get_enriched_snapshots(self, limit: int) -> list[dict[str, Any]] | None: ...

    async def get_latest_snapshots(self, limit: int) -> list[dict[str, Any]] | None: ...


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

        instruments.append(
            {
                "symbol": sym,
                "name": s.get("name", sym),
                "market": s.get("market", ""),
                "industry": s.get("sector", ""),
            }
        )

        market_watch.append(
            {
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
            }
        )

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


__all__ = [
    "build_market_watch_from_snapshots",
    "fetch_market_watch",
]
