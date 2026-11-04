"""Regression tests for audit ENR-07 — the ``enable_sentry`` flag must be wired.

``init_sentry`` used to activate purely on ``SENTRY_DSN``, so the
``enable_sentry`` feature flag was defined but never consulted. Activation is
now centralised in :func:`sentry_enabled`, which requires both a DSN and the
flag (``FF_ENABLE_SENTRY`` env override wins over the default).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.observability_sentry import sentry_enabled


def _settings(dsn: str | None) -> SimpleNamespace:
    return SimpleNamespace(sentry_dsn=dsn)


def test_disabled_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FF_ENABLE_SENTRY", raising=False)
    assert sentry_enabled(_settings(None)) is False


def test_enabled_with_dsn_and_default_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default is on so an already-configured deployment keeps reporting.
    monkeypatch.delenv("FF_ENABLE_SENTRY", raising=False)
    assert sentry_enabled(_settings("https://key@sentry.example/1")) is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "False", "OFF"])
def test_flag_kill_switch_disables_even_with_dsn(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("FF_ENABLE_SENTRY", value)
    assert sentry_enabled(_settings("https://key@sentry.example/1")) is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_flag_cannot_enable_without_dsn(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("FF_ENABLE_SENTRY", value)
    assert sentry_enabled(_settings(None)) is False


def test_init_sentry_is_noop_when_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SDK must not even be imported when the flag is off."""
    import core.observability_sentry as obs

    monkeypatch.setattr(obs, "_initialized", False)
    monkeypatch.setenv("FF_ENABLE_SENTRY", "false")
    assert obs.init_sentry(_settings("https://key@sentry.example/1")) is False


def test_init_sentry_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.observability_sentry as obs

    monkeypatch.setattr(obs, "_initialized", False)
    monkeypatch.delenv("FF_ENABLE_SENTRY", raising=False)
    assert obs.init_sentry(_settings(None)) is False
