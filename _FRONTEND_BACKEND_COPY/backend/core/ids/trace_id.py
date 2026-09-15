from __future__ import annotations

from uuid import uuid4

_trace_context: dict[str, str] = {}


def new_trace_id() -> str:
    trace_id = uuid4().hex
    _trace_context["trace_id"] = trace_id
    return trace_id


def get_trace_id() -> str:
    return _trace_context.get("trace_id", "")


def set_trace_id(trace_id: str) -> None:
    _trace_context["trace_id"] = trace_id


def clear_trace_id() -> None:
    _trace_context.pop("trace_id", None)


class TraceContext:
    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or new_trace_id()
        self._parent: str | None = None
        self._span_id: str | None = None

    def new_span_id(self) -> str:
        self._span_id = uuid4().hex[:16]
        return self._span_id

    @property
    def span_id(self) -> str | None:
        return self._span_id

    @property
    def parent_id(self) -> str | None:
        return self._parent

    @parent_id.setter
    def parent_id(self, value: str | None) -> None:
        self._parent = value
