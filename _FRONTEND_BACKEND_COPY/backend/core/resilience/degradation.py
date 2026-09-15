from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class DegradationLevel(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FULL = "full"


class DegradationManager:
    def __init__(self) -> None:
        self._level = DegradationLevel.NONE
        self._actions: dict[DegradationLevel, list[Callable[[], None]]] = {}

    @property
    def level(self) -> DegradationLevel:
        return self._level

    def set_level(self, level: DegradationLevel) -> None:
        if level == self._level:
            return
        logger.warning("Degradation level changed: %s -> %s", self._level.value, level.value)
        self._level = level
        for action in self._actions.get(level, []):
            try:
                action()
            except Exception as e:
                logger.error("Degradation action failed: %s", e)

    def on_level(self, level: DegradationLevel, action: Callable[[], None]) -> None:
        if level not in self._actions:
            self._actions[level] = []
        self._actions[level].append(action)

    def is_available(self, required_level: DegradationLevel = DegradationLevel.NONE) -> bool:
        levels = {
            DegradationLevel.NONE: 0,
            DegradationLevel.LOW: 1,
            DegradationLevel.MEDIUM: 2,
            DegradationLevel.HIGH: 3,
            DegradationLevel.FULL: 4,
        }
        return levels[self._level] <= levels[required_level]

    def reset(self) -> None:
        self.set_level(DegradationLevel.NONE)
