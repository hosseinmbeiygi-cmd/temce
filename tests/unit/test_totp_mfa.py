"""Tests for MFA/TOTP: RFC 6238 codes, provisioning URIs, MFA login flow."""

from __future__ import annotations

import pytest

from core.security.totp import (
    build_totp_uri,
    generate_totp,
    generate_totp_secret,
    parse_totp_uri,
    verify_totp,
)

# ════════════════════════════════════════════════════════════════
# TOTP generation & verification
# ════════════════════════════════════════════════════════════════


class TestTOTP:
    def test_generate_secret_is_base32(self):
        secret = generate_totp_secret()
        assert len(secret) == 32  # 20 bytes → 32 base32 chars
        # All chars must be valid base32 (A-Z, 2-7)
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_secrets_unique(self):
        assert generate_totp_secret() != generate_totp_secret()

    def test_code_is_digits(self):
        secret = generate_totp_secret()
        code = generate_totp(secret)
        assert code.isdigit()
        assert len(code) == 6

    def test_verify_correct_code(self):
        secret = generate_totp_secret()
        code = generate_totp(secret)
        assert verify_totp(secret, code) is True

    def test_verify_wrong_code(self):
        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False

    def test_verify_invalid_code_format(self):
        secret = generate_totp_secret()
        assert verify_totp(secret, "abc") is False
        assert verify_totp(secret, "") is False
        assert verify_totp(secret, "1234567") is False

    def test_verify_empty_secret(self):
        assert verify_totp("", "123456") is False

    def test_verify_accepts_drift(self):
        """A code from ±1 time step in the past/future must verify."""
        secret = generate_totp_secret()
        now = 1_700_000_000.0
        past_code = generate_totp(secret, timestamp=now - 30)
        assert verify_totp(secret, past_code, timestamp=now) is True

    def test_deterministic_at_same_timestamp(self):
        secret = generate_totp_secret()
        t = 1_700_000_000.0
        assert generate_totp(secret, timestamp=t) == generate_totp(secret, timestamp=t)


# ════════════════════════════════════════════════════════════════
# Provisioning URIs
# ════════════════════════════════════════════════════════════════


class TestTOTPUri:
    def test_uri_structure(self):
        secret = generate_totp_secret()
        uri = build_totp_uri(secret, "alice")
        assert uri.startswith("otpauth://totp/")
        assert "secret=" in uri
        assert "issuer=" in uri
        assert "period=30" in uri
        assert "digits=6" in uri

    def test_uri_contains_account(self):
        secret = generate_totp_secret()
        uri = build_totp_uri(secret, "alice")
        assert "alice" in uri

    def test_parse_roundtrip(self):
        secret = generate_totp_secret()
        uri = build_totp_uri(secret, "bob", issuer="Test Issuer")
        parsed = parse_totp_uri(uri)
        assert parsed["secret"] == secret
        assert parsed["account"] == "bob"
        assert parsed["issuer"] == "Test Issuer"


# ════════════════════════════════════════════════════════════════
# MFA login flow (service-level, with fake cache + fake session)
# ════════════════════════════════════════════════════════════════


class _FakeUser:
    def __init__(
        self, uid, username="testuser", totp_enabled=False, totp_secret=None,
        mfa_method=None, telegram_chat_id=None,
    ):
        from core.security import hash_password

        self.id = uid
        self.username = username
        self.email = "a@b.c"
        self.roles = "user"
        self.is_active = True
        self.is_verified = False
        self.totp_enabled = totp_enabled
        self.totp_secret = totp_secret
        self.mfa_method = mfa_method
        self.telegram_chat_id = telegram_chat_id
        self.hashed_password = hash_password("testpass")
        self.last_login = None
        self.refresh_token = None
        self.full_name = ""
        self.phone = ""


class _FakeCache:
    def __init__(self):
        self._store = {}

    @property
    def is_connected(self):
        return True

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ttl=None):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)

    async def pop(self, key):
        # Atomic remove-and-return
        return self._store.pop(key, None)


