from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import date, datetime
from typing import Any, TypeVar

T = TypeVar("T")
JsonDict = dict[str, Any]
JsonList = list[Any]
JsonValue = str | int | float | bool | None | JsonDict | JsonList
AsyncFunc = Callable[..., Coroutine[Any, Any, Any]]
SyncFunc = Callable[..., Any]
Nullable = T | None
Timestamp = datetime | str | float
DateLike = date | datetime | str
