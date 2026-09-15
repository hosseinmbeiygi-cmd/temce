from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ParsedEvent(BaseModel):
    source: str
    event_type: str
    data: dict[str, Any]
    raw_object_key: str
    fetch_time: str
    parsed_at: str


class Parser(ABC):
    @abstractmethod
    def can_parse(self, source: str, endpoint: str, content_type: str) -> bool: ...

    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def parse(self, payload: bytes) -> list[ParsedEvent]: ...


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: list[Parser] = []

    def register(self, parser: Parser) -> None:
        self._parsers.append(parser)

    def find(self, source: str, endpoint: str, content_type: str) -> Parser | None:
        for p in self._parsers:
            if p.can_parse(source, endpoint, content_type):
                return p
        return None

    def find_by_source(self, source: str) -> Parser | None:
        for p in self._parsers:
            if p.source_name() == source:
                return p
        return None
