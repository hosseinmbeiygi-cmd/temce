from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ParserBase(ABC):
    @abstractmethod
    def parse(self, raw_data: Any) -> dict[str, Any]: ...

    @abstractmethod
    def validate(self, parsed: dict[str, Any]) -> bool: ...


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, ParserBase] = {}

    def register(self, name: str, parser: ParserBase) -> None:
        self._parsers[name] = parser

    def get(self, name: str) -> ParserBase | None:
        return self._parsers.get(name)

    def parse(self, name: str, raw_data: Any) -> dict[str, Any]:
        parser = self.get(name)
        if not parser:
            raise ValueError(f"No parser registered: {name}")
        return parser.parse(raw_data)


parser_registry = ParserRegistry()
