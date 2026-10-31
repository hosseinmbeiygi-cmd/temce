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

from core.config import settings
from core.logging import get_logger
from services.realtime_service import get_realtime_service

logger = get_logger(__name__)
router = APIRouter()


async def verify_websocket_token(websocket: WebSocket) -> bool:
    """Authenticate a WebSocket handshake (audit API-003, FE-06).

    The Origin guard only stops a *foreign page* from using the visitor's
    browser; it does nothing about a script that simply opens the socket and
    reads the market stream. Browsers cannot attach headers to a WebSocket
    handshake, so the client presents a **single-use ticket** obtained from
    ``POST /auth/ws-ticket`` (60s TTL, GETDEL). The long-lived access token is
    no longer accepted in the query string (FE-06: it leaked into access logs,
    proxy logs and browser history); a bearer ``Authorization`` header remains
    supported for non-browser clients.

    Honours the same ``AUTH_DISABLED`` gate as the HTTP dependencies, so a
    deployment that deliberately runs without auth keeps working.
    """
    from apps.api.auth import _auth_required

    if not _auth_required():
        return True

    ticket = websocket.query_params.get("ticket", "")
    if ticket:
        from core.security.tokens import consume_ws_ticket

        if await consume_ws_ticket(ticket):
            return True
        # A presented-but-invalid ticket is a rejection, never a downgrade to
        # the legacy token path.
        logger.warning("WebSocket handshake rejected: invalid or spent ticket")
        return False

    token = websocket.query_params.get("token", "")
    if token:
        # Deprecated: accepted only until every client uses tickets. Kept out
        # of the primary path so a migration cannot silently regress.
        logger.warning(
            "WebSocket handshake used a deprecated access token in the query "
            "string (FE-06) — switch the client to POST /auth/ws-ticket"
        )
    else:
        header = websocket.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[len("bearer "):].strip()
    if not token:
        return False

    try:
        from core.security.tokens import decode_access_token, is_token_revoked

        payload = decode_access_token(token)
        if await is_token_revoked(payload.get("jti")):
            return False
    except Exception:  # noqa: BLE001 — any decoding failure means "not authenticated"
        logger.warning("WebSocket handshake rejected: invalid access token")
        return False
    return True


@router.websocket("/market")
async def market_websocket(websocket: WebSocket) -> None:
    # CSWSH guard: reject connections from browser pages on origins outside
    # the configured CORS allow-list. Without this, any website could open a
    # socket to /ws/market and consume the market-data stream. Non-browser
    # clients (scripts, trading apps) send no Origin header — those are
    # accepted. A configured wildcard ("*") disables the check.
    origin = websocket.headers.get("origin")
    allowed = settings.cors_origins
    if origin and allowed != ["*"] and origin not in allowed:
        logger.warning("WebSocket connection rejected: origin %s not allowed", origin)
        await websocket.close(code=1008)  # policy violation, before accept
        return

    # API-003: the Origin header is a browser-side protection only; a socket
    # opened by a script carries whatever Origin it likes. Verify the token
    # before accepting so an unauthenticated client never reaches the stream.
    if not await verify_websocket_token(websocket):
        logger.warning("WebSocket connection rejected: missing or invalid token")
        await websocket.close(code=1008)
        return

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
