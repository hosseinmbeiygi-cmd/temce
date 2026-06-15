from __future__ import annotations

from typing import Any

from core.context import get_correlation_id, get_request_id
from core.logging import get_logger

logger = get_logger(__name__)


class RequestLog:
    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.method: str = ""
        self.path: str = ""
        self.status_code: int = 0
        self.duration_ms: float = 0.0
        self.ip: str = ""
        self.user_agent: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration_ms": round(self.duration_ms, 2),
            "ip": self.ip,
            "user_agent": self.user_agent,
            "request_id": get_request_id(),
            "correlation_id": get_correlation_id(),
        }


async def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    ip: str = "",
    user_agent: str = "",
    **kwargs: Any,
) -> None:
    log = RequestLog()
    log.method = method
    log.path = path
    log.status_code = status_code
    log.duration_ms = duration_ms
    log.ip = ip
    log.user_agent = user_agent
    logger.info("REQUEST: %s %s %d (%.2fms)", method, path, status_code, duration_ms, extra=log.to_dict())
