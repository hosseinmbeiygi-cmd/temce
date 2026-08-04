"""End-to-end MFA integration test against a real PostgreSQL instance.

Exercises the **real** :class:`UserService` (and its ORM models) through the
complete MFA lifecycle:

    register → setup (totp & email) → confirm → two-step login → disable

The real database proves the ``users`` columns (``totp_secret``,
``totp_enabled``, ``mfa_method``, ``telegram_chat_id`` …) actually persist
and round-trip — the same runtime that the API uses. Only the transport
layer is faked:

- **Redis** is replaced by an in-memory cache (MFA tokens + delivered OTP
  codes) so the test runs without a Redis server.
- **Email/Telegram senders** are faked — the test captures the delivered
  code instead of sending a real message.

A throwaway PostgreSQL schema (``test_mfa_<uuid>``) is created and dropped
around the tests so live tables are never touched. All connections from the
fixture engine land in that schema via asyncpg ``search_path``.

Skipped automatically when PostgreSQL is unreachable (``needs_db`` marker —
see ``tests/conftest.py``). Run with a reachable ``DATABASE_URL``, e.g.::

    DATABASE_URL=$(grep '^DATABASE_URL=' .env | cut -d= -f2-) \\
        python -m pytest tests/unit/test_mfa_integration.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.security.totp import generate_totp
from models.base import Base
from models.user import UserModel
from services.user_service import UserService

# ── In-memory cache (stands in for Redis) ─────────────────────────────

class _MemCache:
    """Minimal async cache with GETDEL (atomic pop) like ``core.cache``."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    @property
    def is_connected(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def pop(self, key: str) -> str | None:
        return self._store.pop(key, None)


# A module-level cache instance shared across every service call in a test,
# so tokens/OTP codes issued by one call are visible to the next.
_CACHE = _MemCache()


def _fake_get_cache() -> _MemCache:
    return _CACHE


# ── OTP delivery stub: capture the code instead of emailing it ────────

_CAPTURED_OTP: dict[str, str] = {}


async def _delivery_capture(self, user, code: str) -> bool:
    """Stand-in for ``UserService._deliver_otp`` — records the code."""
    _CAPTURED_OTP[user.id] = code
    return True


def _db_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://market:market@localhost:5432/market_test",
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# ── Fixture: throwaway Postgres schema with only the users table ──────

@pytest.fixture()
async def mfa_db():
    """Throwaway schema containing only ``users``.

    Function-scoped so every test gets a fresh ``test_mfa_<uuid>`` schema.
    Connections land there via asyncpg ``server_settings.search_path`` —
    unqualified statements from the service therefore hit the throwaway
    tables only; live ``public`` tables are never touched.
    """
    schema = f"test_mfa_{uuid.uuid4().hex[:10]}"
    base_url = _db_url()

    admin = create_async_engine(base_url)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        await admin.dispose()

    engine = create_async_engine(
        base_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[UserModel.__table__])

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield engine, Session
    finally:
        await engine.dispose()
        admin = create_async_engine(base_url)
        try:
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await admin.dispose()


@pytest.fixture(autouse=True)
def _mfa_isolate(monkeypatch):
    """Point the service's cache at the in-memory store for every test."""
    monkeypatch.setattr("core.cache.get_cache", _fake_get_cache)
    _CACHE._store.clear()
    _CAPTURED_OTP.clear()
    yield


# ── Helpers ───────────────────────────────────────────────────────────

async def _count_users(Session) -> int:
    async with Session() as s:
        return len((await s.execute(select(UserModel))).scalars().all())


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.needs_db
async def test_full_mfa_totp_lifecycle_on_real_db(mfa_db):
    """register → setup(totp) → confirm → two-step login → disable."""
    engine, Session = mfa_db

    # ── 1. register ──
    async with Session() as session:
        svc = UserService(session)
        reg = await svc.register("mfa_user", "mfa@example.com", "StrongPass1", "کاربر تست")
        assert reg.success, reg.error
        assert reg.value["access_token"]
        user_id = reg.value["user"]["id"]

        # ── 2. setup (totp) → returns secret + otpauth URI ──
        setup = await svc.setup_mfa(user_id, "StrongPass1", method="totp")
        assert setup.success, setup.error
        data = setup.value
        assert data["method"] == "totp"
        assert data["secret"] and data["uri"]
        await session.commit()

    # Secret must have been persisted to the real DB.
    async with Session() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one()
        assert user.totp_secret == data["secret"]
        assert user.mfa_method == "totp"
        assert user.totp_enabled is False  # not confirmed yet

    # ── 3. confirm with a fresh TOTP code (computed from the stored secret) ──
    async with Session() as session:
        svc = UserService(session)
        code = generate_totp(data["secret"])
        confirm = await svc.confirm_mfa(user_id, code)
        assert confirm.success, confirm.error
        assert confirm.value == {"enabled": True, "method": "totp"}
        await session.commit()

    async with Session() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one()
        assert user.totp_enabled is True
        assert user.totp_confirmed_at is not None

    # ── 4. two-step login: step 1 returns mfa_required + pending token ──
    async with Session() as session:
        svc = UserService(session)
        first = await svc.login("mfa_user", "StrongPass1")
        assert first.success, first.error
        assert first.value["mfa_required"] is True
        assert first.value["method"] == "totp"
        mfa_token = first.value["mfa_token"]

        # Step 2: exchange the pending token + code for real tokens.
        second = await svc.login_with_mfa(mfa_token, generate_totp(data["secret"]))
        assert second.success, second.error
        assert second.value["access_token"] and second.value["refresh_token"]
        assert second.value["user"]["id"] == user_id
        await session.commit()

    # ── 5. disable: password + a valid authenticator code ──
    async with Session() as session:
        svc = UserService(session)
        dis = await svc.disable_mfa(user_id, "StrongPass1", generate_totp(data["secret"]))
        assert dis.success, dis.error
        assert dis.value == {"enabled": False}
        await session.commit()

    async with Session() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one()
        assert user.totp_enabled is False
        assert user.totp_secret is None
        assert user.mfa_method is None


@pytest.mark.needs_db
async def test_mfa_email_otp_flow_on_real_db(mfa_db, monkeypatch):
    """email MFA: delivered code is persisted and verified on the real DB."""
    engine, Session = mfa_db
    monkeypatch.setattr(
        "services.user_service.UserService._deliver_otp", _delivery_capture
    )

    async with Session() as session:
        svc = UserService(session)
        reg = await svc.register("mfa_email_user", "mfa2@example.com", "StrongPass1")
        assert reg.success, reg.error
        user_id = reg.value["user"]["id"]

        # setup(email) delivers a code and persists a pending state
        setup = await svc.setup_mfa(user_id, "StrongPass1", method="email")
        assert setup.success, setup.error
        assert setup.value == {
            "method": "email",
            "pending": True,
            "delivered_to": "email",
        }
        otp = _CAPTURED_OTP.get(user_id)
        assert otp and len(otp) == 6 and otp.isdigit()
        await session.commit()

    # The pending state survived the DB round-trip (mfa_method persisted).
    async with Session() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one()
        assert user.mfa_method == "email"
        assert user.totp_enabled is False

    # confirm with the captured code
    async with Session() as session:
        svc = UserService(session)
        confirm = await svc.confirm_mfa(user_id, _CAPTURED_OTP[user_id])
        assert confirm.success, confirm.error
        await session.commit()

    # wrong code must be rejected
    async with Session() as session:
        svc = UserService(session)
        bad = await svc.confirm_mfa(user_id, "000000")
        assert not bad.success
        # The stored OTP was already consumed by the successful confirm.
        await session.commit()

    # two-step login with email OTP
    async with Session() as session:
        svc = UserService(session)
        first = await svc.login("mfa_email_user", "StrongPass1")
        assert first.success and first.value["mfa_required"]
        token = first.value["mfa_token"]
        # login re-delivers a fresh code — capture it
        otp = _CAPTURED_OTP.get(user_id)
        second = await svc.login_with_mfa(token, otp)
        assert second.success, second.error
        assert second.value["user"]["id"] == user_id
        await session.commit()

    # disable requires a fresh code (send_new_code=True path)
    async with Session() as session:
        svc = UserService(session)
        step1 = await svc.disable_mfa(
            user_id, "StrongPass1", "", send_new_code=True
        )
        assert step1.success and step1.value.get("requires_code") is True
        fresh = _CAPTURED_OTP.get(user_id)
        dis = await svc.disable_mfa(user_id, "StrongPass1", fresh)
        assert dis.success, dis.error
        assert dis.value == {"enabled": False}
        await session.commit()

    async with Session() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one()
        assert user.totp_enabled is False
        assert user.mfa_method is None
        assert await _count_users(Session) == 1  # exactly one user row persisted


@pytest.mark.needs_db
async def test_mfa_wrong_password_and_bruteforce_rejected(mfa_db):
    """setup/disable require the current password; wrong codes are rejected."""
    engine, Session = mfa_db

    async with Session() as session:
        svc = UserService(session)
        reg = await svc.register("mfa_secure_user", "mfa3@example.com", "StrongPass1")
        assert reg.success
        user_id = reg.value["user"]["id"]

        # wrong password → setup refused
        bad_pass = await svc.setup_mfa(user_id, "wrongpass", method="totp")
        assert not bad_pass.success

        # correct password → proceeds
        setup = await svc.setup_mfa(user_id, "StrongPass1", method="totp")
        assert setup.success
        secret = setup.value["secret"]

        # wrong TOTP code → confirm refused
        bad_code = await svc.confirm_mfa(user_id, "000000")
        assert not bad_code.success

        # right code → confirmed
        ok = await svc.confirm_mfa(user_id, generate_totp(secret))
        assert ok.success
        await session.commit()

    # wrong password at disable → refused
    async with Session() as session:
        svc = UserService(session)
        dis = await svc.disable_mfa(user_id, "wrongpass", generate_totp(secret))
        assert not dis.success
        assert dis.error == "Current password is incorrect"
        await session.commit()

    # user still has MFA enabled afterwards
    async with Session() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one()
        assert user.totp_enabled is True
