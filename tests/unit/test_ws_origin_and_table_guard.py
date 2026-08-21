"""Unit tests for two security hardening changes:

1. WebSocket Origin guard (CSWSH prevention) in apps/api/endpoints/websocket.py
2. Table-name identifier guard in apps/api/endpoints/tables.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ════════════════════════════════════════════════════════════════
# 1. WebSocket Origin guard
# ════════════════════════════════════════════════════════════════


def _make_ws(headers: dict[str, str]) -> MagicMock:
    ws = MagicMock()
    ws.headers = headers
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
@patch("apps.api.endpoints.websocket.settings")
async def test_rejects_disallowed_origin(mock_settings) -> None:
    from apps.api.endpoints.websocket import market_websocket

    mock_settings.cors_origins = ["http://localhost:3000"]
    ws = _make_ws({"origin": "https://evil.example.com"})
    with patch("apps.api.endpoints.websocket.get_realtime_service") as mock_svc:
        await market_websocket(ws)
    ws.close.assert_awaited_once_with(code=1008)
    ws.accept.assert_not_awaited()


@pytest.mark.asyncio
@patch("apps.api.endpoints.websocket.settings")
async def test_accepts_allowed_origin(mock_settings) -> None:
    from apps.api.endpoints.websocket import market_websocket

    mock_settings.cors_origins = ["http://localhost:3000"]
    ws = _make_ws({"origin": "http://localhost:3000"})
    mock_service = MagicMock()
    mock_service.register_client = AsyncMock()
    mock_service.handle_message = AsyncMock()
    mock_service.unregister_client = AsyncMock()

    async def _receive():
        raise Exception("end of stream")  # triggers the generic except/finally path

    ws.receive_text = _receive
    with patch("apps.api.endpoints.websocket.get_realtime_service", return_value=mock_service):
        await market_websocket(ws)
    ws.accept.assert_awaited_once()
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
@patch("apps.api.endpoints.websocket.settings")
async def test_accepts_non_browser_client_without_origin(mock_settings) -> None:
    from apps.api.endpoints.websocket import market_websocket

    mock_settings.cors_origins = ["http://localhost:3000"]
    ws = _make_ws({})  # no Origin header → non-browser client
    mock_service = MagicMock()
    mock_service.register_client = AsyncMock()
    mock_service.handle_message = AsyncMock()
    mock_service.unregister_client = AsyncMock()

    async def _receive():
        raise Exception("end of stream")

    ws.receive_text = _receive
    with patch("apps.api.endpoints.websocket.get_realtime_service", return_value=mock_service):
        await market_websocket(ws)
    ws.accept.assert_awaited_once()
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
@patch("apps.api.endpoints.websocket.settings")
async def test_wildcard_origin_disables_check(mock_settings) -> None:
    from apps.api.endpoints.websocket import market_websocket

    mock_settings.cors_origins = ["*"]
    ws = _make_ws({"origin": "https://anything.example.com"})
    mock_service = MagicMock()
    mock_service.register_client = AsyncMock()
    mock_service.handle_message = AsyncMock()
    mock_service.unregister_client = AsyncMock()

    async def _receive():
        raise Exception("end of stream")

    ws.receive_text = _receive
    with patch("apps.api.endpoints.websocket.get_realtime_service", return_value=mock_service):
        await market_websocket(ws)
    ws.accept.assert_awaited_once()
    ws.close.assert_not_awaited()


# ════════════════════════════════════════════════════════════════
# 2. Table-name identifier guard
# ════════════════════════════════════════════════════════════════


class TestSafeIdentifier:
    @pytest.mark.parametrize(
        "name",
        ["instruments", "backtest_runs", "a", "a_1", "signal_accuracy"],
    )
    def test_accepts_valid_snake_case(self, name: str) -> None:
        from apps.api.endpoints.tables import _SAFE_IDENTIFIER

        assert _SAFE_IDENTIFIER.match(name)

    @pytest.mark.parametrize(
        "name",
        ["Instruments", 'weird"name', "a b", "1abc", "users;--", "-leading"],
    )
    def test_rejects_unsafe_names(self, name: str) -> None:
        from apps.api.endpoints.tables import _SAFE_IDENTIFIER

        assert not _SAFE_IDENTIFIER.match(name)
