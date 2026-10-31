"""Regression tests for the ingestion worker's dedup / write-failure contract.

Covers three bugs found during the Phase-3 persistence audit:

1. ``is_duplicate`` was never consulted — the dedup window was written but
   never read, so duplicate payloads were always reprocessed.
2. A failing storage write still marked the payload as seen (the write error
   was swallowed inside ``_write_event``), so the event was never retried.
3. The returned counter was the number of parsed events, not the number of
   events actually persisted.
"""

from __future__ import annotations

from types import SimpleNamespace

from ingestion.worker import IngestionWorker


class FakeDedup:
    def __init__(self, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.seen: list[bytes] = []

    async def is_duplicate(self, source: str, payload: bytes) -> bool:
        return self.duplicate

    async def mark_seen(self, source: str, payload: bytes) -> None:
        self.seen.append(payload)


class FakeLake:
    def __init__(self) -> None:
        self.calls = 0

    async def store_raw(self, **kwargs):
        self.calls += 1
        return "raw/key"


class FakeParser:
    def __init__(self, events):
        self.events = events

    async def parse(self, raw):
        return self.events


class FakeParsers:
    def __init__(self, events):
        self.parser = FakeParser(events)

    def find(self, source, endpoint, content_type):
        return self.parser


class FakeIdentity:
    def __init__(self, resolved: str | None = "INS-1") -> None:
        self.resolved = resolved

    async def resolve(self, source, external_id, symbol):
        return self.resolved


class FakeStorage:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.written: list[str] = []

    async def write_market_snapshot(self, instrument_id, data):
        if self.fail:
            raise RuntimeError("db down")
        self.written.append(instrument_id)


class FakeSource:
    name = "fake"

    def __init__(self, payloads):
        self.payloads = payloads

    async def fetch(self, context=None):
        return SimpleNamespace(payloads=self.payloads)


def _payload(raw: bytes = b'{"x":1}'):
    return SimpleNamespace(
        source="fake",
        endpoint="AllSymbols",
        raw_data=raw,
        content_type="application/json",
        fetch_time=None,
        metadata={},
    )


def _event():
    return SimpleNamespace(event_type="market_snapshot", data={"symbol": "A"}, source="fake")


def _worker(events, *, dedup, storage, identity=None):
    return IngestionWorker(
        config=SimpleNamespace(),
        http=None,
        lake=FakeLake(),
        parsers=FakeParsers(events),
        dedup=dedup,
        identity_resolver=identity or FakeIdentity(),
        storage=storage,
    )


async def test_duplicate_payload_is_skipped_before_parsing() -> None:
    dedup = FakeDedup(duplicate=True)
    storage = FakeStorage()
    worker = _worker([_event()], dedup=dedup, storage=storage)

    count = await worker._ingest_source(FakeSource([_payload()]))

    assert count == 0
    assert storage.written == []
    assert worker._lake.calls == 0
    assert dedup.seen == []


async def test_failed_write_is_not_marked_seen_and_is_retried() -> None:
    dedup = FakeDedup()
    storage = FakeStorage(fail=True)
    worker = _worker([_event(), _event()], dedup=dedup, storage=storage)

    count = await worker._ingest_source(FakeSource([_payload()]))

    assert count == 0
    assert dedup.seen == []
    assert storage.written == []


async def test_unresolved_instrument_is_skipped_without_infinite_retry() -> None:
    dedup = FakeDedup()
    storage = FakeStorage()
    worker = _worker([_event()], dedup=dedup, storage=storage, identity=FakeIdentity(resolved=None))
    payload = _payload()

    count = await worker._ingest_source(FakeSource([payload]))

    assert count == 0
    assert storage.written == []
    # The event cannot ever resolve, so the payload must not be retried forever.
    assert dedup.seen == [payload.raw_data]


async def test_counter_counts_persisted_events_and_marks_seen_once() -> None:
    dedup = FakeDedup()
    storage = FakeStorage()
    worker = _worker([_event(), _event()], dedup=dedup, storage=storage)
    payload = _payload()

    count = await worker._ingest_source(FakeSource([payload]))

    assert count == 2
    assert storage.written == ["INS-1", "INS-1"]
    assert dedup.seen == [payload.raw_data]
