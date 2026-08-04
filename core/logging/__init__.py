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
        # NOTE: we must NOT delegate to super().emit() here — the stdlib
        # StreamHandler.emit catches every exception internally and routes it
        # to handleError(), which prints a noisy "--- Logging error ---"
        # traceback instead of letting our UnicodeEncodeError handler run.
        # Writing the formatted message directly lets us degrade gracefully
        # on consoles that cannot encode non-ASCII text (e.g. Windows cp1252
        # with Persian/→ characters in exception text).
        try:
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            if record.exc_info and record.exc_info[0]:
                # Exception text can't be encoded — drop silently rather than
                # spamming "--- Logging error ---" for every failed record.
                return
            try:
                safe_msg = self.format(record).replace(
                    record.getMessage(), "[TEXT ENCODING ERROR]", 1
                )
                self.stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)


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

    # Centralized aggregation via Redis Streams (best-effort, opt-in)
    if getattr(settings, "log_aggregation_enabled", False):
        try:
            from integrations.observability.log_aggregator import install_aggregation_handler

            install_aggregation_handler(source=settings.log_aggregation_source)
        except Exception:
            logging.getLogger(__name__).debug("Log aggregation handler not installed", exc_info=True)


_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str | None = None) -> logging.Logger:
    if name is None:
        import inspect

        frame = inspect.currentframe()
        name = frame.f_back.f_globals["__name__"] if frame and frame.f_back else "root"
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]
