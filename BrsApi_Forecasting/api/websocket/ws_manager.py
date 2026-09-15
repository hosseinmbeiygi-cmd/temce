# api/websocket/ws_manager.py — Connection registry + event broadcast for precompute stream.
# Reads contracts/events.md for event shapes; does NOT import precompute worker modules.
from __future__ import annotations

import asyncio
import logging
from typing import Any

from contracts.events import PRECOMPUTATION_GROUP_COMPLETED, PRECOMPUTATION_COMPLETED, PRECOMPUTATION_PROGRESS, SYMBOL_RESULT_UPDATED

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory connection registry
# ---------------------------------------------------------------------------

# {websocket: {"groups": set[SymbolGroup], "client_id": str}}
_active_connections: dict[Any, dict[str, Any]] = {}
_registry_lock = asyncio.Lock()


async def register(websocket: Any, groups: set[str] | None = None, client_id: str = "") -> None:
    """Accept a connection into the broadcast pool."""
    async with _registry_lock:
        _active_connections[websocket] = {
            "groups": groups or set(),
            "client_id": client_id or f"client-{id(websocket)}",
        }
    logger.info("WS connected: %s groups=%s", _active_connections[websocket]["client_id"], sorted(groups or []))


async def unregister(websocket: Any) -> None:
    async with _registry_lock:
        _active_connections.pop(websocket, None)


# ---------------------------------------------------------------------------
# Broadcast helpers — one per event from contracts/events.md
# ---------------------------------------------------------------------------

async def broadcast_progress(group: str, completed: int, total: int, percent: float, current_symbol: str) -> None:
    payload = PRECOMPUTATION_PROGRESS(group=group, completed=completed, total=total, percent=percent, current_symbol=current_symbol).model_dump()
    await _broadcast("PRECOMPUTATION_PROGRESS", payload)


async def broadcast_group_completed(group: str, total_processed: int, failed: int, timestamp: str) -> None:
    payload = PRECOMPUTATION_GROUP_COMPLETED(group=group, total_processed=total_processed, failed=failed, timestamp=timestamp).model_dump()
    await _broadcast("PRECOMPUTATION_GROUP_COMPLETED", payload)


async def broadcast_completed(total: int, success: int, failed: int, avg_dri: float, duration_seconds: float, timestamp: str) -> None:
    payload = PRECOMPUTATION_COMPLETED(total=total, success=success, failed=failed, avg_dri=avg_dri, duration_seconds=duration_seconds, timestamp=timestamp).model_dump()
    await _broadcast("PRECOMPUTATION_COMPLETED", payload)


async def broadcast_symbol_updated(symbol: str, group: str, armor_score: float, data_dri: float, is_unreliable: bool) -> None:
    payload = SYMBOL_RESULT_UPDATED(symbol=symbol, group=group, armor_score=armor_score, data_dri=data_dri, is_unreliable=is_unreliable).model_dump()
    await _broadcast("SYMBOL_RESULT_UPDATED", payload)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

async def _broadcast(event: str, payload: dict[str, Any]) -> None:
    """Send `payload` to every connected WebSocket inside `event` envelope."""
    if not _active_connections:
        return

    envelope = {"event": event, "data": payload}
    disconnected: list[Any] = []

    async with _registry_lock:
        connections = list(_active_connections.items())

    for websocket, meta in connections:
        try:
            await websocket.send_json(envelope)
        except Exception:
            disconnected.append(websocket)
            logger.warning("WS send failed for %s — removing", meta.get("client_id"))

    if disconnected:
        await _purge(disconnected)


async def _purge(websockets: list[Any]) -> None:
    async with _registry_lock:
        for ws in websockets:
            _active_connections.pop(ws, None)


async def get_connection_count() -> int:
    async with _registry_lock:
        return len(_active_connections)
