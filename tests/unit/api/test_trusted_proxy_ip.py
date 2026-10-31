"""SEC-06: rate-limit identity must not be client-controlled.

``_get_client_ip`` trusted any ``X-Forwarded-For`` header, so a script could
send a new fake IP per attempt and never hit the login/OTP limits. The header
is now honoured only when the *socket peer* is a configured proxy.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.config import settings


def _request(peer: str | None, xff: str | None = None) -> SimpleNamespace:
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    client = SimpleNamespace(host=peer) if peer else None
    return SimpleNamespace(client=client, headers=headers)


def test_xff_is_ignored_without_trusted_proxies(monkeypatch) -> None:
    from apps.api.endpoints.auth import _get_client_ip

    monkeypatch.setattr(settings, "trusted_proxies", [], raising=False)

    assert _get_client_ip(_request("1.2.3.4", "9.9.9.9")) == "1.2.3.4"


def test_xff_is_used_only_by_a_trusted_proxy(monkeypatch) -> None:
    from apps.api.endpoints.auth import _get_client_ip

    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"], raising=False)

    assert _get_client_ip(_request("10.0.0.1", "9.9.9.9")) == "9.9.9.9"
    # Same header from an untrusted peer stays spoof-proof.
    assert _get_client_ip(_request("1.2.3.4", "9.9.9.9")) == "1.2.3.4"


def test_trusted_proxy_cidr_is_supported(monkeypatch) -> None:
    from apps.api.endpoints.auth import _get_client_ip

    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/24"], raising=False)

    assert _get_client_ip(_request("10.0.0.7", "8.8.8.8")) == "8.8.8.8"


def test_first_xff_hop_wins_behind_a_proxy(monkeypatch) -> None:
    from apps.api.endpoints.auth import _get_client_ip

    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"], raising=False)

    assert _get_client_ip(_request("10.0.0.1", "203.0.113.5, 10.0.0.1")) == "203.0.113.5"


def test_missing_peer_is_unknown(monkeypatch) -> None:
    from apps.api.endpoints.auth import _get_client_ip

    monkeypatch.setattr(settings, "trusted_proxies", [], raising=False)

    assert _get_client_ip(_request(None, "9.9.9.9")) == "unknown"


@pytest.mark.parametrize("endpoint", ["refresh", "logout"])
def test_new_endpoints_have_limits(endpoint: str) -> None:
    from apps.api.endpoints import auth as auth_module

    rate, burst = auth_module._AUTH_LIMITS[endpoint]
    assert rate > 0 and burst >= 1
