"""
Armor Precompute WebSocket — apps/api/endpoints/precompute_ws.py
=================================================================
WebSocket at /api/v1/ws/precompute
Mirrors the logic in api/ws_manager.py but as a FastAPI router endpoint
so it can be mounted via apps.api.router at prefix /ws.

Frontend hooks: frontend/src/hooks/usePrecomputeStatus.ts connects to
  ws://host:8000/api/v1/ws/precompute
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.ws_manager import get_armor_ws_manager
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Armor WS"])


@router.websocket("/precompute")
async def ws_precompute(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    allowed = settings.cors_origins
    if origin and allowed != ["*"] and origin not in allowed:
        logger.warning("Armor WS rejected: origin %s not allowed", origin)
        await websocket.close(code=1008)
        return

    manager = get_armor_ws_manager()
    await manager.connect(websocket)
    try:
        while True:
            # Keep-alive loop — client may send {"action":"ping"} or anything
            # We simply consume and optionally echo pong to keep the connection alive
            raw = await websocket.receive_text()
            if raw.strip() == '{"action":"ping"}' or '"ping"' in raw:
                try:
                    await websocket.send_text('{"type":"pong","ts":' + str(__import__("time").time()) + '}')
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Armor WS error")
    finally:
        await manager.disconnect(websocket)
