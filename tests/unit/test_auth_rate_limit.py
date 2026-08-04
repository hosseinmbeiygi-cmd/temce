"""Regression tests for the auth endpoint brute-force rate limiting.

Covers the critical fix in ``apps/api/endpoints/auth.py``:
previously the limiter registered bare keys (``auth:login``) but checked
per-IP keys (``auth:login:{ip}``) — and ``RateLimiter.allow()`` returns
``True`` for unregistered keys, so the brute-force protection silently
never activated. The fix registers the limit lazily per-IP-key via
``has_limit()`` + ``set_limit()`` inside ``_rate_limit_auth``.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.api.endpoints import auth as auth_module
from core.rate_limit.limiter import RateLimiter


@pytest.fixture
def limiter():
    """Fresh RateLimiter per test, wired into the auth module."""
    lim = RateLimiter()
    with patch.object(auth_module, "_limiter", lim):
        yield lim


def _make_request(client_ip: str = "203.0.113.7"):
    """Build a minimal fake FastAPI Request with a client IP."""
    return SimpleNamespace(client=SimpleNamespace(host=client_ip))


class TestAuthRateLimit:
    """Verify login/register/change_password rate limiting actually blocks."""

    def test_login_allows_burst_then_blocks(self, limiter: RateLimiter):
        """5 allowed attempts per IP, then 6th raises 429."""
        req = _make_request()
        for _ in range(5):
            auth_module._rate_limit_auth(req, "login")  # should not raise

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth_module._rate_limit_auth(req, "login")
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    def test_keys_are_ip_scoped(self, limiter: RateLimiter):
        """Different IPs get independent buckets — the original bug."""
        ip_a = _make_request("203.0.113.1")
        ip_b = _make_request("203.0.113.2")

        from fastapi import HTTPException

        # Exhaust IP A
        for _ in range(5):
            auth_module._rate_limit_auth(ip_a, "login")

        # IP A now blocked
        with pytest.raises(HTTPException):
            auth_module._rate_limit_auth(ip_a, "login")

        # IP B still has full quota
        for _ in range(5):
            auth_module._rate_limit_auth(ip_b, "login")
        with pytest.raises(HTTPException):
            auth_module._rate_limit_auth(ip_b, "login")

    def test_endpoints_have_separate_buckets(self, limiter: RateLimiter):
        """login and register use distinct keys — exhausting one doesn't hit the other."""
        req = _make_request()

        from fastapi import HTTPException

        # Exhaust login (burst 5)
        for _ in range(5):
            auth_module._rate_limit_auth(req, "login")
        with pytest.raises(HTTPException):
            auth_module._rate_limit_auth(req, "login")

        # register (burst 3) is untouched
        for _ in range(3):
            auth_module._rate_limit_auth(req, "register")
        with pytest.raises(HTTPException):
            auth_module._rate_limit_auth(req, "register")

    def test_window_resets_after_60s(self, limiter: RateLimiter):
        """After the window elapses, the bucket refills (sliding window prunes)."""
        req = _make_request()

        from fastapi import HTTPException

        for _ in range(5):
            auth_module._rate_limit_auth(req, "login")
        with pytest.raises(HTTPException):
            auth_module._rate_limit_auth(req, "login")

        # Simulate time passing beyond the 60s window
        with patch("core.rate_limit.limiter.time.monotonic", side_effect=[time.monotonic() + 61.0]):
            auth_module._rate_limit_auth(req, "login")  # should not raise

    def test_missing_client_ip_uses_unknown_key(self, limiter: RateLimiter):
        """Requests without a client fall back to a stable 'unknown' bucket."""
        req = SimpleNamespace(client=None)

        from fastapi import HTTPException

        for _ in range(5):
            auth_module._rate_limit_auth(req, "login")
        with pytest.raises(HTTPException):
            auth_module._rate_limit_auth(req, "login")


class TestAuthLimitsConfig:
    """Verify the declared per-endpoint limits match the config dict."""

    def test_config_has_all_endpoints(self):
        assert set(auth_module._AUTH_LIMITS) == {
            "login", "register", "change_password", "mfa_login", "mfa_setup"
        }

    def test_config_bursts_are_positive(self):
        for endpoint, (_rate, burst) in auth_module._AUTH_LIMITS.items():
            assert burst >= 1, f"{endpoint} burst must be >= 1"
