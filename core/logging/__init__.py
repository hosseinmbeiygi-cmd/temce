"""Structured logging powered by structlog.

Provides the same ``get_logger(name)`` API used across 250+ files, but now
returns a structlog ``BoundLogger`` that:

* Outputs JSON in production (``log_format=json``).
* Outputs human-readable text in development (``log_format=text``).
* Carries contextual fields (``request_id``, ``job_name``, ``source``, …)
  that are automatically included in every log line.
* Integrates with stdlib ``logging`` so third-party libraries still work.

Usage::

    from core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("sync_started", symbol="خودرو", count=42)

    # Or with %s style (stdlib integration)
    logger.info("synced %d symbols", count)

    # Bind context for the current scope
    from core.logging import bind_context, unbind_context
    bind_context(request_id="abc-123", job_name="brsapi_all_symbols")
    logger.info("processing")  # includes request_id + job_name
    unbind_context("request_id")
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from core.config import settings
from core.context import get_correlation_id, get_request_id, get_user_id

# ── stdlib compatibility layer ─────────────────────────────────────────────
# SafeStreamHandler: degrades gracefully on consoles that cannot encode
# non-ASCII text (e.g. Windows cp1252 with Persian characters).
# Kept as-is from the previous implementation.


class SafeStreamHandler(logging.StreamHandler[Any]):
    """Stream handler that degrades gracefully on encoding errors."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            if record.exc_info and record.exc_info[0]:
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


# ── structlog configuration ────────────────────────────────────────────────
# Structured field contract (one JSON object per line):
#   timestamp, level, logger, event, exception (when raised),
#   request_id / correlation_id / user_id (from core.context or bind_context),
#   plus every structured keyword argument and stdlib ``extra`` field.

_STDLIB_RECORD_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
    "asctime",
}


def _add_context_ids(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Attach request/correlation/user IDs from ``core.context`` to every record."""
    for key, getter in (
        ("request_id", get_request_id),
        ("correlation_id", get_correlation_id),
        ("user_id", get_user_id),
    ):
        if event_dict.get(key):
            continue
        value = getter()
        if value:
            event_dict[key] = value
    return event_dict


def _merge_stdlib_extras(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Promote stdlib ``extra={...}`` fields to top-level JSON keys.

    Runs before ``wrap_for_formatter`` for structlog records (``_record`` is not
    set yet, so this is a no-op) and during ``foreign_pre_chain`` for
    third-party records.
    """
    record = event_dict.get("_record")
    if record is None:
        return event_dict
    for key, value in record.__dict__.items():
        if key in _STDLIB_RECORD_RESERVED or key.startswith("_"):
            continue
        event_dict.setdefault(key, value)
    return event_dict


_SHARED_PROCESSORS: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    _add_context_ids,
    _merge_stdlib_extras,
    # Interpolate stdlib-style ``logger.info("synced %d", n)`` args so the
    # shipped ``event`` is the final message, not a format string.
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]


def _json_serializer(obj: Any, **kwargs: Any) -> str:
    """JSON serializer used by the renderer (fallback supplied via ``default=str``)."""
    return json.dumps(obj, **kwargs)


def _build_json_formatter() -> structlog.stdlib.ProcessorFormatter:
    """Return the single JSON formatter used by console, file, and shipping.

    ``ProcessorFormatter`` copies each record before rendering, so the same
    formatter can safely serve multiple handlers.
    """
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            # ``default=str`` must be explicit: structlog otherwise installs a
            # repr-based fallback that turns Decimal("1.5") into "Decimal('1.5')".
            structlog.processors.JSONRenderer(serializer=_json_serializer, default=str),
        ],
    )


class _SafeConsoleRenderer:
    """ConsoleRenderer that degrades gracefully on encoding errors.

    On Windows cp1252 consoles, tracebacks with non-ASCII characters
    (e.g. Unicode file paths) would cause UnicodeEncodeError.  This
    renderer catches that and replaces unencodable characters.
    """

    def __init__(self) -> None:
        self._renderer = structlog.dev.ConsoleRenderer()

    def __call__(self, logger: Any, method_name: str, event_dict: Any) -> str:
        try:
            return self._renderer(logger, method_name, event_dict)
        except UnicodeEncodeError:
            # Replace unencodable chars and retry
            safe = {k: self._safe_val(v) for k, v in event_dict.items()}
            return self._renderer(logger, method_name, safe)

    @staticmethod
    def _safe_val(val: Any) -> Any:
        if isinstance(val, str):
            return val.encode("utf-8", errors="replace").decode("utf-8")
        return val


def _build_text_processors() -> list[structlog.types.Processor]:
    return [
        *_SHARED_PROCESSORS,
        structlog.processors.format_exc_info,
        _SafeConsoleRenderer(),
    ]


def setup_logging() -> None:
    """Configure structlog + stdlib logging based on ``settings``.

    In ``log_format="json"`` *every* record — including third-party stdlib
    records — is rendered through ``ProcessorFormatter``, so one log line is
    always one JSON object that can be shipped to Loki/ELK/Vector unchanged.
    """
    fmt = settings.log_format
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    if fmt == "json":
        structlog.configure(
            processors=[
                *_SHARED_PROCESSORS,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        formatter: logging.Formatter = _build_json_formatter()
    else:
        structlog.configure(
            processors=_build_text_processors(),
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Stdlib handlers — third-party libraries (httpx, sqlalchemy, etc.) still
    # go through stdlib, so they use the same formatter as structlog records.
    handlers: list[logging.Handler] = []

    console: logging.StreamHandler[Any] = SafeStreamHandler(sys.stdout)
    console.setFormatter(formatter)
    handlers.append(console)

    if settings.log_file:
        from pathlib import Path

        path = Path(settings.log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(formatter)
        handlers.append(fh)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "asyncio", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Centralized aggregation via Redis Streams (best-effort, opt-in).
    # The aggregator always ships JSON, even when the console is text-mode.
    if getattr(settings, "log_aggregation_enabled", False):
        try:
            from integrations.observability.log_aggregator import (
                install_aggregation_handler,
            )

            install_aggregation_handler(
                source=settings.log_aggregation_source,
                formatter=_build_json_formatter(),
            )
        except Exception:
            logging.getLogger(__name__).debug(
                "Log aggregation handler not installed", exc_info=True
            )


# ── Public API ─────────────────────────────────────────────────────────────

_loggers: dict[str, structlog.stdlib.BoundLogger] = {}


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger with stdlib-compatible API.

    Usage is identical to the previous stdlib-based implementation::

        logger = get_logger(__name__)
        logger.info("something happened", key="value")
        logger.warning("slow query", duration_ms=1200)
        logger.exception("unhandled error")
    """
    if name is None:
        import inspect

        frame = inspect.currentframe()
        name = frame.f_back.f_globals["__name__"] if frame and frame.f_back else "root"
    if name not in _loggers:
        _loggers[name] = structlog.get_logger(name)
    return _loggers[name]


# ── Context binding helpers ────────────────────────────────────────────────
# These wrap structlog.contextvars so callers don't need to import structlog.


def bind_context(**kwargs: Any) -> None:
    """Bind contextual fields to the current async context (thread-local).

    These fields are automatically included in every log line until
    ``unbind_context`` is called::

        bind_context(request_id="abc-123", job_name="sync")
        logger.info("started")  # includes request_id + job_name
        unbind_context("request_id")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove previously bound contextual fields."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Remove all bound contextual fields."""
    structlog.contextvars.clear_contextvars()
