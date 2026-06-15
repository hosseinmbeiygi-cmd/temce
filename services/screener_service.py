"""Screener Service — Multi-Stage Pipeline for Smart Money Stock Selection.

5-Phase Architecture (matching the mathematical spec):
  1. Liquidity Screening   — RVOL, value turnover, minimum value
  2. Power & Ownership     — Buyer power, net real money flow, concentration
  3. Price Structure       — Compression, relative strength, close location
  4. Order Flow            — Absorption, microstructure, order imbalance
  5. Trigger Score         — Breakout readiness, resistance proximity

Each phase produces a sub-score in [0, 1].  The final Smart Money Composite
Score (SMC) is the primary ranking metric.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any

from services.smart_money.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ScreenedSymbol:
    """Result of running the full pipeline on one instrument."""

    symbol: str
    name: str
    market: str
    industry: str
    last_price: float
    change_pct: float
    volume: int
    value: float

    # Phase scores (0 – 1)
    liquidity_score: float = 0.0
    power_score: float = 0.0
    structure_score: float = 0.0
    orderflow_score: float = 0.0
    trigger_score: float = 0.0

    # Composite
    smc_score: float = 0.0
    phase: str = "neutral"

    # Extra info
    rank: int = 0
    reason: str = ""
    details: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Screener pipeline
# ---------------------------------------------------------------------------


class ScreenerPipeline:
    """5-phase pipeline that scores a single instrument via the Smart Money engine."""

    def __init__(self) -> None:
        self._engine = ScoringEngine()

    def run(
        self,
        symbol: str,
        name: str,
        market: str,
        industry: str,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ScreenedSymbol:
        # 1 – Score via Smart Money engine
        try:
            result = self._engine.analyze(quote, history)
        except Exception as exc:
            logger.warning("Screener engine failed for %s: %s", symbol, exc)
            return ScreenedSymbol(
                symbol=symbol,
                name=name,
                market=market,
                industry=industry,
                last_price=quote.get("price_close", 0.0),
                change_pct=0.0,
                volume=int(quote.get("volume", 0)),
                value=float(quote.get("value", 0)),
                reason=f"Engine error: {exc}",
            )

        scores = result.get("scores", {})
        penalties = result.get("penalties", {})
        features = result.get("features", {})
        smc = result.get("smart_money_score", 0.0)
        phase = result.get("phase", "neutral")

        # ---- Phase 1: Liquidity Score ----
        rvol_n = features.get("rvol_n", 0.0)
        vtr_n = features.get("vtr_n", 0.0)
        pvs = scores.get("accumulation", 0.0)
        liquidity_score = 0.35 * rvol_n + 0.35 * vtr_n + 0.30 * pvs
        liquidity_score = min(1.0, max(0.0, liquidity_score))

        # ---- Phase 2: Power & Ownership Score ----
        bp_n = features.get("bp_n", 0.0)
        nrmf_n = features.get("nrmf_n", 0.0)
        bc_n = features.get("bc_n", 0.0)
        power_score = 0.40 * bp_n + 0.30 * nrmf_n + 0.15 * bc_n + 0.15 * scores.get("buyer_power", 0.0)
        power_score = min(1.0, max(0.0, power_score))

        # ---- Phase 3: Price Structure Score ----
        rec_n = features.get("rec_n", 0.0)
        clv_n = features.get("clv_n", 0.0)
        rrs = scores.get("breakout_readiness", 0.0)
        ess = scores.get("float_lock", 0.0)
        structure_score = 0.25 * clv_n + 0.25 * rec_n + 0.25 * rrs + 0.25 * ess
        structure_score = min(1.0, max(0.0, structure_score))

        # ---- Phase 4: Order Flow Score ----
        lss_n = features.get("lss_n", 0.0)
        rmr_n = features.get("rmr_n", 0.0)
        abs_score = scores.get("absorption", 0.0)
        dry_n = features.get("dry_n", 0.0)
        orderflow_score = (
            0.30 * abs_score + 0.20 * lss_n + 0.20 * rmr_n + 0.15 * dry_n + 0.15 * scores.get("microstructure", 0.0)
        )
        orderflow_score = min(1.0, max(0.0, orderflow_score))

        # ---- Phase 5: Trigger Score ----
        br = scores.get("breakout_readiness", 0.0)
        trigger_score = 0.60 * br + 0.20 * rrs + 0.10 * abs_score + 0.10 * ess
        trigger_score = min(1.0, max(0.0, trigger_score))

        # ---- Composite ----
        # Penalty adjustments
        dist_risk = penalties.get("distribution_risk", 0.0)
        fake_risk = penalties.get("fake_breakout_risk", 0.0)
        dead_comp = penalties.get("dead_compression", 0.0)
        penalty_factor = 1.0 - 0.15 * dist_risk - 0.10 * fake_risk - 0.08 * dead_comp
        smc_adjusted = max(0.0, smc * max(0.0, penalty_factor))

        # Build reason string
        reasons = []
        if liquidity_score > 0.6:
            reasons.append("نقدشوندگی بالا")
        if power_score > 0.6:
            reasons.append("ورود پول قوی")
        if structure_score > 0.6:
            reasons.append("ساختار قیمتی مستحکم")
        if orderflow_score > 0.6:
            reasons.append("جذب عرضه فعال")
        if trigger_score > 0.6:
            reasons.append("آماده شکست")
        reason = " · ".join(reasons) if reasons else ("در حال نظارت" if smc_adjusted > 0.4 else "ضعیف")

        details = {
            "liquidity_score": round(liquidity_score, 4),
            "power_score": round(power_score, 4),
            "structure_score": round(structure_score, 4),
            "orderflow_score": round(orderflow_score, 4),
            "trigger_score": round(trigger_score, 4),
            "smc_score": round(smc_adjusted, 4),
            "rvol_n": round(rvol_n, 4),
            "bp_n": round(bp_n, 4),
            "nrmf_n": round(nrmf_n, 4),
            "clv_n": round(clv_n, 4),
            "rec_n": round(rec_n, 4),
            "abs_score": round(abs_score, 4),
        }
        details.update({k: round(v, 4) for k, v in features.items() if isinstance(v, float) and k not in details})

        return ScreenedSymbol(
            symbol=symbol,
            name=name,
            market=market,
            industry=industry,
            last_price=quote.get("price_close", 0.0),
            change_pct=quote.get("price_change_pct", 0.0),
            volume=int(quote.get("volume", 0)),
            value=float(quote.get("value", 0)),
            liquidity_score=round(liquidity_score, 4),
            power_score=round(power_score, 4),
            structure_score=round(structure_score, 4),
            orderflow_score=round(orderflow_score, 4),
            trigger_score=round(trigger_score, 4),
            smc_score=round(smc_adjusted, 4),
            phase=phase,
            reason=reason,
            details=details,
        )


# ---------------------------------------------------------------------------
# Quote / history helpers (mock — replace with real data source)
# ---------------------------------------------------------------------------


def _make_rng(w: dict[str, Any]) -> random.Random:
    """Create a deterministic RNG from a market-watch row's symbol."""
    seed = abs(hash(w.get("symbol", ""))) % (2**31)
    return random.Random(seed)