class _DisconnectedCache:
    @property
    def is_connected(self):
        return False

    async def get(self, key):
        return None

    async def set(self, key, value, ttl=None):
        pass

    async def delete(self, key):
        pass

    async def pop(self, key):
        return None


class TestMFALoginFlow:
    @pytest.mark.asyncio
    async def test_login_mfa_required_first_step(self, monkeypatch):
        from services.user_service import UserService

        secret = generate_totp_secret()
        user = _FakeUser("usr-1", totp_enabled=True, totp_secret=secret)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)

        svc = UserService(FakeSession())
        result = await svc.login("testuser", "testpass")
        assert result.success
        data = result.value
        assert data["mfa_required"] is True
        assert data["mfa_token"]

        # The token was stored in the cache keyed by the user id
        assert any(v == "usr-1" for v in cache._store.values())

    @pytest.mark.asyncio
    async def test_login_with_mfa_wrong_code(self, monkeypatch):
        from services.user_service import UserService

        secret = generate_totp_secret()
        user = _FakeUser("usr-1", totp_enabled=True, totp_secret=secret)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)

        svc = UserService(FakeSession())
        first = await svc.login("testuser", "testpass")
        token = first.value["mfa_token"]
        result = await svc.login_with_mfa(token, "000000")
        assert not result.success
        assert "Invalid" in (result.error or "")

    @pytest.mark.asyncio
    async def test_login_with_mfa_correct_code(self, monkeypatch):
        from services.user_service import UserService

        secret = generate_totp_secret()
        user = _FakeUser("usr-1", totp_enabled=True, totp_secret=secret)
        code = generate_totp(secret)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)

        svc = UserService(FakeSession())
        first = await svc.login("testuser", "testpass")
        token = first.value["mfa_token"]
        result = await svc.login_with_mfa(token, code)
        assert result.success
        assert result.value.get("access_token")
        assert result.value.get("refresh_token")

    @pytest.mark.asyncio
    async def test_login_mfa_fails_closed_when_cache_down(self, monkeypatch):
        """When the cache is unavailable the MFA token can never be redeemed,
        so the login must fail instead of returning a dead-end token."""
        from services.user_service import UserService

        secret = generate_totp_secret()
        user = _FakeUser("usr-1", totp_enabled=True, totp_secret=secret)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        monkeypatch.setattr("core.cache.get_cache", lambda: _DisconnectedCache())

        svc = UserService(FakeSession())
        result = await svc.login("testuser", "testpass")
        assert not result.success
        assert "unavailable" in (result.error or "")

    @pytest.mark.asyncio
    async def test_mfa_token_single_use(self, monkeypatch):
        from services.user_service import UserService

        secret = generate_totp_secret()
        user = _FakeUser("usr-1", totp_enabled=True, totp_secret=secret)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)

        svc = UserService(FakeSession())
        first = await svc.login("testuser", "testpass")
        token = first.value["mfa_token"]

        code = generate_totp(secret)
        ok = await svc.login_with_mfa(token, code)
        assert ok.success
        # Second use must fail (token consumed)
        again = await svc.login_with_mfa(token, code)
        assert not again.success


# ════════════════════════════════════════════════════════════════
# Log aggregation handler
# ════════════════════════════════════════════════════════════════


