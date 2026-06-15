from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import orjson


def default_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "_asdict"):
        return json.dumps(obj._asdict())
    if hasattr(obj, "__dict__"):
        return json.dumps(obj.__dict__)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def dumps(data: Any, **kwargs: Any) -> str:
    try:
        return orjson.dumps(data, default=default_serializer).decode("utf-8")
    except Exception:
        return json.dumps(data, default=default_serializer, ensure_ascii=False, **kwargs)


def loads(s: str | bytes) -> Any:
    try:
        return orjson.loads(s)
    except Exception:
        return json.loads(s)


def pretty(data: Any) -> str:
    return json.dumps(data, default=default_serializer, indent=2, ensure_ascii=False)


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
