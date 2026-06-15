from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class GlobalMarketsHealth:
    async def check(self, providers: dict[str, Any]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, provider in providers.items():
            try:
                health = await provider.health()
                results[name] = health
            except Exception as e:
                results[name] = {"status": ProviderHealth.DOWN, "message": str(e)}
        return results