class TestLogAggregator:
    def test_handler_emits_to_redis(self, monkeypatch):
        import logging

        from integrations.observability.log_aggregator import RedisLogHandler

        class FakeRedisClient:
            def __init__(self):
                self.entries = []

            def xadd(self, key, fields, maxlen=None):
                self.entries.append(fields)

        fake = FakeRedisClient()

        class FakeCache:
            @property
            def is_connected(self):
                return True

            @property
            def client(self):
                return fake

        monkeypatch.setattr("core.cache.get_cache", lambda: FakeCache())

        handler = RedisLogHandler(source="test-service")
        record = logging.LogRecord(
            name="test.module", level=logging.WARNING, pathname="x.py",
            lineno=10, msg="hello %s", args=("world",), exc_info=None,
        )
        handler.emit(record)
        assert len(fake.entries) == 1
        assert handler.published == 1
        import json

        payload = json.loads(fake.entries[0]["data"])
        assert payload["source"] == "test-service"
        assert payload["level"] == "WARNING"
        assert payload["message"] == "hello world"

    def test_handler_failure_does_not_crash(self, monkeypatch):
        import logging

        from integrations.observability.log_aggregator import RedisLogHandler

        class BrokenCache:
            @property
            def is_connected(self):
                return True

            @property
            def client(self):
                raise RuntimeError("redis down")

        monkeypatch.setattr("core.cache.get_cache", lambda: BrokenCache())

        handler = RedisLogHandler(source="x")
        record = logging.LogRecord(
            name="m", level=logging.INFO, pathname="p.py", lineno=1,
            msg="msg", args=(), exc_info=None,
        )
        # Must not raise
        handler.emit(record)
        assert handler.failures >= 1


# ════════════════════════════════════════════════════════════════
# Delivered OTP MFA (email / Telegram via generate_otp)
# ════════════════════════════════════════════════════════════════


async def _delivery_ok(self, user, code):
    """Fake delivery (patched as an instance method) that returns True
    and records the sent code for later verification."""
    _delivery_ok.last_code = code
    return True


