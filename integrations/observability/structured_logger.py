from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

_default_logger = get_logger(__name__)


class StructuredLogger:
    def __init__(self, name: str = "structured", level: int = logging.INFO):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())
            self._logger.addHandler(handler)

    def info(self, message: str, **context: Any) -> None:
        self._logger.info(message, extra={"context": context})

    def warning(self, message: str, **context: Any) -> None:
        self._logger.warning(message, extra={"context": context})

    def error(self, message: str, **context: Any) -> None:
        self._logger.error(message, extra={"context": context})

    def debug(self, message: str, **context: Any) -> None:
        self._logger.debug(message, extra={"context": context})

    def critical(self, message: str, **context: Any) -> None:
        self._logger.critical(message, extra={"context": context})

    def exception(self, message: str, **context: Any) -> None:
        self._logger.exception(message, extra={"context": context})

    def bind(self, **kwargs: Any) -> StructuredLogger:
        new_logger = StructuredLogger(self._logger.name, self._logger.level)
        new_logger._logger = self._logger
        return new_logger


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        ctx = getattr(record, "context", {})
        if ctx:
            data.update(ctx)
        if record.exc_info and record.exc_info[0]:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)
