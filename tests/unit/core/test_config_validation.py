"""Regression tests for audit CFG-02 / SEC-05 (config hardening).

``validate_production`` must reject insecure defaults for both ``production``
and ``staging`` deployments: a default signing key, ``auth_disabled=True``,
open CORS, SQLite, an insecure refresh cookie, or a missing OTLP endpoint.
"""

from __future__ import annotations

import pytest

from core.config import Settings

_SECURE_KWARGS = {
    "secret_key": "a-real-signing-key",
    "auth_cookie_secure": True,
    "otlp_endpoint": "http://collector:4317",
    "cors_origins": ["https://example.com"],
    "database_url": "postgresql+asyncpg://user:pw@db:5432/market",
}


def _settings(**overrides):
    return Settings(**{**_SECURE_KWARGS, **overrides})


def test_production_rejects_auth_disabled() -> None:
    settings = _settings(environment="production", auth_disabled=True)
    with pytest.raises(RuntimeError) as excinfo:
        settings.validate_production()
    assert "AUTH_DISABLED" in str(excinfo.value)


def test_production_rejects_default_secret() -> None:
    settings = _settings(environment="production", secret_key="change-me-in-production")
    with pytest.raises(RuntimeError) as excinfo:
        settings.validate_production()
    assert "SECRET_KEY" in str(excinfo.value)


def test_staging_rejects_default_secret() -> None:
    settings = _settings(environment="staging", secret_key="change-me-in-production")
    with pytest.raises(RuntimeError) as excinfo:
        settings.validate_production()
    assert "SECRET_KEY" in str(excinfo.value)


def test_secure_production_settings_pass() -> None:
    settings = _settings(environment="production")
    settings.validate_production()  # must not raise


def test_development_is_not_validated() -> None:
    # Local development may use the insecure defaults on purpose.
    settings = _settings(environment="development", auth_disabled=True, secret_key="change-me-in-production")
    settings.validate_production()  # must not raise
