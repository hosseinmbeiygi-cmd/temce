from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def register(self, name: str, capabilities: dict[str, Any]) -> None:
        self._entries[name] = capabilities
        logger.info("Registered capabilities for: %s", name)

    def unregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def get(self, name: str) -> dict[str, Any] | None:
        return self._entries.get(name)

    def list_all(self) -> dict[str, dict[str, Any]]:
        return dict(self._entries)

    def find_by_capability(self, capability: str) -> list[str]:
        return [name for name, caps in self._entries.items() if caps.get(capability)]
