from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import orjson

from core.logging import get_logger
from core.paths import validate_safe_path

logger = get_logger(__name__)


def loads(s: str | bytes, use_orjson: bool = True) -> Any:
    if use_orjson:
        try:
            return orjson.loads(s)
        except Exception as e:
            logger.debug("orjson failed, falling back to json: %s", e)
            pass
    return json.loads(s)


def load_json_file(path: str) -> Any:
    safe_path = validate_safe_path(path)
    with open(safe_path, encoding="utf-8") as f:
        return loads(f.read())


def safe_loads(s: str | bytes, default: Any = None) -> Any:
    try:
        return loads(s)
    except (json.JSONDecodeError, ValueError, TypeError):
        return default


def parse_datetime_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_date_iso(value: str) -> date:
    return date.fromisoformat(value)


def parse_decimal(value: str | float | int) -> Decimal:
    return Decimal(str(value))
