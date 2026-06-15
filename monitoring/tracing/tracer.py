from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    parent_span_id: str | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "parent_span_id": self.parent_span_id,
        }


class Tracer:
    def __init__(self) -> None:
        self._active_spans: dict[str, Span] = {}
        self._completed_spans: list[Span] = []
        self._trace_id: str = ""

    def _new_trace_id(self) -> str:
        return uuid.uuid4().hex

    def _new_span_id(self) -> str:
        return uuid.uuid4().hex[:16]

    @asynccontextmanager
    async def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> AsyncIterator[Span]:
        trace_id = self._trace_id or self._new_trace_id()
        span_id = self._new_span_id()
        parent_span_id = None
        if self._active_spans:
            parent_span_id = next(iter(self._active_spans.values())).span_id

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            start_time=datetime.now(UTC),
            attributes=attributes or {},
            parent_span_id=parent_span_id,
        )
        self._active_spans[span_id] = span
        logger.debug("Span started: %s (trace=%s, span=%s)", name, trace_id, span_id)
        try:
            yield span
        except Exception as e:
            span.attributes["error"] = str(e)
            span.attributes["error_type"] = type(e).__name__
            raise
        finally:
            span.end_time = datetime.now(UTC)
            self._active_spans.pop(span_id, None)
            self._completed_spans.append(span)
            logger.debug(
                "Span ended: %s (duration=%.2fms)",
                name,
                span.duration_ms or 0,
            )

    def inject_context(self, headers: dict[str, str]) -> dict[str, str]:
        trace_id = self._trace_id or self._new_trace_id()
        span_id = ""
        if self._active_spans:
            span_id = next(iter(self._active_spans.values())).span_id
        headers["X-Trace-Id"] = trace_id
        headers["X-Span-Id"] = span_id
        return headers

    def extract_context(self, headers: dict[str, str]) -> dict[str, str | None]:
        return {
            "trace_id": headers.get("X-Trace-Id"),
            "span_id": headers.get("X-Span-Id"),
        }

    def get_completed_spans(self) -> list[dict[str, Any]]:
        return [span.to_dict() for span in self._completed_spans]

    def get_trace_spans(self, trace_id: str) -> list[dict[str, Any]]:
        return [span.to_dict() for span in self._completed_spans if span.trace_id == trace_id]

    def reset(self) -> None:
        self._active_spans.clear()
        self._completed_spans.clear()
        self._trace_id = ""


tracer = Tracer()
