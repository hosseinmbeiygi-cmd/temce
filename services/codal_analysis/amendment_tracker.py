from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnnouncementNode:
    announcement_id: str
    symbol: str
    title: str
    publish_date: str
    fiscal_period: str
    report_type: str
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    correction_number: int = 0
    is_current: bool = True
    is_superseded: bool = False
    metadata_: dict[str, Any] = field(default_factory=dict)


@dataclass
class AmendmentChain:
    symbol: str
    fiscal_period: str
    report_type: str
    nodes: list[AnnouncementNode] = field(default_factory=list)
    latest_valid: AnnouncementNode | None = None
    chain_length: int = 0
    has_conflict: bool = False


class ChainAmendmentTracker:
    """
    Tracks chains of amendments/corrections for financial reports.
    Each announcement can have a parent (the one it corrects) and children (corrections of this one).
    """

    def __init__(self):
        self._nodes: dict[str, AnnouncementNode] = {}
        self._symbol_index: dict[str, list[str]] = {}

    def register_announcement(
        self,
        announcement_id: str,
        symbol: str,
        title: str,
        publish_date: str,
        fiscal_period: str,
        report_type: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnnouncementNode:
        node = AnnouncementNode(
            announcement_id=announcement_id,
            symbol=symbol,
            title=title,
            publish_date=publish_date,
            fiscal_period=fiscal_period,
            report_type=report_type,
            parent_id=parent_id,
            metadata_=metadata or {},
        )

        if parent_id and parent_id in self._nodes:
            parent = self._nodes[parent_id]
            parent.children.append(announcement_id)
            node.correction_number = parent.correction_number + 1
            parent.is_current = False

        self._nodes[announcement_id] = node
        if symbol not in self._symbol_index:
            self._symbol_index[symbol] = []
        self._symbol_index[symbol].append(announcement_id)

        return node

    def get_chain(self, symbol: str, fiscal_period: str, report_type: str) -> AmendmentChain:
        chain = AmendmentChain(symbol=symbol, fiscal_period=fiscal_period, report_type=report_type)
        for node in self._nodes.values():
            if node.symbol == symbol and node.fiscal_period == fiscal_period and node.report_type == report_type:
                chain.nodes.append(node)
        chain.nodes.sort(key=lambda x: x.publish_date)
        chain.chain_length = len(chain.nodes)
        if chain.nodes:
            chain.latest_valid = chain.nodes[-1]
            chain.latest_valid.is_current = True
        return chain

    def get_announcement_dependency_graph(self, symbol: str) -> dict[str, list[str]]:
        """Returns adjacency list representing the dependency graph."""
        graph: dict[str, list[str]] = {}
        for node in self._nodes.values():
            if node.symbol == symbol:
                graph[node.announcement_id] = node.children
        return graph

    def traverse_to_latest(self, announcement_id: str) -> AnnouncementNode | None:
        """Follow the amendment chain to find the latest valid version."""
        current = self._nodes.get(announcement_id)
        if not current:
            return None
        visited: set[str] = set()
        while current.children and current.announcement_id not in visited:
            visited.add(current.announcement_id)
            next_id = current.children[-1]
            next_node = self._nodes.get(next_id)
            if not next_node:
                break
            current = next_node
        return current

    def get_amendment_history(self, symbol: str, fiscal_period: str, report_type: str) -> list[dict[str, Any]]:
        chain = self.get_chain(symbol, fiscal_period, report_type)
        return [
            {
                "announcement_id": n.announcement_id,
                "publish_date": n.publish_date,
                "correction_number": n.correction_number,
                "is_current": n.is_current,
                "is_superseded": n != chain.latest_valid,
                "title": n.title,
            }
            for n in chain.nodes
        ]

    def detect_conflicts(self, symbol: str) -> list[dict[str, Any]]:
        """Detect conflicting amendment chains (e.g., two chains for same period)."""
        chains: dict[str, dict[str, list[str]]] = {}
        for node in self._nodes.values():
            if node.symbol != symbol:
                continue
            key = f"{node.fiscal_period}:{node.report_type}"
            if key not in chains:
                chains[key] = {"nodes": [], "parents": set()}
            chains[key]["nodes"].append(node.announcement_id)
            if node.parent_id:
                chains[key]["parents"].add(node.parent_id)

        conflicts = []
        for key, data in chains.items():
            if len(data["nodes"]) > 5:
                conflicts.append({
                    "symbol": symbol,
                    "period_type": key,
                    "node_count": len(data["nodes"]),
                    "severity": "high",
                    "detail": f"Excessive amendments ({len(data['nodes'])}) for {key}",
                })

        return conflicts
