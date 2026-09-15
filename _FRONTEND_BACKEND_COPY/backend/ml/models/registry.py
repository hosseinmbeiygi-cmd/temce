from __future__ import annotations

from typing import Any

from core.logging import get_logger
from ml.models.base import BaseModel

logger = get_logger(__name__)


class ModelRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, type[BaseModel]] = {}

    def register(self, name: str, model_cls: type[BaseModel]) -> None:
        self._builders[name] = model_cls

    def create(self, name: str, params: dict[str, Any] | None = None) -> BaseModel:
        cls = self._builders.get(name)
        if cls is None:
            logger.debug("Unknown model: %s", name)
            raise ValueError("Unknown model")
        return cls(name=name, params=params or {})

    def list_models(self) -> list[str]:
        return list(self._builders.keys())


model_registry = ModelRegistry()
