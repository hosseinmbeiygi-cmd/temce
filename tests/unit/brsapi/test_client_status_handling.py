"""End-to-end HTTP status handling of ``BrsApiClient.fetch``.

Every response class must map onto one deterministic ``Result`` — and the retry
loop, the budget governor and the circuit breaker must react to it exactly once:

* ``200``            → parsed payload, governor notified.
* any redirect       → ``provider_blocked``, never followed, never retried,
                        cooldown armed on the governor (the provider redirects
                        over-quota accounts to a multi-GB file).
* ``402``            → ``quota_exhausted``, not retried (retrying cannot pay).
* ``401/403/451``    → ``provider_blocked``, not retried.
* ``408/429/5xx``    → retried with ``Retry-After``/backoff, then
                        ``retries_exhausted``.
* timeout/network    → retried with exponential backoff, then ``timeout`` /
                        ``network_error``.
* other 4xx          → ``http_error``, not retried.
* open breaker       → ``circuit_open`` with zero HTTP requests.

The retry loop is what actually spends the provider budget, so the request
count is asserted in every case (``handler.calls == n``).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

import brsapi.budget as budget_module
import brsapi.client as client_module
import brsapi.rate_limiter as rate_limiter
from brsapi.client import BrsApiClient
from brsapi.config import EndpointCategory, EndpointConfig

ENDPOINT = EndpointConfig(
    path="/Tsetmc/AllSymbols.php",
    category=EndpointCategory.TSETMC,
)
URL = "http://test.local/Tsetmc/AllSymbols.php"


# ── Test doubles ────────────────────────────────────────────────────────────


class FakeLimiter:
    """Only the two methods the client touches; no shared singleton state."""

    def configure(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def status(self) -> dict[str, Any]:
        return {}


class FakeGovernor:
    def __init__(self) -> None:
        self.acquired = 0
        self.ok = 0
        self.redirects: list[str] = []

    async def check_allowed(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def acquire(self, *_args: Any, **_kwargs: Any) -> None:
        self.acquired += 1

    async def report_ok(self) -> None:
        self.ok += 1

    async def report_302(self, location: str = "") -> None:
        self.redirects.append(location)

    async def stats(self) -> dict[str, Any]:
        return {}


def sequence(*items: Any) -> httpx.MockTransport:
    """Mock transport replaying responses/exceptions; counts every request."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(items) - 1)
        calls["n"] += 1
        item = items[index]
        if isinstance(item, Exception):
            raise item
        return item

    transport = httpx.MockTransport(handler)
    transport.calls = calls  # type: ignore[attr-defined]
    return transport


@pytest.fixture
def governor() -> FakeGovernor:
    return FakeGovernor()


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return recorded


@pytest.fixture
async def make_client(monkeypatch, governor):
    monkeypatch.setattr(client_module.brsapi_settings, "enabled", True)
    clients: list[BrsApiClient] = []

    async def factory(transport: httpx.MockTransport, *, max_retries: int = 2) -> BrsApiClient:
        client = BrsApiClient(
            api_key="test",
            base_url="http://test.local",
            rate_limiter=FakeLimiter(),
            budget_governor=governor,
        )
        client._client = httpx.AsyncClient(transport=transport)
        client._max_retries = max_retries
        clients.append(client)
        return client

    yield factory

    for client in clients:
        await client.stop()


async def _fetch(client: BrsApiClient):
    return await client.fetch(ENDPOINT)


# ── 200 ─────────────────────────────────────────────────────────────────────


async def test_200_parses_payload_and_notifies_governor(make_client, governor) -> None:
    transport = sequence(httpx.Response(200, json=[{"l18": "فملی"}]))
    client = await make_client(transport)

    result = await _fetch(client)

    assert result.success is True
    assert result.value.data == [{"l18": "فملی"}]
    assert transport.calls["n"] == 1
    assert governor.ok == 1


# ── Redirects (302 anti-abuse + any other 3xx) ──────────────────────────────


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_redirect_is_blocked_without_retry_and_arms_cooldown(
    make_client, governor, status
) -> None:
    transport = sequence(
        httpx.Response(status, headers={"Location": "https://cdn.example/Windows.iso"})
    )
    client = await make_client(transport)

    result = await _fetch(client)

    assert result.success is False
    assert result.error_code == "provider_blocked"
    assert str(status) in (result.error or "")
    assert transport.calls["n"] == 1, "a redirect must never be retried"
    assert governor.redirects == ["https://cdn.example/Windows.iso"]


# ── Quota / credential rejection ────────────────────────────────────────────


async def test_402_is_quota_exhausted_without_retry(make_client) -> None:
    transport = sequence(httpx.Response(402, text="payment required"))
    client = await make_client(transport, max_retries=3)

    result = await _fetch(client)

    assert result.error_code == "quota_exhausted"
    assert transport.calls["n"] == 1


@pytest.mark.parametrize("status", [401, 403, 451])
async def test_credential_rejection_is_provider_blocked_without_retry(
    make_client, status
) -> None:
    transport = sequence(httpx.Response(status, text="forbidden"))
    client = await make_client(transport, max_retries=3)

    result = await _fetch(client)

    assert result.error_code == "provider_blocked"
    assert transport.calls["n"] == 1


# ── Retryable statuses ──────────────────────────────────────────────────────


