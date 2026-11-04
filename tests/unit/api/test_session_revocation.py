"""SEC-07: a password change ends every session, not just the current token.

The revoked-jti blacklist only covers the token presented in the request; every
other device keeps its own access token. A user-wide cutoff (``auth:user_revoked``)
is compared against the JWT ``iat`` so all sessions issued before the change
are rejected. The password-change endpoint refuses to run while the revocation
store is unavailable instead of leaving the old tokens valid.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

import core.cache as cache_module
import core.security.tokens as tokens_module
from core.security.tokens import (
    is_user_session_revoked,
    revoke_user_access_tokens,
)


class _FakeCache:
    def __init__(self, connected: bool = True) -> None:
        self.store: dict[str, Any] = {}
        self.ttls: dict[str, int] = {}
        self._connected = connected

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get(self, key: str) -> Any | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.store[key] = value
        if ttl is not None:
            self.ttls[key] = ttl


@pytest.fixture
def cache(monkeypatch: pytest.MonkeyPatch) -> _FakeCache:
    fake = _FakeCache()
    monkeypatch.setattr(cache_module, "get_cache", lambda: fake)
    return fake


def _now() -> float:
    return float(int(datetime.now(UTC).timestamp()))


async def test_revocation_rejects_tokens_issued_before_the_cutoff(cache) -> None:
    old_iat = _now() - 600
    assert await revoke_user_access_tokens("usr_1") is True

    assert await is_user_session_revoked("usr_1", old_iat) is True
    # A token issued after the change (same second boundary excluded) is fine.
    assert await is_user_session_revoked("usr_1", _now() + 5) is False


async def test_marker_is_stored_with_the_token_lifetime_ttl(cache) -> None:
    await revoke_user_access_tokens("usr_1")

    key = "auth:user_revoked:usr_1"
    assert key in cache.store
    assert cache.ttls[key] >= 60


async def test_no_marker_means_not_revoked(cache) -> None:
    assert await is_user_session_revoked("usr_1", _now() - 600) is False
    assert await is_user_session_revoked(None, 1.0) is False
    assert await is_user_session_revoked("usr_1", None) is False


async def test_unreadable_marker_fails_closed(cache) -> None:
    cache.store["auth:user_revoked:usr_1"] = "garbage"

    assert await is_user_session_revoked("usr_1", _now()) is True


async def test_redis_outage_fails_open_but_revocation_reports_failure(monkeypatch) -> None:
    fake = _FakeCache(connected=False)
    monkeypatch.setattr(cache_module, "get_cache", lambda: fake)

    assert await revoke_user_access_tokens("usr_1") is False
    assert await is_user_session_revoked("usr_1", _now() - 600) is False


async def test_access_tokens_carry_iat() -> None:
    token = tokens_module.create_access_token({"sub": "usr_1"})
    payload = tokens_module.decode_access_token(token)

    assert isinstance(payload.get("iat"), int)
    assert payload["iat"] <= int(datetime.now(UTC).timestamp()) + 1


# ── request-level rejection ───────────────────────────────────────────────


async def test_dependency_rejects_a_revoked_user_session(cache, monkeypatch) -> None:
    from apps.api import dependencies

    async def not_revoked(_jti):
        return False

    monkeypatch.setattr(dependencies, "is_token_revoked", not_revoked)
    await revoke_user_access_tokens("usr_1")

    with pytest.raises(HTTPException) as excinfo:
        await dependencies._reject_if_revoked({"sub": "usr_1", "iat": _now() - 600})

    assert excinfo.value.status_code == 401


# ── password change fails closed when the store is down ──────────────────


async def test_change_password_refuses_without_a_revocation_store(monkeypatch) -> None:
    from apps.api.endpoints import auth as auth_module

    monkeypatch.setattr(cache_module, "get_cache", lambda: _FakeCache(connected=False))

    with pytest.raises(HTTPException) as excinfo:
        await auth_module.change_password(
            req=SimpleNamespace(current_password="a", new_password="b"),
            request=SimpleNamespace(client=None, headers={}),
            current_user={"sub": "usr_1"},
            authorization="",
            session=None,
            _=None,
        )

    assert excinfo.value.status_code == 503