class TestOTPDeliveryMFA:
    @pytest.mark.asyncio
    async def test_setup_email_delivers_code_and_pends(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1")

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        monkeypatch.setattr("core.cache.get_cache", lambda: _FakeCache())
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        svc = UserService(FakeSession())
        result = await svc.setup_mfa("usr-1", "testpass", method="email")
        assert result.success
        data = result.value
        assert data["method"] == "email"
        assert data["pending"] is True
        assert user.mfa_method == "email"
        assert user.totp_secret is None
        assert _delivery_ok.last_code

    @pytest.mark.asyncio
    async def test_confirm_email_with_delivered_code(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1", mfa_method="email")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        setup = await svc.setup_mfa("usr-1", "testpass", method="email")
        assert setup.success
        code = _delivery_ok.last_code

        ok = await svc.confirm_mfa("usr-1", code)
        assert ok.success
        assert user.totp_enabled is True
        assert ok.value["method"] == "email"

        # Wrong code after success must fail (code already consumed)
        bad = await svc.confirm_mfa("usr-1", code)
        assert not bad.success

    @pytest.mark.asyncio
    async def test_confirm_email_wrong_code(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1", mfa_method="email")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        await svc.setup_mfa("usr-1", "testpass", method="telegram")
        bad = await svc.confirm_mfa("usr-1", "000000")
        assert not bad.success
        assert user.totp_enabled is False

    @pytest.mark.asyncio
    async def test_setup_telegram_stores_per_user_chat_id(self, monkeypatch):
        """setup_mfa(method="telegram") persists the per-user chat ID."""
        from services.user_service import UserService

        user = _FakeUser("usr-1", mfa_method="telegram")

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        monkeypatch.setattr("core.cache.get_cache", lambda: _FakeCache())
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        svc = UserService(FakeSession())
        result = await svc.setup_mfa(
            "usr-1", "testpass", method="telegram", telegram_chat_id="  987654321  "
        )
        assert result.success
        assert user.telegram_chat_id == "987654321"  # trimmed

    @pytest.mark.asyncio
    async def test_deliver_otp_telegram_uses_per_user_chat_id(self, monkeypatch):
        """Telegram OTP delivery passes the user's chat ID to the sender.

        Per-user chat ID wins over the global ``settings.telegram_chat_id`` so
        codes reach the right chat in multi-user deployments.
        """
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="telegram", telegram_chat_id="42")
        captured = {}

        class _FakeSender:
            def __init__(self, chat_id=""):
                captured["chat_id"] = chat_id

            async def send(self, message, parse_mode="HTML"):
                captured["message"] = message
                return ResultOk()

        class ResultOk:
            success = True

        monkeypatch.setattr(
            "integrations.notifications.telegram_sender.TelegramSender", _FakeSender
        )

        svc = UserService.__new__(UserService)
        ok = await svc._deliver_otp(user, "123456")
        assert ok is True
        assert captured["chat_id"] == "42"
        assert "123456" in captured["message"]

    @pytest.mark.asyncio
    async def test_deliver_otp_telegram_falls_back_to_global_chat_id(self, monkeypatch):
        """Without a per-user chat ID the global settings value is used."""
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="telegram", telegram_chat_id=None)
        captured = {}

        class _FakeSender:
            def __init__(self, chat_id=""):
                captured["chat_id"] = chat_id

            async def send(self, message, parse_mode="HTML"):
                return ResultOk()

        class ResultOk:
            success = True

        monkeypatch.setattr(
            "integrations.notifications.telegram_sender.TelegramSender", _FakeSender
        )

        svc = UserService.__new__(UserService)
        ok = await svc._deliver_otp(user, "123456")
        assert ok is True
        assert captured["chat_id"] == ""  # empty → TelegramSender falls back to settings

    @pytest.mark.asyncio
    async def test_login_otp_flow(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="email")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        first = await svc.login("testuser", "testpass")
        assert first.success
        assert first.value["mfa_required"] is True
        assert first.value["method"] == "email"
        token = first.value["mfa_token"]
        code = _delivery_ok.last_code

        ok = await svc.login_with_mfa(token, code)
        assert ok.success
        assert ok.value.get("access_token")

    @pytest.mark.asyncio
    async def test_login_otp_wrong_code(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="telegram")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        first = await svc.login("testuser", "testpass")
        token = first.value["mfa_token"]
        bad = await svc.login_with_mfa(token, "000000")
        assert not bad.success

    @pytest.mark.asyncio
    async def test_disable_email_sends_fresh_code_then_disables(self, monkeypatch):
        """disable_mfa for OTP methods must deliver a fresh code first — the
        code stored at login/setup time is not reused for disabling."""
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="email")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        # Step 1: request a fresh code (no stale code in cache)
        first = await svc.disable_mfa("usr-1", "testpass", "", send_new_code=True)
        assert first.success
        assert first.value["requires_code"] is True
        fresh = _delivery_ok.last_code
        assert fresh

        # Step 2: submit the delivered code to complete the disable
        done = await svc.disable_mfa("usr-1", "testpass", fresh)
        assert done.success
        assert done.value["enabled"] is False
        assert user.mfa_method is None

    @pytest.mark.asyncio
    async def test_disable_email_wrong_code(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="email")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)
        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _delivery_ok)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        first = await svc.disable_mfa("usr-1", "testpass", "", send_new_code=True)
        assert first.success
        bad = await svc.disable_mfa("usr-1", "testpass", "000000")
        assert not bad.success
        assert user.totp_enabled is True  # still enabled

    @pytest.mark.asyncio
    async def test_otp_delivery_failure_fails_closed(self, monkeypatch):
        from services.user_service import UserService

        user = _FakeUser("usr-1", totp_enabled=True, mfa_method="email")
        cache = _FakeCache()
        monkeypatch.setattr("core.cache.get_cache", lambda: cache)

        async def _fail_delivery(user, code):
            return False

        monkeypatch.setattr("services.user_service.UserService._deliver_otp", _fail_delivery)

        class FakeSession:
            async def execute(self, *a, **k):
                class R:
                    def scalar_one_or_none(self):
                        return user

                return R()

            async def flush(self, *a, **k):
                pass

        svc = UserService(FakeSession())
        result = await svc.login("testuser", "testpass")
        assert not result.success
        assert "verification code" in (result.error or "")
