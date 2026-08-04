"""Feature Store — separates feature computation from scoring.

Each layer computes raw features independently. The store caches them
and provides them to the scoring engine. This enables:
- Independent testing of each feature
- Reuse in backtesting and ML pipelines
- Feature drift monitoring
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureVector:
    """Computed features for a single symbol at a point in time."""
    symbol: str = ""
    timestamp: float = 0.0

    # Layer 1: Price-Volume
    rvol_n: float = 0.0
    vtr_n: float = 0.0
    clv_n: float = 0.0
    rec_n: float = 0.0
    ipe_n: float = 0.0
    lf_n: float = 0.0
    pvs: float = 0.0

    # Layer 2: Absorption
    dps_n: float = 0.0
    lss_n: float = 0.0
    rmr_n: float = 0.0
    abs_score: float = 0.0

    # Layer 3: Ownership
    bp_n: float = 0.0
    nrmf_n: float = 0.0
    bc_n: float = 0.0
    se_n: float = 0.0
    fd: float = 0.0
    fls: float = 0.0

    # Layer 4: Compression
    rc: float = 0.0
    atrc: float = 0.0
    vvd: float = 0.0
    ess: float = 0.0

    # Layer 5: Relative Strength
    rsi3_n: float = 0.0
    rsi5_n: float = 0.0
    rsi10_n: float = 0.0
    rss_n: float = 0.0
    rds_n: float = 0.0
    rrs: float = 0.0

    # Layer 6: Breakout
    rp_n: float = 0.0
    btf_n: float = 0.0
    pt: float = 0.0
    bcp: float = 0.0
    brs: float = 0.0

    # Layer 7: Buyer Power
    rbp_n: float = 0.0
    z_rbp_n: float = 0.0
    z_vr_n: float = 0.0
    z_pc_n: float = 0.0
    z_nrmf_n: float = 0.0
    z_am_n: float = 0.0
    bps: float = 0.0

    # Layer 8: Microstructure
    vpin_n: float = 0.0
    abs_n: float = 0.0
    dpsv_n: float = 0.0
    dry_n: float = 0.0
    sa_n: float = 0.0
    mcs: float = 0.0

    # Layer 9: Breakout Quality
    eff_n: float = 0.0
    pt_n: float = 0.0
    accept_n: float = 0.0
    bqs: float = 0.0

    # Data quality metadata
    data_quality_score: float = 1.0
    analysis_mode: str = "full"
    history_days: int = 0

    def to_dict(self) -> dict[str, float]:
        """Convert to dict for scoring engine consumption."""
        result = {}
        for k, v in self.__dict__.items():
            if k.startswith("_") or k in ("symbol", "timestamp", "data_quality_score", "analysis_mode", "history_days"):
                continue
            if isinstance(v, float):
                result[k] = v
        return result

    def get_layer_scores(self) -> dict[str, float]:
        """Return just the layer-level scores."""
        return {
            "pvs": self.pvs,
            "abs": self.abs_score,
            "fls": self.fls,
            "ess": self.ess,
            "rrs": self.rrs,
            "brs": self.brs,
            "bps": self.bps,
            "mcs": self.mcs,
            "bqs": self.bqs,
        }


class FeatureStore:
    """Caches and provides computed features for symbols.

    Separates feature computation from scoring logic.
    Supports feature drift monitoring and independent layer testing.
    Memory-optimized with LRU eviction and __slots__.
    """

    def __init__(self, ttl: int = 30, max_size: int = 500) -> None:
        self._cache: dict[str, tuple[float, FeatureVector]] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, symbol: str) -> FeatureVector | None:
        """Get cached features for a symbol if still valid."""
        if symbol in self._cache:
            ts, fv = self._cache[symbol]
            if time.time() - ts < self._ttl:
                self._hits += 1
                # Move to end for LRU (re-insert)
                del self._cache[symbol]
                self._cache[symbol] = (ts, fv)
                return fv
            del self._cache[symbol]
        self._misses += 1
        return None

    def put(self, symbol: str, features: FeatureVector) -> None:
        """Cache features for a symbol."""
        # Remove if exists (to update position)
        if symbol in self._cache:
            del self._cache[symbol]
        self._cache[symbol] = (time.time(), features)
        # LRU eviction: remove oldest entries
        while len(self._cache) > self._max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]

    def invalidate(self, symbol: str) -> None:
        """Invalidate cache for a specific symbol (event-based)."""
        self._cache.pop(symbol, None)

    def invalidate_all(self) -> None:
        """Invalidate entire cache."""
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics for observability."""
        now = time.time()
        total = len(self._cache)
        valid = sum(1 for _, (ts, _) in self._cache.items() if now - ts < self._ttl)
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
            "hit_rate": f"{hit_rate:.1f}%",
            "hits": self._hits,
            "misses": self._misses,
        }

    def compute_all_features(
        self,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
        layer_results: dict[str, dict[str, float]],
        data_quality_score: float = 1.0,
        analysis_mode: str = "full",
        history_days: int = 0,
    ) -> FeatureVector:
        """Build a FeatureVector from pre-computed layer results."""
        fv = FeatureVector(
            symbol=quote.get("symbol", ""),
            timestamp=time.time(),
            data_quality_score=data_quality_score,
            analysis_mode=analysis_mode,
            history_days=history_days,
        )

        # Flatten all layer results into the feature vector
        for _layer_name, layer_data in layer_results.items():
            for key, val in layer_data.items():
                if hasattr(fv, key) and isinstance(val, (int, float)):
                    setattr(fv, key, round(float(val), 4))

        return fv
