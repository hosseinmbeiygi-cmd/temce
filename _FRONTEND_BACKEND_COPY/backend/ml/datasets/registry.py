from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class DatasetRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, Any] = {}

    def register(self, name: str, builder: Any) -> None:
        self._builders[name] = builder
        logger.debug("Registered dataset builder: %s", name)

    def get(self, name: str) -> Any | None:
        return self._builders.get(name)

    def list(self) -> list[str]:
        return list(self._builders.keys())
