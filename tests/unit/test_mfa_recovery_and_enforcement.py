"""MFA hardening: recovery codes, enforced enrollment, TOTP replay protection."""

from __future__ import annotations

import pytest

from core.config import settings as app_settings
from core.security import hash_password
from core.security.totp import generate_totp, generate_totp_secret
from services.user_service import RECOVERY_CODE_COUNT, UserService


class _FakeUser:
    def __init__(
        self,
        uid="usr-1",
        username="testuser",
        roles="user",
        totp_enabled=False,
        totp_secret=None,
        mfa_method=None,
    ):
        self.id = uid
        self.username = username
        self.email = "a@b.c"
        self.roles = roles
        self.is_active = True
        self.is_verified = False
        self.totp_enabled = totp_enabled
        self.totp_secret = totp_secret
        self.totp_confirmed_at = None
        self.mfa_method = mfa_method
        self.telegram_chat_id = None
        self.hashed_password = hash_password("testpass")
        self.last_login = None
        self.refresh_token = None
        self.full_name = ""
        self.phone = ""


class _FakeSession:
    def __init__(self, user):
        self.user = user

    async def execute(self, *_a, **_k):
        class _R:
            def __init__(self, user):
                self._user = user

            def scalar_one_or_none(self):
                return self._user

        return _R(self.user)

    async def flush(self, *_a, **_k):
        pass


class _FakeCache:
    """In-memory cache with the persistent-write API used by recovery codes."""

    def __init__(self, connected=True):
        self._store = {}
        self._connected = connected

    @property
    def is_connected(self):
        return self._connected

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ttl=None):
        self._store[key] = value

    async def set_persistent(self, key, value):
        self._store[key] = value
        return True

    async def delete(self, key):
        self._store.pop(key, None)

    async def pop(self, key):
        return self._store.pop(key, None)


@pytest.fixture
def cache(monkeypatch):
    fake = _FakeCache()
    monkeypatch.setattr("core.cache.get_cache", lambda: fake)
    return fake


def _svc(user) -> UserService:
    return UserService(_FakeSession(user))


# ── Recovery codes ───────────────────────────────────────────────────────


async def test_confirm_mfa_issues_recovery_codes(cache):
    secret = generate_totp_secret()
    user = _FakeUser(totp_secret=secret, mfa_method="totp")
    svc = _svc(user)

    result = await svc.confirm_mfa("usr-1", generate_totp(secret))

    assert result.success
    assert user.totp_enabled is True
    codes = result.value["recovery_codes"]
    assert len(codes) == RECOVERY_CODE_COUNT
    assert len(set(codes)) == RECOVERY_CODE_COUNT

    status = await svc.mfa_status("usr-1")
    assert status.value["recovery_codes_remaining"] == RECOVERY_CODE_COUNT


async def test_recovery_code_login_is_single_use(cache):
    secret = generate_totp_secret()
    user = _FakeUser(totp_enabled=True, totp_secret=secret, mfa_method="totp")
    svc = _svc(user)
    codes = (await svc.confirm_mfa("usr-1", generate_totp(secret))).value["recovery_codes"]

    first = await svc.login("testuser", "testpass")
    ok = await svc.login_with_recovery_code(first.value["mfa_token"], codes[0])
    assert ok.success
    assert ok.value["access_token"]
    assert ok.value["recovery_codes_remaining"] == RECOVERY_CODE_COUNT - 1

    second = await svc.login("testuser", "testpass")
    again = await svc.login_with_recovery_code(second.value["mfa_token"], codes[0])
    assert again.success is False
    assert "already used" in (again.error or "").lower()


async def test_wrong_recovery_code_rejected(cache):
    secret = generate_totp_secret()
    user = _FakeUser(totp_enabled=True, totp_secret=secret, mfa_method="totp")
    svc = _svc(user)
    await svc.confirm_mfa("usr-1", generate_totp(secret))

    first = await svc.login("testuser", "testpass")
    bad = await svc.login_with_recovery_code(first.value["mfa_token"], "deadbeef-cafe")
    assert bad.success is False


async def test_recovery_login_fails_closed_when_store_down(monkeypatch):
    secret = generate_totp_secret()
    user = _FakeUser(totp_enabled=True, totp_secret=secret, mfa_method="totp")
    svc = _svc(user)

    # Enrollment path with a working store, then the store dies.
    monkeypatch.setattr("core.cache.get_cache", lambda: _FakeCache())
    await svc.confirm_mfa("usr-1", generate_totp(secret))

    monkeypatch.setattr("core.cache.get_cache", lambda: _FakeCache(connected=False))
    result = await svc.login_with_recovery_code("some-mfa-token", "deadbeef-cafe")
    assert result.success is False


