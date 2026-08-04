"""Shared test fixtures for unit tests.

The ``app`` fixture is session-scoped — FastAPI app creation
(including endpoint imports) is done **once per test session**
rather than once per test file.  This avoids paying the ~20s
endpoint-import tax on every test module that needs a real app.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Return the fully configured FastAPI application.

    Import is lazy (inside the fixture body) so no endpoint modules
    are loaded until the very first test that requests ``app``.
    With ``scope=session`` that cost is paid exactly once.
    """
    from apps.api.app import create_app
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Return an httpx AsyncClient wired to the test app via ASGI.

    This fixture is function-scoped (the default) so every test
    function gets a fresh client — no request leakage between tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Auth helpers ────────────────────────────────────────────────
# Some endpoints require authentication (_require_user, _require_admin, etc.).
# We override ``get_current_user`` with a mock so those endpoints return
# 200 instead of 401 during tests.  The override is cleaned up after
# each test via ``dependency_overrides.clear()``.

_MOCK_ADMIN: dict[str, Any] = {
    "username": "test_admin",
    "roles": ["admin"],
    "user_id": 1,
}

_MOCK_USER: dict[str, Any] = {
    "username": "test_user",
    "roles": ["user"],
    "user_id": 2,
}


@pytest_asyncio.fixture
async def admin_client(app: FastAPI, client: AsyncClient) -> AsyncClient:
    """Client with admin-level auth (``get_current_user`` returns admin)."""
    from apps.api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: _MOCK_ADMIN
    yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_client(app: FastAPI, client: AsyncClient) -> AsyncClient:
    """Client with regular-user auth (``get_current_user`` returns ``{roles: ["user"]}``)."""
    from apps.api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    yield client
    app.dependency_overrides.clear()
