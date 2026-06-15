from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex[:24]
    return f"{prefix}_{uid}" if prefix else uid


def new_uuid() -> str:
    return uuid.uuid4().hex


def new_short_id(length: int = 12) -> str:
    return uuid.uuid4().hex[:length]


def new_snowflake_id(worker_id: int = 1) -> int:
    import time

    EPOCH = 1700000000000
    now = int(time.time() * 1000)
    seq = 0
    return ((now - EPOCH) << 12) | ((worker_id & 0x3FF) << 2) | (seq & 0x03)


def id_from_timestamp(prefix: str = "") -> str:
    ts = datetime.now(UTC).strftime("%y%m%d%H%M%S%f")[:16]
    rand = uuid.uuid4().hex[:8]
    return f"{prefix}_{ts}{rand}" if prefix else f"{ts}{rand}"