def build_quote_from_watch(w: dict[str, Any]) -> dict[str, Any]:
    """Convert a market-watch row into a quote dict the engine expects."""
    rng = _make_rng(w)
    last = w.get("last_price", 0.0)
    close = w.get("close", last)
    change_pct = w.get("change", 0.0)
    val = float(w.get("value", 0))
    return {
        "price_open": close * (1 - change_pct / 200.0),
        "price_close": close,
        "price_high": w.get("high", close * 1.02),
        "price_low": w.get("low", close * 0.98),
        "price_last": last,
        "price_change": w.get("change_value", 0),
        "price_change_pct": change_pct,
        "volume": w.get("volume", 0),
        "value": val,
        "trade_count": max(1, int(w.get("volume", 0) / 5000)),
        "avg_buy": rng.uniform(20_000_000, 60_000_000),
        "avg_sell": rng.uniform(10_000_000, 35_000_000),
        "real_buy_value": val * rng.uniform(0.4, 0.7),
        "real_sell_value": val * rng.uniform(0.3, 0.6),
        "real_buy_count": int(rng.uniform(300, 900)),
        "real_sell_count": int(rng.uniform(200, 700)),
        "date": "1403/08/16",
        "time": "12:30:00",
    }


def build_history_from_watch(w: dict[str, Any], days: int = 30) -> list[dict[str, Any]]:
    """Generate deterministic synthetic history from a market-watch row.

    Uses the symbol as random seed so the same symbol always gets the same
    synthetic history across API calls.
    """
    rng = _make_rng(w)

    base_price = w.get("close", w.get("last_price", 1000))
    base_vol = w.get("volume", 1_000_000)
    history: list[dict[str, Any]] = []
    for i in range(days):
        factor = 1.0 + rng.uniform(-0.03, 0.03)
        p = base_price * factor * (1.0 + 0.002 * math.sin(i / 5.0))
        v = int(base_vol * rng.uniform(0.3, 1.8))
        o = p * rng.uniform(0.98, 1.02)
        c = p * rng.uniform(0.98, 1.02)
        h = max(o, c) * rng.uniform(1.0, 1.025)
        low = min(o, c) * rng.uniform(0.975, 1.0)
        history.append(
            {
                "price_open": round(o, 1),
                "price_close": round(c, 1),
                "price_high": round(h, 1),
                "price_low": round(low, 1),
                "price_last": round(c * rng.uniform(0.99, 1.01), 1),
                "volume": v,
                "value": v * ((o + c) / 2),
                "avg_buy": rng.uniform(15_000_000, 50_000_000),
                "avg_sell": rng.uniform(10_000_000, 30_000_000),
                "real_buy_value": float(v * (o + c) / 2) * rng.uniform(0.4, 0.65),
                "real_sell_value": float(v * (o + c) / 2) * rng.uniform(0.35, 0.55),
                "real_buy_count": int(rng.uniform(300, 800)),
                "real_sell_count": int(rng.uniform(250, 650)),
                "date": f"1403/0{rng.randint(1, 8):02d}/{rng.randint(1, 30):02d}",
            }
        )
    return history


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


