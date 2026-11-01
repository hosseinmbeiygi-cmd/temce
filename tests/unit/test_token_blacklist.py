"""JWT blacklist completeness: access *and* refresh tokens.

Covers the shared revocation invariants (``validate_access_token``), refresh
token jti/iat issuance, rotation revoking the presented refresh token, and the
multi-worker guarantee that revocations live in a shared (Redis) store rather
than process memory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import core.cache as cache_module
from core.exceptions import AuthenticationError
from core.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    is_token_revoked,
    revoke_access_token,
    revoke_refresh_token,
    revoke_token,
    revoke_user_access_tokens,
    validate_access_token,
)


class _SharedStore:
    """One dict shared by every "worker" view below."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}


class _WorkerCache:
    def __init__(self, store: _SharedStore, connected: bool = True) -> None:
        self.store = store
        self._connected = connected

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get(self, key: str) -> Any | None:
        return self.store.data.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.store.data[key] = value

    async def pop(self, key: str) -> Any | None:
        return self.store.data.pop(key, None)


@pytest.fixture
def workers(monkeypatch: pytest.MonkeyPatch):
    """Two cache views over one shared store, selectable per call."""
    shared = _SharedStore()
    a = _WorkerCache(shared)
    b = _WorkerCache(shared)
    state = {"current": a}
    monkeypatch.setattr(cache_module, "get_cache", lambda: state["current"])
    return state, a, b


# ── validate_access_token ────────────────────────────────────────────────


async def test_valid_access_token_passes(workers) -> None:
    token = create_access_token({"sub": "usr_1"})
    payload = await validate_access_token(token)
    assert payload["sub"] == "usr_1"


async def test_refresh_token_is_not_accepted_as_access_token(workers) -> None:
    refresh = create_refresh_token({"sub": "usr_1"})
    with pytest.raises(AuthenticationError, match="Invalid token type"):
        await validate_access_token(refresh)


async def test_revoked_access_token_is_rejected(workers) -> None:
    token = create_access_token({"sub": "usr_1"})
    await revoke_access_token(token)
    with pytest.raises(AuthenticationError, match="revoked"):
        await validate_access_token(token)


async def test_password_change_cutoff_rejects_older_access_token(workers) -> None:
    # iat must predate the cutoff (same-second tokens are explicitly outside
    # the SEC-07 window, see test_session_revocation.py).
    old_iat = int(datetime.now(UTC).timestamp()) - 600
    token = create_access_token({"sub": "usr_1", "iat": old_iat})
    await revoke_user_access_tokens("usr_1")
    with pytest.raises(AuthenticationError, match="Session ended"):
        await validate_access_token(token)


# ── multi-worker visibility ──────────────────────────────────────────────


async def test_revocation_written_by_one_worker_is_seen_by_another(workers) -> None:
    state, worker_a, worker_b = workers
    token = create_access_token({"sub": "usr_1"})
    jti = decode_access_token(token)["jti"]

    state["current"] = worker_a
    await revoke_token(jti, ttl=60)

    state["current"] = worker_b
    assert await is_token_revoked(jti) is True
    with pytest.raises(AuthenticationError):
        await validate_access_token(token)


# ── refresh tokens ───────────────────────────────────────────────────────


async def test_refresh_token_carries_jti_and_iat(workers) -> None:
    payload = decode_refresh_token(create_refresh_token({"sub": "usr_1"}))
    assert payload["type"] == "refresh"
    assert payload.get("jti")
    assert isinstance(payload.get("iat"), int)
    assert payload["iat"] <= int(datetime.now(UTC).timestamp()) + 1


async def test_revoked_refresh_token_is_detected(workers) -> None:
    refresh = create_refresh_token({"sub": "usr_1"})
    jti = decode_refresh_token(refresh)["jti"]
    await revoke_refresh_token(refresh)
    assert await is_token_revoked(jti) is True


async def test_revoke_refresh_token_ignores_non_refresh_input(workers) -> None:
    # An access token (or garbage) must not be blacklisted by the refresh helper.
    access = create_access_token({"sub": "usr_1"})
    await revoke_refresh_token(access)
    assert await is_token_revoked(decode_access_token(access)["jti"]) is False


# ── refresh rotation (UserService) ───────────────────────────────────────


class _FakeResult:
    def __init__(self, user: Any) -> None:
        self._user = user

    def scalar_one_or_none(self) -> Any:
        return self._user


class _FakeSession:
    def __init__(self, user: Any) -> None:
        self.user = user
        self.flushes = 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult(self.user)

    async def flush(self) -> None:
        self.flushes += 1


def _user(refresh: str):
    return SimpleNamespace(
        id="usr_1",
        username="user",
        email="user@example.test",
        full_name="",
        phone="",
        roles="user",
        is_active=True,
        is_verified=True,
        last_login=None,
        refresh_token=refresh,
    )


async def test_rotation_blacklists_the_presented_refresh_token(workers) -> None:
    from services.user_service import UserService

    old = create_refresh_token({"sub": "usr_1"})
    svc = UserService(_FakeSession(_user(old)))

    result = await svc.refresh_token(old)

    assert result.success is True
    assert result.value["refresh_token"] != old
    assert await is_token_revoked(decode_refresh_token(old)["jti"]) is True
    # The freshly issued token is usable.
    assert await is_token_revoked(decode_refresh_token(result.value["refresh_token"])["jti"]) is False


async def test_refresh_rejects_a_blacklisted_token(workers) -> None:
    from services.user_service import UserService

    refresh = create_refresh_token({"sub": "usr_1"})
    await revoke_refresh_token(refresh)
    svc = UserService(_FakeSession(_user(refresh)))

    result = await svc.refresh_token(refresh)

    assert result.success is False
    assert "revoked" in (result.error or "").lower()


async def test_refresh_rejects_a_session_ended_by_password_change(workers) -> None:
    from services.user_service import UserService

    old_iat = int(datetime.now(UTC).timestamp()) - 600
    refresh = create_refresh_token({"sub": "usr_1", "iat": old_iat})
    await revoke_user_access_tokens("usr_1")
    svc = UserService(_FakeSession(_user(refresh)))

    result = await svc.refresh_token(refresh)

    assert result.success is False
    assert "session ended" in (result.error or "").lower()


# ── fail-open policy stays explicit ──────────────────────────────────────


async def test_redis_outage_keeps_validation_available(monkeypatch) -> None:
    """Documented availability-first policy: a dead store is not a lockout."""
    monkeypatch.setattr(cache_module, "get_cache", lambda: _WorkerCache(_SharedStore(), connected=False))
    payload = await validate_access_token(create_access_token({"sub": "usr_1"}))
    assert payload["sub"] == "usr_1"
