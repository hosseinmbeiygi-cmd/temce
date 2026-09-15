from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IndustryGroup:
    code: str
    name: str
    parent_code: str | None = None
    description: str | None = None


@dataclass
class IndexInfo:
    id: str
    name: str
    symbol: str
    weight_type: str = "market_cap"
    constituents: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)


class GroupRegistry:
    def __init__(self) -> None:
        self._groups: dict[str, IndustryGroup] = {}
        self._indices: dict[str, IndexInfo] = {}
        self._instrument_groups: dict[str, list[str]] = {}

    def add_group(self, group: IndustryGroup) -> None:
        self._groups[group.code] = group

    def get_group(self, code: str) -> IndustryGroup | None:
        return self._groups.get(code)

    def add_index(self, index: IndexInfo) -> None:
        self._indices[index.id] = index

    def get_index(self, index_id: str) -> IndexInfo | None:
        return self._indices.get(index_id)

    def get_index_by_symbol(self, symbol: str) -> IndexInfo | None:
        for idx in self._indices.values():
            if idx.symbol == symbol:
                return idx
        return None

    def get_index_constituents(self, index_id: str, date: str | None = None) -> list[str]:
        idx = self._indices.get(index_id)
        if idx is None:
            return []
        return idx.constituents

    def get_index_weight(self, index_id: str, instrument_id: str) -> float:
        idx = self._indices.get(index_id)
        if idx is None:
            return 0.0
        return idx.weights.get(instrument_id, 0.0)

    def groups_for_instrument(self, instrument_id: str) -> list[IndustryGroup]:
        codes = self._instrument_groups.get(instrument_id, [])
        return [self._groups[c] for c in codes if c in self._groups]

    async def load_from_db(self, db: Any) -> None:
        rows = await db.fetch("SELECT * FROM market_groups")
        for row in rows:
            self.add_group(
                IndustryGroup(
                    code=str(row["code"]),
                    name=row["name"],
                    parent_code=row.get("parent_code"),
                    description=row.get("description"),
                )
            )
        logger.info("Loaded %d groups from DB", len(rows))

    def hierarchy(self, group_code: str) -> list[IndustryGroup]:
        result: list[IndustryGroup] = []
        current = self._groups.get(group_code)
        while current:
            result.append(current)
            current = self._groups.get(current.parent_code) if current.parent_code else None
        return result

    def children_of(self, group_code: str) -> list[IndustryGroup]:
        return [g for g in self._groups.values() if g.parent_code == group_code]
