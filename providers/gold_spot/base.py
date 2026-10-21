"""Synchronous gold spot provider contract.

``fetch_resilient_gold_spot`` runs each provider call inside a bounded
executor, so providers expose a plain synchronous ``fetch()`` rather than the
async ``BaseProvider`` contract used by request-scoped data providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GoldSpotProviderError(RuntimeError):
    """Raised when a provider cannot produce a usable gold spot quote."""


class GoldSpotProvider(ABC):
    """A source of a USD-per-troy-ounce gold spot quote."""

    name: str

    @abstractmethod
    def fetch(self) -> dict[str, Any]:
        """Return ``{"price": float, "timestamp": epoch_seconds}``."""
