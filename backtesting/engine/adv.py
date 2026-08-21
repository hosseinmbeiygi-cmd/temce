"""Per-symbol ADV (average daily volume) resolution — audit F5.

The Broker previously fell back to a single generic ``1_000_000`` ADV for every
instrument, so a share with a real ADV of 50k received far less slippage than
reality. ``AdvResolver`` fixes that by resolving the *actual* average daily
volume per symbol from ``brsapi_historical_daily`` (30-day window), with an
in-process TTL cache:

- ``resolve(symbol)`` — async; fetches from the DB on cache miss, never raises.
- ``peek(symbol)`` — sync, cache-only; used by the synchronous backtest path
  (BacktestSimulator/Broker.submit_order_sync) which cannot await DB I/O.
- Callers may also pre-warm the cache (e.g. the async service layer) before
  running a sync simulation so ``peek`` always hits real data.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

DEFAULT_ADV_WINDOW_DAYS = 30
DEFAULT_ADV_TTL_SECONDS = 6 * 3600  # 6 hours
_DB_ERROR_LOG_INTERVAL = 3600.0  # at most one DB-error log per hour


class AdvResolver:
    """Resolve and cache per-symbol average daily volume from the market DB."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_ADV_TTL_SECONDS,
        window_days: int = DEFAULT_ADV_WINDOW_DAYS,
    ) -> None:
        self._cache: dict[str, tuple[int, float]] = {}  # symbol -> (adv, expires_at)
        self._ttl_seconds = ttl_seconds
        self._window_days = window_days
        self._last_db_error_logged: float = 0.0

    # ── Cache introspection ────────────────────────────────────────────────

    def peek(self, symbol: str) -> int | None:
        """Return a cached ADV synchronously (no I/O). None on cache miss."""
        now = time.time()
        hit = self._cache.get(symbol)
        if hit is not None and hit[1] > now:
            return hit[0]
        return None

    def cached_symbols(self) -> list[str]:
        """Symbols currently held in the cache (for monitoring)."""
        now = time.time()
        return [s for s, (_, exp) in self._cache.items() if exp > now]

    def clear(self) -> None:
        self._cache.clear()

    def set(self, symbol: str, adv: int, ttl_seconds: int | None = None) -> None:
        """Manually seed the cache (e.g. pre-warm from an async caller)."""
        self._cache[symbol] = (max(int(adv), 0), time.time() + (ttl_seconds or self._ttl_seconds))

    # ── Resolution ─────────────────────────────────────────────────────────

    async def resolve(self, symbol: str) -> int | None:
        """Resolve ADV for ``symbol``, fetching from the DB on cache miss.

        Returns None when unavailable (no DB, unknown symbol) — never raises.
        """
        cached = self.peek(symbol)
        if cached is not None:
            return cached
        adv = await self._fetch_from_db(symbol)
        if adv is not None and adv > 0:
            self.set(symbol, adv)
        return adv

    async def resolve_many(self, symbols: list[str]) -> dict[str, int]:
        """Resolve ADV for many symbols in one pass; returns {symbol: adv}."""
        result: dict[str, int] = {}
        for symbol in symbols:
            adv = await self.resolve(symbol)
            if adv is not None:
                result[symbol] = adv
        return result

    async def _fetch_from_db(self, symbol: str) -> int | None:
        """Average daily volume over the last ``window_days`` trading days."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return None
            async with async_session_factory() as session:
                row = (
                    await session.execute(
                        text(
                            "SELECT AVG(trade_volume) "
                            "FROM brsapi_historical_daily "
                            "WHERE symbol = :sym AND trade_volume > 0 AND price_close > 0 "
                            f"AND gregorian_date >= CURRENT_DATE - INTERVAL '{int(self._window_days)} days'"
                        ),
                        {"sym": symbol},
                    )
                ).fetchone()
                if row is not None and row[0]:
                    return int(round(float(row[0])))
        except Exception as exc:  # noqa: BLE001 — resolver must never raise
            now = time.time()
            if now - self._last_db_error_logged > _DB_ERROR_LOG_INTERVAL:
                logger.warning(
                    "ADV lookup failed for '%s' (will retry next window): %s", symbol, exc
                )
                self._last_db_error_logged = now
        return None


_singleton: AdvResolver | None = None


def get_adv_resolver() -> AdvResolver:
    """Return the shared process-wide AdvResolver instance."""
    global _singleton
    if _singleton is None:
        _singleton = AdvResolver()
    return _singleton
