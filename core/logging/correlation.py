from __future__ import annotations

import logging
import uuid

from core.context import get_correlation_id, set_correlation_id
from core.logging import get_logger

logger = get_logger(__name__)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        correlation_id = get_correlation_id()
        if correlation_id:
            record.correlation_id = correlation_id
        else:
            record.correlation_id = ""
        return True


def ensure_correlation_id() -> str:
    cid = get_correlation_id()
    if not cid:
        cid = uuid.uuid4().hex[:16]
        set_correlation_id(cid)
    return cid


def correlation_context(correlation_id: str | None = None) -> str:
    cid = correlation_id or uuid.uuid4().hex[:16]
    set_correlation_id(cid)
    return cid
