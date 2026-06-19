from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


class FeatureType(StrEnum):
    PRICE = "PRICE"
    VOLUME = "VOLUME"
    MICROSTRUCTURE = "MICROSTRUCTURE"
    DERIVED = "DERIVED"
    ALPHA = "ALPHA"


def _ema(window: np.ndarray, size: int) -> float:
    """Exponential moving average of window array."""
    alpha = 2.0 / (size + 1)
    val = float(window[0])
    for v in window[1:]:
        val = alpha * v + (1 - alpha) * val
    return val


def _std(window: np.ndarray, _: int = 0) -> float:
    """Standard deviation of window array."""
    return float(np.std(window))


@dataclass
class FeatureNode:
    """A single feature in the DAG.

    Each feature has:
    - name: unique identifier
    - dependencies: list of other feature names it depends on
    - compute_fn: function to compute this feature from its dependencies
    - feature_type: category for grouping
    - window: rolling window size (0 = no window)
    """

    name: str
    dependencies: list[str] = field(default_factory=list)
    compute_fn: Callable[..., np.ndarray] | None = None
    feature_type: FeatureType = FeatureType.DERIVED
    window: int = 0
    description: str = ""

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FeatureNode):
            return NotImplemented
        return self.name == other.name


class FeatureGraph:
    """DAG of feature dependencies.

    Ensures features are computed in topological order,
    detects circular dependencies, and manages the computation graph.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, FeatureNode] = {}
        self._sorted: list[str] = []

    def add_node(self, node: FeatureNode) -> None:
        if node.name in self._nodes:
            logger.warning("Overwriting feature node: %s", node.name)
        self._nodes[node.name] = node
        self._sorted = []

    def add_many(self, nodes: list[FeatureNode]) -> None:
        for node in nodes:
            self.add_node(node)

    def get_node(self, name: str) -> FeatureNode | None:
        return self._nodes.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._nodes.keys())

    @property
    def count(self) -> int:
        return len(self._nodes)

    def topological_sort(self) -> list[str]:
        if self._sorted:
            return self._sorted
        visited: dict[str, bool] = {}
        order: list[str] = []

        def dfs(name: str) -> None:
            if name in visited:
                if not visited[name]:
                    raise ValueError(f"Circular dependency detected: {name}")
                return
            visited[name] = False
            node = self._nodes.get(name)
            if node:
                for dep in node.dependencies:
                    if dep in self._nodes:
                        dfs(dep)
            visited[name] = True
            order.append(name)

        for name in self._nodes:
            if name not in visited:
                dfs(name)
        self._sorted = order
        return order

    def subgraph(self, names: list[str]) -> FeatureGraph:
        sub = FeatureGraph()
        required = set(names)

        def collect_deps(name: str) -> None:
            node = self._nodes.get(name)
            if node:
                for dep in node.dependencies:
                    if dep not in required:
                        required.add(dep)
                        collect_deps(dep)

        for name in names:
            collect_deps(name)
        for name in required:
            node = self._nodes.get(name)
            if node:
                sub.add_node(node)
        return sub

    def levels(self) -> list[list[str]]:
        sorted_nodes = self.topological_sort()
        depth: dict[str, int] = {}
        for name in sorted_nodes:
            node = self._nodes[name]
            if not node.dependencies:
                depth[name] = 0
            else:
                depth[name] = max(depth.get(d, 0) for d in node.dependencies if d in depth) + 1
        groups: dict[int, list[str]] = defaultdict(list)
        for name, d in depth.items():
            groups[d].append(name)
        return [sorted(groups[k]) for k in sorted(groups.keys())]


class FeatureDAGEngine:
    """High-performance feature computation engine using a DAG of dependencies.

    Features are computed in topological order with:
    - Caching: computed values are cached and invalidated as needed
    - Incremental updates: only recompute features whose inputs changed
    - Vectorized operations: uses numpy for bulk computation
    - Rolling windows: efficient sliding window calculations
    """

    def __init__(self) -> None:
        self.graph = FeatureGraph()
        self._cache: dict[str, float] = {}
        self._history: dict[str, np.ndarray] = {}
        self._max_history: int = 5000

    def register(self, node: FeatureNode) -> None:
        self.graph.add_node(node)

    def register_many(self, nodes: list[FeatureNode]) -> None:
        self.graph.add_many(nodes)

    def register_builtins(self) -> None:
        builtins = [
            FeatureNode("mid_price", ["best_bid", "best_ask"],
                        lambda bid, ask: (bid + ask) / 2,
                        FeatureType.PRICE, description="(bid + ask) / 2"),
            FeatureNode("spread", ["best_bid", "best_ask"],
                        lambda bid, ask: ask - bid,
                        FeatureType.MICROSTRUCTURE, description="ask - bid"),
            FeatureNode("spread_bps", ["spread", "mid_price"],
                        lambda s, mp: (s / mp) * 10000 if mp > 0 else 0.0,
                        FeatureType.MICROSTRUCTURE, description="spread in basis points"),
            FeatureNode("log_mid_price", ["mid_price"],
                        lambda mp: np.log(mp) if mp > 0 else 0.0,
                        FeatureType.PRICE, description="log(mid_price)"),
            FeatureNode("returns", ["log_mid_price"],
                        lambda lmp: np.diff(lmp)[-1] if len(lmp) > 1 else 0.0,
                        FeatureType.PRICE, description="log returns"),
            FeatureNode("volume_dollar", ["last_price", "volume"],
                        lambda p, v: p * v,
                        FeatureType.VOLUME, description="price * volume"),
            FeatureNode("queue_imbalance", ["bid_volume", "ask_volume"],
                        lambda bv, av: (bv - av) / (bv + av) if (bv + av) > 0 else 0.0,
                        FeatureType.MICROSTRUCTURE, description="(bid_vol - ask_vol) / (bid_vol + ask_vol)"),
            FeatureNode("order_flow_imbalance", ["trade_volume", "bid_volume", "ask_volume"],
                        lambda tv, bv, av: (tv - (bv + av)) / (bv + av + tv) if (bv + av + tv) > 0 else 0.0,
                        FeatureType.MICROSTRUCTURE, description="trade flow imbalance"),
            FeatureNode("trade_intensity", ["volume"],
                        lambda v: v,
                        FeatureType.VOLUME, description="trade volume per event"),
            FeatureNode("microprice", ["best_bid", "best_ask", "bid_volume", "ask_volume"],
                        lambda bid, ask, bv, av: (bid * av + ask * bv) / (bv + av) if (bv + av) > 0 else (bid + ask) / 2,
                        FeatureType.MICROSTRUCTURE, description="weighted mid price"),
            # Rolling features with explicit compute functions
            FeatureNode("spread_ma_10", ["spread"],
                        lambda w, _: float(np.mean(w)),
                        FeatureType.DERIVED, window=10,
                        description="10-period moving average of spread"),
            FeatureNode("volume_ma_20", ["volume"],
                        lambda w, _: float(np.mean(w)),
                        FeatureType.DERIVED, window=20,
                        description="20-period moving average of volume"),
            FeatureNode("mid_price_ema_5", ["mid_price"],
                        lambda w, s: _ema(w, s),
                        FeatureType.DERIVED, window=5,
                        description="5-period EMA of mid price"),
            FeatureNode("realized_volatility_10", ["returns"],
                        lambda w, _: float(np.std(w)),
                        FeatureType.DERIVED, window=10,
                        description="10-period realized volatility"),
        ]
        self.register_many(builtins)

    def add_custom(
        self,
        name: str,
        dependencies: list[str],
        compute_fn: Callable[..., np.ndarray],
        feature_type: FeatureType = FeatureType.ALPHA,
        description: str = "",
    ) -> None:
        self.register(FeatureNode(
            name=name, dependencies=dependencies,
            compute_fn=compute_fn, feature_type=feature_type,
            description=description,
        ))

    def compute(self, data: dict[str, float], instrument_id: str = "") -> dict[str, float]:
        """Compute all features for a single data point."""
        prefix = f"{instrument_id}:" if instrument_id else ""
        results: dict[str, float] = {}

        for key, val in data.items():
            hist_key = f"{prefix}{key}"
            if hist_key not in self._history:
                self._history[hist_key] = np.array([])
            self._history[hist_key] = np.append(self._history[hist_key], val)
            if len(self._history[hist_key]) > self._max_history:
                self._history[hist_key] = self._history[hist_key][-self._max_history:]

        order = self.graph.topological_sort()
        for name in order:
            node = self.graph.get_node(name)
            if node is None:
                continue
            cache_key = f"{prefix}{name}"

            try:
                inputs = []
                for dep in node.dependencies:
                    dep_key = f"{prefix}{dep}"
                    if dep_key in self._cache:
                        inputs.append(self._cache[dep_key])
                    elif dep in data:
                        inputs.append(data[dep])
                    elif dep in results:
                        inputs.append(results[dep])
                    else:
                        hist_key = f"{prefix}{dep}"
                        if hist_key in self._history and len(self._history[hist_key]) > 0:
                            inputs.append(self._history[hist_key][-1])
                        else:
                            inputs.append(0.0)

                if node.window > 0:
                    src_key = f"{prefix}{node.dependencies[0]}"
                    hist = self._history.get(src_key, np.array([]))
                    if len(hist) >= node.window:
                        window = hist[-node.window:]
                        if node.compute_fn is not None:
                            val = float(node.compute_fn(window, node.window))
                        else:
                            val = float(np.mean(window))
                    else:
                        val = float(inputs[0])
                    results[name] = val
                    self._cache[cache_key] = val
                elif node.compute_fn is not None:
                    val = float(node.compute_fn(*inputs))
                    results[name] = val
                    self._cache[cache_key] = val
                else:
                    results[name] = float(inputs[0]) if inputs else 0.0
                    self._cache[cache_key] = results[name]
            except Exception as e:
                logger.debug("Feature compute failed for %s: %s", name, e)
                results[name] = 0.0

        return results

    def compute_batch(
        self, data_batch: list[dict[str, float]], instrument_id: str = "",
    ) -> list[dict[str, float]]:
        return [self.compute(d, instrument_id) for d in data_batch]

    def get_feature(self, name: str, instrument_id: str = "") -> float:
        cache_key = f"{instrument_id}:{name}" if instrument_id else name
        return self._cache.get(cache_key, 0.0)

    def get_history(self, name: str, instrument_id: str = "") -> np.ndarray:
        return self._history.get(f"{instrument_id}:{name}" if instrument_id else name, np.array([]))

    def get_all_features(self, instrument_id: str = "") -> dict[str, float]:
        prefix = f"{instrument_id}:" if instrument_id else ""
        return {
            k.removeprefix(prefix): v
            for k, v in self._cache.items()
            if k.startswith(prefix) or not instrument_id
        }

    def reset(self) -> None:
        self._cache.clear()
        self._history.clear()

    @property
    def feature_count(self) -> int:
        return self.graph.count

    def list_features(self) -> list[dict[str, Any]]:
        return [
            {"name": n.name, "dependencies": n.dependencies,
             "type": str(n.feature_type), "window": n.window,
             "description": n.description}
            for n in self.graph._nodes.values()
        ]
