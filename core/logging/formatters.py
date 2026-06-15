from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from core.context import get_correlation_id, get_request_id, get_user_id


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            data["exception"] = self.formatException(record.exc_info)
        correlation_id = get_correlation_id()
        if correlation_id:
            data["correlation_id"] = correlation_id
        request_id = get_request_id()
        if request_id:
            data["request_id"] = request_id
        user_id = get_user_id()
        if user_id:
            data["user_id"] = user_id
        if hasattr(record, "extra"):
            data["extra"] = record.extra
        return json.dumps(data, ensure_ascii=False)


class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        formatted = super().format(record)
        return f"{color}{formatted}{self.RESET}"
