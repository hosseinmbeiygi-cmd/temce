"""Security hardening tests: registration gate + /docs exposure.

RED:
  - register endpoint accepts requests even when REGISTRATION_OPEN=False
  - create_app() passes docs_url='/docs' unconditionally even in production

GREEN:
  - register returns 403 when settings.registration_open is False
  - create_app() passes docs_url=None / openapi_url=None when is_production=True
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Registration gate ────────────────────────────────────────────────────────

def _make_register_app(registration_open: bool, mock_svc=None):
    """Return a FastAPI test app with the register route and all dependencies mocked."""
    from fastapi import FastAPI
    from core.database import get_session
    from apps.api.endpoints.auth import router as auth_router, register_rate_limit

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _mock_session():
        yield AsyncMock()

    app.dependency_overrides[get_session] = _mock_session
    app.dependency_overrides[register_rate_limit] = lambda: None  # bypass rate limiter

    return app


@pytest.mark.asyncio
async def test_register_returns_403_when_registration_closed():
    """When registration_open=False, /auth/register must return 403.

    RED: endpoint calls user_service.register() and returns 200 regardless.
    GREEN: endpoint raises 403 HTTPException before touching the service.
    """
    from fastapi.testclient import TestClient

    app = _make_register_app(registration_open=False)

    mock_settings = MagicMock()
    mock_settings.registration_open = False
    mock_settings.auth_cookie_name = "refresh_token"

    with patch("apps.api.endpoints.auth.settings", mock_settings):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/register", json={
                "username": "attacker",
                "email": "a@a.com",
                "password": "P@ssw0rd123",
            })

    assert resp.status_code == 403, (
        f"Expected 403 when registration_open=False but got {resp.status_code}. "
        "Open registration in production allows an attacker to claim the admin account."
    )


@pytest.mark.asyncio
async def test_register_proceeds_when_registration_open():
    """When registration_open=True, the endpoint proceeds normally (regression guard)."""
    from fastapi.testclient import TestClient

    app = _make_register_app(registration_open=True)

    mock_svc = MagicMock()
    mock_svc.register = AsyncMock(return_value=MagicMock(
        success=True,
        value={"access_token": "tok", "refresh_token": "ref",
               "user": {"id": "u1", "username": "u", "email": "e@e.com",
                        "full_name": "", "phone": "", "roles": ["user"],
                        "is_active": True, "is_verified": False}}
    ))

    mock_settings = MagicMock()
    mock_settings.registration_open = True
    mock_settings.auth_cookie_name = "refresh_token"
    mock_settings.auth_cookie_secure = False
    mock_settings.auth_cookie_samesite = "lax"
    mock_settings.auth_cookie_domain = ""
    mock_settings.refresh_token_expire_days = 30

    with patch("apps.api.endpoints.auth.settings", mock_settings):
        with patch("apps.api.endpoints.auth.UserService", lambda *a, **kw: mock_svc):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/auth/register", json={
                    "username": "user1",
                    "email": "user1@test.com",
                    "password": "P@ssw0rd123",
                })

    assert resp.status_code == 200, (
        f"Expected 200 when registration_open=True but got {resp.status_code}."
    )


# ─── /docs and /openapi.json disabled in production ──────────────────────────

def _capture_create_app_fastapi_kwargs(is_production: bool) -> dict:
    """Call create_app() with a patched settings and capture what kwargs
    were passed to FastAPI(). Stops early once kwargs are captured to avoid
    needing a full settings mock for all routes."""
    import fastapi as _fastapi_module
    from apps.api import app as app_module  # noqa: F401

    captured: dict = {}
    real_cls = _fastapi_module.FastAPI

    class _Capture(real_cls):
        def __init__(self_inner, *args, **kwargs):
            captured.update(kwargs)
            # Raise so we stop before all the route registrations that need
            # more settings attrs — we only care about docs_url/openapi_url.
            raise RuntimeError("__captured__")

    mock_settings = MagicMock()
    mock_settings.is_production = is_production

    with patch("apps.api.app.FastAPI", _Capture):
        with patch("apps.api.app.settings", mock_settings):
            try:
                from apps.api.app import create_app
                create_app()
            except RuntimeError as exc:
                if "__captured__" not in str(exc):
                    raise

    return captured


def test_create_app_docs_url_is_none_in_production():
    """create_app() must pass docs_url=None to FastAPI when is_production=True.

    RED: create_app() hardcodes docs_url='/docs'.
    GREEN: docs_url=None when settings.is_production is True.
    """
    kwargs = _capture_create_app_fastapi_kwargs(is_production=True)

    assert kwargs.get("docs_url") is None, (
        f"Expected docs_url=None in production but got {kwargs.get('docs_url')!r}. "
        "API schema must not be publicly accessible in production."
    )
    assert kwargs.get("openapi_url") is None, (
        f"Expected openapi_url=None in production but got {kwargs.get('openapi_url')!r}."
    )


def test_create_app_docs_url_is_set_in_development():
    """create_app() must pass docs_url='/docs' in non-production (regression guard)."""
    kwargs = _capture_create_app_fastapi_kwargs(is_production=False)

    assert kwargs.get("docs_url") == "/docs", (
        f"Expected docs_url='/docs' in development but got {kwargs.get('docs_url')!r}."
    )
    assert kwargs.get("openapi_url") == "/openapi.json", (
        f"Expected openapi_url='/openapi.json' in development but got {kwargs.get('openapi_url')!r}."
    )
