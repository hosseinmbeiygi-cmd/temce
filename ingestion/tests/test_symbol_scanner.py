"""Tests for the market-aware AllSymbols scanner (no HTTP)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from core.result import Result
from ingestion.symbol_scanner import (
    AllSymbolsScanner,
    MarketSession,
    ScanCadence,
    ScanResult,
    tehran_timezone,
)

TZ = tehran_timezone()
# 2026-09-09 is a Wednesday; the Tehran week runs Saturday..Wednesday.
WEDNESDAY_10AM = datetime(2026, 9, 9, 10, 0, tzinfo=TZ)
WEDNESDAY_8PM = datetime(2026, 9, 9, 20, 0, tzinfo=TZ)
THURSDAY_10AM = datetime(2026, 9, 10, 10, 0, tzinfo=TZ)


def _row(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "ins_id": "1",
        "price_last": 1000.0,
        "price_close": 1000.0,
        "price_yesterday": 990.0,
        "trade_volume": 10,
        "trade_value": 10_000.0,
        "trade_count": 3,
        "fetched_at": datetime.now(UTC).replace(microsecond=0, tzinfo=None),
    }


class FakeClient:
    def __init__(self, result: Result) -> None:
        self._result = result
        self.calls = 0

    async def fetch_all_symbols(self, *, symbol_type: str = "1") -> Result:
        self.calls += 1
        return self._result


class FastSession(MarketSession):
    def next_delay(self, cadence: ScanCadence, now: datetime | None = None) -> float:
        return 0.01


def test_market_session_detects_open_hours() -> None:
    session = MarketSession()
    assert session.in_market_hours(WEDNESDAY_10AM) is True
    assert session.in_market_hours(WEDNESDAY_8PM) is False


def test_market_session_skips_weekend() -> None:
    session = MarketSession()
    assert session.is_trading_day(THURSDAY_10AM) is False
    assert session.in_market_hours(THURSDAY_10AM) is False


def test_next_delay_is_30s_in_market_hours() -> None:
    session = MarketSession()
    assert session.next_delay(ScanCadence(), WEDNESDAY_10AM) == 30.0


def test_next_delay_waits_for_next_open_off_hours() -> None:
    session = MarketSession()
    delay = session.next_delay(ScanCadence(), WEDNESDAY_8PM)
    assert delay == 300.0  # capped by the off-hours cadence


def test_seconds_until_open_lands_on_saturday_open() -> None:
    session = MarketSession()
    opened = WEDNESDAY_8PM + timedelta(seconds=session.seconds_until_open(WEDNESDAY_8PM))
    assert opened.weekday() == 5  # Saturday
    assert (opened.hour, opened.minute) == (8, 30)


async def test_scan_once_validates_and_counts() -> None:
    client = FakeClient(Result.ok([_row("فولاد"), _row("خودرو"), _row("")]))
    scanner = AllSymbolsScanner(client)
    result = await scanner.scan_once()

    assert result.success is True
    scan: ScanResult = result.unwrap()
    assert scan.raw_count == 3
    assert scan.accepted_count == 2
    assert scan.rejected_count == 1
    assert scanner.scan_count == 1
    assert scanner.last_result is scan
    assert scan.as_dict()["accepted"] == 2


async def test_scan_once_propagates_failure() -> None:
    client = FakeClient(Result.fail("quota exhausted"))
    scanner = AllSymbolsScanner(client)
    result = await scanner.scan_once()

    assert result.success is False
    assert result.error == "quota exhausted"
    assert scanner.failure_count == 1
    assert scanner.last_result is None


async def test_run_loop_calls_on_scan_and_stops() -> None:
    client = FakeClient(Result.ok([_row("فولاد")]))
    seen: list[ScanResult] = []

    async def on_scan(scan: ScanResult) -> None:
        seen.append(scan)

    scanner = AllSymbolsScanner(client, session=FastSession(), on_scan=on_scan)
    task = asyncio.create_task(scanner.run())
    await asyncio.sleep(0.05)
    scanner.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert seen
    assert client.calls >= 1
    assert scanner.scan_count == len(seen)
