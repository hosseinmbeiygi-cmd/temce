from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import orjson

from core.paths import validate_safe_path


def default_serializer(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        # Return the mapping itself, not a JSON string nested inside the
        # surrounding payload.
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "_asdict") and callable(obj._asdict):
        return obj._asdict()
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
