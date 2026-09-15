"""Data Mesh Architecture — domain-oriented data management for Iranian market.

This module provides the foundation for a Data Mesh architecture that separates
market data into independent domains:

1. StockDomain — TSE, IFB, Base Market
2. CommodityDomain — Gold, Silver, IME commodities
3. CurrencyDomain — USD/IRR, EUR/IRR, free market rates
4. MacroDomain — Inflation, economic indicators, news

Each domain owns its data, provides standardized interfaces, and can evolve
independently. This replaces the monolithic data approach.

Note: This is the architectural foundation. Full implementation requires
moving from the current monolithic database to domain-specific schemas.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DomainHealth:
    """Health status of a data domain."""

    domain: str
    is_healthy: bool = True
    last_sync: str = ""
    record_count: int = 0
    error: str | None = None


class DataDomain(ABC):
    """Abstract base class for a data domain."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain name."""

    @abstractmethod
    async def health_check(self) -> DomainHealth:
        """Check domain health."""

    @abstractmethod
    async def get_latest(self, symbol: str) -> dict[str, Any] | None:
        """Get latest data for a symbol."""

    @abstractmethod
    async def get_history(self, symbol: str, days: int = 30) -> list[dict[str, Any]]:
        """Get historical data for a symbol."""


class StockDomain(DataDomain):
    """Stock market domain (TSE, IFB, Base Market)."""

    @property
    def name(self) -> str:
        return "stock"

    async def health_check(self) -> DomainHealth:
        return DomainHealth(domain=self.name, is_healthy=True)

    async def get_latest(self, symbol: str) -> dict[str, Any] | None:
        return None

    async def get_history(self, symbol: str, days: int = 30) -> list[dict[str, Any]]:
        return []


class CommodityDomain(DataDomain):
    """Commodity domain (Gold, Silver, IME)."""

    @property
    def name(self) -> str:
        return "commodity"

    async def health_check(self) -> DomainHealth:
        return DomainHealth(domain=self.name, is_healthy=True)

    async def get_latest(self, symbol: str) -> dict[str, Any] | None:
        return None

    async def get_history(self, symbol: str, days: int = 30) -> list[dict[str, Any]]:
        return []


class CurrencyDomain(DataDomain):
    """Currency domain (USD/IRR, EUR/IRR)."""

    @property
    def name(self) -> str:
        return "currency"

    async def health_check(self) -> DomainHealth:
        return DomainHealth(domain=self.name, is_healthy=True)

    async def get_latest(self, symbol: str) -> dict[str, Any] | None:
        return None

    async def get_history(self, symbol: str, days: int = 30) -> list[dict[str, Any]]:
        return []


class MacroDomain(DataDomain):
    """Macro-economic domain (inflation, indicators, news)."""

    @property
    def name(self) -> str:
        return "macro"

    async def health_check(self) -> DomainHealth:
        return DomainHealth(domain=self.name, is_healthy=True)

    async def get_latest(self, symbol: str) -> dict[str, Any] | None:
        return None

    async def get_history(self, symbol: str, days: int = 30) -> list[dict[str, Any]]:
        return []


class DataMeshRegistry:
    """Registry of all data domains."""

    def __init__(self) -> None:
        self._domains: dict[str, DataDomain] = {}

    def register(self, domain: DataDomain) -> None:
        self._domains[domain.name] = domain
        logger.info("Registered data domain: %s", domain.name)

    def get(self, name: str) -> DataDomain | None:
        return self._domains.get(name)

    def list_domains(self) -> list[str]:
        return list(self._domains.keys())

    async def health_check_all(self) -> list[DomainHealth]:
        results: list[DomainHealth] = []
        for domain in self._domains.values():
            try:
                health = await domain.health_check()
                results.append(health)
            except Exception as e:
                results.append(
                    DomainHealth(
                        domain=domain.name,
                        is_healthy=False,
                        error=str(e),
                    )
                )
        return results


# Default registry instance
mesh_registry = DataMeshRegistry()
mesh_registry.register(StockDomain())
mesh_registry.register(CommodityDomain())
mesh_registry.register(CurrencyDomain())
mesh_registry.register(MacroDomain())
