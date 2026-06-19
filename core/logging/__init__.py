from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import settings


class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except UnicodeEncodeError:
            if record.exc_info and record.exc_info[0]:
                return
            safe_msg = self.format(record).replace(
                record.getMessage(), "[TEXT ENCODING ERROR]", 1
            )
            self.stream.write(safe_msg + self.terminator)
            self.flush()


class JsonFormatter(logging.Formatter):
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
        if hasattr(record, "extra"):
            data["extra"] = record.extra
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    fmt = settings.log_format
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []

    console = SafeStreamHandler(sys.stdout)
    if fmt == "json":
        console.setFormatter(JsonFormatter())
    else:
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    handlers.append(console)

    if settings.log_file:
        path = Path(settings.log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        handlers.append(fh)

    logging.basicConfig(level=level, handlers=handlers, force=True)


_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str | None = None) -> logging.Logger:
    if name is None:
        import inspect

        frame = inspect.currentframe()
        name = frame.f_back.f_globals["__name__"] if frame and frame.f_back else "root"
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]
