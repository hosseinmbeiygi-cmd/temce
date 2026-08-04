"""Centralized log aggregation via Redis Streams.

Services already emit structured JSON logs to stdout (see
``core.logging.JsonFormatter``). This module optionally *also* forwards each
record to a Redis Stream (``log-aggregator:stream``) so a central collector
(Loki/ELK/Vector) can tail one durable source across all replicas and
services.

Design notes:
- Publish is best-effort and non-blocking: failures are swallowed and only
  counted in a local counter, so logging can never take the app down.
- Consumers mark a ``source`` field (service name + optional replica) so the
  collector can distinguish producers.
- Redis is used as a lightweight broker only; no consumer logic lives here.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_STREAM_KEY = "log-aggregator:stream"
_MAX_STREAM_LEN = 50_000  # approximate cap — trims oldest entries


class RedisLogHandler(logging.Handler):
    """A logging.Handler that publishes JSON records to a Redis Stream.

    Attach it to the root logger in ``setup_logging`` when
    ``LOG_AGGREGATION_ENABLED=true``. Every record becomes one stream entry
    with a ``{source, level, timestamp, message, ...}`` payload.
    """

    def __init__(self, source: str | None = None) -> None:
        super().__init__()
        self.source = source or settings.app_name
        self._publish_failures = 0
        self._published = 0
        self._client: Any = None

    # ── stats (used by /metrics + admin) ──
    @property
    def published(self) -> int:
        return self._published

    @property
    def failures(self) -> int:
        return self._publish_failures

    def _ensure_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            from core.cache import get_cache

            cache = get_cache()
            if not cache.is_connected or cache.client is None:
                return None
            self._client = cache.client
        except Exception:  # noqa: BLE001 — must never crash logging
            # Accessing ``cache.client`` itself may raise (Redis down) — count it
            # so operators can observe the failure via ``failures``.
            self._publish_failures += 1
            self._client = None
        return self._client

    def emit(self, record: logging.LogRecord) -> None:
        client = self._ensure_client()
        if client is None:
            return
        try:
            payload: dict[str, Any] = {
                "source": self.source,
                "level": record.levelname,
                "timestamp": datetime.now(UTC).isoformat(),
                "name": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            if record.exc_info and record.exc_info[0]:
                payload["exception"] = self.formatException(record.exc_info)
            entry = json.dumps(payload, ensure_ascii=False, default=str)
            client.xadd(_STREAM_KEY, {"data": entry}, maxlen=_MAX_STREAM_LEN)
            self._published += 1
        except Exception:  # noqa: BLE001 — logging must never crash the app
            self._publish_failures += 1
            self._client = None  # reconnect on next emit


_handler: RedisLogHandler | None = None


def get_redis_log_handler() -> RedisLogHandler | None:
    """Return the process-wide RedisLogHandler singleton (or None)."""
    global _handler
    if _handler is None:
        _handler = RedisLogHandler()
    return _handler


def install_aggregation_handler(source: str | None = None) -> RedisLogHandler | None:
    """Attach the aggregation handler to the root logger.

    Returns the handler (so callers can inspect stats) or None when
    aggregation is disabled via ``LOG_AGGREGATION_ENABLED=false``.
    """
    if not getattr(settings, "log_aggregation_enabled", False):
        return None
    handler = get_redis_log_handler()
    if source:
        handler.source = source
    root = logging.getLogger()
    if handler not in root.handlers:
        root.addHandler(handler)
    logger.info("Log aggregation handler installed (stream=%s)", _STREAM_KEY)
    return handler
