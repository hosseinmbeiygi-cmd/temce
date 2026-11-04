"""The sync outcome must be persisted on the sync-log row, not only returned.

History and the admin panel read ``brsapi_sync_log``; if ``outcome`` stayed in
the in-memory report, a failed run would still be indistinguishable from an
empty one once it left the request.
"""

from __future__ import annotations

from types import SimpleNamespace

from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.parsers.errors import BrsApiParseError
from brsapi.services import sync_service as sync_service_module
from brsapi.services.sync_service import BrsApiSyncService

ENDPOINT = SimpleNamespace(path="/Test/Endpoint.php", category=SimpleNamespace(value="test"))


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeClient:
    def __init__(
        self,
        data=None,
        *,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.data = data
        self.error = error
        self.error_code = error_code

    async def fetch(self, endpoint, params=None, category_override=None):
        if self.error is not None:
            return SimpleNamespace(
                success=False, error=self.error, error_code=self.error_code, value=None
            )
        return SimpleNamespace(
            success=True,
            value=SimpleNamespace(
                endpoint=endpoint.path,
                data=self.data,
                is_empty=not self.data,
                raw_bytes=None,
                status_code=200,
                received_at=None,
            ),
        )


async def _run(client, *, parser=lambda data: data):
    session = FakeSession()
    service = BrsApiSyncService(client=client, session=session)
    report = await service.sync(
        ENDPOINT,
        parser=parser,
        model_class=SymbolSnapshotModel,
        session=session,
    )
    return report, session


def _log_outcome(session: FakeSession) -> str:
    return session.added[-1].outcome


async def test_empty_sync_is_logged_as_empty() -> None:
    report, session = await _run(FakeClient([]))

    assert report.outcome == "empty"
    assert _log_outcome(session) == "empty"


async def test_parse_failure_is_logged_as_parse_error() -> None:
    def broken_parser(_data):
        raise BrsApiParseError("unexpected payload shape")

    report, session = await _run(FakeClient({"unexpected": []}), parser=broken_parser)

    assert report.outcome == "parse_error"
    assert _log_outcome(session) == "parse_error"


async def test_malformed_fetch_is_logged_as_malformed() -> None:
    report, session = await _run(
        FakeClient(
            error="MalformedResponse: HTML instead of JSON",
            error_code="malformed",
        )
    )

    assert report.outcome == "malformed"
    assert _log_outcome(session) == "malformed"


async def test_storage_failure_is_logged_as_storage_error(monkeypatch) -> None:
    async def failed_insert(self, records, **kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(
        sync_service_module.BulkUpsertRepository,
        "bulk_insert",
        failed_insert,
    )
    report, session = await _run(FakeClient([{"symbol": "S0", "fetched_at": None}]))

    assert report.outcome == "storage_error"
    assert _log_outcome(session) == "storage_error"


async def test_single_record_parser_none_is_logged_as_empty() -> None:
    # ``parse_nav`` / ``parse_symbol_detail`` are typed ``dict | None`` and use
    # None for "already stored"; that is a no-op, not a shape failure.
    report, session = await _run(FakeClient({"symbol": "S0"}), parser=lambda _data: None)

    assert report.outcome == "empty"
    assert _log_outcome(session) == "empty"


async def test_successful_sync_is_logged_as_success(monkeypatch) -> None:
    async def capture_insert(self, records, **kwargs):
        return len(records)

    monkeypatch.setattr(
        sync_service_module.BulkUpsertRepository,
        "bulk_insert",
        capture_insert,
    )
    report, session = await _run(FakeClient([{"symbol": "S0", "fetched_at": None}]))

    assert report.outcome == "success"
    assert _log_outcome(session) == "success"
