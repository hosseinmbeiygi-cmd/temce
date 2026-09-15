from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CollectedData:
    source: str
    symbol: str
    data_type: str
    raw_data: Any
    collected_at: datetime = field(default_factory=datetime.now)
    metadata: dict | None = None


class BaseLibraryAdapter(ABC):
    def __init__(self) -> None:
        self.source_name = self.__class__.__name__.replace("Adapter", "").lower()
        self.errors: list[dict] = []

    @abstractmethod
    def get_capabilities(self) -> dict[str, bool]: ...

    @abstractmethod
    def collect_symbol(self, symbol: str) -> list[CollectedData]: ...

    def collect_all(self, symbols: list[str]) -> dict[str, list[CollectedData]]:
        import time

        results: dict[str, list[CollectedData]] = {}
        for symbol in symbols:
            try:
                results[symbol] = self.collect_symbol(symbol)
                time.sleep(0.3)
            except Exception as e:
                self.handle_error(e, symbol)
                results[symbol] = []
        return results

    def handle_error(self, error: Exception, symbol: str | None = None) -> None:
        self.errors.append(
            {
                "timestamp": datetime.now(),
                "symbol": symbol,
                "error": str(error),
            }
        )

    def get_errors(self) -> list[dict]:
        return self.errors
