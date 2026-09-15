from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class StatusEntry:
    def __init__(self, provider: str, status: ProviderHealth) -> None:
        self.provider = provider
        self.status = status
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
        }


class ProviderStatusHistory:
    def __init__(self, max_entries: int = 10000) -> None:
        self.max_entries = max_entries
        self._entries: dict[str, deque[StatusEntry]] = {}

    def record(self, provider: str, status: ProviderHealth) -> None:
        if provider not in self._entries:
            self._entries[provider] = deque(maxlen=self.max_entries)
        self._entries[provider].append(StatusEntry(provider, status))

    def get_history(self, provider: str, limit: int = 100) -> list[StatusEntry]:
        entries = self._entries.get(provider, deque())
        return list(entries)[-limit:]

    def get_latest(self, provider: str) -> StatusEntry | None:
        entries = self._entries.get(provider)
        if not entries:
            return None
        return entries[-1]

    def get_all_providers(self) -> dict[str, list[StatusEntry]]:
        return {name: list(entries) for name, entries in self._entries.items()}
