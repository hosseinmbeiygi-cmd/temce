"""``AllSymbols.php`` scanner — the whole market in one request.

Cadence: every 30 seconds while the Tehran market is open, backing off to a
configurable off-hours interval (default 300s) and waking up right at the next
open.  Only raw fetching + basic validation happen here; no technical
computation.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time as dt_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.logging import get_logger
from core.result import Result

from .brs_api_client import BrsApiIngestionClient, DEFAULT_ALL_SYMBOLS_TYPE
from .config import IngestionConfig
from .raw_validation import RawQuoteValidator, RawValidationReport

logger = get_logger(__name__)

# Tehran Stock Exchange trades Saturday..Wednesday (Mon=0 .. Sun=6).
DEFAULT_TRADING_WEEKDAYS: tuple[int, ...] = (5, 6, 0, 1, 2)
_FALLBACK_TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def tehran_timezone() -> Any:
    """``Asia/Tehran`` with a fixed +03:30 fallback (Windows lacks tzdata)."""
    try:
        return ZoneInfo("Asia/Tehran")
    except (ZoneInfoNotFoundError, Exception):  # noqa: BLE001 - never fail on tz
        return _FALLBACK_TEHRAN_TZ


@dataclass(frozen=True)
class ScanCadence:
    """Poll interval in seconds, inside vs outside market hours."""

    market_seconds: int = 30
    off_hours_seconds: int = 300

    def __post_init__(self) -> None:
        if self.market_seconds <= 0 or self.off_hours_seconds <= 0:
            raise ValueError("cadence intervals must be positive")


@dataclass
class ScanResult:
    """One completed AllSymbols scan."""

    fetched_at: datetime
    symbol_type: str
    raw_count: int
    latency_ms: float
    validation: RawValidationReport
    records: list[dict[str, Any]] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return self.validation.accepted_count

    @property
    def rejected_count(self) -> int:
        return self.validation.rejected_count

    def as_dict(self) -> dict[str, Any]:
        return {
            "fetched_at": self.fetched_at.isoformat(),
            "symbol_type": self.symbol_type,
            "raw_count": self.raw_count,
            "accepted": self.accepted_count,
            "rejected": self.rejected_count,
            "duplicates": self.validation.duplicate_symbols,
            "latency_ms": round(self.latency_ms, 1),
        }


class MarketSession:
    """Tehran market clock: trading weekdays + open/close window."""

    def __init__(
        self,
        *,
        open_time: str = "08:30",
        close_time: str = "15:30",
        timezone_name: str = "Asia/Tehran",
        trading_weekdays: tuple[int, ...] = DEFAULT_TRADING_WEEKDAYS,
    ) -> None:
        self._tz = tehran_timezone()
        self._open = dt_time.fromisoformat(open_time)
        self._close = dt_time.fromisoformat(close_time)
        self._timezone_name = timezone_name
        self._weekdays = tuple(trading_weekdays)

    @classmethod
    def from_config(cls, config: IngestionConfig) -> MarketSession:
        return cls(
            open_time=config.market_open,
            close_time=config.market_close,
            timezone_name=config.market_timezone,
        )

    @property
    def open_time(self) -> dt_time:
        return self._open

    @property
    def close_time(self) -> dt_time:
        return self._close

    def local_now(self, now: datetime | None = None) -> datetime:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        return current.astimezone(self._tz)

    def is_trading_day(self, now: datetime | None = None) -> bool:
        return self.local_now(now).weekday() in self._weekdays

    def in_market_hours(self, now: datetime | None = None) -> bool:
        local = self.local_now(now)
        if local.weekday() not in self._weekdays:
            return False
        return self._open <= local.time() <= self._close

    def seconds_until_open(self, now: datetime | None = None) -> float:
        """Seconds until the next session open (0.0 when already open)."""
        local = self.local_now(now)
        if self.in_market_hours(local):
            return 0.0

        candidate_day = local
        if local.time() > self._close or local.weekday() not in self._weekdays:
            candidate_day = local + timedelta(days=1)
        while candidate_day.weekday() not in self._weekdays:
            candidate_day += timedelta(days=1)

        candidate_day = candidate_day.replace(
            hour=self._open.hour,
            minute=self._open.minute,
            second=0,
            microsecond=0,
        )
        return max(0.0, (candidate_day - local).total_seconds())

    def next_delay(self, cadence: ScanCadence, now: datetime | None = None) -> float:
        """Seconds to sleep before the next scan."""
        if self.in_market_hours(now):
            return float(cadence.market_seconds)
        return float(min(cadence.off_hours_seconds, max(self.seconds_until_open(now), 1.0)))


class AllSymbolsScanner:
    """Fetch the whole market on a market-aware cadence."""

    def __init__(
        self,
        client: BrsApiIngestionClient,
        *,
        cadence: ScanCadence | None = None,
        session: MarketSession | None = None,
        validator: RawQuoteValidator | None = None,
        symbol_type: str = DEFAULT_ALL_SYMBOLS_TYPE,
        on_scan: Callable[[ScanResult], Awaitable[None]] | None = None,
    ) -> None:
        self._client = client
        self._cadence = cadence or ScanCadence()
        self._session = session or MarketSession()
        self._validator = validator or RawQuoteValidator()
        self._symbol_type = symbol_type
        self._on_scan = on_scan
        self._stop = asyncio.Event()
        self._last_result: ScanResult | None = None
        self._scan_count = 0
        self._failure_count = 0

    @property
    def cadence(self) -> ScanCadence:
        return self._cadence

    @property
    def session(self) -> MarketSession:
        return self._session

    @property
    def last_result(self) -> ScanResult | None:
        return self._last_result

    @property
    def scan_count(self) -> int:
        return self._scan_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def stop(self) -> None:
        self._stop.set()

    async def scan_once(self) -> Result[ScanResult]:
        """Run a single scan and validate the raw rows."""
        started = time.perf_counter()
        fetched_at = datetime.now(UTC)
        result = await self._client.fetch_all_symbols(symbol_type=self._symbol_type)
        latency_ms = (time.perf_counter() - started) * 1000

        if not result.success:
            self._failure_count += 1
            logger.warning("AllSymbols scan failed: %s", result.error)
            return Result.fail(result.error or "AllSymbols scan failed")

        rows = result.value or []
        validation = self._validator.validate(rows)
        scan = ScanResult(
            fetched_at=fetched_at,
            symbol_type=self._symbol_type,
            raw_count=len(rows),
            latency_ms=latency_ms,
            validation=validation,
            records=validation.accepted,
        )
        self._last_result = scan
        self._scan_count += 1
        logger.info(
            "AllSymbols scan: %d accepted / %d rejected (%d duplicates) in %.0fms",
            scan.accepted_count,
            scan.rejected_count,
            validation.duplicate_symbols,
            latency_ms,
        )
        return Result.ok(scan)

    async def run(self) -> None:
        """Scan until :meth:`stop` is called, honouring the market cadence."""
        self._stop.clear()
        logger.info(
            "AllSymbols scanner started (market=%ds off-hours=%ds)",
            self._cadence.market_seconds,
            self._cadence.off_hours_seconds,
        )
        while not self._stop.is_set():
            result = await self.scan_once()
            if result.success and result.value is not None and self._on_scan is not None:
                try:
                    await self._on_scan(result.value)
                except Exception:  # noqa: BLE001 - a sink must not kill the loop
                    logger.exception("on_scan handler failed")
            await self._sleep_next()
        logger.info("AllSymbols scanner stopped after %d scans", self._scan_count)

    async def _sleep_next(self) -> None:
        delay = self._session.next_delay(self._cadence)
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except TimeoutError:
            return
