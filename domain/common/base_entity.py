from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class BaseEntity:
    def __init__(self, id: str, created_at: datetime | None = None, updated_at: datetime | None = None) -> None:
        self._id = id
        self._created_at = created_at or datetime.now(UTC).replace(tzinfo=None)
        self._updated_at = updated_at

    @property
    def id(self) -> str:
        return self._id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime | None:
        return self._updated_at

    def mark_updated(self) -> None:
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id})"
