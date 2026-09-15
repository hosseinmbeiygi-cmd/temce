"""precompute/redis_client.py — local Redis client for the precompute scope.

Strict isolation: this scope never imports ``core.redis_client`` or any other
module's client. The connection details come only from ``precompute.config``
(env-driven), so the api and precompute sides agree on the same Redis without
sharing code.

Loop affinity
-------------
Celery prefork/solo workers run each task under its own ``asyncio.run()``
loop (see ``celery_tasks._run_sync``).  An aioredis client is bound to the
loop that created its connections — reusing a global client on a later loop
raises ``RuntimeError: ... attached to a different loop`` (swallowed by the
best-effort excepts here, silently LOSING events).  The client is therefore
cached **per running loop**, and a loop is never reused after it closes.
"""
from __future__ import annotations

import json
import logging
import threading
import time

import redis.asyncio as aioredis

from .config import PrecomputeConfig, load_config

logger = logging.getLogger("precompute.redis_client")

_config = load_config()

# Per-loop client registry: id(asyncio loop) -> client.  Guarded by a lock
# because Celery threads (beat, control) may touch this module.  Insertion-
# ordered; capped so a long-lived worker that loops per task cannot leak.
_MAX_CACHED_CLIENTS = 8
_clients: dict[int, aioredis.Redis] = {}
_clients_lock = threading.Lock()

# Circuit breaker: after N consecutive failures, skip Redis for a cool-down
# window instead of stalling every emit on connect retries (a dead broker
# must not turn each publish into a multi-second hang).
_FAILURE_THRESHOLD = 3
_COOLDOWN_SECONDS = 10.0
_consecutive_failures = 0
_open_until = 0.0


def _loop_id() -> int:
    import asyncio

    loop = asyncio.get_running_loop()  # only called inside a running loop
    return id(loop)


def get_redis(config: PrecomputeConfig | None = None) -> aioredis.Redis:
    """Return the current loop's async Redis client (lazy, loop-affine)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as exc:  # pragma: no cover — defensive
        raise RuntimeError("precompute.redis_client.get_redis() requires a running event loop") from exc

    lid = id(loop)
    with _clients_lock:
        existing = _clients.get(lid)
        if existing is not None:
            return existing

    cfg = config or _config
    client = aioredis.from_url(
        cfg.redis_url,
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
        health_check_interval=15,
    )
    with _clients_lock:
        # Cap the registry: drop the oldest entries once full.  Their loops
        # are long gone (each asyncio.run() loop is used exactly once by a
        # task), so the dropped clients' transports are garbage-collectable.
        while len(_clients) >= _MAX_CACHED_CLIENTS:
            _clients.pop(next(iter(_clients)), None)
        _clients[lid] = client
    return client


async def _breaker_open() -> bool:
    global _open_until
    if time.monotonic() < _open_until:
        return True
    return False


def _record_failure() -> None:
    global _consecutive_failures, _open_until
    _consecutive_failures += 1
    if _consecutive_failures >= _FAILURE_THRESHOLD:
        _open_until = time.monotonic() + _COOLDOWN_SECONDS
        logger.warning(
            "precompute Redis circuit OPEN for %.0fs after %d consecutive failures",
            _COOLDOWN_SECONDS,
            _consecutive_failures,
        )


def _record_success() -> None:
    global _consecutive_failures, _open_until
    _consecutive_failures = 0
    _open_until = 0.0


async def publish_event(event_type: str, payload: dict, config: PrecomputeConfig | None = None) -> None:
    """Publish a contract event onto the precompute events channel (fire-and-forget)."""
    cfg = config or _config
    if await _breaker_open():
        logger.debug("precompute Redis breaker open — dropping %s event", event_type)
        return
    try:
        client = get_redis(cfg)
        await client.publish(
            cfg.events_channel,
            json.dumps({"type": event_type, "payload": payload, "ts": _now_ts()}, ensure_ascii=False, default=str),
        )
        _record_success()
    except Exception:
        # Event delivery must never break computation.
        _record_failure()
        logger.debug("precompute publish_event failed for %s", event_type, exc_info=True)


async def save_result(symbol: str, result: dict, config: PrecomputeConfig | None = None) -> None:
    """Persist one SymbolComputationResult to the hot layer (read by api)."""
    cfg = config or _config
    if await _breaker_open():
        logger.debug("precompute Redis breaker open — skipping result save for %s", symbol)
        return
    try:
        client = get_redis(cfg)
        await client.set(
            cfg.result_key_template.format(symbol=symbol),
            json.dumps(result, ensure_ascii=False, default=str),
            ex=cfg.result_ttl_seconds,
        )
        _record_success()
    except Exception:
        # Hot layer is best-effort; the api has a graceful fallback.
        _record_failure()
        logger.debug("precompute save_result failed for %s", symbol, exc_info=True)


def _now_ts() -> float:
    return time.time()