async def test_disable_mfa_clears_recovery_codes(cache):
    secret = generate_totp_secret()
    user = _FakeUser(totp_enabled=True, totp_secret=secret, mfa_method="totp")
    svc = _svc(user)
    codes = (await svc.confirm_mfa("usr-1", generate_totp(secret))).value["recovery_codes"]

    done = await svc.disable_mfa("usr-1", "testpass", generate_totp(secret))
    assert done.success
    assert codes  # issued at enable time

    assert await svc._recovery_codes_remaining("usr-1") == 0


async def test_regenerate_recovery_codes_invalidates_old_set(cache):
    secret = generate_totp_secret()
    user = _FakeUser(totp_enabled=True, totp_secret=secret, mfa_method="totp")
    svc = _svc(user)
    old = (await svc.confirm_mfa("usr-1", generate_totp(secret))).value["recovery_codes"]

    regen = await svc.regenerate_recovery_codes("usr-1", "testpass")
    assert regen.success
    new = regen.value["recovery_codes"]
    assert set(old).isdisjoint(new)

    first = await svc.login("testuser", "testpass")
    assert (await svc.login_with_recovery_code(first.value["mfa_token"], old[0])).success is False

    second = await svc.login("testuser", "testpass")
    assert (await svc.login_with_recovery_code(second.value["mfa_token"], new[0])).success is True


# ── Enforcement policy ───────────────────────────────────────────────────


async def test_enforced_role_blocks_login_until_enrollment(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", ["admin"])
    monkeypatch.setattr(app_settings, "mfa_required_for_all", False)
    user = _FakeUser(roles="admin")

    result = await _svc(user).login("testuser", "testpass")

    assert result.success
    assert result.value["mfa_required"] is True
    assert result.value["enrollment_required"] is True
    assert "access_token" not in result.value


async def test_non_enforced_role_logs_in_normally(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", ["admin"])
    monkeypatch.setattr(app_settings, "mfa_required_for_all", False)
    user = _FakeUser(roles="user")

    result = await _svc(user).login("testuser", "testpass")

    assert result.success
    assert result.value.get("access_token")


async def test_enforce_all(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", [])
    monkeypatch.setattr(app_settings, "mfa_required_for_all", True)

    result = await _svc(_FakeUser(roles="viewer")).login("testuser", "testpass")

    assert result.value["enrollment_required"] is True


async def test_enabled_mfa_takes_the_normal_two_factor_path(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", ["admin"])
    secret = generate_totp_secret()
    user = _FakeUser(roles="admin", totp_enabled=True, totp_secret=secret, mfa_method="totp")

    result = await _svc(user).login("testuser", "testpass")

    assert result.value["mfa_required"] is True
    assert result.value.get("enrollment_required") is not True


# ── Enrollment flow ──────────────────────────────────────────────────────


async def test_enrollment_start_finish_issues_tokens_and_codes(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", ["admin"])
    user = _FakeUser(roles="admin")
    svc = _svc(user)

    login = await svc.login("testuser", "testpass")
    start = await svc.start_enrollment(login.value["mfa_token"], "testpass")
    assert start.success
    assert start.value["uri"].startswith("otpauth://totp/")
    assert start.value["mfa_token"] != login.value["mfa_token"]

    finish = await svc.finish_enrollment(
        start.value["mfa_token"], generate_totp(start.value["secret"])
    )
    assert finish.success
    assert finish.value["access_token"]
    assert len(finish.value["recovery_codes"]) == RECOVERY_CODE_COUNT
    assert user.totp_enabled is True


async def test_enrollment_finish_rejects_wrong_code(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", ["admin"])
    user = _FakeUser(roles="admin")
    svc = _svc(user)

    login = await svc.login("testuser", "testpass")
    start = await svc.start_enrollment(login.value["mfa_token"], "testpass")
    bad = await svc.finish_enrollment(start.value["mfa_token"], "000000")

    assert bad.success is False
    assert user.totp_enabled is False


async def test_enrollment_requires_the_password(cache, monkeypatch):
    monkeypatch.setattr(app_settings, "mfa_required_roles", ["admin"])
    svc = _svc(_FakeUser(roles="admin"))

    login = await svc.login("testuser", "testpass")
    bad = await svc.start_enrollment(login.value["mfa_token"], "wrong")

    assert bad.success is False
    assert "password" in (bad.error or "").lower()


# ── TOTP replay protection ───────────────────────────────────────────────


async def test_totp_code_cannot_be_replayed(cache):
    secret = generate_totp_secret()
    user = _FakeUser(totp_enabled=True, totp_secret=secret, mfa_method="totp")
    svc = _svc(user)
    code = generate_totp(secret)

    first = await svc.login("testuser", "testpass")
    ok = await svc.login_with_mfa(first.value["mfa_token"], code)
    assert ok.success

    second = await svc.login("testuser", "testpass")
    replay = await svc.login_with_mfa(second.value["mfa_token"], code)
    assert replay.success is False
    assert "Invalid" in (replay.error or "")
