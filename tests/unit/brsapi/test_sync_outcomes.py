"""Offline contract tests for BrsApi fetch/parse/sync outcomes.

These tests never contact BrsApi. They pin the distinction between a valid
empty response, malformed/HTML payloads, parser failures, provider blocks,
timeouts and storage failures so a source error can no longer be reported as
``success=True, items_count=0``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from brsapi.client import BrsApiMalformedResponseError, BrsApiSourceError
from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.parsers import CommodityParser, CryptoParser, ImeParser, TsetmcParser
from brsapi.parsers.errors import BrsApiParseError
from brsapi.services import sync_service as sync_service_module
from brsapi.services.sync_service import BrsApiSyncService

ENDPOINT = SimpleNamespace(path="/Test/Endpoint.php", category=SimpleNamespace(value="test"))


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeClient:
    def __init__(
        self,
        data=None,
        *,
        error: str | None = None,
        error_code: str | None = None,
        received_at=None,
    ) -> None:
        self.data = data
        self.error = error
        self.error_code = error_code
        self.received_at = received_at

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
                received_at=self.received_at,
            ),
        )


def _record(*, fetched_at=datetime(2020, 1, 1, 0, 0, 0)) -> dict:
    return {"symbol": "S0", "price_last": 1.0, "fetched_at": fetched_at}


# ── Client: malformed / provider envelopes ──────────────────────────────────


def test_html_payload_is_traceable_malformed_error() -> None:
    from brsapi.client import BrsApiClient

    client = BrsApiClient(api_key="test", base_url="http://test.local")
    with pytest.raises(BrsApiMalformedResponseError, match="HTML"):
        client._parse_response(b"<html><body>Suspend.php</body></html>", "text/html")


def test_broken_json_is_traceable_malformed_error() -> None:
    from brsapi.client import BrsApiClient

    client = BrsApiClient(api_key="test", base_url="http://test.local")
    with pytest.raises(BrsApiMalformedResponseError, match="invalid JSON"):
        client._parse_response(b'{"gold": [', "application/json")


def test_provider_error_envelope_inside_http_200_is_not_data() -> None:
    from brsapi.client import BrsApiClient

    client = BrsApiClient(api_key="test", base_url="http://test.local")
    with pytest.raises(BrsApiSourceError, match="402"):
        client._parse_response(
            b'{"code_http": 402, "successful": false, "message_error": "quota exhausted"}',
            "application/json",
        )


def test_no_data_envelope_is_valid_empty_json() -> None:
    from brsapi.client import BrsApiClient, BrsApiResponse

    client = BrsApiClient(api_key="test", base_url="http://test.local")
    data = client._parse_response(b'{"status": "no_data"}', "application/json")
    response = BrsApiResponse(endpoint="/Test", status_code=200, data=data)
    assert response.is_empty is True
    assert response.success is True


# ── Parsers: malformed shape is not silently [] ─────────────────────────────


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (TsetmcParser.parse_all_symbols, "garbage"),
        (TsetmcParser.parse_shareholders, None),
        (TsetmcParser.parse_transactions, {"unexpected": []}),
        (CommodityParser.parse, "garbage"),
        (CryptoParser.parse, "garbage"),
        (ImeParser.parse_futures, "garbage"),
    ],
)
def test_malformed_parser_payload_raises(parser, payload) -> None:
    with pytest.raises(BrsApiParseError):
        parser(payload)


def test_valid_empty_parser_payloads_stay_empty() -> None:
    assert TsetmcParser.parse_all_symbols([]) == []
    assert TsetmcParser.parse_shareholders([]) == []
    assert TsetmcParser.parse_shareholders({"data": []}) == []
    assert TsetmcParser.parse_candlesticks({"status": "no_data"}) == []


# ── Sync: one distinct outcome per failure mode ─────────────────────────────


async def _run_sync(client, *, parser=lambda data: data, dedup_seconds=0, received_at=None):
    if received_at is not None:
        # The receive time is a property of the fetched response, so give the
        # client the value the test wants that response to carry.
        client.received_at = received_at
    session = FakeSession()
    service = BrsApiSyncService(client=client, session=session)
    report = await service.sync(
        ENDPOINT,
        parser=parser,
        model_class=SymbolSnapshotModel,
        dedup_seconds=dedup_seconds,
        session=session,
    )
    return report, session


async def test_valid_empty_response_is_success_empty_outcome() -> None:
    report, session = await _run_sync(FakeClient([]))

    assert report.success is True
    assert report.items_count == 0
    assert report.outcome == "empty"
    assert session.added[-1].status == "success"


async def test_parser_exception_is_parse_error_not_empty_success() -> None:
    def broken_parser(_data):
        raise BrsApiParseError("unexpected payload shape")

    report, session = await _run_sync(FakeClient({"unexpected": []}), parser=broken_parser)

    assert report.success is False
    assert report.outcome == "parse_error"
    assert "ParseError" in (report.error or "")
    assert session.added[-1].status == "error"


async def test_malformed_client_error_has_malformed_outcome() -> None:
    report, session = await _run_sync(
        FakeClient(
            error="MalformedResponse: HTML instead of JSON",
            error_code="malformed",
        )
    )

    assert report.success is False
    assert report.outcome == "malformed"
    assert session.added[-1].status == "error"


async def test_provider_block_has_provider_blocked_outcome() -> None:
    report, _session = await _run_sync(
        FakeClient(
            error="BrsApi quota exceeded (HTTP 302 → Suspend.php)",
            error_code="provider_blocked",
        )
    )

    assert report.success is False
    assert report.outcome == "provider_blocked"


async def test_timeout_has_timeout_outcome() -> None:
    report, _session = await _run_sync(
        FakeClient(error="Request timeout after 3 retries", error_code="timeout")
    )

    assert report.success is False
    assert report.outcome == "timeout"


async def test_storage_error_has_storage_error_outcome(monkeypatch) -> None:
    async def failed_insert(self, records, **kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(
        sync_service_module.BulkUpsertRepository,
        "bulk_insert",
        failed_insert,
    )
    report, session = await _run_sync(FakeClient([_record()]))

    assert report.success is False
    assert report.outcome == "storage_error"
    assert session.added[-1].status == "error"


async def test_records_are_stamped_with_actual_receive_time(monkeypatch) -> None:
    received_at = datetime(2026, 10, 28, 12, 34, 56, tzinfo=UTC)
    captured: list[dict] = []

    async def capture_insert(self, records, **kwargs):
        captured.extend(records)
        return len(records)

    monkeypatch.setattr(
        sync_service_module.BulkUpsertRepository,
        "bulk_insert",
        capture_insert,
    )
    report, _session = await _run_sync(
        FakeClient([_record(fetched_at=datetime(2020, 1, 1, 0, 0, 0))]),
        received_at=received_at,
    )

    assert report.success is True
    assert captured[0]["fetched_at"] == datetime(2026, 10, 28, 12, 34, 56)


async def test_raw_payload_uses_actual_receive_time(monkeypatch) -> None:
    received_at = datetime(2026, 10, 28, 12, 34, 56, tzinfo=UTC)
    captured: dict = {}

    async def capture_store(self, **kwargs):
        captured.update(kwargs)

    async def capture_insert(self, records, **kwargs):
        return len(records)

    monkeypatch.setattr(
        sync_service_module.RawPayloadRepository,
        "store",
        capture_store,
    )
    monkeypatch.setattr(
        sync_service_module.BulkUpsertRepository,
        "bulk_insert",
        capture_insert,
    )
    client = FakeClient([_record()], received_at=received_at)
    client.fetch = lambda endpoint, params=None, category_override=None: _raw_client_result(
        endpoint, received_at
    )

    report, _session = await _run_sync(client)

    assert report.success is True
    assert captured["receive_time"] == datetime(2026, 10, 28, 12, 34, 56)


async def _raw_client_result(endpoint, received_at):
    return SimpleNamespace(
        success=True,
        value=SimpleNamespace(
            endpoint=endpoint.path,
            data=[_record()],
            is_empty=False,
            raw_bytes=b'{"ok": true}',
            status_code=200,
            received_at=received_at,
        ),
    )
