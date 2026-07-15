from __future__ import annotations

from typing import Any

from core.logging import get_logger
from ingestion.library_sources.base_adapter import BaseLibraryAdapter, CollectedData

logger = get_logger(__name__)


class UniversalCollector:
    def __init__(self, symbols: list[str] | None = None) -> None:
        self.symbols = symbols or []
        self.adapters: dict[str, BaseLibraryAdapter] = {}
        self.results: dict[str, dict[str, list[CollectedData]]] = {}
        self._init_adapters()

    def _init_adapters(self) -> None:
        adapters_to_register = [
            ("finpy", "ingestion.library_sources.finpy_adapter", "FinpyAdapter"),
            ("pytse_client", "ingestion.library_sources.pytse_client_adapter", "PytseClientAdapter"),
            ("sadra_tse", "ingestion.library_sources.sadra_tse_adapter", "SadraTseAdapter"),
            ("algotik", "ingestion.library_sources.algotik_adapter", "AlgotikAdapter"),
        ]
        for name, module_path, class_name in adapters_to_register:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                self.adapters[name] = cls()
                logger.info("Registered adapter: %s", name)
            except Exception as e:
                logger.warning("Failed to register adapter %s: %s", name, e)

    def collect_all(self, symbols: list[str] | None = None) -> dict[str, dict[str, list[CollectedData]]]:
        symbols = symbols or self.symbols
        if not symbols:
            logger.warning("No symbols provided for collection")
            return {}

        logger.info("Starting universal data collection for %d symbols via %d adapters", len(symbols), len(self.adapters))

        for name, adapter in self.adapters.items():
            try:
                logger.info("Running adapter: %s", name)
                data = adapter.collect_all(symbols)
                self.results[name] = data
                total_items = sum(len(items) for items in data.values())
                logger.info("Adapter %s collected %d data items", name, total_items)
            except Exception as e:
                logger.error("Adapter %s failed: %s", name, e)
                self.results[name] = {}

        return self.results

    def collect_single(self, symbol: str) -> dict[str, list[CollectedData]]:
        result: dict[str, list[CollectedData]] = {}
        for name, adapter in self.adapters.items():
            try:
                result[name] = adapter.collect_symbol(symbol)
            except Exception as e:
                logger.error("Adapter %s failed for %s: %s", name, symbol, e)
                result[name] = []
        return result

    def get_status(self) -> dict[str, Any]:
        return {
            "adapters": list(self.adapters.keys()),
            "symbols_count": len(self.symbols),
            "results": {
                name: {
                    "symbols": len(data),
                    "total_items": sum(len(items) for items in data.values()),
                }
                for name, data in self.results.items()
            },
            "errors": {
                name: len(adapter.get_errors())
                for name, adapter in self.adapters.items()
            },
        }
