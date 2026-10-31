"""Failure classification must read structured codes, not message text.

Every failure the BrsApi layer can produce carries a machine-readable code:
``BrsApiMalformedResponseError``/``BrsApiSourceError`` for transport-shaped
failures, ``BrsApiParseError`` for payload shapes, and ``Result.error_code``
for everything the client returns. ``BrsApiSyncService`` maps those codes onto
``SyncReport.outcome``; rewording a message must never change the outcome.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import brsapi.client as client_module
from brsapi.client import (
    BrsApiClient,
    BrsApiMalformedResponseError,
    BrsApiSourceError,
)
from brsapi.parsers import TsetmcParser
from brsapi.parsers.errors import BrsApiParseError
from brsapi.services.sync_service import BrsApiSyncService
from core.result import Result

ENDPOINT = SimpleNamespace(path="/Test/Endpoint.php", category=SimpleNamespace(value="test"))


# ── Client errors ───────────────────────────────────────────────────────────


def _client() -> BrsApiClient:
    return BrsApiClient(api_key="test", base_url="http://test.local")


def test_html_body_carries_malformed_code() -> None:
    with pytest.raises(BrsApiMalformedResponseError) as excinfo:
        _client()._parse_response(b"<html><body>Suspend.php</body></html>", "text/html")

    assert excinfo.value.code == "malformed"


def test_broken_json_carries_malformed_code() -> None:
    with pytest.raises(BrsApiMalformedResponseError) as excinfo:
        _client()._parse_response(b'{"gold": [', "application/json")

    assert excinfo.value.code == "malformed"


def test_provider_payment_envelope_carries_quota_code() -> None:
    with pytest.raises(BrsApiSourceError) as excinfo:
        _client()._parse_response(
            b'{"code_http": 402, "successful": false, "message_error": "quota exhausted"}',
            "application/json",
        )

    assert excinfo.value.code == "quota_exhausted"


ENDPOINT_CONFIG = SimpleNamespace(
    path="/X.php",
    category=SimpleNamespace(value="test"),
    critical=False,
    default_params={},
)


@pytest.mark.asyncio
async def test_fetch_propagates_the_typed_error_code(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client_module.brsapi_settings, "enabled", True)
    client._client = object()

    async def boom(*args, **kwargs):
        raise BrsApiMalformedResponseError("HTML page instead of JSON")

    client._do_fetch = boom
    result = await client.fetch(ENDPOINT_CONFIG)

    assert result.success is False
    assert result.error_code == "malformed"


@pytest.mark.asyncio
async def test_fetch_marks_unknown_exceptions_as_source_error(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client_module.brsapi_settings, "enabled", True)
    client._client = object()

    async def boom(*args, **kwargs):
        raise RuntimeError("something else")

    client._do_fetch = boom
    result = await client.fetch(ENDPOINT_CONFIG)

    assert result.success is False
    assert result.error_code == "source_error"


def test_other_provider_error_envelope_carries_blocked_code() -> None:
    with pytest.raises(BrsApiSourceError) as excinfo:
        _client()._parse_response(
            b'{"code_http": 403, "successful": false, "message_error": "forbidden"}',
            "application/json",
        )

    assert excinfo.value.code == "provider_blocked"


# ── Parser errors ───────────────────────────────────────────────────────────


def test_non_list_payload_is_unexpected_shape() -> None:
    with pytest.raises(BrsApiParseError) as excinfo:
        TsetmcParser.parse_all_symbols("garbage")

    assert excinfo.value.code == "unexpected_shape"


def test_missing_payload_is_missing_payload() -> None:
    with pytest.raises(BrsApiParseError) as excinfo:
        TsetmcParser.parse_transactions(None)

    assert excinfo.value.code == "missing_payload"


def test_unknown_envelope_is_unrecognised_envelope() -> None:
    with pytest.raises(BrsApiParseError) as excinfo:
        TsetmcParser.parse_shareholders({"unexpected": []})

    assert excinfo.value.code == "unrecognised_envelope"


# ── Result ──────────────────────────────────────────────────────────────────


def test_result_fail_carries_the_code() -> None:
    result = Result.fail("anything", code="timeout")

    assert result.success is False
    assert result.error_code == "timeout"
    assert Result.ok(1).error_code is None


# ── Outcome derived from the code, never the prose ──────────────────────────


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
    def __init__(self, error: str, error_code: str | None) -> None:
        self.error = error
        self.error_code = error_code

    async def fetch(self, endpoint, params=None, category_override=None):
        return SimpleNamespace(
            success=False, error=self.error, error_code=self.error_code, value=None
        )


async def _outcome(error: str, error_code: str | None) -> str:
    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(error, error_code), session=session)
    report = await service.sync(
        ENDPOINT,
        parser=lambda data: data,
        model_class=object,
        session=session,
    )
    assert session.added[-1].outcome == report.outcome
    return report.outcome


async def test_misleading_message_does_not_change_the_outcome() -> None:
    # The prose screams "timeout", the code says the body was unreadable.
    assert await _outcome("Request timeout after 3 retries", "malformed") == "malformed"


async def test_unclassified_message_is_a_source_error() -> None:
    # No code: the text is not consulted, so quota-sounding prose stays generic.
    assert await _outcome("quota exceeded (HTTP 302 → Suspend.php)", None) == "source_error"
