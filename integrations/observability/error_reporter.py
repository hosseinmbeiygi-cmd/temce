from __future__ import annotations

import contextlib
import logging
import sys
import traceback
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ErrorReporter:
    def __init__(self, dsn: str | None = None, environment: str = ""):
        self._dsn = dsn or ""
        self._environment = environment or "development"
        self._extra_handlers: list[callable] = []

    def report(self, exc: Exception, context: dict[str, Any] | None = None) -> None:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        error_data = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(tb),
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": self._environment,
            "context": context or {},
        }
        logger.error("Error reported: %s - %s", type(exc).__name__, exc)
        for handler in self._extra_handlers:
            with contextlib.suppress(Exception):
                handler(error_data)
        if self._dsn:
            self._send_to_service(error_data)

    def report_message(self, message: str, level: str = "error", context: dict[str, Any] | None = None) -> None:
        error_data = {
            "type": "message",
            "message": message,
            "level": level,
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": self._environment,
            "context": context or {},
        }
        logger.log(getattr(logging, level.upper(), logging.ERROR), "Reported: %s", message)
        for handler in self._extra_handlers:
            with contextlib.suppress(Exception):
                handler(error_data)

    def add_handler(self, handler: callable) -> None:
        self._extra_handlers.append(handler)

    def _send_to_service(self, data: dict[str, Any]) -> None:
        try:
            import httpx

            with httpx.Client(timeout=10.0) as client:
                client.post(self._dsn, json=data)
        except Exception as e:
            logger.warning("Failed to send error report to DSN: %s", e)

    def report_exc_info(self, context: dict[str, Any] | None = None) -> None:
        exc_type, exc_value, tb = sys.exc_info()
        if exc_type and exc_value:
            self.report(exc_value, context)

    @property
    def handlers(self) -> list[callable]:
        return list(self._extra_handlers)
