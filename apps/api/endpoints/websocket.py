"""
WebSocket endpoint for real-time market data streaming.

Connection: ws://localhost:8000/api/v1/ws/market
Protocol:
  Client -> Server:
    {"action": "subscribe", "symbols": ["فولاد", "فملی"]}
    {"action": "unsubscribe", "symbols": ["فولاد"]}
    {"action": "ping"}
  Server -> Client:
    {"action": "price", "symbol": "فولاد", "price": 45200, ...}
    {"action": "subscribed", "symbols": ["فولاد", "فملی"]}
    {"action": "pong", "ts": 1720000000.0}
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.logging import get_logger
from services.realtime_service import get_realtime_service

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/market")
async def market_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    connection_id = str(uuid.uuid4())[:8]
    service = get_realtime_service()

    await service.register_client(
        connection_id=connection_id,
        send_fn=websocket.send_text,
        symbols=[],
    )
    logger.info("WebSocket client connected: %s", connection_id)

    try:
        while True:
            raw = await websocket.receive_text()
            await service.handle_message(connection_id, raw)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", connection_id)
    except Exception:
        logger.exception("WebSocket error for %s", connection_id)
    finally:
        await service.unregister_client(connection_id)
