from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)

# Audit DS-04: the three foreign providers ship with an ``api.example.com``
# base URL. They can never return data, so ``health()`` must not report ready
# and ``fetch_news`` must not pretend to be configured.
PLACEHOLDER_HOST = "api.example.com"


def base_url_is_placeholder(client: Any) -> bool:
    return PLACEHOLDER_HOST in str(getattr(client, "base_url", ""))


class ForeignNewsHealth:
    async def check(self, providers: dict[str, Any]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, provider in providers.items():
            try:
                health = await provider.health()
                results[name] = health
            except Exception as e:
                results[name] = {"status": ProviderHealth.DOWN, "message": str(e)}
        return results
