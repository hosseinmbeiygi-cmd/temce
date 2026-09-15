from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class InstrumentNode:
    instrument_id: str
    market_id: str
    market_type: str = ""
    sector: str = ""
    connections: dict[str, float] = field(default_factory=dict)  # target_id -> weight


class InstrumentGraph:
    """Graph of cross-market instrument relationships.

    Supports:
    - Lead-lag detection
    - Correlation-based edges
    - Sector/industry grouping
    - Cross-asset hedge identification
    """

    def __init__(self) -> None:
        self._nodes: dict[str, InstrumentNode] = {}

    def add_instrument(
        self, instrument_id: str, market_id: str, market_type: str = "", sector: str = ""
    ) -> InstrumentNode:
        if instrument_id not in self._nodes:
            self._nodes[instrument_id] = InstrumentNode(
                instrument_id=instrument_id,
                market_id=market_id,
                market_type=market_type,
                sector=sector,
            )
        return self._nodes[instrument_id]

    def add_connection(self, from_id: str, to_id: str, weight: float) -> None:
        if from_id in self._nodes and to_id in self._nodes:
            self._nodes[from_id].connections[to_id] = weight

    def compute_correlation_edges(self, returns_data: dict[str, list[float]], threshold: float = 0.5) -> None:
        """Create graph edges from return correlations.

        Args:
            returns_data: Dict of {instrument_id: return_series}
            threshold: Minimum absolute correlation to create edge
        """
        ids = list(returns_data.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_i, id_j = ids[i], ids[j]
                ret_i = np.array(returns_data[id_i])
                ret_j = np.array(returns_data[id_j])
                min_len = min(len(ret_i), len(ret_j))
                if min_len < 10:
                    continue
                corr = float(np.corrcoef(ret_i[:min_len], ret_j[:min_len])[0, 1])
                if abs(corr) >= threshold:
                    self.add_connection(id_i, id_j, corr)
                    self.add_connection(id_j, id_i, corr)

    def detect_lead_lag(self, returns_data: dict[str, list[float]], max_lag: int = 10) -> dict[str, dict[str, int]]:
        """Detect lead-lag relationships between instruments.

        Args:
            returns_data: Dict of {instrument_id: return_series}
            max_lag: Maximum lag to test

        Returns:
            Dict of {instrument_id: {lagged_instrument: optimal_lag}}
        """
        results: dict[str, dict[str, int]] = {}
        ids = list(returns_data.keys())

        for leader in ids:
            results[leader] = {}
            leader_ret = np.array(returns_data[leader])
            for follower in ids:
                if leader == follower:
                    continue
                follower_ret = np.array(returns_data[follower])
                best_lag = 0
                best_corr = 0.0
                for lag in range(1, max_lag + 1):
                    if len(leader_ret) <= lag or len(follower_ret) <= lag:
                        continue
                    corr = float(np.corrcoef(leader_ret[:-lag], follower_ret[lag:])[0, 1])
                    if abs(corr) > abs(best_corr):
                        best_corr = corr
                        best_lag = lag
                if best_corr > 0.3:
                    results[leader][follower] = best_lag
        return results

    def get_connected(self, instrument_id: str, min_weight: float = 0.0) -> list[tuple[str, float]]:
        """Get all instruments connected to the given one."""
        node = self._nodes.get(instrument_id)
        if node is None:
            return []
        return [(t, w) for t, w in node.connections.items() if abs(w) >= min_weight]

    def get_market_subgraph(self, market_id: str) -> InstrumentGraph:
        """Extract subgraph for a specific market."""
        subgraph = InstrumentGraph()
        for nid, node in self._nodes.items():
            if node.market_id == market_id:
                subgraph._nodes[nid] = node
        return subgraph

    def get_sector_subgraph(self, sector: str) -> InstrumentGraph:
        """Extract subgraph for a specific sector."""
        subgraph = InstrumentGraph()
        for nid, node in self._nodes.items():
            if node.sector == sector:
                subgraph._nodes[nid] = node
        return subgraph

    @property
    def n_nodes(self) -> int:
        return len(self._nodes)

    @property
    def n_edges(self) -> int:
        return sum(len(n.connections) for n in self._nodes.values()) // 2

    def reset(self) -> None:
        self._nodes.clear()
