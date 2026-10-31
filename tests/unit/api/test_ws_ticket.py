"""FE-06 — WebSocket handshakes must carry a single-use ticket, not the token.

The browser cannot set an ``Authorization`` header on a WebSocket handshake,
so the socket URL used to carry the long-lived access token — visible in
access/proxy logs, browser history and URL-capturing tooling. The client now
trades the access token for a 60-second ticket over authenticated HTTP; the
backend stores only its SHA-256 and redeems it exactly once (GETDEL).

These tests are offline: a dict-backed fake stands in for Redis.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

import core.cache as cache_module
from core.security.tokens import (
    WS_TICKET_TTL_SECONDS,
    consume_ws_ticket,
    create_ws_ticket,
)


class _FakeCache:
    def __init__(self, connected: bool = True) -> None:
        self.store: dict[str, Any] = {}
        self.ttls: dict[str, int] = {}
        self._connected = connected

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.store[key] = value
        if ttl is not None:
            self.ttls[key] = ttl

    async def pop(self, key: str) -> Any | None:
        return self.store.pop(key, None)


@pytest.fixture
def cache(monkeypatch: pytest.MonkeyPatch) -> _FakeCache:
    fake = _FakeCache()
    monkeypatch.setattr(cache_module, "get_cache", lambda: fake)
    return fake


# ── Ticket lifecycle ────────────────────────────────────────────────────────


async def test_ticket_is_stored_hashed_and_expires_in_sixty_seconds(cache) -> None:
    ticket = await create_ws_ticket("user-1")

    assert ticket
    assert ticket not in cache.store, "the raw ticket must never be persisted"
    digest = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    key = f"auth:ws_ticket:{digest}"
    assert cache.store[key] == {"purpose": "ws-handshake", "sub": "user-1"}
    assert cache.ttls[key] == WS_TICKET_TTL_SECONDS == 60


async def test_ticket_is_redeemable_exactly_once(cache) -> None:
    ticket = await create_ws_ticket("user-1")

    assert await consume_ws_ticket(ticket) is True
    assert await consume_ws_ticket(ticket) is False, "replay must be rejected"


async def test_unknown_or_empty_ticket_is_rejected(cache) -> None:
    assert await consume_ws_ticket("not-a-ticket") is False
    assert await consume_ws_ticket("") is False


async def test_redis_outage_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCache(connected=False)
    monkeypatch.setattr(cache_module, "get_cache", lambda: fake)

    assert await create_ws_ticket("user-1") is None
    assert await consume_ws_ticket("anything") is False


async def test_wrong_purpose_value_is_not_a_ticket(cache) -> None:
    ticket = "abc"
    digest = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    cache.store[f"auth:ws_ticket:{digest}"] = {"purpose": "password-reset"}

    assert await consume_ws_ticket(ticket) is False


# ── Handshake verification ─────────────────────────────────────────────────


class _FakeWebSocket:
    def __init__(self, query: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> None:
        self.query_params = query or {}
        self.headers = headers or {}


@pytest.fixture
def auth_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.api.auth as auth_module

    monkeypatch.setattr(auth_module, "_auth_required", lambda: True)


async def test_handshake_accepts_a_fresh_ticket(cache, auth_enabled) -> None:
    from apps.api.endpoints.websocket import verify_websocket_token

    ticket = await create_ws_ticket("user-1")
    ws = _FakeWebSocket(query={"ticket": ticket})

    assert await verify_websocket_token(ws) is True  # type: ignore[arg-type]


async def test_handshake_rejects_a_spent_ticket(cache, auth_enabled) -> None:
    from apps.api.endpoints.websocket import verify_websocket_token

    ticket = await create_ws_ticket("user-1")
    ws = _FakeWebSocket(query={"ticket": ticket})
    assert await verify_websocket_token(ws) is True  # type: ignore[arg-type]

    replay = _FakeWebSocket(query={"ticket": ticket})
    assert await verify_websocket_token(replay) is False  # type: ignore[arg-type]


async def test_invalid_ticket_does_not_fall_back_to_the_legacy_token(cache, auth_enabled) -> None:
    """A presented-but-bad ticket is a rejection, not a downgrade."""
    from apps.api.endpoints.websocket import verify_websocket_token

    ws = _FakeWebSocket(query={"ticket": "bogus", "token": "some-access-token"})

    assert await verify_websocket_token(ws) is False  # type: ignore[arg-type]


async def test_missing_ticket_and_header_is_rejected(cache, auth_enabled) -> None:
    from apps.api.endpoints.websocket import verify_websocket_token

    assert await verify_websocket_token(_FakeWebSocket()) is False  # type: ignore[arg-type]


async def test_auth_disabled_keeps_the_handshake_open(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.api.auth as auth_module

    monkeypatch.setattr(auth_module, "_auth_required", lambda: False)
    from apps.api.endpoints.websocket import verify_websocket_token

    assert await verify_websocket_token(_FakeWebSocket()) is True  # type: ignore[arg-type]
