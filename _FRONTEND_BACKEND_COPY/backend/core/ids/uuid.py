from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_uuid() -> str:
    return uuid.uuid4().hex


def new_uuid_dashed() -> str:
    return str(uuid.uuid4())


def new_short_uuid(length: int = 12) -> str:
    return uuid.uuid4().hex[:length]


def uuid_from_timestamp(prefix: str = "") -> str:
    ts = datetime.now(UTC).strftime("%y%m%d%H%M%S%f")[:18]
    rand = uuid.uuid4().hex[:6]
    return f"{prefix}_{ts}{rand}" if prefix else f"{ts}{rand}"


def is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(hex=value)
        return True
    except (ValueError, AttributeError):
        return False


class UUIDGenerator:
    def __init__(self, prefix: str = "", separator: str = "_") -> None:
        self.prefix = prefix
        self.separator = separator

    def generate(self) -> str:
        uid = uuid.uuid4().hex
        if self.prefix:
            return f"{self.prefix}{self.separator}{uid}"
        return uid

    def generate_dashed(self) -> str:
        uid = str(uuid.uuid4())
        if self.prefix:
            return f"{self.prefix}{self.separator}{uid}"
        return uid
