from __future__ import annotations

from typing import Any

from backtesting.universe.groups import GroupRegistry

from .symbol_graph import SymbolRelationGraph


class IndexGraph:
    MAJOR_INDICES = [
        "TEDPIX",
        "TEDIX",
        "TEFIX",
        "TEGIX",
        "TEDPIX30",
        "TEDPIX50",
    ]

    def __init__(self, groups: GroupRegistry, relations: SymbolRelationGraph | None = None) -> None:
        self._groups = groups
        self._relations = relations

    def get_index_weight(self, index_symbol: str, instrument_symbol: str) -> float:
        index = self._groups.get_index_by_symbol(index_symbol)
        if index is None:
            return 0.0
        return index.weights.get(instrument_symbol, 0.0)

    def get_top_weights(self, index_symbol: str, top_n: int = 10) -> list[tuple[str, float]]:
        index = self._groups.get_index_by_symbol(index_symbol)
        if index is None:
            return []
        sorted_weights = sorted(index.weights.items(), key=lambda x: x[1], reverse=True)
        return sorted_weights[:top_n]

    def get_sector_weights(self, index_symbol: str) -> dict[str, float]:
        index = self._groups.get_index_by_symbol(index_symbol)
        if index is None or not index.constituents:
            return {}
        sector_weights: dict[str, float] = {}
        for inst_id in index.constituents:
            groups_info = self._groups.groups_for_instrument(inst_id)
            weight = index.weights.get(inst_id, 0.0)
            for g in groups_info:
                sector_weights[g.code] = sector_weights.get(g.code, 0.0) + weight
        return sector_weights

    def rebalance_impact(self, index_symbol: str, old_date: str, new_date: str) -> dict[str, Any]:
        return {
            "index": index_symbol,
            "added": [],
            "removed": [],
            "weight_changes": {},
        }
