from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str:
    return _request_id.get()


def set_user_id(user_id: str) -> None:
    _user_id.set(user_id)


def get_user_id() -> str:
    return _user_id.get()


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str:
    return _correlation_id.get()


@dataclass
class ExecutionContext:
    request_id: str = ""
    user_id: str = ""
    correlation_id: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(cls) -> ExecutionContext:
        return cls(
            request_id=get_request_id(),
            user_id=get_user_id(),
            correlation_id=get_correlation_id(),
        )
