"""
ðŸ¦ Fund Sync Service â€” Ø³Ø±ÙˆÛŒØ³ Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ Ø¯ÙˆØ±Ù‡â€ŒØ§ÛŒ ØµÙ†Ø¯ÙˆÙ‚â€ŒÙ‡Ø§ Ø§Ø² BrsApi

Ø¯Ùˆ Ø­Ø§Ù„Øª Ø§Ø¬Ø±Ø§:
  1. Periodic (Ù‡Ø± Û±Ûµ Ø¯Ù‚ÛŒÙ‚Ù‡ Ø¯Ø± Ø³Ø§Ø¹Ø§Øª Ø¨Ø§Ø²Ø§Ø±) â€” Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù‚ÛŒÙ…Øªâ€ŒÙ‡Ø§ÛŒ Ù„Ø­Ø¸Ù‡â€ŒØ§ÛŒ
  2. Daily (Ø´Ø¨Ø§Ù†Ù‡) â€” Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ú©Ø§Ù…Ù„ Ø¨Ø§ Ø¯Ø§Ø¯Ù‡â€ŒÙ‡Ø§ÛŒ Ù¾Ø§ÛŒØ§Ù†ÛŒ

Ù‡Ø± Ø¯Ùˆ Ø­Ø§Ù„Øª Ø§Ø² ``FundService.update_from_brsapi()`` Ø¨Ø±Ø§ÛŒ Ù‡Ø± Ù†Ù…Ø§Ø¯ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ù…ÛŒâ€ŒÚ©Ù†Ù†Ø¯.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# â”€â”€ Known fund symbols (from _SAMPLE_FUNDS) â”€â”€

from domain.instruments.symbol_catalog import KNOWN_FUND_SYMBOLS  # noqa: F401 â€” re-exported for API compat

# â”€â”€ Market hours (Tehran time) â”€â”€

MARKET_OPEN = time(8, 45)  # 08:45 Tehran
MARKET_CLOSE = time(12, 30)  # 12:30 Tehran

# â”€â”€ Concurrency â”€â”€

MAX_CONCURRENT = 5  # Max concurrent API calls to BrsApi (rate-limit safety)
DELAY_BETWEEN_SYMBOLS = 1.5  # Seconds between each symbol to avoid rate-limit bursts


# â”€â”€ Data classes â”€â”€


@dataclass
class SyncResult:
    """Result of syncing a single fund."""

    symbol: str
    success: bool
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class SyncReport:
    """Report of a full sync cycle."""

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def summary(self) -> str:
        return (
            f"{self.total} symbols: "
            f"{self.success} ok, {self.failed} failed, {self.skipped} skipped "
            f"({self.duration_ms / 1000:.1f}s)"
        )


# â”€â”€ Service â”€â”€


class FundSyncService:
    """
    Ø³Ø±ÙˆÛŒØ³ Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ Ø¯ÙˆØ±Ù‡â€ŒØ§ÛŒ ØµÙ†Ø¯ÙˆÙ‚â€ŒÙ‡Ø§ Ø§Ø² BrsApi.

    Args:
        fund_service: ``FundService`` instance with DB session.
        brsapi: ``BrsApiQueryService`` instance for fetching data.
    """

    def __init__(self, fund_service: Any, brsapi: Any) -> None:
        self._fund_service = fund_service
        self._brsapi = brsapi
        self._lock = asyncio.Lock()

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def sync_all_funds(
        self,
        symbols: list[str] | None = None,
        max_concurrent: int = MAX_CONCURRENT,
    ) -> SyncReport:
        """
        Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ Ù‡Ù…Ù‡ ØµÙ†Ø¯ÙˆÙ‚â€ŒÙ‡Ø§.

        Args:
            symbols: Ù„ÛŒØ³Øª Ù†Ù…Ø§Ø¯Ù‡Ø§ (Ù¾ÛŒØ´â€ŒÙØ±Ø¶: Ù‡Ù…Ù‡ ØµÙ†Ø¯ÙˆÙ‚â€ŒÙ‡Ø§ÛŒ Ø´Ù†Ø§Ø®ØªÙ‡ Ø´Ø¯Ù‡).
            max_concurrent: (kept for API compat) â€” execution is sequential
                because ``FundService``/``BrsApiQueryService`` share one
                AsyncSession that is not concurrency-safe.

        Returns:
            ``SyncReport`` Ø¨Ø§ Ø¢Ù…Ø§Ø± Ú©Ø§Ù…Ù„.
        """
        async with self._lock:
            return await self._sync_all(symbols or KNOWN_FUND_SYMBOLS, max_concurrent)

    async def sync_single_fund(self, symbol: str) -> SyncResult:
        """
        Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ ÛŒÚ© ØµÙ†Ø¯ÙˆÙ‚ Ù…Ø´Ø®Øµ.

        Args:
            symbol: Ù†Ù…Ø§Ø¯ ØµÙ†Ø¯ÙˆÙ‚ (Ù…Ø«Ù„Ø§Ù‹ ``"Ø¢Ú¯Ø§Ø³"``).
        """
        start = asyncio.get_running_loop().time()
        try:
            result = await self._fund_service.update_from_brsapi(
                symbol=symbol,
                brsapi=self._brsapi,
            )
            elapsed = (asyncio.get_running_loop().time() - start) * 1000
            if "error" in result:
                return SyncResult(
                    symbol=symbol,
                    success=False,
                    error=result["error"],
                    duration_ms=elapsed,
                )
            return SyncResult(symbol=symbol, success=True, duration_ms=elapsed)
        except Exception as e:
            # Rollback the session to recover from InFailedSQLTransactionError.
            # When a query fails, asyncpg leaves the connection in a failed
            # transaction state; all subsequent queries on the same session
            # will also fail until we issue ROLLBACK.
            if hasattr(self._brsapi, "session") and self._brsapi.session is not None:
                with contextlib.suppress(Exception):
                    await self._brsapi.session.rollback()
            elapsed = (asyncio.get_running_loop().time() - start) * 1000
            logger.exception("Failed to sync fund %s", symbol)
            return SyncResult(
                symbol=symbol,
                success=False,
                error=str(e)[:200],
                duration_ms=elapsed,
            )

    # â”€â”€ Internal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _sync_all(
        self,
        symbols: list[str],
        max_concurrent: int,
    ) -> SyncReport:
        """Internal: sync all symbols sequentially.

        NOTE: intentionally serialized â€” ``FundService`` and
        ``BrsApiQueryService`` share a single AsyncSession, and running
        ``update_from_brsapi`` concurrently on one session raises
        ``InvalidRequestError: This session is provisioning a new connection;
        concurrent operations are not permitted``. Sequential execution is
        also rate-limit friendly (``DELAY_BETWEEN_SYMBOLS`` between calls).
        """
        start = asyncio.get_running_loop().time()
        report = SyncReport(total=len(symbols))

        for symbol in symbols:
            result = await self.sync_single_fund(symbol)
            # Small delay between symbols to avoid rate-limit bursts
            await asyncio.sleep(DELAY_BETWEEN_SYMBOLS)
            if result.success:
                report.success += 1
            else:
                report.failed += 1
                report.errors.append(
                    {
                        "symbol": result.symbol,
                        "error": result.error,
                        "duration_ms": result.duration_ms,
                    }
                )

        report.duration_ms = (asyncio.get_running_loop().time() - start) * 1000
        logger.info("Fund sync complete: %s", report.summary)
        return report


# â”€â”€ Market-hours helper â”€â”€


def _is_market_open() -> bool:
    """Check if Tehran market is currently in trading hours."""
    import pytz

    tehran_tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tehran_tz).time()
    return MARKET_OPEN <= now <= MARKET_CLOSE


def _next_market_open_delay() -> float:
    """Seconds until the next market open."""
    import pytz

    tehran_tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tehran_tz)
    today_open = now.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    if now.time() < MARKET_OPEN:
        return (today_open - now).total_seconds()
    # Next day
    import datetime as dt

    tomorrow = now + dt.timedelta(days=1)
    tomorrow_open = tomorrow.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    return (tomorrow_open - now).total_seconds()
