from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, TypeVar

from core.json import dumps, loads

T = TypeVar("T")


class JSONSerializer(Generic[T]):
    def serialize(self, obj: T) -> str:
        return dumps(self._to_serializable(obj))

    def deserialize(self, data: str, target_type: type[T]) -> T:
        raw = loads(data)
        return self._from_raw(raw, target_type)

    def _to_serializable(self, obj: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, (list, tuple)):
            return [self._to_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return {k: self._to_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        return str(obj)

    def _from_raw(self, raw: Any, target_type: type[T]) -> T:
        if target_type in (dict, list):
            return raw
        if hasattr(target_type, "model_validate"):
            return target_type.model_validate(raw)
        return raw


class DataclassSerializer:
    def serialize(self, obj: Any) -> str:
        from dataclasses import asdict, is_dataclass

        if not is_dataclass(obj):
            raise TypeError("Object must be a dataclass")
        return dumps(asdict(obj))

    def deserialize(self, data: str, target_type: type) -> Any:
        from dataclasses import fields

        raw = loads(data)
        field_types = {f.name: f.type for f in fields(target_type)}
        kwargs = {}
        for name, value in raw.items():
            if name in field_types:
                kwargs[name] = value
        return target_type(**kwargs)