class ScreenerService:
    """Main screener service — run the pipeline over a list of instruments."""

    def __init__(self) -> None:
        self._pipeline = ScreenerPipeline()

    def screen(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        sort_by: str = "smc_score",
        sort_order: str = "desc",
        limit: int = 50,
        min_score: float = 0.0,
        market: str | None = None,
    ) -> list[ScreenedSymbol]:
        """Run the full 5-phase pipeline over a list of instruments."""
        # Build a lookup from watch data
        watch_map: dict[str, dict[str, Any]] = {}
        for w in market_watch:
            watch_map[w.get("symbol", "")] = w

        results: list[ScreenedSymbol] = []
        for instr in instruments:
            sym = instr.get("symbol", "")
            if market and instr.get("market") != market:
                continue
            w = watch_map.get(sym)
            if not w:
                continue

            quote = build_quote_from_watch(w)
            history = build_history_from_watch(w)

            item = self._pipeline.run(
                symbol=sym,
                name=instr.get("name", sym),
                market=instr.get("market", ""),
                industry=instr.get("industry", ""),
                quote=quote,
                history=history,
            )
            if item.smc_score < min_score:
                continue
            results.append(item)

        # Sort
        reverse = sort_order.lower() != "asc"
        results.sort(key=lambda r: getattr(r, sort_by, 0.0), reverse=reverse)

        # Assign ranks
        for i, r in enumerate(results, 1):
            r.rank = i

        return results[:limit]

    def screen_by_symbol(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        symbol: str,
    ) -> ScreenedSymbol | None:
        """Run the pipeline for a single symbol."""
        instr = next((i for i in instruments if i.get("symbol") == symbol), None)
        if not instr:
            return None
        w = next((mw for mw in market_watch if mw.get("symbol") == symbol), None)
        if not w:
            return None

        quote = build_quote_from_watch(w)
        history = build_history_from_watch(w)

        return self._pipeline.run(
            symbol=symbol,
            name=instr.get("name", symbol),
            market=instr.get("market", ""),
            industry=instr.get("industry", ""),
            quote=quote,
            history=history,
        )
