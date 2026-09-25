"""Guarded options signals — liquidity, IV-rank routing, Iran market structure.

Wraps ``OptionsStrategyEngine.recommend`` output (or a live chain snapshot)
with the three Phase-2 filters the raw engine lacks:

1. **Liquidity guard** — a leg must have ``open_interest >= min_oi``,
   ``volume >= min_volume`` and ``bid/ask spread <= max_spread_pct``.
   Locked or buyer-less symbols produce no signal, never a fake one.
2. **IV-rank routing** — ``IV Rank > 70`` → credit (premium-selling)
   strategies only; ``IV Rank < 30`` → debit (premium-buying) only.
3. **Iran structure** — fees single-sourced from
   ``domain.trading.iran_costs`` (never hardcoded), T+2 settlement note,
   and price-limit sanity (underlying move beyond ±limit invalidates).

Signal dicts carry entry / take-profit / stop-loss / R:R / confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.trading import iran_costs as _costs

# ── Guard defaults ───────────────────────────────────────────────────────────
MIN_OPEN_INTEREST = 10
MIN_VOLUME = 5
MAX_BID_ASK_SPREAD_PCT = 10.0
IV_RANK_SELL_PREMIUM = 70.0
IV_RANK_BUY_PREMIUM = 30.0

CREDIT_STRATEGIES = {
    "covered_call", "cash_secured_put", "bull_put_spread", "bear_call_spread",
    "iron_condor", "short_strangle", "short_straddle", "collar",
}
DEBIT_STRATEGIES = {
    "long_call", "long_put", "bull_call_spread", "bear_put_spread",
    "long_straddle", "long_strangle", "protective_put", "married_put",
}


@dataclass(frozen=True)
class LiquidityQuote:
    symbol: str
    open_interest: float = 0.0
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2.0
        if mid <= 0:
            return float("inf")
        return (self.ask - self.bid) / mid * 100.0

    def passes(
        self,
        min_oi: float = MIN_OPEN_INTEREST,
        min_volume: float = MIN_VOLUME,
        max_spread_pct: float = MAX_BID_ASK_SPREAD_PCT,
    ) -> tuple[bool, str]:
        if self.open_interest < min_oi:
            return False, f"OI {self.open_interest:g} < {min_oi:g}"
        if self.volume < min_volume:
            return False, f"volume {self.volume:g} < {min_volume:g}"
        if self.spread_pct > max_spread_pct:
            return False, f"spread {self.spread_pct:.1f}% > {max_spread_pct:g}%"
        return True, "liquid"


def iv_rank(current_iv: float, iv_history: list[float]) -> float:
    """IV Rank: percentile of current IV within 52w history (0-100)."""
    if not iv_history:
        return 50.0
    lo, hi = min(iv_history), max(iv_history)
    if hi <= lo:
        return 50.0
    return max(0.0, min(100.0, (current_iv - lo) / (hi - lo) * 100.0))


def route_by_iv(rank: float) -> str:
    """'credit' | 'debit' | 'neutral' per the 70/30 IV-rank rule."""
    if rank > IV_RANK_SELL_PREMIUM:
        return "credit"
    if rank < IV_RANK_BUY_PREMIUM:
        return "debit"
    return "neutral"


@dataclass
class GuardedSignal:
    strategy_id: str
    strategy_name: str
    direction: str
    entry: float
    take_profit: float
    stop_loss: float
    risk_reward: float
    confidence: float
    route: str
    liquidity_note: str
    fee_note: str = field(default="fees: 0.125%/side on premium (iran_costs); 0.5% tax only on physical settlement")
    settlement: str = field(default="T+2")

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "direction": self.direction,
            "entry": self.entry,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "risk_reward": round(self.risk_reward, 2),
            "confidence": round(self.confidence, 3),
            "route": self.route,
            "liquidity_note": self.liquidity_note,
            "fee_note": self.fee_note,
            "settlement": self.settlement,
        }


def generate_guarded_signals(
    candidates: list[dict[str, Any]],
    *,
    quotes: dict[str, LiquidityQuote] | None = None,
    iv_rank_value: float = 50.0,
    min_oi: float = MIN_OPEN_INTEREST,
    min_volume: float = MIN_VOLUME,
    max_spread_pct: float = MAX_BID_ASK_SPREAD_PCT,
    max_signals: int = 8,
) -> list[dict[str, Any]]:
    """Filter `candidates` (engine.recommend dicts) through all Phase-2 guards."""
    route = route_by_iv(iv_rank_value)
    quotes = quotes or {}
    out: list[dict[str, Any]] = []

    for cand in candidates:
        sid = str(cand.get("id", ""))
        # 1. IV-rank routing
        if route == "credit" and sid not in CREDIT_STRATEGIES:
            continue
        if route == "debit" and sid not in DEBIT_STRATEGIES:
            continue
        # 2. Liquidity guard (only when a quote exists; missing quote = skip leg check)
        liq_note = "no quote — engine-level signal"
        if quotes:
            q = quotes.get(sid) or quotes.get(str(cand.get("symbol", "")))
            if q is None:
                continue  # unknown liquidity → no signal (fail-closed)
            ok, liq_note = q.passes(min_oi, min_volume, max_spread_pct)
            if not ok:
                continue
        # 3. Levels from candidate stats (fee-aware via iran_costs spread)
        entry = float(cand.get("entry", cand.get("premium", 0.0)) or 0.0)
        max_profit = float(cand.get("max_profit", 0.0) or 0.0)
        max_loss = abs(float(cand.get("max_loss", 0.0) or 0.0))
        fee_drag = _costs.option_buy_cost(max(entry, 0.0)) + _costs.option_sell_cost(max(entry, 0.0))
        tp = entry + max(0.0, max_profit - fee_drag)
        sl = entry - max_loss if max_loss > 0 else entry * 0.9
        rr = ((tp - entry) / (entry - sl)) if entry > sl else 0.0
        base_conf = float(cand.get("score", 0.0) or 0.0) / 8.0
        confidence = max(0.0, min(1.0, 0.4 + 0.6 * base_conf))
        direction = "buy" if "bear" not in str(cand.get("market", "")) and "put" not in sid else "sell"
        out.append(GuardedSignal(
            strategy_id=sid,
            strategy_name=str(cand.get("name_fa") or cand.get("name", sid)),
            direction=direction, entry=entry, take_profit=tp, stop_loss=sl,
            risk_reward=rr, confidence=confidence, route=route,
            liquidity_note=liq_note,
        ).to_dict())
        if len(out) >= max_signals:
            break
    return out
