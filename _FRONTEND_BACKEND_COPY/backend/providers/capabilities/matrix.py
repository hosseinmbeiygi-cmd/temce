from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


FEATURE_CATEGORIES = {
    "realtime": ["quote", "orderbook", "trades", "market_watch"],
    "historical": ["daily", "intraday", "adjusted", "dividends"],
    "reference": ["instruments", "corporate_actions", "financials"],
    "macro": ["commodities", "fx", "energy", "metals", "gold", "indices"],
    "news": ["domestic", "foreign", "rss", "sentiment"],
    "manual": ["codal", "macro", "news", "quotes"],
}


class CapabilityMatrix:
    def __init__(self) -> None:
        self._matrix: dict[str, dict[str, bool]] = {}

    def set_capability(self, provider: str, feature: str, supported: bool = True) -> None:
        self._matrix.setdefault(provider, {})[feature] = supported

    def has_capability(self, provider: str, feature: str) -> bool:
        return self._matrix.get(provider, {}).get(feature, False)

    def get_capabilities(self, provider: str) -> dict[str, bool]:
        return self._matrix.get(provider, {})

    def find_providers(self, feature: str) -> list[str]:
        return [p for p, caps in self._matrix.items() if caps.get(feature)]

    def list_all(self) -> dict[str, dict[str, bool]]:
        return dict(self._matrix)
