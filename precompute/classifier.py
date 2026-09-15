"""
Classifier — precompute/classifier.py
======================================
Groups symbols into A/B/C by priority score:

    priority = w1*liquidity + w2*value + w3*volume + w4*index_effect + w5*user_basket

Weights are tuned for TSE (Tehran Stock Exchange):
    - liquidity (turnover, free float): 0.30
    - value (trade value, market cap proxy): 0.25
    - volume (share volume): 0.20
    - index_effect (market cap × beta): 0.15
    - user_basket (watchlist / portfolio flag): 0.10 (bonus +10)

Thresholds (percentiles):
    A: top 30% (high liquidity / high index effect) — processed first, every 30s during market
    B: next 40% (mid)
    C: bottom 30% (low liquidity) — last

Decoupled: no import from ingestion/api/frontend — only contracts/schemas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.schemas import SymbolGroup

# Weights sum to 1.0
W_LIQUIDITY = 0.30
W_VALUE = 0.25
W_VOLUME = 0.20
W_INDEX_EFFECT = 0.15
W_USER_BASKET = 0.10

# Percentile cutoffs
A_CUTOFF = 0.70  # top 30% -> A
B_CUTOFF = 0.30  # bottom 30% -> C, middle -> B


@dataclass
class SymbolFeatures:
    symbol: str
    # Raw inputs (all optional — missing data handled via auditor)
    free_float_pct: float | None = None  # 0..100
    turnover_ratio: float | None = None  # 0..1
    trade_value: float | None = None  # Rial
    market_cap_proxy: float | None = None  # price * share count or proxy
    trade_volume: float | None = None  # shares
    beta: float | None = None  # index sensitivity
    is_in_user_basket: bool = False  # watchlist / portfolio

    # Normalized helpers 0..1
    def liquidity_score(self) -> float:
        # blend free float + turnover
        ff = (self.free_float_pct or 0) / 100.0
        tr = min(1.0, (self.turnover_ratio or 0) * 10)  # turnover 0.1 -> 1.0
        return max(0.0, min(1.0, 0.6 * ff + 0.4 * tr))

    def value_score(self) -> float:
        # log scale for trade value (1e9 .. 1e14 Rial)
        import math

        v = self.trade_value or 0
        if v <= 0:
            return 0.0
        # log10(1e9)=9, log10(1e14)=14 -> map 9..14 -> 0..1
        lv = math.log10(max(v, 1e9))
        return max(0.0, min(1.0, (lv - 9) / 5))

    def volume_score(self) -> float:
        import math

        vol = self.trade_volume or 0
        if vol <= 0:
            return 0.0
        lv = math.log10(max(vol, 1e3))
        # 1e3 .. 1e9 -> 0..1
        return max(0.0, min(1.0, (lv - 3) / 6))

    def index_effect_score(self) -> float:
        cap = self.market_cap_proxy or 0
        b = self.beta if self.beta is not None else 1.0
        if cap <= 0:
            return 0.0
        import math

        # cap proxy 1e11 .. 1e15 Rial
        lv = math.log10(max(cap, 1e11))
        base = max(0.0, min(1.0, (lv - 11) / 4))
        # beta amplifies (0.5..1.5 -> 0.7..1.3 multiplier)
        mult = max(0.7, min(1.3, 0.7 + 0.6 * b))
        return max(0.0, min(1.0, base * mult))


def compute_priority(features: SymbolFeatures) -> float:
    """Compute 0..1 priority; higher means should be in group A."""
    liq = features.liquidity_score()
    val = features.value_score()
    vol = features.volume_score()
    idx = features.index_effect_score()
    basket = 1.0 if features.is_in_user_basket else 0.0
    score = (
        W_LIQUIDITY * liq
        + W_VALUE * val
        + W_VOLUME * vol
        + W_INDEX_EFFECT * idx
        + W_USER_BASKET * basket
    )
    return max(0.0, min(1.0, score))


def classify_symbols(features_list: list[SymbolFeatures]) -> dict[str, SymbolGroup]:
    """
    Classify a batch of symbols into A/B/C by priority percentiles.

    Returns dict symbol -> SymbolGroup.
    Also handles edge: empty list -> {} and single symbol -> A.
    """
    if not features_list:
        return {}
    if len(features_list) == 1:
        return {features_list[0].symbol: SymbolGroup.A}

    scored = [(f.symbol, compute_priority(f)) for f in features_list]
    scored.sort(key=lambda x: x[1], reverse=True)

    n = len(scored)
    # cut indices
    a_end = max(1, int(n * 0.30))  # top 30%
    c_start = n - max(1, int(n * 0.30))  # bottom 30% starts here

    result: dict[str, SymbolGroup] = {}
    for idx, (sym, _) in enumerate(scored):
        if idx < a_end:
            result[sym] = SymbolGroup.A
        elif idx >= c_start:
            result[sym] = SymbolGroup.C
        else:
            result[sym] = SymbolGroup.B
    return result


# Convenience: classify from raw dicts (e.g. from BrsApi enriched snapshots)
def classify_from_dicts(
    rows: list[dict[str, Any]],
    user_basket: set[str] | None = None,
) -> dict[str, SymbolGroup]:
    basket = user_basket or set()
    feats: list[SymbolFeatures] = []
    for r in rows:
        sym = r.get("symbol") or r.get("name") or ""
        if not sym:
            continue
        feats.append(
            SymbolFeatures(
                symbol=sym,
                free_float_pct=r.get("free_float_pct") or r.get("freeFloatPct"),
                turnover_ratio=r.get("turnover_ratio") or r.get("turnover"),
                trade_value=r.get("trade_value") or r.get("value") or r.get("tradeValue"),
                market_cap_proxy=r.get("market_cap") or r.get("trade_value"),
                trade_volume=r.get("trade_volume") or r.get("volume"),
                beta=r.get("beta"),
                is_in_user_basket=sym in basket,
            )
        )
    return classify_symbols(feats)
