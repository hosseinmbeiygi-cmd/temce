"""ParseError must reach the consumers, not stop at the parser boundary.

Both consumers are exercised offline: the ingestion worker (in-process) and
``BrsApiSyncService.sync`` (which receives the parser as a callable). A payload
that could not be read has to end up as a failure, never as a successful run
with ``items_count=0``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.services.sync_service import BrsApiSyncService
from ingestion.parser import ParsedEvent
from ingestion.parser.errors import ParseError
from ingestion.replay import ReplayEngine
from ingestion.worker import IngestionWorker

# ── Ingestion worker ────────────────────────────────────────────────────────


class FakeLake:
    def __init__(self) -> None:
        self.stored: list[dict] = []

    async def store_raw(self, **kwargs):
        self.stored.append(kwargs)
        return "raw/2026/01/01/payload.json"


class FakeRegistry:
    def __init__(self, parser) -> None:
        self._parser = parser

    def find(self, source, endpoint, content_type):
        return self._parser


class FailingParser:
    def __init__(self, reason: str = "invalid_json") -> None:
        self.reason = reason

    async def parse(self, payload: bytes):
        raise ParseError(self.reason, "unreadable payload", source="dummy")


class EmptyParser:
    async def parse(self, payload: bytes):
        return []


class FakeSource:
    name = "dummy"

    def __init__(self, payloads) -> None:
        self._payloads = payloads

    async def fetch(self, context=None):
        return SimpleNamespace(payloads=self._payloads)


def _payload(source: str = "dummy") -> SimpleNamespace:
    return SimpleNamespace(
        source=source,
        endpoint="/dummy",
        raw_data=b"<html>Suspend.php</html>",
        content_type="text/html",
        fetch_time="2026-01-01T00:00:00+00:00",
        metadata={},
    )


def _worker(parser, *, lake=None) -> IngestionWorker:
    return IngestionWorker(
        config=SimpleNamespace(),
        http=None,
        lake=lake or FakeLake(),
        parsers=FakeRegistry(parser),
        dedup=None,
    )


async def test_worker_raises_parse_error_and_keeps_raw_payload():
    lake = FakeLake()
    worker = _worker(FailingParser(), lake=lake)

    with pytest.raises(ParseError):
        await worker._ingest_source(FakeSource([_payload()]))

    # The raw copy is stored before parsing, so a replay can still recover it.
    assert lake.stored and lake.stored[0]["source"] == "dummy"


async def test_worker_ingest_all_marks_parse_failure_as_failed_source():
    worker = _worker(FailingParser("html_response"))
    worker.register_source(FakeSource([_payload()]))

    results = await worker.ingest_all()

    # -1 is the worker's failure signal; 0 would read as "nothing new".
    assert results == {"dummy": -1}


async def test_worker_ingest_all_keeps_valid_empty_payload_as_zero():
    worker = _worker(EmptyParser())
    worker.register_source(FakeSource([_payload()]))

    results = await worker.ingest_all()

    assert results == {"dummy": 0}


# ── BrsApiSyncService ───────────────────────────────────────────────────────

ENDPOINT = SimpleNamespace(path="/Test/Endpoint.php", category=SimpleNamespace(value="test"))


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class FakeClient:
    def __init__(self, data) -> None:
        self.data = data

    async def fetch(self, endpoint, params=None, category_override=None):
        return SimpleNamespace(
            success=True,
            value=SimpleNamespace(
                endpoint=endpoint.path,
                data=self.data,
                is_empty=not self.data,
                raw_bytes=b"{}",
                status_code=200,
                received_at=None,
            ),
        )


async def _run_sync(data, parser):
    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(data), session=session)
    report = await service.sync(
        ENDPOINT,
        parser=parser,
        model_class=SymbolSnapshotModel,
        session=session,
    )
    return report, session


async def test_sync_service_reports_parse_error_as_failure():
    def broken_parser(_data):
        raise ParseError("invalid_json", "unreadable payload", source="dummy")

    report, session = await _run_sync({"data": []}, broken_parser)

    assert report.success is False
    assert "ParseError" in (report.error or "")
    assert "invalid_json" in (report.error or "")
    assert session.added[-1].status == "error"


async def test_sync_service_reports_unexpected_parser_result_as_failure():
    report, session = await _run_sync({"data": []}, lambda _data: 42)

    assert report.success is False
    assert "unexpected parser result type int" in (report.error or "")
    assert session.added[-1].status == "error"


async def test_sync_service_keeps_valid_empty_parser_result_as_success():
    report, session = await _run_sync({"status": "no_data"}, lambda _data: [])

    assert report.success is True
    assert report.items_count == 0
    assert session.added[-1].status == "success"


# ── ReplayEngine ────────────────────────────────────────────────────────────

VALID_PAYLOAD = b'{"data_type": "market_watch", "records": [{"symbol": "ABC"}]}'
EMPTY_PAYLOAD = b'{"data_type": "market_watch", "records": []}'
HTML_PAYLOAD = b"<html><body>Suspend.php</body></html>"


class FakeReplayLake:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects
        self.read: list[str] = []

    async def list_raw(self, source, date_prefix=None):
        return list(self._objects)

    async def get_raw(self, key):
        self.read.append(key)
        return self._objects[key]


class FakeReplayRegistry:
    def __init__(self, parser) -> None:
        self._parser = parser

    def find_by_source(self, source):
        return self._parser


class ReplayParser:
    """Dispatches on the payload, so one replay run can mix all three outcomes."""

    async def parse(self, payload: bytes):
        if payload.startswith(b"<"):
            raise ParseError("html_response", "response is HTML", source="dummy")
        if payload == EMPTY_PAYLOAD:
            return []
        return [
            ParsedEvent(
                source="dummy",
                event_type="market_snapshot",
                data={"symbol": "ABC"},
                raw_object_key="",
                fetch_time="2026-01-01T00:00:00+00:00",
                parsed_at="2026-01-01T00:00:00+00:00",
            )
        ]


def _replay_engine(objects: dict[str, bytes]) -> ReplayEngine:
    return ReplayEngine(
        lake=FakeReplayLake(objects),
        parser_registry=FakeReplayRegistry(ReplayParser()),
        storage=None,
    )


async def test_replay_counts_parse_error_as_failed_not_replayed():
    engine = _replay_engine({"good.json": VALID_PAYLOAD, "broken.json": HTML_PAYLOAD})

    result = await engine.replay_source("dummy")

    # The unreadable object must land in ``failed``; counting it in ``replayed``
    # would report a recovery run that never recovered anything.
    assert result == {
        "source": "dummy",
        "total_objects": 2,
        "replayed": 1,
        "failed": 1,
    }


async def test_replay_keeps_valid_empty_payload_as_replayed():
    engine = _replay_engine({"good.json": VALID_PAYLOAD, "empty.json": EMPTY_PAYLOAD})

    result = await engine.replay_source("dummy")

    # A valid response with no records was read successfully, so it is not a
    # failure — the same distinction the parser contract makes.
    assert result["replayed"] == 2
    assert result["failed"] == 0
