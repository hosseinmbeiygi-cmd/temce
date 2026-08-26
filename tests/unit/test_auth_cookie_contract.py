"""HTTP-level tests for the cookie-only auth contract.

Locks in the security property that ``refresh_token`` is NEVER included in
JSON responses — it travels only inside the httpOnly cookie:

  - register / login / mfa-login return ``{user, access_token}`` + Set-Cookie
  - /auth/refresh reads the token ONLY from the cookie (body ignored) and
    returns ``{access_token, user}`` while rotating the cookie

Uses a bare FastAPI app with the auth router, mocked UserService methods and
no-op rate-limit dependencies (no DB, no Redis).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.auth import (  # noqa: E402
    login_rate_limit,
    mfa_login_rate_limit,
    register_rate_limit,
)
from apps.api.endpoints.auth import (
    router as auth_router,
)
from core.config import settings  # noqa: E402
from core.database import get_session  # noqa: E402
from core.typing import Result  # noqa: E402

pytestmark = pytest.mark.needs_db


# ── Helpers ─────────────────────────────────────────────────────

def _user_dict() -> dict:
    return {
        "id": "usr_1",
        "username": "ali",
        "email": "ali@example.com",
        "full_name": "علی",
        "phone": "",
        "roles": ["user"],
        "is_active": True,
        "is_verified": False,
        "last_login": None,
    }


def make_app() -> FastAPI:
    """Bare app with the auth router; rate limits + DB session disabled."""
    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def no_session():
        yield None

    app.dependency_overrides[get_session] = no_session
    app.dependency_overrides[login_rate_limit] = lambda: None
    app.dependency_overrides[register_rate_limit] = lambda: None
    app.dependency_overrides[mfa_login_rate_limit] = lambda: None
    return app


def _set_cookie_header(resp) -> str:
    return resp.headers.get("set-cookie", "")


# ── Tests ───────────────────────────────────────────────────────

class TestResponsesOmitRefreshToken:
    """register / login / mfa-login return user+access_token, never refresh_token."""

    @pytest.mark.asyncio
    async def test_register_response_omits_refresh_token(self):
        app = make_app()
        with patch(
            "services.user_service.UserService.register",
            new=AsyncMock(
                return_value=Result.ok(
                    {
                        "user": _user_dict(),
                        "access_token": "acc-token",
                        "refresh_token": "ref-token",
                    }
                )
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/auth/register",
                    json={
                        "username": "ali",
                        "email": "ali@example.com",
                        "password": "strongpass123",
                    },
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["access_token"] == "acc-token"
        assert body["data"]["user"]["username"] == "ali"
        # The security property: refresh_token never appears in JSON.
        assert "refresh_token" not in body["data"]
        assert "refresh_token" not in resp.text
        # …it lives in the httpOnly cookie instead.
        cookie = _set_cookie_header(resp)
        assert settings.auth_cookie_name in cookie
        assert "httponly" in cookie.lower()

    @pytest.mark.asyncio
    async def test_login_response_omits_refresh_token(self):
        app = make_app()
        with patch(
            "services.user_service.UserService.login",
            new=AsyncMock(
                return_value=Result.ok(
                    {
                        "user": _user_dict(),
                        "access_token": "acc-token",
                        "refresh_token": "ref-token",
                    }
                )
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/auth/login",
                    json={"username": "ali", "password": "secret123"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "access_token" in body["data"]
        assert "refresh_token" not in body["data"]
        assert "refresh_token" not in resp.text
        cookie = _set_cookie_header(resp)
        assert settings.auth_cookie_name in cookie
        assert "httponly" in cookie.lower()

    @pytest.mark.asyncio
    async def test_mfa_login_response_omits_refresh_token(self):
        app = make_app()
        with patch(
            "services.user_service.UserService.login_with_mfa",
            new=AsyncMock(
                return_value=Result.ok(
                    {
                        "user": _user_dict(),
                        "access_token": "acc-token",
                        "refresh_token": "ref-token",
                    }
                )
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/auth/mfa/login",
                    json={"mfa_token": "mfa-token-123", "code": "123456"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body["data"]
        assert "refresh_token" not in body["data"]
        assert "refresh_token" not in resp.text


class TestRefreshCookieOnly:
    """/auth/refresh reads the token only from the cookie and omits it from JSON."""

    @pytest.mark.asyncio
    async def test_refresh_with_cookie_rotates_token_and_omits_refresh_token(self):
        app = make_app()
        with patch(
            "services.user_service.UserService.refresh_token",
            new=AsyncMock(
                return_value=Result.ok(
                    {
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "user": _user_dict(),
                    }
                )
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies={settings.auth_cookie_name: "old-refresh"},
            ) as client:
                resp = await client.post(
                    "/auth/refresh",
                    json={},  # no token in the body — cookie only
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["access_token"] == "new-access"
        assert body["data"]["user"]["username"] == "ali"
        assert "refresh_token" not in body["data"]
        assert "refresh_token" not in resp.text
        # The rotated refresh token lands in the cookie, not the body.
        cookie = _set_cookie_header(resp)
        assert settings.auth_cookie_name in cookie
        assert "httponly" in cookie.lower()

    @pytest.mark.asyncio
    async def test_refresh_ignores_body_token(self):
        """A token smuggled in the JSON body is ignored — only the cookie counts."""
        app = make_app()
        with patch(
            "services.user_service.UserService.refresh_token",
            new=AsyncMock(side_effect=AssertionError("body token must be ignored")),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Send a forged refresh_token in the body but NO cookie.
                resp = await client.post(
                    "/auth/refresh",
                    json={"refresh_token": "forged-body-token"},
                )

        # Endpoint reads the (missing) cookie → rejects without calling the service.
        assert resp.status_code == 401
        body = resp.json()
        # JSONResponse with ApiResponse body keeps success=False shape for frontend !res.ok handling
        assert body["success"] is False
        assert "No refresh token provided" in body["error"]["message"]


class TestLogout:
    """Logout must expire the cookie even when the access token is unavailable."""

    @pytest.mark.asyncio
    async def test_logout_without_access_token_still_clears_cookie(self):
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/auth/logout")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        cookie = _set_cookie_header(resp).lower()
        assert settings.auth_cookie_name.lower() in cookie
        assert "max-age=0" in cookie

    @pytest.mark.asyncio
    async def test_logout_clears_the_present_server_refresh_token(self):
        from core.security.tokens import create_refresh_token

        class FakeResult:
            def __init__(self, value):
                self.value = value

            def scalar_one_or_none(self):
                return self.value

        class FakeSession:
            def __init__(self, user):
                self.user = user

            async def execute(self, _query):
                return FakeResult(self.user)

            async def flush(self):
                return None

        user = SimpleNamespace(id="usr_1", refresh_token=None)
        refresh_token = create_refresh_token({"sub": user.id})
        user.refresh_token = refresh_token
        app = make_app()
        session = FakeSession(user)

        async def fake_session():
            yield session

        app.dependency_overrides[get_session] = fake_session
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={settings.auth_cookie_name: refresh_token},
        ) as client:
            resp = await client.post("/auth/logout")

        assert resp.status_code == 200
        assert user.refresh_token is None
