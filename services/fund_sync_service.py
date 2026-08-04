"""
🏦 Fund Sync Service — سرویس همگام‌سازی دوره‌ای صندوق‌ها از BrsApi

دو حالت اجرا:
  1. Periodic (هر ۱۵ دقیقه در ساعات بازار) — به‌روزرسانی قیمت‌های لحظه‌ای
  2. Daily (شبانه) — به‌روزرسانی کامل با داده‌های پایانی

هر دو حالت از ``FundService.update_from_brsapi()`` برای هر نماد استفاده می‌کنند.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# ── Known fund symbols (from _SAMPLE_FUNDS) ──

KNOWN_FUND_SYMBOLS: list[str] = [
    "آگاس", "آسامید", "آکاریز", "آکشاورز", "اسپید", "اشتیاق", "اطلس", "افتم",
    "اقبال", "الماس", "امید", "امین", "انرژی", "ایثار", "ایرانیان",
    "باپویا", "بدرخش", "باهنر", "باور", "برکت", "بسامان", "بهینه",
    "پارسیان", "پدیده", "پیشگامان", "پویا",
    "تابان", "تاپ", "تدبیر", "توسعه", "ثابت",
    "جامان", "جاوید", "حافظ", "خبرگان", "خرد",
    "دانش", "دلیران", "رادین", "رازی", "رفاه",
    "سپهر", "ستاره", "سدید", "سرآمد", "سرمد", "شفا", "صبا", "صنعت",
    "طلوع", "عقیق", "فردا", "فیروزه", "ققنوس",
    "کارآفرین", "کامران", "کیوان", "گنجینه",
    "مبین", "مثقال", "محصول", "مهر",
    "نادر", "ناهید", "نخل", "نیک", "وفاق", "همراه", "یسنا",
    "گهر", "زرفام", "نیرو", "دماوند", "البرز", "آذین", "بامداد", "بهار", "پارمیدا",
]

# ── Market hours (Tehran time) ──

MARKET_OPEN = time(8, 45)   # 08:45 Tehran
MARKET_CLOSE = time(12, 30)  # 12:30 Tehran

# ── Concurrency ──

MAX_CONCURRENT = 5           # Max concurrent API calls to BrsApi (rate-limit safety)
DELAY_BETWEEN_SYMBOLS = 1.5  # Seconds between each symbol to avoid rate-limit bursts


# ── Data classes ──


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


# ── Service ──


class FundSyncService:
    """
    سرویس همگام‌سازی دوره‌ای صندوق‌ها از BrsApi.

    Args:
        fund_service: ``FundService`` instance with DB session.
        brsapi: ``BrsApiQueryService`` instance for fetching data.
    """

    def __init__(self, fund_service: Any, brsapi: Any) -> None:
        self._fund_service = fund_service
        self._brsapi = brsapi
        self._lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────────

    async def sync_all_funds(
        self,
        symbols: list[str] | None = None,
        max_concurrent: int = MAX_CONCURRENT,
    ) -> SyncReport:
        """
        همگام‌سازی همه صندوق‌ها.

        Args:
            symbols: لیست نمادها (پیش‌فرض: همه صندوق‌های شناخته شده).
            max_concurrent: (kept for API compat) — execution is sequential
                because ``FundService``/``BrsApiQueryService`` share one
                AsyncSession that is not concurrency-safe.

        Returns:
            ``SyncReport`` با آمار کامل.
        """
        async with self._lock:
            return await self._sync_all(symbols or KNOWN_FUND_SYMBOLS, max_concurrent)

    async def sync_single_fund(self, symbol: str) -> SyncResult:
        """
        همگام‌سازی یک صندوق مشخص.

        Args:
            symbol: نماد صندوق (مثلاً ``"آگاس"``).
        """
        start = asyncio.get_event_loop().time()
        try:
            result = await self._fund_service.update_from_brsapi(
                symbol=symbol,
                brsapi=self._brsapi,
            )
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            if "error" in result:
                return SyncResult(
                    symbol=symbol, success=False,
                    error=result["error"], duration_ms=elapsed,
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
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            logger.exception("Failed to sync fund %s", symbol)
            return SyncResult(
                symbol=symbol, success=False,
                error=str(e)[:200], duration_ms=elapsed,
            )

    # ── Internal ───────────────────────────────────────────────────

    async def _sync_all(
        self,
        symbols: list[str],
        max_concurrent: int,
    ) -> SyncReport:
        """Internal: sync all symbols sequentially.

        NOTE: intentionally serialized — ``FundService`` and
        ``BrsApiQueryService`` share a single AsyncSession, and running
        ``update_from_brsapi`` concurrently on one session raises
        ``InvalidRequestError: This session is provisioning a new connection;
        concurrent operations are not permitted``. Sequential execution is
        also rate-limit friendly (``DELAY_BETWEEN_SYMBOLS`` between calls).
        """
        start = asyncio.get_event_loop().time()
        report = SyncReport(total=len(symbols))

        for symbol in symbols:
            result = await self.sync_single_fund(symbol)
            # Small delay between symbols to avoid rate-limit bursts
            await asyncio.sleep(DELAY_BETWEEN_SYMBOLS)
            if result.success:
                report.success += 1
            else:
                report.failed += 1
                report.errors.append({
                    "symbol": result.symbol,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                })

        report.duration_ms = (asyncio.get_event_loop().time() - start) * 1000
        logger.info("Fund sync complete: %s", report.summary)
        return report


# ── Market-hours helper ──


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
