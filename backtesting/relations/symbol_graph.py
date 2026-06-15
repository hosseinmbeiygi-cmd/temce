from __future__ import annotations

from collections import defaultdict
from enum import StrEnum
from typing import Any


class RelationType(StrEnum):
    HOLDING = "holding"
    SUBSIDIARY = "subsidiary"
    PARENT = "parent"
    INVESTMENT = "investment"
    RIVAL = "rival"
    PEER_GROUP = "peer_group"
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    SYMBOL_CHANGE = "symbol_change"
    DERIVATIVE_UNDERLYING = "derivative_underlying"


class SymbolRelationGraph:
    def __init__(self) -> None:
        self._edges: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    def add_relation(self, from_id: str, to_id: str, relation: RelationType) -> None:
        self._edges[from_id][relation.value].add(to_id)

    def get_relations(self, instrument_id: str, relation: RelationType | None = None) -> list[str]:
        if relation:
            return list(self._edges[instrument_id].get(relation.value, set()))
        result: set[str] = set()
        for rel_set in self._edges[instrument_id].values():
            result.update(rel_set)
        return list(result)

    def has_relation(self, from_id: str, to_id: str) -> bool:
        return any(to_id in rel_set for rel_set in self._edges[from_id].values())

    def get_related_by_type(self, relation: RelationType) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for src in self._edges:
            targets = list(self._edges[src].get(relation.value, set()))
            if targets:
                result[src] = targets
        return result

    def get_peer_group(self, instrument_id: str) -> list[str]:
        peers: list[str] = []
        for src, rels in self._edges.items():
            if instrument_id in rels.get(RelationType.PEER_GROUP.value, set()):
                peers.append(src)
        peers.extend(self._edges[instrument_id].get(RelationType.PEER_GROUP.value, set()))
        return list(set(peers))

    async def load_from_db(self, db: Any) -> None:
        rows = await db.fetch("SELECT * FROM symbol_relations")
        for row in rows:
            self.add_relation(
                str(row["from_instrument_id"]),
                str(row["to_instrument_id"]),
                RelationType(row["relation_type"]),
            )
