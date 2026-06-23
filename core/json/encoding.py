from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import orjson

from core.paths import validate_safe_path


def default_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump())
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


def pretty(data: Any) -> str:
    return json.dumps(data, default=default_serializer, indent=2, ensure_ascii=False)


def dump_json_file(path: str, data: Any, **kwargs: Any) -> None:
    safe_path = validate_safe_path(path)
    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(dumps(data, **kwargs))
