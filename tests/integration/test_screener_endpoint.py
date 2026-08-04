"""Integration tests for the screener API endpoint.

Verifies that the endpoint delegates market-data fetching to the shared
``services.market_watch_helper.fetch_market_watch`` helper instead of
reimplementing snapshot conversion inline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.api.app import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _fake_get_session(session):
    """Return an async generator that yields the provided session object."""

    async def _gen():
        yield session

    return _gen


@pytest.mark.asyncio
async def test_screener_endpoint_uses_shared_market_watch_helper(client: AsyncClient) -> None:
    """GET /api/v1/screener should use ``fetch_market_watch`` from the shared helper."""
    instruments = [
        {"symbol": "TEST", "name": "Test Co", "market": "BOURS", "industry": "TEST"},
    ]
    market_watch = [
        {
            "symbol": "TEST",
            "name": "Test Co",
            "last_price": 1234,
            "close": 1230,
            "change": 0.5,
            "volume": 10_000,
            "value": 12_340_000,
            "market": "BOURS",
            "sector": "TEST",
        },
    ]

    mock_fetch = AsyncMock(return_value=(instruments, market_watch))
    mock_session = AsyncMock()

    mock_screener_instance = MagicMock()
    mock_screener_instance.screen = AsyncMock(return_value=([], {"total": 0, "page": 1, "page_size": 10, "total_pages": 0}))
    mock_screener_cls = MagicMock(return_value=mock_screener_instance)

    with (
        patch("services.market_watch_helper.fetch_market_watch", mock_fetch),
        patch("core.database.get_session", _fake_get_session(mock_session)),
        patch("services.screener_service.ScreenerService", mock_screener_cls),
        patch("apps.api.endpoints.screener._cache_get", return_value=None),
        patch("apps.api.endpoints.screener._cache_set") as _,
    ):
        resp = await client.get("/api/v1/screener", params={"limit": 10})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0

    mock_fetch.assert_awaited_once()
    mock_screener_cls.assert_called_once_with(session=mock_session, history_limit=60)
    mock_screener_instance.screen.assert_awaited_once()
