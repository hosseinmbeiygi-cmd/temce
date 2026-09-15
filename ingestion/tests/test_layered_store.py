"""Tests for the Hot (Redis) / Warm (TimescaleDB) persistence path."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from ingestion.layered_store import (
    HOT_TTL_SECONDS,
    HotLayer,
    LayeredStoragePipeline,
    SymbolSnapshotWarmSink,
)
from ingestion.raw_validation import RawValidationReport
from ingestion.symbol_scanner import ScanResult

FETCHED_AT = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)


def _record(symbol: str, price: float = 1000.0) -> dict:
    return {
        "symbol": symbol,
        "ins_id": "1",
        "name": f"{symbol} corp",
        "sector": "فلزات اساسی",
        "price_last": price,
        "price_close": price,
        "price_yesterday": 990.0,
        "price_last_change_pct": 1.0,
        "trade_volume": 10,
        "trade_value": 10_000.0,
        "trade_count": 3,
        "base_volume": 1_000,
        "market_value": 1_000_000.0,
        "time": "12:30:00",
        "raw_json": '{"noisy": "payload"}',
        "fetched_at": FETCHED_AT.replace(tzinfo=None),
    }


def _scan(*symbols: str) -> ScanResult:
    records = [_record(symbol) for symbol in symbols]
    report = RawValidationReport(accepted=records)
    return ScanResult(
        fetched_at=FETCHED_AT,
        symbol_type="1",
        raw_count=len(records),
        latency_ms=12.0,
        validation=report,
        records=records,
    )


class FakeWarmSink:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.records: list | None = None

    async def write_batch(self, records) -> int:
        if self.error is not None:
            raise self.error
        self.records = list(records)
        return len(self.records)


class _AsyncSessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[tuple[str, list]] = []
        self.commits = 0

    async def execute(self, statement, params):
        self.statements.append((str(statement), params))
        return SimpleNamespace(rowcount=len(params))

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


async def test_hot_layer_writes_quotes_and_index() -> None:
    hot = HotLayer()
    written = await hot.write_batch([_record("فولاد"), _record("خودرو")], fetched_at=FETCHED_AT)

    assert written == 2
    quote = await hot.get_quote("فولاد")
    assert quote["price_last"] == 1000.0
    assert "raw_json" not in quote  # heavy fields stay in the warm layer
    assert quote["fetched_at"] == FETCHED_AT.isoformat()

    latest = await hot.latest_scan()
    assert latest["count"] == 2
    assert latest["symbols"] == ["فولاد", "خودرو"]


async def test_hot_layer_skips_rows_without_symbol() -> None:
    hot = HotLayer()
    written = await hot.write_batch([{"symbol": "", "price_last": 1.0}], fetched_at=FETCHED_AT)
    assert written == 0
    assert await hot.latest_scan() is None


def test_hot_ttl_covers_three_scan_cycles() -> None:
    assert HOT_TTL_SECONDS == 90


async def test_pipeline_writes_hot_then_warm() -> None:
    warm = FakeWarmSink()
    pipeline = LayeredStoragePipeline(hot=HotLayer(), warm=warm)

    report = await pipeline.persist(_scan("فولاد", "خودرو"))

    assert report.ok is True
    assert report.hot_written == 2
    assert report.warm_written == 2
    assert warm.records is not None and len(warm.records) == 2


async def test_pipeline_reports_warm_failure_without_losing_hot() -> None:
    warm = FakeWarmSink(error=RuntimeError("db down"))
    hot = HotLayer()
    pipeline = LayeredStoragePipeline(hot=hot, warm=warm)

    report = await pipeline.persist(_scan("فولاد"))

    assert report.ok is False
    assert report.hot_written == 1
    assert report.warm_error == "db down"
    assert await hot.get_quote("فولاد") is not None


async def test_pipeline_runs_hot_only_when_no_warm_sink() -> None:
    pipeline = LayeredStoragePipeline(hot=HotLayer(), warm=None)
    report = await pipeline.persist(_scan("فولاد"))

    assert report.hot_written == 1
    assert report.warm_written == 0
    assert report.warm_error is None


async def test_warm_sink_bulk_upserts_symbol_snapshots() -> None:
    session = FakeSession()
    sink = SymbolSnapshotWarmSink(lambda: _AsyncSessionContext(session))

    written = await sink.write_batch([_record("فولاد")])

    assert written == 1
    assert session.commits == 1
    statement, params = session.statements[0]
    assert "brsapi_symbol_snapshots" in statement
    assert "ON CONFLICT (\"symbol\", \"fetched_at\") DO UPDATE" in statement
    assert params[0]["symbol"] == "فولاد"


async def test_warm_sink_rejects_unknown_columns() -> None:
    session = FakeSession()
    sink = SymbolSnapshotWarmSink(lambda: _AsyncSessionContext(session))

    try:
        await sink.write_batch([{"symbol": "فولاد", "not_a_column": 1}])
    except ValueError as exc:
        assert "Unknown column" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown column")
