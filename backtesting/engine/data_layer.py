from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DataChunk:
    market_id: str
    instrument_ids: list[str]
    start_time: datetime
    end_time: datetime
    records: list[dict[str, Any]]
    chunk_size: int = 0


class DataLake(ABC):
    @abstractmethod
    async def load_chunk(
        self,
        market_id: str,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AsyncIterator[DataChunk]: ...

    @abstractmethod
    async def get_instruments(self, market_id: str) -> list[str]: ...

    @abstractmethod
    async def get_available_markets(self) -> list[str]: ...


@dataclass
class InMemoryDataLake(DataLake):
    data: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    chunk_size: int = 10_000

    async def load_chunk(
        self,
        market_id: str,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AsyncIterator[DataChunk]:
        records = self.data.get(market_id, [])
        if instrument_ids:
            records = [r for r in records if r.get("instrument_id") in instrument_ids]
        if start_time:
            records = [r for r in records if r.get("timestamp", datetime.min) >= start_time]
        if end_time:
            records = [r for r in records if r.get("timestamp", datetime.max) <= end_time]

        instruments = list({r.get("instrument_id", "") for r in records})
        for i in range(0, len(records), self.chunk_size):
            chunk_records = records[i : i + self.chunk_size]
            if not chunk_records:
                continue
            yield DataChunk(
                market_id=market_id,
                instrument_ids=instruments,
                start_time=chunk_records[0].get("timestamp", datetime.min),
                end_time=chunk_records[-1].get("timestamp", datetime.max),
                records=chunk_records,
                chunk_size=len(chunk_records),
            )

    async def get_instruments(self, market_id: str) -> list[str]:
        records = self.data.get(market_id, [])
        return list({r.get("instrument_id", "") for r in records})

    async def get_available_markets(self) -> list[str]:
        return list(self.data.keys())

    def add_records(self, market_id: str, records: list[dict[str, Any]]) -> None:
        if market_id not in self.data:
            self.data[market_id] = []
        self.data[market_id].extend(records)
        self.data[market_id].sort(key=lambda r: r.get("timestamp", datetime.min))
