from __future__ import annotations

import logging
from typing import Any


class ContextLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._context: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._context[key] = value

    def remove(self, key: str) -> None:
        self._context.pop(key, None)

    def clear(self) -> None:
        self._context.clear()

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        extra = kwargs.pop("extra", {})
        extra["context"] = dict(self._context)
        self._logger.log(level, msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def get_context_logger(name: str | None = None) -> ContextLogger:
    return ContextLogger(get_logger(name))


from core.logging import get_logger