async def test_429_honours_retry_after_then_succeeds(make_client, sleeps) -> None:
    transport = sequence(
        httpx.Response(429, headers={"Retry-After": "2"}),
        httpx.Response(200, json=[]),
    )
    client = await make_client(transport)

    result = await _fetch(client)

    assert result.success is True
    assert transport.calls["n"] == 2
    assert sleeps == [2.0], "Retry-After: 2 must be the exact delay"


@pytest.mark.parametrize("status", [408, 500, 502, 503, 504])
async def test_transient_status_is_retried_then_succeeds(make_client, sleeps, status) -> None:
    transport = sequence(
        httpx.Response(status),
        httpx.Response(200, json={"ok": True}),
    )
    client = await make_client(transport)

    result = await _fetch(client)

    assert result.success is True
    assert transport.calls["n"] == 2


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_retry_budget_is_bounded(make_client, sleeps, status) -> None:
    transport = sequence(httpx.Response(status))  # always the same failure
    client = await make_client(transport, max_retries=2)

    result = await _fetch(client)

    assert result.success is False
    assert result.error_code == "retries_exhausted"
    assert transport.calls["n"] == 3, "1 attempt + max_retries"
    assert len(sleeps) == 2, "the last attempt must not sleep"


# ── Non-retryable client errors ─────────────────────────────────────────────


async def test_404_is_http_error_without_retry(make_client) -> None:
    transport = sequence(httpx.Response(404, text="not found"))
    client = await make_client(transport, max_retries=3)

    result = await _fetch(client)

    assert result.error_code == "http_error"
    assert transport.calls["n"] == 1


# ── Transport failures ──────────────────────────────────────────────────────


async def test_timeout_retries_with_exponential_backoff(make_client, sleeps) -> None:
    transport = sequence(httpx.ConnectTimeout("timed out"))
    client = await make_client(transport, max_retries=2)

    result = await _fetch(client)

    assert result.error_code == "timeout"
    assert transport.calls["n"] == 3
    # backoff_base ** (attempt + 1) → 1.5, 2.25
    assert sleeps == [1.5, 2.25]


async def test_network_error_is_classified_and_retried(make_client, sleeps) -> None:
    transport = sequence(httpx.ConnectError("connection refused"))
    client = await make_client(transport, max_retries=1)

    result = await _fetch(client)

    assert result.error_code == "network_error"
    assert transport.calls["n"] == 2


# ── Budget governor fast path (no HTTP at all) ─────────────────────────────


class _RejectingGovernor(FakeGovernor):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    async def check_allowed(self, *_args: Any, **_kwargs: Any) -> None:
        raise self._error


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (budget_module.BudgetSoftRejectError("soft ceiling"), "budget_soft_limit"),
        (rate_limiter.RateLimitExhaustedError("daily budget spent"), "quota_exhausted"),
        (budget_module.BudgetBlockedError("302 cooldown"), "provider_blocked"),
    ],
    ids=["soft-limit", "daily-exhausted", "302-cooldown"],
)
async def test_governor_fast_path_rejects_before_http(
    monkeypatch, error, expected_code
) -> None:
    monkeypatch.setattr(client_module.brsapi_settings, "enabled", True)
    monkeypatch.setattr(client_module.brsapi_settings, "fail_fast_on_daily_exhausted", True)
    transport = sequence(httpx.Response(200, json=[]))
    client = BrsApiClient(
        api_key="test",
        base_url="http://test.local",
        rate_limiter=FakeLimiter(),
        budget_governor=_RejectingGovernor(error),
    )
    client._client = httpx.AsyncClient(transport=transport)

    try:
        result = await client.fetch(ENDPOINT)
    finally:
        await client.stop()

    assert result.success is False
    assert result.error_code == expected_code
    assert transport.calls["n"] == 0, "a budget rejection must not spend a request"


# ── Circuit breaker ─────────────────────────────────────────────────────────


async def test_breaker_opens_after_repeated_failures_and_stops_http(make_client) -> None:
    transport = sequence(httpx.Response(404, text="not found"))
    client = await make_client(transport, max_retries=0)

    for _ in range(5):
        result = await _fetch(client)
        assert result.error_code == "http_error"
    assert transport.calls["n"] == 5

    blocked = await _fetch(client)

    assert blocked.error_code == "circuit_open"
    assert transport.calls["n"] == 5, "an open breaker must not touch the network"


async def test_breaker_does_not_count_successes(make_client) -> None:
    # Four failures then a success must reset the count: the breaker stays closed.
    transport = sequence(
        httpx.Response(404),
        httpx.Response(404),
        httpx.Response(404),
        httpx.Response(404),
        httpx.Response(200, json=[]),
    )
    client = await make_client(transport, max_retries=0)

    codes = [(await _fetch(client)).error_code for _ in range(5)]

    assert codes[:4] == ["http_error"] * 4
    assert codes[4] is None
    assert client._circuit_breaker(ENDPOINT.path).state == "closed"


async def test_success_after_recovery_window_probes_and_closes(make_client) -> None:
    transport = sequence(*([httpx.Response(404)] * 5), httpx.Response(200, json=[]))
    client = await make_client(transport, max_retries=0)

    for _ in range(5):
        await _fetch(client)
    breaker = client._circuit_breaker(ENDPOINT.path)
    assert breaker.state == "open"

    breaker.last_failure_time -= 31.0  # recovery_timeout is 30s

    probed = await _fetch(client)

    assert probed.success is True
    assert breaker.state == "closed"
    assert transport.calls["n"] == 6
