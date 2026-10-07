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


async def _mock_admin_user(authorization: str = "") -> dict[str, Any]:
    """Stand-in for ``get_current_user`` used by the authenticated fixtures."""
    _ = authorization
    return dict(_MOCK_ADMIN)


async def _mock_regular_user(authorization: str = "") -> dict[str, Any]:
    """Stand-in for ``get_current_user`` returning a plain user."""
    _ = authorization
    return dict(_MOCK_USER)


def _authenticate(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    current_user: Any,
    replacement: Any,
) -> dict[Any, Any]:
    """Make every auth path in the app resolve to ``current_user``'s role set.

    Two mechanisms are needed.  ``Depends(get_current_user)`` (used by
    ``require_roles``, ``require_role`` and friends) is satisfied by the
    dependency-override map — note the override is registered as the *callable
    itself*, so FastAPI awaits it and injects its return value; wrapping it in a
    ``lambda`` would inject the function object and every consumer would then
    fail on ``current_user.get(...)``.

    Mount-time helpers such as ``require_user_for_writes`` call
    ``get_current_user`` *directly*, so the override map never reaches them and
    an authenticated write would still answer 401.  Patching the module global
    covers that second path.

    Returns the overrides that were in place beforehand so the caller can
    restore exactly that state instead of blasting every override away.
    """
    from apps.api import dependencies

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[current_user] = replacement
    monkeypatch.setattr(dependencies, "get_current_user", replacement, raising=False)
    return previous


def _restore_overrides(app: FastAPI, previous: dict[Any, Any]) -> None:
    """Put ``app.dependency_overrides`` back the way ``_authenticate`` found it."""
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest_asyncio.fixture
async def admin_client(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    """Client with admin-level auth (``get_current_user`` returns admin)."""
    from apps.api.dependencies import get_current_user

    previous = _authenticate(app, monkeypatch, get_current_user, _mock_admin_user)
    try:
        yield client
    finally:
        _restore_overrides(app, previous)


@pytest_asyncio.fixture
async def user_client(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    """Client with regular-user auth (``get_current_user`` returns ``{roles: ["user"]}``)."""
    from apps.api.dependencies import get_current_user

    previous = _authenticate(app, monkeypatch, get_current_user, _mock_regular_user)
    try:
        yield client
    finally:
        _restore_overrides(app, previous)
