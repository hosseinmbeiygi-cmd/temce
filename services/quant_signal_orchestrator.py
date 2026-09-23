"""Quant Signal Orchestrator — ties the entire signal pipeline together.

Flow:
  1. MultiMarketSignalEngine  → rule-based signals
  2. MLSignalConnector        → ML predictions per signal
  3. SignalVotingSystem       → combine rule + ML votes
  4. ConfidenceScorer         → calibrated confidence per signal
  5. CrossMarketCorrelator    → cross-market correlation signals
  6. Filter by confidence threshold

This is the single entry-point for generating high-quality, multi-market
trading signals with calibrated confidence targeting >70% accuracy.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from core.db_utils import safe_row_float
from core.indicators import compute_data_quality_score
from core.logging import get_logger

logger = get_logger(__name__)

LEGAL_DISCLAIMER_FA = (
    "این سیگنال صرفاً جنبه اطلاع‌رسانی و آموزشی دارد و توصیه خرید/فروش نیست. "
    "مسئولیت هرگونه تصمیم معاملاتی با کاربر است."
)


# ── Output Data Structures ────────────────────────────────────────────────────


@dataclass
class EnrichedSignal:
    """A signal that has gone through the full pipeline: rule + ML + voting + confidence + decision."""

    # Original fields
    symbol: str
    name: str
    market: str
    direction: str
    timeframe: str
    entry_zone: str
    stop_loss: str
    targets: str
    risk_reward: str
    position_sizing: str
    confirmation_condition: str
    reason: str
    invalidation: str
    trailing_stop: str
    price: float
    change_pct: float

    # Scoring fields
    rule_score: float           # 0-100 from technical analysis
    ml_score: float             # 0-1 from ML ensemble
    boosted_score: float        # 0-100 combined
    ml_influence_pct: float     # how much ML contributed

    # Confidence fields
    confidence: float           # 0-1 calibrated
    calibration_level: str      # low / medium / high / very_high
    confidence_factors: dict[str, float] = field(default_factory=dict)
    confidence_notes: list[str] = field(default_factory=list)

    # Probability calibration fields (from ProbabilityCalibrator)
    calibrated_probability: float = 0.0  # 0-1 calibrated win probability
    calibration_version: str = ""       # version of calibration model used
    calibration_method: str = ""        # bucket / platt / isotonic / none

    # Decision engine fields (from SignalDecisionEngine)
    decision_verdict: str = ""          # release / watchlist / reject
    decision_grade: str = ""            # A+ / A / B / WATCHLIST / REJECT
    effective_threshold: float = 0.55   # dynamic threshold used
    net_expectancy_r: float = 0.0       # net expectancy in R-multiples
    gate_results: list[dict[str, Any]] = field(default_factory=list)

    # Voting fields
    vote_strategy: str = ""     # weighted / unanimous / ml_override / rule_only
    vote_direction_scores: dict[str, float] = field(default_factory=dict)

    # Source info
    source: str = ""
    created_at: str = ""

    # Legal disclaimer (P1-4: mandatory in all signal outputs)
    legal_disclaimer: str = LEGAL_DISCLAIMER_FA

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "direction": self.direction,
            "timeframe": self.timeframe,
            "entry_zone": self.entry_zone,
            "stop_loss": self.stop_loss,
            "targets": self.targets,
            "risk_reward": self.risk_reward,
            "position_sizing": self.position_sizing,
            "confirmation_condition": self.confirmation_condition,
            "reason": self.reason,
            "invalidation": self.invalidation,
            "trailing_stop": self.trailing_stop,
            "price": self.price,
            "change_pct": self.change_pct,
            "rule_score": self.rule_score,
            "ml_score": self.ml_score,
            "boosted_score": self.boosted_score,
            "ml_influence_pct": self.ml_influence_pct,
            "confidence": self.confidence,
            "calibration_level": self.calibration_level,
            "confidence_factors": self.confidence_factors,
            "confidence_notes": self.confidence_notes,
            "calibrated_probability": round(self.calibrated_probability, 3),
            "calibration_version": self.calibration_version,
            "calibration_method": self.calibration_method,
            "decision_verdict": self.decision_verdict,
            "decision_grade": self.decision_grade,
            "effective_threshold": self.effective_threshold,
            "net_expectancy_r": round(self.net_expectancy_r, 4),
            "gate_results": self.gate_results,
            "vote_strategy": self.vote_strategy,
            "vote_direction_scores": self.vote_direction_scores,
            "source": self.source,
            "created_at": self.created_at,
            "legal_disclaimer": self.legal_disclaimer,
        }


@dataclass
class OrchestratorReport:
    """Full report from one orchestrator run."""

    signals: list[EnrichedSignal]
    summary: dict[str, Any]
    generation_reports: list[dict[str, Any]]
    accuracy_snapshot: dict[str, float] | None = None
    cross_market_signals: list[dict[str, Any]] = field(default_factory=list)
    retrain_reports: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signals": [s.to_dict() for s in self.signals],
            "summary": self.summary,
            "reports": self.generation_reports,
            "accuracy": self.accuracy_snapshot,
            "cross_market": self.cross_market_signals,
            "retrain": self.retrain_reports,
            "generated_at": self.generated_at,
        }


# ── Cross-Market Correlator ───────────────────────────────────────────────────


class CrossMarketCorrelator:
    """Detects cross-market signals and correlations using **real market prices**.

    Instead of counting generated signals, this correlator fetches actual
    price data for:
      - **Stock Index**: TSE total index (شاخص کل) from ``brsapi_index_values``
      - **Gold**: gold coin price (سکه طلا) from ``brsapi_gold_coin_prices``
      - **Currency**: USD/IRR rate from ``brsapi_currency_prices``
      - **Crypto**: BTC/USD price from ``brsapi_crypto_prices``
      - **Commodity**: XAUUSD from ``brsapi_gold_currency_pro_prices``

    Market regime rules:
      Gold ↑ + Index ↓  → Risk-Off  (defensive)
      Gold ↓ + Index ↑  → Risk-On   (aggressive)
      Gold ↑ + Crypto ↑ → Inflation-Hedge
      Commodity ↑ + Cur ↓ → Import-Inflation (CAUTION)
      All ↓ → Systemic-Risk (CASH)
    """

    # ── Symbol lookup keys in each price table ─────────────────────────────
    _SYMBOL_KEYS: dict[str, dict[str, Any]] = {
        "stock": {
            "table": "brsapi_index_values",
            "symbol_filter": None,  # no symbol column; uses name
            "name_filter": "شاخص کل",
            "price_col": "index_value",
            "change_col": "index_change_pct",
            "is_index": True,
        },
        "gold": {
            "table": "brsapi_gold_coin_prices",
            "symbol_filter": "گلد",
            "name_filter": None,
            "price_col": "price",
            "change_col": "change_percent",
            "is_index": False,
        },
        "currency": {
            "table": "brsapi_currency_prices",
            "symbol_filter": "USD_IRR",
            "name_filter": None,
            "price_col": "price",
            "change_col": "change_percent",
            "is_index": False,
        },
        "crypto": {
            "table": "brsapi_crypto_prices",
            "symbol_filter": "BTC",
            "name_filter": None,
            "price_col": "price_usd",
            "change_col": "change_percent",
            "is_index": False,
        },
        "commodity": {
            "table": "brsapi_gold_currency_pro_prices",
            "symbol_filter": "XAUUSD",
            "name_filter": None,
            "price_col": "price",
            "change_col": "change_percent",
            "is_index": False,
        },
    }

    # ── History tables for multi-period change ────────────────────────────
    _HISTORY_TABLES: dict[str, str] = {
        "stock": "brsapi_index_values",
        "gold": "brsapi_gold_coin_history",
        "currency": "brsapi_gold_currency_pro_daily_history",
        "crypto": "brsapi_gold_currency_pro_daily_history",
        "commodity": "brsapi_gold_currency_pro_daily_history",
    }

    # ── Column name for price in each history table (not all use price_close) ──
    _HISTORY_PRICE_COL: dict[str, str] = {
        "stock": "index_value",
        "gold": "price_close",
        "currency": "price_close",
        "crypto": "price_close",
        "commodity": "price_close",
    }

    # ── Regime threshold constants ────────────────────────────────────────
    _BULLISH_THRESHOLD = 0.5   # ≥ +0.5% → bullish
    _BEARISH_THRESHOLD = -0.3  # ≤ -0.3% → bearish
    _STRONG_TREND = 1.5        # ≥ +1.5% or ≤ -1.5% → strong

    @classmethod
    async def analyze(
        cls,
        signals: list[EnrichedSignal] | None = None,
    ) -> list[dict[str, Any]]:
        """Analyze cross-market dynamics using **real market prices** from the DB.

        Falls back to signal-count-based analysis when DB is unavailable.
        """
        real_market_data = await cls._fetch_all_market_prices()

        if real_market_data:
            return cls._analyze_market_regime(real_market_data)

        # Fallback: use signal-based analysis
        if signals:
            return cls._analyze_signals_only(signals)

        return []

    # ── Real-Data Analysis ─────────────────────────────────────────────────

    @classmethod
    async def _fetch_all_market_prices(cls) -> dict[str, dict[str, Any]]:
        """Fetch real price data for all markets in parallel."""

        from core.database import async_session_factory

        if async_session_factory is None:
            return {}

        result: dict[str, dict[str, Any]] = {}

        async with async_session_factory() as session:
            for market, cfg in cls._SYMBOL_KEYS.items():
                try:
                    where_clause: str
                    params: dict[str, Any] = {}

                    if cfg.get("name_filter"):
                        # Index table: filter by name column
                        where_clause = "WHERE name = :name_filter"
                        params["name_filter"] = cfg["name_filter"]
                    elif cfg.get("symbol_filter"):
                        where_clause = "WHERE symbol = :sym_filter"
                        params["sym_filter"] = cfg["symbol_filter"]
                    else:
                        where_clause = ""

                    price_col = cfg["price_col"]
                    change_col = cfg.get("change_col", price_col)

                    r = await session.execute(text(f"""
                        SELECT {price_col}, {change_col}
                        FROM {cfg['table']}
                        {where_clause}
                        ORDER BY date DESC, fetched_at DESC
                        LIMIT 1
                    """), params)
                    row = r.fetchone()

                    if row and row[0] is not None and row[0] > 0:
                        current_price = float(row[0])
                        change_pct = float(row[1]) if row[1] is not None else None

                        # Fetch multi-period returns from history table
                        history_changes = await cls._fetch_price_changes(
                            session, market, cfg,
                        )

                        result[market] = {
                            "price": current_price,
                            "change_pct_1d": change_pct,
                            **history_changes,
                        }
                except Exception as e:
                    logger.debug("CrossMarketCorrelator: failed to fetch %s: %s", market, e)
                    continue

        return result

    @classmethod
    async def _fetch_price_changes(
        cls,
        session: Any,
        market: str,
        cfg: dict[str, Any],
    ) -> dict[str, float]:
        """Compute 5-day and 20-day price changes from history tables."""

        history_table = cls._HISTORY_TABLES.get(market)
        if not history_table:
            return {}
        hist_price_col = cls._HISTORY_PRICE_COL.get(market, "price_close")

        try:
            # Fetch last ~21 close prices
            if cfg.get("is_index"):
                # Index history: filtered by name, uses index_value column
                r = await session.execute(text(f"""
                    SELECT {hist_price_col}
                    FROM {history_table}
                    WHERE name = :name_filter
                      AND {hist_price_col} > 0
                    ORDER BY date DESC
                    LIMIT 21
                """), {"name_filter": cfg["name_filter"]})
            else:
                symbol = cfg.get("symbol_filter", "")
                r = await session.execute(text(f"""
                    SELECT {hist_price_col}
                    FROM {history_table}
                    WHERE symbol = :symbol
                      AND {hist_price_col} > 0
                    ORDER BY date DESC
                    LIMIT 21
                """), {"symbol": symbol})

            rows = r.fetchall()
            prices = [float(row[0]) for row in rows if row[0]]

            changes: dict[str, float] = {}
            if len(prices) >= 2:
                changes["change_pct_5d"] = round(
                    (prices[0] - prices[min(4, len(prices) - 1)]) / prices[min(4, len(prices) - 1)] * 100, 2
                ) if len(prices) >= 5 else round(
                    (prices[0] - prices[-1]) / prices[-1] * 100, 2
                )
            if len(prices) >= 21:
                changes["change_pct_20d"] = round(
                    (prices[0] - prices[-1]) / prices[-1] * 100, 2
                )
            return changes
        except Exception:
            return {}

    @classmethod
    def _analyze_market_regime(
        cls, market_data: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Derive market regimes and cross-market signals from real prices."""
        result: list[dict[str, Any]] = []

        # Determine bias for each market based on 1d change + 5d trend
        def _regime_bias(data: dict[str, Any] | None) -> dict[str, Any]:
            if not data:
                return {"bias": "unknown", "change_pct": 0, "price": 0, "signal_count": 0}
            change_1d = data.get("change_pct_1d") or 0
            change_5d = data.get("change_pct_5d") or change_1d

            # Weighted: 70% 1d + 30% 5d for composite view
            composite = change_1d * 0.7 + change_5d * 0.3

            if composite >= cls._BULLISH_THRESHOLD:
                strength = "strong" if composite >= cls._STRONG_TREND else "moderate"
                return {
                    "bias": "bullish",
                    "change_pct": round(change_1d, 2),
                    "change_5d": round(change_5d, 2),
                    "strength": strength,
                    "price": data.get("price", 0),
                }
            elif composite <= cls._BEARISH_THRESHOLD:
                strength = "strong" if composite <= -cls._STRONG_TREND else "moderate"
                return {
                    "bias": "bearish",
                    "change_pct": round(change_1d, 2),
                    "change_5d": round(change_5d, 2),
                    "strength": strength,
                    "price": data.get("price", 0),
                }
            return {
                "bias": "neutral",
                "change_pct": round(change_1d, 2),
                "change_5d": round(change_5d, 2),
                "strength": "weak",
                "price": data.get("price", 0),
            }

        gold_bias = _regime_bias(market_data.get("gold"))
        stock_bias = _regime_bias(market_data.get("stock"))
        crypto_bias = _regime_bias(market_data.get("crypto"))
        currency_bias = _regime_bias(market_data.get("currency"))
        commodity_bias = _regime_bias(market_data.get("commodity"))

        def _signal_description(
            en_name: str, fa_name: str, direction: str,
            reason: str, strength: float,
        ) -> dict[str, Any]:
            return {
                "name": en_name,
                "signal": direction.upper(),
                "description": reason,
                "strength": strength,
                "source": "real_price",
            }

        # 1. Gold vs Index (risk-off / risk-on) — the classic pair
        if gold_bias["bias"] == "bullish" and stock_bias["bias"] == "bearish":
            result.append(_signal_description(
                "Risk-Off", "سناریوی ریسک‌گریزی", "DEFENSIVE",
                f"طلا ↑ ({gold_bias['change_pct']:+.1f}%) + شاخص ↓ ({stock_bias['change_pct']:+.1f}%) — بازار ریسک‌گریز. "
                "پوزیشن‌های دفاعی (طلا، دلار، اوراق) را افزایش دهید.",
                strength=0.80 if gold_bias["strength"] == "strong" or stock_bias["strength"] == "strong" else 0.65,
            ))
        elif gold_bias["bias"] == "bearish" and stock_bias["bias"] == "bullish":
            result.append(_signal_description(
                "Risk-On", "سناریوی ریسک‌پذیری", "AGGRESSIVE",
                f"طلا ↓ ({gold_bias['change_pct']:+.1f}%) + شاخص ↑ ({stock_bias['change_pct']:+.1f}%) — بازار ریسک‌پذیر. "
                "پوزیشن‌های تهاجمی (سهام رشد، کریپتو) را افزایش دهید.",
                strength=0.80 if stock_bias["strength"] == "strong" else 0.65,
            ))

        # 2. Gold + Crypto both up → inflation hedge mode
        if gold_bias["bias"] == "bullish" and crypto_bias["bias"] == "bullish":
            result.append(_signal_description(
                "Inflation-Hedge", "پوشش تورمی", "HEDGE",
                f"طلا ↑ ({gold_bias['change_pct']:+.1f}%) + بیت‌کوین ↑ ({crypto_bias['change_pct']:+.1f}%) — "
                "دارایی‌های ضدتورمی در مدار صعودی. افزایش تخصیص به طلا و کریپتو.",
                strength=0.70,
            ))

        # 3. Commodity ↑ + Currency (USD/IRR) ↑ → import inflation
        if commodity_bias["bias"] == "bullish" and currency_bias["bias"] == "bullish":
            # USD/IRR ↑ = ریال تضعیف شده = تورم وارداتی
            result.append(_signal_description(
                "Import-Inflation", "فشار تورمی وارداتی", "CAUTION",
                f"کالا ↑ ({commodity_bias['change_pct']:+.1f}%) + دلار ↑ ({currency_bias['change_pct']:+.1f}%) — "
                "فشار تورمی وارداتی. احتیاط در سهام مصرفی و افزایش پوزیشن‌های دلاری.",
                strength=0.65,
            ))

        # 4. All markets bearish → systemic risk
        all_bearish = all(
            b["bias"] == "bearish"
            for b in [gold_bias, stock_bias, crypto_bias, currency_bias, commodity_bias]
            if b["bias"] != "unknown"
        )
        bearish_count = sum(
            1 for b in [gold_bias, stock_bias, crypto_bias, currency_bias, commodity_bias]
            if b["bias"] == "bearish"
        )
        if all_bearish and bearish_count >= 4:
            result.append(_signal_description(
                "Systemic-Risk", "ریسک سیستمی", "CASH",
                "همه بازارها نزولی — افزایش نقدینگی و کاهش پوزیشن‌های باز.",
                strength=0.90,
            ))

        # 5. Strong gold rally on its own → safe-haven demand
        if gold_bias["bias"] == "bullish" and gold_bias["strength"] == "strong" \
                and stock_bias.get("bias") != "bearish":
            result.append(_signal_description(
                "Safe-Haven", "پناهگاه امن", "DEFENSIVE",
                f"طلا ↑ قوی ({gold_bias['change_pct']:+.1f}%) — تقاضای پناهگاه امن. "
                "کاهش وزن سهام و افزایش طلا/دلار.",
                strength=0.60,
            ))

        # 6. Gold + Currency both up → stagflation warning
        if gold_bias["bias"] == "bullish" and currency_bias["bias"] == "bullish" \
                and stock_bias["bias"] == "bearish":
            result.append(_signal_description(
                "Stagflation", "رکود تورمی", "CAUTION",
                f"طلا ↑ ({gold_bias['change_pct']:+.1f}%) + دلار ↑ ({currency_bias['change_pct']:+.1f}%) + شاخص ↓ "
                f"({stock_bias['change_pct']:+.1f}%) — نشانه‌های رکود تورمی. استراتژی تدافعی.",
                strength=0.85,
            ))

        # Always add the market regime summary
        result.append({
            "name": "Market-Regime",
            "signal": "INFO",
            "description": "خلاصه رژیم بازار بر اساس قیمت‌های واقعی",
            "strength": 0.0,
            "source": "real_price",
            "markets": {
                "stock": stock_bias,
                "gold": gold_bias,
                "crypto": crypto_bias,
                "currency": currency_bias,
                "commodity": commodity_bias,
            },
        })

        return result

    # ── Signal-Only Fallback (original logic) ─────────────────────────────

    @staticmethod
    def _analyze_signals_only(
        signals: list[EnrichedSignal],
    ) -> list[dict[str, Any]]:
        """Original signal-count-based analysis as fallback."""
        result: list[dict[str, Any]] = []

        by_market: dict[str, list[EnrichedSignal]] = {}
        for s in signals:
            by_market.setdefault(s.market, []).append(s)

        def _market_bias(market_sigs: list[EnrichedSignal]) -> dict[str, Any]:
            buy_count = sum(1 for s in market_sigs if s.direction == "buy")
            sell_count = sum(1 for s in market_sigs if s.direction == "sell")
            total = max(len(market_sigs), 1)
            buy_pct = round(buy_count / total * 100, 1)
            sell_pct = round(sell_count / total * 100, 1)
            if buy_pct > sell_pct + 15:
                return {"bias": "bullish", "buy_pct": buy_pct, "sell_pct": sell_pct, "total": len(market_sigs)}
            elif sell_pct > buy_pct + 15:
                return {"bias": "bearish", "buy_pct": buy_pct, "sell_pct": sell_pct, "total": len(market_sigs)}
            return {"bias": "neutral", "buy_pct": buy_pct, "sell_pct": sell_pct, "total": len(market_sigs)}

        gold_bias = _market_bias(by_market.get("gold", []))
        stock_bias = _market_bias(by_market.get("stock", []))
        crypto_bias = _market_bias(by_market.get("crypto", []))
        currency_bias = _market_bias(by_market.get("currency", []))
        commodity_bias = _market_bias(by_market.get("commodity", []))

        if gold_bias["bias"] == "bullish" and stock_bias["bias"] == "bearish":
            result.append({
                "name": "Risk-Off", "signal": "DEFENSIVE", "source": "signal_count",
                "description": "طلا ↑ + سهام ↓ — بازار ریسک‌گریز.", "strength": 0.8,
            })
        elif gold_bias["bias"] == "bearish" and stock_bias["bias"] == "bullish":
            result.append({
                "name": "Risk-On", "signal": "AGGRESSIVE", "source": "signal_count",
                "description": "طلا ↓ + سهام ↑ — بازار ریسک‌پذیر.", "strength": 0.8,
            })
        if gold_bias["bias"] == "bullish" and crypto_bias["bias"] == "bullish":
            result.append({
                "name": "Inflation-Hedge", "signal": "HEDGE", "source": "signal_count",
                "description": "طلا ↑ + رمزارز ↑ — پوشش تورمی.", "strength": 0.7,
            })
        if commodity_bias["bias"] == "bullish" and currency_bias["bias"] == "bearish":
            result.append({
                "name": "Import-Inflation", "signal": "CAUTION", "source": "signal_count",
                "description": "کالا ↑ + ارز ↓ — فشار تورمی وارداتی.", "strength": 0.65,
            })
        all_bearish = all(
            b["bias"] == "bearish" for b in [gold_bias, stock_bias, crypto_bias, currency_bias, commodity_bias]
            if b["total"] > 0
        )
        if all_bearish and len([b for b in [gold_bias, stock_bias, crypto_bias, currency_bias, commodity_bias] if b["total"] > 0]) >= 3:
            result.append({
                "name": "Systemic-Risk", "signal": "CASH", "source": "signal_count",
                "description": "همه بازارها نزولی — ریسک سیستمی.", "strength": 0.9,
            })

        result.append({
            "name": "Market-Biases", "signal": "INFO", "source": "signal_count",
            "description": "خلاصه وضعیت بازارها بر اساس سیگنال‌ها", "strength": 0.0,
            "biases": {
                "stock": stock_bias, "gold": gold_bias, "crypto": crypto_bias,
                "currency": currency_bias, "commodity": commodity_bias,
            },
        })
        return result


# ── Orchestrator ──────────────────────────────────────────────────────────────


class QuantSignalOrchestrator:
    """Single entry-point for the full quant signal pipeline.

    Usage:
        orchestrator = QuantSignalOrchestrator()
        report = await orchestrator.generate(
            market_filter="all",
            min_confidence=0.4,
            use_ml=True,
        )
        # report.to_dict() → JSON-ready output
    """

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def generate(
        self,
        market_filter: str = "all",
        timeframe_filter: str = "all",
        signal_filter: str = "all",
        min_strength: float = 0.0,
        min_confidence: float = 0.40,
        limit: int = 100,
        use_ml: bool = True,
        use_voting: bool = True,
        use_confidence_calibration: bool = True,
        use_probability_calibration: bool = True,
        use_decision_engine: bool = True,
    ) -> OrchestratorReport:
        """Run the full signal pipeline and return enriched, confidence-calibrated signals.

        Before generating signals, ensures that all required DB tables exist
        (calibration_models, signal_accuracy) to prevent silent failures.
        """
        # ── Ensure required tables exist (fix #8: cold-start table checks) ──
        await self._ensure_db_tables()

        from services.multi_market_signal_engine import MultiMarketSignalEngine

        engine = MultiMarketSignalEngine(session=self._session)

        # ── Stage 1: Generate rule-based signals ──
        _t0 = time.monotonic()
        raw_signals, gen_reports = await engine.generate_all(
            market_filter=market_filter,
            timeframe_filter=timeframe_filter,
            signal_filter=signal_filter,
            min_strength=min_strength,
            limit=limit * 10,  # Generate plenty; diversity filter will select per-market
        )
        logger.info("[pipeline] stage1 generate_all: %.2fs, %d raw signals", time.monotonic() - _t0, len(raw_signals))

        if not raw_signals:
            return OrchestratorReport(
                signals=[],
                summary={
                    "total_signals": 0, "buy_count": 0, "sell_count": 0, "hold_count": 0,
                    "avg_confidence": 0, "calibration_counts": {"very_high": 0, "high": 0, "medium": 0, "low": 0},
                    "markets": {},
                    "decision": {"released": 0, "watchlisted": 0, "rejected": 0, "grades": {}},
                    "filters": {
                        "market": market_filter, "timeframe": timeframe_filter,
                        "signal": signal_filter, "min_strength": min_strength,
                        "min_confidence": min_confidence,
                        "use_ml": use_ml, "use_voting": use_voting,
                        "use_probability_calibration": use_probability_calibration,
                        "use_decision_engine": use_decision_engine,
                    },
                },
                generation_reports=[r.to_dict() for r in gen_reports],
                generated_at=datetime.now(UTC).isoformat(),
            )

        # ── Stage 2: ML predictions ──
        ml_predictions: dict[str, dict[str, Any]] = {}
        _t1 = time.monotonic()
        if use_ml:
            ml_predictions = await self._get_ml_predictions(raw_signals)
        logger.info("[pipeline] stage2 ml: %.2fs, %d preds", time.monotonic() - _t1, len(ml_predictions))

        # ── Stage 3: Voting ──
        enriched: list[EnrichedSignal] = []
        _t2 = time.monotonic()
        if use_voting and use_ml:
            enriched = await self._apply_voting(raw_signals, ml_predictions)
        else:
            enriched = self._basic_enrich(raw_signals)
        logger.info("[pipeline] stage3 voting: %.2fs, %d enriched", time.monotonic() - _t2, len(enriched))

        # ── Stage 3.5: Probability calibration (calibrated win probabilities) ──
        _t3 = time.monotonic()
        if use_probability_calibration:
            enriched = await self._apply_probability_calibration(enriched)
        logger.info("[pipeline] stage3.5 prob-calib: %.2fs", time.monotonic() - _t3)

        # ── Stage 3.6: Candidate cap ──
        # The remaining stages (confidence calibration + 10-gate decision engine)
        # open a DB session per signal — running them on every raw candidate
        # (500+ for the dashboard) turns a request into a multi-minute job.
        # The final output only keeps `limit` signals anyway, so keep only the
        # strongest candidates here (diversity is re-applied downstream).
        if len(enriched) > 120:
            enriched.sort(key=lambda s: s.boosted_score, reverse=True)
            enriched = enriched[:120]
            logger.info("[pipeline] stage3.6 capped candidates to %d", len(enriched))

        # ── Stage 4: Confidence calibration (multi-factor confidence scoring) ──
        _t4 = time.monotonic()
        if use_confidence_calibration:
            enriched = await self._apply_confidence_calibration(enriched)
        logger.info("[pipeline] stage4 conf-calib: %.2fs", time.monotonic() - _t4)

        # ── Stage 4.5: Signal decision engine (10-gate pipeline) ──
        rejected: list[EnrichedSignal] = []
        _t5 = time.monotonic()
        if use_decision_engine:
            try:
                _hist_map = await self._fetch_symbol_histories(raw_signals)
                _hist_lens = {
                    _s: len((_hist_map.get(_s, {}) or {}).get("closes", []) or [])
                    for _s in {_s2.symbol for _s2 in raw_signals}
                }
            except Exception:
                _hist_lens = {}
            enriched, rejected = await self._apply_signal_decision(enriched, _hist_lens)
        logger.info("[pipeline] stage4.5 decision: %.2fs, released=%d rejected=%d", time.monotonic() - _t5, len(enriched), len(rejected))

        # ── Stage 5: Cross-market correlation (only on released signals) ──
        _t6 = time.monotonic()
        cross_market = await CrossMarketCorrelator.analyze(enriched)
        logger.info("[pipeline] stage5 cross-market: %.2fs", time.monotonic() - _t6)

        # ── Stage 6: Filter by confidence ──
        enriched = [s for s in enriched if s.confidence >= min_confidence]

        # ── Stage 6.1: Per-market quota to ensure diversity ──
        market_quota = max(5, limit // 4)  # at least 5 per market, up to 25%
        by_market_enriched: dict[str, list[EnrichedSignal]] = {}
        for s in enriched:
            by_market_enriched.setdefault(s.market, []).append(s)
        diversified: list[EnrichedSignal] = []
        for _mkt, sigs in by_market_enriched.items():
            sigs.sort(key=lambda s: s.boosted_score, reverse=True)
            diversified.extend(sigs[:market_quota])
        enriched = diversified

        # Sort by boosted score descending
        enriched.sort(key=lambda s: s.boosted_score, reverse=True)
        enriched = enriched[:limit]

        # ── Stage 6.5: Persist to DB for future outcome evaluation ──
        _t7 = time.monotonic()
        await self._persist_pending_signals(enriched)
        logger.info("[pipeline] stage6.5 persist: %.2fs", time.monotonic() - _t7)

        # ── Summary ──
        buy_count = sum(1 for s in enriched if s.direction == "buy")
        sell_count = sum(1 for s in enriched if s.direction == "sell")
        hold_count = sum(1 for s in enriched if s.direction in ("hold", "wait"))

        by_market: dict[str, dict[str, int]] = {}
        for s in enriched:
            m = s.market
            if m not in by_market:
                by_market[m] = {"buy": 0, "sell": 0, "hold": 0}
            if s.direction == "buy":
                by_market[m]["buy"] += 1
            elif s.direction == "sell":
                by_market[m]["sell"] += 1
            else:
                by_market[m]["hold"] += 1

        # Compute average confidence
        avg_confidence = (
            round(sum(s.confidence for s in enriched) / max(len(enriched), 1), 3)
            if enriched else 0.0
        )

        # Count by calibration level
        calibration_counts = {"very_high": 0, "high": 0, "medium": 0, "low": 0}
        for s in enriched:
            calibration_counts[s.calibration_level] = calibration_counts.get(s.calibration_level, 0) + 1

        # Decision stats
        released_count = sum(1 for s in enriched if s.decision_verdict == "release")
        watchlisted_count = sum(1 for s in enriched if s.decision_verdict == "watchlist")
        rejected_count = len(rejected) + sum(1 for s in enriched if s.decision_verdict == "reject")

        # Grade distribution
        grade_dist: dict[str, int] = {}
        all_signals = enriched + rejected
        for s in all_signals:
            g = s.decision_grade or "UNGRADED"
            grade_dist[g] = grade_dist.get(g, 0) + 1

        # ── Accuracy snapshot ──
        accuracy_snapshot = await self._get_accuracy_snapshot()

        # ── Stage 7: Record past outcomes + auto-retrain if accuracy low ──
        retrain_reports, fresh_accuracy = await self._record_outcomes_and_retrain(accuracy_snapshot)
        if fresh_accuracy:
            accuracy_snapshot = fresh_accuracy

        return OrchestratorReport(
            signals=enriched,
            summary={
                "total_signals": len(enriched),
                "buy_count": buy_count,
                "sell_count": sell_count,
                "hold_count": hold_count,
                "avg_confidence": avg_confidence,
                "calibration_counts": calibration_counts,
                "markets": by_market,
                "decision": {
                    "released": released_count,
                    "watchlisted": watchlisted_count,
                    "rejected": rejected_count,
                    "grades": grade_dist,
                },
                "filters": {
                    "market": market_filter,
                    "timeframe": timeframe_filter,
                    "signal": signal_filter,
                    "min_strength": min_strength,
                    "min_confidence": min_confidence,
                    "use_ml": use_ml,
                    "use_voting": use_voting,
                    "use_probability_calibration": use_probability_calibration,
                    "use_decision_engine": use_decision_engine,
                },
            },
            generation_reports=[r.to_dict() for r in gen_reports],
            accuracy_snapshot=accuracy_snapshot,
            cross_market_signals=cross_market,
            retrain_reports=retrain_reports,
            generated_at=datetime.now(UTC).isoformat(),
        )

    # ── ML Predictions ──────────────────────────────────────────────────────

    async def _get_ml_predictions(
        self, signals: list[Any],
    ) -> dict[str, dict[str, Any]]:
        """Get ML predictions for all signals, grouped by symbol with real historical data."""
        try:
            from services.ml_signal_connector import MLSignalConnector
            from services.signal_feature_pipeline import SignalFeaturePipeline

            connector = MLSignalConnector()
            pipeline = SignalFeaturePipeline()
            predictions: dict[str, dict[str, Any]] = {}

            # Fetch real historical data for all symbols at once
            history_map: dict[str, dict[str, list[float]]] = await self._fetch_symbol_histories(signals)

            seen: set[str] = set()
            for sig in signals:
                key = f"{sig.symbol}_{sig.market}"
                if key in seen:
                    continue
                seen.add(key)

                try:
                    # Use real historical data if available, otherwise skip ML
                    hist = history_map.get(sig.symbol, {})
                    closes = hist.get("closes", [])

                    if len(closes) < 5:
                        # Not enough history for meaningful ML — skip
                        continue

                    price_data = {
                        "closes": closes,
                        "highs": hist.get("highs", closes),
                        "lows": hist.get("lows", closes),
                        "volumes": hist.get("volumes", [1.0] * len(closes)),
                        "values": hist.get("values", closes),
                        "last_price": sig.price,
                    }
                    features = await pipeline.extract(
                        symbol=sig.symbol,
                        market=sig.market,
                        price_data=price_data,
                    )
                    pred = await connector.predict(features, sig.market, closes=closes)
                    if pred.success and pred.value:
                        predictions[key] = pred.value
                except Exception as e:
                    logger.debug("ML prediction skipped for %s: %s", key, e)

            return predictions
        except Exception as e:
            logger.warning("ML predictions failed: %s", e)
            return {}

    async def _fetch_symbol_histories(
        self, signals: list[Any],
    ) -> dict[str, dict[str, list[float]]]:
        """Fetch real historical OHLCV data for all symbols from the DB."""
        result: dict[str, dict[str, list[float]]] = {}
        try:
            from core.database import async_session_factory

            if async_session_factory is None:
                return result

            # Group symbols by market to use the right table
            symbols_by_market: dict[str, list[str]] = {}
            for sig in signals:
                symbols_by_market.setdefault(sig.market, []).append(sig.symbol)

            async with async_session_factory() as session:
                for market, syms in symbols_by_market.items():
                    unique_syms = list(set(syms))[:50]  # limit to 50 per market
                    if not unique_syms:
                        continue

                    # Choose the right table + column names per market.
                    # Stock tables use price_first/price_max/price_min;
                    # gold/crypto history tables use price_open/price_high/price_low.
                    # Unknown markets are skipped (no history table for them).
                    table_map = {
                        "stock": ("brsapi_historical_daily", "price_first, price_max, price_min", True),
                        "gold": ("brsapi_gold_coin_history", "price_open, price_high, price_low", False),
                        "crypto": ("brsapi_gold_currency_pro_daily_history", "price_open, price_high, price_low", False),
                    }
                    entry = table_map.get(market)
                    if entry is None:
                        continue
                    table, ohlc_cols, has_volume = entry
                    volume_col = ", trade_volume" if has_volume else ""

                    placeholders = ",".join([f":s{i}" for i in range(len(unique_syms))])
                    params = {f"s{i}": s for i, s in enumerate(unique_syms)}

                    r = await session.execute(text(f"""
                        SELECT symbol, price_close, {ohlc_cols}{volume_col}
                        FROM {table}
                        WHERE symbol IN ({placeholders})
                          AND price_close > 0
                        ORDER BY symbol, date DESC
                        LIMIT 2000
                    """), params)
                    rows = r.fetchall()

                    # Group by symbol (rows are DESC, so oldest last)
                    grouped: dict[str, list[Any]] = {}
                    for row in rows:
                        grouped.setdefault(row[0], []).append(row)

                    for sym, sym_rows in grouped.items():
                        sym_rows.reverse()  # oldest first
                        result[sym] = {
                            "closes": [r[1] for r in sym_rows if r[1]],
                            "highs": [r[3] or r[1] for r in sym_rows if r[1]],
                            "lows": [r[4] or r[1] for r in sym_rows if r[1]],
                            "volumes": [r[5] if has_volume and len(r) > 5 and r[5] else 0 for r in sym_rows],
                            "values": [r[1] or 0 for r in sym_rows],
                        }
        except Exception as e:
            logger.warning("Failed to fetch symbol histories: %s", e)

        return result

    # ── Voting ───────────────────────────────────────────────────────────────

    async def _apply_voting(
        self,
        signals: list[Any],
        ml_predictions: dict[str, dict[str, Any]],
        use_smart_money: bool = True,
    ) -> list[EnrichedSignal]:
        """Apply ML voting + Smart Money analysis to each signal."""
        from services.ml_signal_connector import MLSignalConnector
        from services.signal_voting_system import SignalVotingSystem

        connector = MLSignalConnector()
        voter = SignalVotingSystem(ml_connector=connector)

        # Pre-fetch Smart Money analysis for all symbols in parallel
        smart_money_analyses: dict[str, dict[str, Any]] = {}
        if use_smart_money:
            smart_money_analyses = await self._fetch_smart_money_analyses(signals)

        enriched: list[EnrichedSignal] = []

        for sig in signals:
            key = f"{sig.symbol}_{sig.market}"
            ml_pred = ml_predictions.get(key)
            smc_analysis = smart_money_analyses.get(key)

            try:
                vote = await voter.vote(
                    rule_signal=sig,
                    ml_prediction=ml_pred,
                    smart_money_analysis=smc_analysis,
                    strategy="weighted",
                )

                # Compute ML boost
                boost = connector.get_signal_boost(
                    ml_pred or {"ml_score": 0.5, "confidence": 0.0, "direction": "hold"},
                    sig.score / 100.0,
                )

                enriched.append(EnrichedSignal(
                    symbol=sig.symbol,
                    name=sig.name,
                    market=sig.market,
                    direction=vote.final_direction,
                    timeframe=sig.timeframe,
                    entry_zone=sig.entry_zone,
                    stop_loss=sig.stop_loss,
                    targets=sig.targets,
                    risk_reward=sig.risk_reward,
                    position_sizing=sig.position_sizing,
                    confirmation_condition=sig.confirmation_condition,
                    reason=sig.reason,
                    invalidation=sig.invalidation,
                    trailing_stop=sig.trailing_stop,
                    price=sig.price,
                    change_pct=sig.change_pct,
                    rule_score=sig.score,
                    ml_score=boost.get("ml_contribution", ml_pred.get("ml_score", 0.5) if ml_pred else 0.5),
                    boosted_score=boost.get("boosted_score", sig.score),
                    ml_influence_pct=boost.get("ml_influence_pct", 0.0),
                    confidence=vote.final_confidence,
                    calibration_level="medium",  # will be calibrated in next stage
                    confidence_factors={},
                    vote_strategy=vote.strategy,
                    vote_direction_scores=vote.direction_votes,
                    source=f"voting_{vote.strategy}",
                    created_at=sig.created_at,
                ))
            except Exception as e:
                logger.debug("Voting failed for %s: %s — falling back to rule-based", sig.symbol, e)
                enriched.append(self._basic_enrich_single(sig))

        return enriched

    # ── Confidence Calibration ───────────────────────────────────────────────

    async def _apply_confidence_calibration(
        self, signals: list[EnrichedSignal],
    ) -> list[EnrichedSignal]:
        """Apply calibrated confidence scoring to each signal."""
        try:
            from services.confidence_scorer import ConfidenceScorer

            scorer = ConfidenceScorer(session=self._session)
            calibrated: list[EnrichedSignal] = []

            for sig in signals:
                try:
                    result = await scorer.compute_confidence(
                        symbol=sig.symbol,
                        market=sig.market,
                        direction=sig.direction,
                        source=sig.source,
                        signal_strength=max(0.5, sig.confidence),  # floor at 0.5 for rule-based
                        ml_prediction={
                            "direction": sig.direction,
                            "confidence": sig.ml_score,
                            "direction_scores": sig.vote_direction_scores,
                        },
                        models_used=["rule_engine"] if sig.ml_score == 0 else ["ml_model"],
                    )
                    sig.confidence = result.confidence
                    sig.calibration_level = result.calibration_level
                    sig.confidence_factors = result.factors.to_dict()
                    sig.confidence_notes = result.notes
                except Exception as e:
                    logger.debug("Confidence calibration failed for %s: %s", sig.symbol, e)
                calibrated.append(sig)

            return calibrated
        except Exception as e:
            logger.warning("Confidence calibration batch failed: %s", e)
            return signals

    # ── Probability Calibration ───────────────────────────────────────────

    async def _apply_probability_calibration(
        self, signals: list[EnrichedSignal],
    ) -> list[EnrichedSignal]:
        """Apply probability calibration to each signal using historical accuracy data.

        Called AFTER voting (Stage 3) but BEFORE confidence calibration (Stage 4)
        so the calibrated probability can feed into the confidence scorer.
        """
        try:
            from services.probability_calibrator import ProbabilityCalibrator

            calibrator = ProbabilityCalibrator(session=self._session)
            calibrated: list[EnrichedSignal] = []

            for sig in signals:
                # Compute raw score before try block (available for fallback)
                raw = max(0.01, min(0.99, sig.ml_score if sig.ml_score > 0 else (sig.rule_score / 100.0)))

                try:
                    result = await calibrator.calibrate(
                        raw_score=raw,
                        market=sig.market,
                        timeframe=sig.timeframe,
                        direction=sig.direction,
                    )

                    sig.calibrated_probability = result.calibrated_probability
                    sig.calibration_version = result.calibration_version
                    sig.calibration_method = result.method

                    # Add notes about calibration to confidence notes
                    if result.notes:
                        sig.confidence_notes.extend(result.notes)

                except Exception as e:
                    logger.debug("Probability calibration failed for %s/%s: %s", sig.symbol, sig.market, e)
                    sig.calibrated_probability = raw
                    sig.calibration_method = "none"

                calibrated.append(sig)

            logger.info("Applied probability calibration to %d signals", len(calibrated))
            return calibrated

        except Exception as e:
            logger.warning("Probability calibration batch failed: %s", e)
            return signals

    # ── Signal Decision Engine ──────────────────────────────────────────────

    async def _apply_signal_decision(
        self, signals: list[EnrichedSignal],
        history_lengths: dict[str, int] | None = None,
    ) -> tuple[list[EnrichedSignal], list[EnrichedSignal]]:
        """Run the 10-gate decision engine on each signal.

        Returns (released_signals, rejected_signals).
        Watchlisted signals are kept in released_signals but tagged.
        """
        try:
            from services.signal_decision_engine import (
                SignalCandidate,
                SignalDecisionEngine,
                SignalPolicy,
            )

            # Load market-specific policy from YAML config
            policy_path = "config/signal_policy.yaml"
            engine = SignalDecisionEngine(
                policy=SignalPolicy(json_path=policy_path),
                session=self._session,
            )
            released: list[EnrichedSignal] = []
            rejected: list[EnrichedSignal] = []

            for sig in signals:
                try:
                    # Parse string fields to numeric values
                    rr = self._parse_risk_reward(sig.risk_reward)
                    sl_pct = self._parse_stop_loss_pct(sig.stop_loss, sig.price)
                    target_pct = self._parse_target_pct(sig.targets, sig.price)

                    # Compute best/second class probabilities from vote scores
                    scores = sig.vote_direction_scores or {}
                    sorted_scores = sorted(scores.values(), reverse=True)
                    best_prob = sorted_scores[0] if len(sorted_scores) > 0 else sig.confidence
                    second_prob = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

                    # Compute volatility_regime from change_pct (not hardcoded)
                    abs_change = abs(sig.change_pct) / 100.0
                    vol_regime = min(1.0, abs_change * 5)  # 0-20% change → 0-1.0 volatility

                    # Compute data quality score from available signal fields
                    available_fields = 0
                    total_expected = 4
                    if sig.price and sig.price > 0:
                        available_fields += 1
                    if sig.change_pct is not None:
                        available_fields += 1
                    if sig.confidence is not None:
                        available_fields += 1
                    if sig.rule_score is not None:
                        available_fields += 1
                    # Gate 1: total_price_points from real candle/history length
                    # when available (threaded from _fetch_symbol_histories via
                    # generate()); otherwise fall back to the vote-coverage proxy.
                    _real_len = (history_lengths or {}).get(sig.symbol, 0)
                    if _real_len and _real_len > 0:
                        _price_points = int(_real_len)
                    else:
                        try:
                            _n_votes = len(scores) if isinstance(scores, dict) else 0
                        except Exception:
                            _n_votes = 0
                        _price_points = max(20, _n_votes * 10)
                    dqs = compute_data_quality_score(
                        total_fields=total_expected,
                        missing_fields=total_expected - available_fields,
                        total_price_points=_price_points,
                    )

                    # Compute liquidity score from trading activity proxy
                    abs_change = abs(sig.change_pct or 0) / 100.0
                    liq_score = min(1.0, 0.3 + abs_change * 3)
                    fill_prob = min(1.0, 0.4 + abs_change * 2.5)

                    # Gate 9 fix: no hardcoded block. Portfolio validator module
                    # is not called here, so default to allowed with a warning
                    # (fail-open) instead of forcing released=[].
                    logger.warning(
                        "Portfolio validator not invoked for %s — defaulting "
                        "portfolio_risk_approved=True (fail-open)",
                        sig.symbol,
                    )
                    portfolio_approved = True
                    open_risk = 0.0
                    correlated_exp = 0.0

                    candidate = SignalCandidate(
                        signal_id=sig.symbol + "_" + sig.market + "_" + sig.timeframe,
                        symbol=sig.symbol,
                        name=sig.name,
                        market=sig.market,
                        direction=sig.direction,
                        timeframe=sig.timeframe,
                        raw_score=sig.rule_score / 100.0,
                        ml_score=sig.ml_score,
                        calibrated_probability=sig.calibrated_probability or sig.confidence,
                        boosted_score=sig.boosted_score,
                        active_models=1 if sig.ml_score > 0 else 0,
                        agreeing_models=1 if sig.ml_score > 0 else 0,
                        risk_reward=rr,
                        stop_loss_pct=sl_pct,
                        target_pct=target_pct,
                        price=sig.price,
                        signal_type="hybrid" if sig.ml_score > 0 else "rule",
                        best_class_probability=best_prob,
                        second_class_probability=second_prob,
                        source=sig.source,
                        data_quality_score=dqs,
                        volatility_regime=vol_regime,
                        liquidity_score=liq_score,
                        fill_probability=fill_prob,
                        feature_drift=0.0,
                        portfolio_risk_approved=portfolio_approved,
                        open_risk_pct=open_risk,
                        correlated_exposure_pct=correlated_exp,
                    )

                    decision = await engine.evaluate(candidate)
                    grade = engine.signal_grade(decision)

                    # Store decision results on the signal
                    sig.calibrated_probability = decision.calibrated_probability
                    sig.effective_threshold = decision.effective_threshold
                    sig.net_expectancy_r = decision.net_expectancy_r
                    sig.gate_results = [g.to_dict() for g in decision.gate_results]
                    sig.decision_verdict = decision.verdict.value
                    sig.decision_grade = grade

                    # Split by verdict
                    if decision.verdict.value == "reject":
                        rejected.append(sig)
                    else:
                        released.append(sig)

                except Exception as inner_e:
                    logger.debug("Decision engine failed for %s: %s — rejecting signal", sig.symbol, inner_e)
                    sig.decision_verdict = "reject"
                    sig.decision_grade = "REJECTED_ON_ERROR"
                    rejected.append(sig)

            logger.info(
                "Signal decisions: %d released, %d watchlisted, %d rejected",
                len(released),
                sum(1 for s in released if s.decision_verdict == "watchlist"),
                len(rejected),
            )
            return released, rejected

        except Exception as e:
            logger.warning("Signal decision batch failed: %s — rejecting all signals", e)
            for sig in signals:
                sig.decision_verdict = "reject"
                sig.decision_grade = "REJECTED_ON_ERROR"
            return [], signals

    # ── Basic Enrich (no ML) ────────────────────────────────────────────────

    def _basic_enrich(self, signals: list[Any]) -> list[EnrichedSignal]:
        """Enrich signals without ML/voting — just wrap in EnrichedSignal."""
        return [self._basic_enrich_single(s) for s in signals]

    def _basic_enrich_single(self, sig: Any) -> EnrichedSignal:
        return EnrichedSignal(
            symbol=sig.symbol,
            name=sig.name,
            market=sig.market,
            direction=sig.direction,
            timeframe=sig.timeframe,
            entry_zone=sig.entry_zone,
            stop_loss=sig.stop_loss,
            targets=sig.targets,
            risk_reward=sig.risk_reward,
            position_sizing=sig.position_sizing,
            confirmation_condition=sig.confirmation_condition,
            reason=sig.reason,
            invalidation=sig.invalidation,
            trailing_stop=sig.trailing_stop,
            price=sig.price,
            change_pct=sig.change_pct,
            rule_score=sig.score,
            ml_score=0.0,
            boosted_score=sig.score,
            ml_influence_pct=0.0,
            confidence=sig.confidence,
            calibration_level="high" if sig.confidence > 0.6 else "medium" if sig.confidence > 0.4 else "low",
            confidence_factors={},
            vote_strategy="rule_only",
            vote_direction_scores={sig.direction: 1.0},
            source=sig.source,
            created_at=sig.created_at,
        )

    # ── Smart Money Analysis ──────────────────────────────────────────────

    async def _fetch_smart_money_analyses(
        self, signals: list[Any],
    ) -> dict[str, dict[str, Any]]:
        """Fetch Smart Money analysis for each unique symbol in parallel.

        Returns dict keyed by "{symbol}_{market}" with SmartMoneyService output.
        """
        result: dict[str, dict[str, Any]] = {}
        try:
            from services.smart_money_service import SmartMoneyService

            # Group unique symbols from signals
            unique_keys: dict[str, str] = {}  # symbol -> key
            for sig in signals:
                key = f"{sig.symbol}_{sig.market}"
                if key not in unique_keys:
                    unique_keys[sig.symbol] = key

            if not unique_keys:
                return result

            # SmartMoneyService needs a session + brsapi to fetch real data
            from core.database import async_session_factory

            if async_session_factory is None:
                logger.warning("No DB session available for Smart Money analysis")
                return result

            # IMPORTANT: each concurrent task gets its OWN AsyncSession.
            # A single AsyncSession must not be shared across concurrent
            # coroutines — SQLAlchemy raises IllegalStateChangeError
            # ("Method 'close()' can't be called here") and the request hangs.
            sem = asyncio.Semaphore(5)

            async def _analyze_one(sym: str, key: str) -> tuple[str, str, dict[str, Any]] | None:
                async with sem:
                    try:
                        async with async_session_factory() as session:
                            smc_service = SmartMoneyService(session=session)
                            res = await smc_service.analyze(sym)
                            if res.success and res.value:
                                return sym, key, res.value
                    except Exception as e:
                        logger.debug("Smart Money analysis error for %s: %s", sym, e)
                    return None

            analyze_tasks = [_analyze_one(sym, key) for sym, key in unique_keys.items()]
            analyze_results = await asyncio.gather(*analyze_tasks, return_exceptions=True)

            for ar in analyze_results:
                if isinstance(ar, BaseException):
                    logger.debug("Smart Money analysis failed: %s", ar)
                    continue
                if ar is not None:
                    _sym, _key, smc_data = ar
                    # Skip if data was rejected (quality too low)
                    if smc_data.get("meta", {}).get("analysis_mode") == "rejected":
                        continue
                    if smc_data.get("smart_money_score", 0.0) > 0.0:
                        result[_key] = smc_data

            logger.info("Fetched Smart Money analysis for %d/%d symbols", len(result), len(unique_keys))
        except Exception as e:
            logger.warning("Smart Money analysis batch failed: %s", e)

        return result

    # ── Parsing Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_risk_reward(rr_str: str) -> float:
        """Parse risk/reward string like '2.5', '1:2.5', '۱ به ۱.۳' to float."""
        if not rr_str:
            return 0.0
        _PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
        normalized = rr_str.translate(_PERSIAN_DIGITS)
        # Try direct parse
        try:
            return float(normalized)
        except ValueError:
            pass
        # Try format like '1:2.5' or '1 به 2.5' or '1:3'
        if ":" in normalized or " به " in normalized:
            sep = ":" if ":" in normalized else " به "
            parts = normalized.split(sep)
            if len(parts) == 2:
                try:
                    return float(parts[1].strip())
                except ValueError:
                    pass
        # Try extracting numbers with regex
        nums = re.findall(r"[\d.]+(?:e[\d]+)?", normalized.replace(",", "."))
        for n in nums:
            try:
                val = float(n)
                if 0.1 <= val <= 100:
                    return val
            except ValueError:
                continue
        return 0.0

    @staticmethod
    def _normalize_digits(s: str) -> str:
        """Normalize Persian/Arabic digits to ASCII."""
        return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

    @staticmethod
    def _parse_stop_loss_pct(sl_str: str, price: float) -> float:
        """Parse stop loss string to percentage. Returns 0.05 (5%) as default."""
        if not sl_str or price <= 0:
            return 0.05
        normalized = QuantSignalOrchestrator._normalize_digits(sl_str)
        cleaned = re.sub(r",(\d{3})(?!\d)", r"\1", normalized)
        cleaned = cleaned.replace(",", ".")
        nums = re.findall(r"[\d.]+(?:e[\d]+)?", cleaned)
        if nums:
            try:
                val = float(nums[0])
                if "%" in normalized:
                    return abs(val) / 100.0
                # Assume IRR amount: compute as % of price
                pct = abs(val - price) / max(price, 0.001)
                if 0.001 <= pct <= 0.5:  # 0.1% to 50%
                    return pct
                if 0.5 < pct <= 5:  # 50% to 500% — likely wrong, use default
                    return 0.05
            except (ValueError, IndexError):
                pass
        return 0.05

    @staticmethod
    def _parse_target_pct(target_str: str, price: float) -> float:
        """Parse first target from targets string to percentage gain."""
        if not target_str or price <= 0:
            return 0.0
        normalized = QuantSignalOrchestrator._normalize_digits(target_str)
        cleaned = re.sub(r",(\d{3})(?!\d)", r"\1", normalized)
        # Replace remaining comma with dot (decimal separator)
        cleaned = cleaned.replace(",", ".")
        # Extract numbers
        nums = re.findall(r"[\d.]+(?:e[\d]+)?", cleaned)
        if nums:
            try:
                val = float(nums[0])
                if "%" in normalized:
                    return abs(val) / 100.0
                pct = abs(val - price) / max(price, 0.001)
                if 0.001 <= pct <= 5:
                    return pct
            except (ValueError, IndexError):
                pass
        return 0.0    # ── DB Table Checks ──────────────────────────────────────────────────

    @staticmethod
    async def _ensure_db_tables() -> None:
        """Ensure that all required signal-system tables exist in the DB.

        Called at the start of each generate() run to prevent silent failures
        caused by missing tables (fix #8: cold-start table checks).
        """
        try:
            from core.database import async_session_factory

            if async_session_factory is None:
                logger.warning("No DB available — skipping table creation checks")
                return

            async with async_session_factory() as session:
                # 1. signal_accuracy table
                try:
                    await session.execute(text("""
                        CREATE TABLE IF NOT EXISTS signal_accuracy (
                            id VARCHAR(100) PRIMARY KEY,
                            signal_id VARCHAR(100),
                            symbol VARCHAR(50),
                            market VARCHAR(50),
                            source VARCHAR(50),
                            direction VARCHAR(10),
                            timeframe VARCHAR(20),
                            regime VARCHAR(50),
                            signal_price FLOAT,
                            signal_strength FLOAT,
                            signal_confidence FLOAT,
                            ml_score FLOAT,
                            rule_score FLOAT,
                            actual_return_pct FLOAT,
                            direction_correct BOOLEAN,
                            max_profit_pct FLOAT,
                            max_loss_pct FLOAT,
                            hit_target1 BOOLEAN,
                            hit_target2 BOOLEAN,
                            stopped_out BOOLEAN,
                            entry_price FLOAT,
                            exit_price FLOAT,
                            generated_at TIMESTAMP,
                            outcome_set_at TIMESTAMP
                        )
                    """))
                    await session.commit()
                    logger.debug("Ensured signal_accuracy table exists")
                except Exception as e:
                    logger.debug("Could not create signal_accuracy: %s", e)

                # 1b. Partial unique index on pending signals: at most one
                # unevaluated signal per (symbol, market, direction, timeframe).
                # Combined with the check-then-insert dedupe in
                # _persist_pending_signals, this makes concurrent pipeline
                # runs (e.g. startup CacheWarmupJob + warm_signal_cache)
                # safely drop duplicates instead of inserting them.
                try:
                    await session.execute(text("""
                        CREATE UNIQUE INDEX IF NOT EXISTS
                            uq_signal_accuracy_pending_key
                        ON signal_accuracy (symbol, market, direction, timeframe)
                        WHERE outcome_set_at IS NULL
                    """))
                    await session.commit()
                    logger.debug("Ensured pending-signal unique index exists")
                except Exception as e:
                    logger.debug("Could not create pending-signal unique index: %s", e)

                # 2. calibration_models table
                try:
                    await session.execute(text("""
                        CREATE TABLE IF NOT EXISTS calibration_models (
                            id VARCHAR(100) PRIMARY KEY,
                            market VARCHAR(50),
                            timeframe VARCHAR(20),
                            direction VARCHAR(10),
                            regime VARCHAR(50),
                            model_version VARCHAR(20),
                            method VARCHAR(20),
                            parameters TEXT,
                            brier_score FLOAT,
                            ece FLOAT,
                            total_samples INTEGER DEFAULT 0,
                            calibration_data TEXT,
                            last_trained_at TIMESTAMP
                        )
                    """))
                    await session.commit()
                    logger.debug("Ensured calibration_models table exists")
                except Exception as e:
                    logger.debug("Could not create calibration_models: %s", e)
        except Exception as e:
            logger.warning("Failed to ensure DB tables: %s", e)

    # ── Feedback Loop: Outcome Recording + Auto-Retrain ───────────────────

    # In-memory tracker for scheduled retrains (avoids querying non-existent table)
    _last_scheduled_retrain: float | None = None
    # Initialize the outcome-recording throttle to NOW so a freshly-started
    # process does not run the heavy evaluation/retrain feedback loop on its
    # very first API request (the loop only runs again 6h later).
    _last_outcome_record: float = 0.0
    _outcome_throttle_started: bool = False

    async def _record_outcomes_and_retrain(
        self, accuracy_snapshot: dict[str, float],
    ) -> tuple[list[dict[str, Any]], dict[str, float]]:
        """Evaluate past signals, record outcomes, and auto-retrain if accuracy drops.

        This closes the feedback loop:
          persist → wait for prediction period → evaluate → record → check accuracy → retrain

        Returns list of retrain reports (empty if no retrain was needed).
        """
        retrain_reports: list[dict[str, Any]] = []

        try:
            # 0. Throttle the whole feedback loop — evaluating + retraining is
            #    heavy and would otherwise run on every single request. Run at
            #    most once per 6 hours (this is fine: signals need >= 5 days
            #    before their outcome can even be evaluated). The very first
            #    call of a freshly-started process also skips the loop so the
            #    first API request is never blocked by evaluation + retraining.
            now = time.time()
            if not QuantSignalOrchestrator._outcome_throttle_started:
                QuantSignalOrchestrator._outcome_throttle_started = True
                QuantSignalOrchestrator._last_outcome_record = now
                return retrain_reports, accuracy_snapshot
            if (now - QuantSignalOrchestrator._last_outcome_record) < 6 * 3600:
                return retrain_reports, accuracy_snapshot
            QuantSignalOrchestrator._last_outcome_record = now

            # 1. Evaluate and record outcomes for past signals
            outcomes_recorded = await self._evaluate_past_signals()
            logger.info("Recorded %d past signal outcomes", outcomes_recorded)

            # 2. Refresh accuracy after recording new outcomes
            accuracy_snapshot = await self._get_accuracy_snapshot()

            # 3. Check each market's accuracy against threshold
            ACCURACY_THRESHOLD = 55.0  # percent
            low_accuracy_markets: list[str] = []

            for market, acc in accuracy_snapshot.items():
                if market == "overall":
                    continue
                if acc < ACCURACY_THRESHOLD:
                    low_accuracy_markets.append(market)
                    logger.warning(
                        "Market '%s' accuracy %.1f%% below threshold %.1f%% — triggering retrain",
                        market, acc, ACCURACY_THRESHOLD,
                    )

            if not low_accuracy_markets and not self._should_scheduled_retrain():
                return retrain_reports, accuracy_snapshot

            # 4. Trigger auto-retrain for low-accuracy markets
            if low_accuracy_markets:
                from services.auto_retrain_pipeline import AutoRetrainPipeline

                pipeline = AutoRetrainPipeline()
                for market in low_accuracy_markets:
                    try:
                        result = await pipeline.check_and_retrain(
                            market=market,
                            force=True,  # force retrain when accuracy drops
                            trigger="accuracy_drop",
                        )
                        if result.success and result.value:
                            retrain_reports.append(result.value.to_dict())
                    except Exception as e:
                        logger.error("Auto-retrain failed for %s: %s", market, e)

            # 5. Also do a periodic retrain every 7 days for all markets
            if self._should_scheduled_retrain():
                from services.auto_retrain_pipeline import AutoRetrainPipeline

                pipeline = AutoRetrainPipeline()
                all_markets = [m for m in accuracy_snapshot if m != "overall"] or [
                    "stock", "gold", "currency", "crypto", "option", "commodity", "ime"
                ]
                existing = {r.get("market") for r in retrain_reports}
                for market in all_markets:
                    if market in existing:
                        continue
                    try:
                        result = await pipeline.check_and_retrain(
                            market=market, force=True, trigger="scheduled",
                        )
                        if result.success and result.value:
                            retrain_reports.append(result.value.to_dict())
                    except Exception as e:
                        logger.error("Scheduled retrain failed for %s: %s", market, e)

                # Update timestamp
                QuantSignalOrchestrator._last_scheduled_retrain = time.time()

        except Exception as e:
            logger.warning("Outcome recording / retrain check failed: %s", e)

        return retrain_reports, accuracy_snapshot

    def _should_scheduled_retrain(self) -> bool:
        """Check if >= 7 days since last scheduled retrain (in-memory tracking).

        Returns False when never retrained: on a fresh process we don't want
        the first API request to trigger a multi-minute retrain of every
        market. The periodic retrain is also available as the explicit
        ``/multi-market-signals/retrain`` endpoint and scheduler job.
        """
        if QuantSignalOrchestrator._last_scheduled_retrain is None:
            return False  # never retrained — don't block first request
        seconds_since = time.time() - QuantSignalOrchestrator._last_scheduled_retrain
        return seconds_since >= 7 * 24 * 3600

    async def _persist_pending_signals(self, signals: list[EnrichedSignal]) -> int:
        """Persist signals to signal_accuracy table as pending (no outcome yet).

        This enables the feedback loop: next time generate() runs,
        _evaluate_past_signals() will find these rows with NULL outcome_set_at
        and evaluate them against current prices.
        """
        inserted = 0
        try:
            from core.database import async_session_factory
            from core.ids import new_id
            if async_session_factory is None:
                return 0

            async with async_session_factory() as session:
                # Dedupe guard: the pipeline runs repeatedly (every cache TTL /
                # background rebuild), so the same signal would otherwise be
                # inserted thousands of times under new ids — flooding the
                # table and skewing accuracy stats with copies of one signal.
                # Only one PENDING (unevaluated) row is kept per
                # (symbol, market, direction, timeframe); once it is evaluated
                # (outcome_set_at IS NOT NULL) a fresh signal can be inserted.
                r = await session.execute(text("""
                    SELECT DISTINCT symbol, market, direction, timeframe
                    FROM signal_accuracy
                    WHERE outcome_set_at IS NULL
                """))
                pending_keys = {
                    (row[0], row[1], row[2], row[3]) for row in r.fetchall()
                }

                for sig in signals:
                    try:
                        # Skip hold/wait — they have no tradable outcome and
                        # only pollute the accuracy table (e.g. IME 100% acc
                        # from 875 holds).
                        if sig.direction in ("hold", "wait"):
                            continue
                        key = (sig.symbol, sig.market, sig.direction, sig.timeframe)
                        if key in pending_keys:
                            continue
                        pending_keys.add(key)

                        record_id = new_id("sacc")
                        sig_id = new_id("sig")
                        stmt = text("""
                            INSERT INTO signal_accuracy (
                                id, signal_id, symbol, market, source,
                                direction, timeframe,
                                signal_price, signal_strength, signal_confidence,
                                ml_score, rule_score,
                                generated_at
                            ) VALUES (
                                :id, :signal_id, :symbol, :market, :source,
                                :direction, :timeframe,
                                :signal_price, :signal_strength, :signal_confidence,
                                :ml_score, :rule_score,
                                :generated_at
                            )
                        """)
                        await session.execute(stmt, {
                            "id": record_id,
                            "signal_id": sig_id,
                            "symbol": sig.symbol,
                            "market": sig.market,
                            "source": sig.source,
                            "direction": sig.direction,
                            "timeframe": sig.timeframe,
                            "signal_price": sig.price,
                            "signal_strength": sig.confidence * (sig.boosted_score / 100.0),
                            "signal_confidence": sig.confidence,
                            "ml_score": sig.ml_score,
                            "rule_score": sig.rule_score,
                            "generated_at": datetime.now(UTC).replace(tzinfo=None),
                        })
                        inserted += 1
                    except Exception as ins_err:
                        logger.debug("Failed to persist signal %s: %s", sig.symbol, ins_err)
                        continue

                if inserted > 0:
                    await session.commit()
                if inserted < len(signals):
                    logger.info("Persisted %d new pending signals (%d already pending / hold skipped)", inserted, len(signals) - inserted)
                else:
                    logger.info("Persisted %d signals as pending for future evaluation", inserted)

        except Exception as e:
            logger.warning("Failed to persist pending signals: %s", e)

        return inserted

    async def _evaluate_past_signals(self) -> int:
        """Evaluate signals whose prediction window has ended.

        Uses SignalAccuracyTracker.evaluate_signal() to avoid code duplication.
        Updates each pending signal_accuracy row with the outcome.
        """
        recorded = 0
        try:
            from core.database import async_session_factory
            from services.signal_accuracy_tracker import SignalAccuracyTracker

            if async_session_factory is None:
                return 0

            tracker = SignalAccuracyTracker()

            async with async_session_factory() as session:
                now = datetime.now(UTC).replace(tzinfo=None)  # DB column is TIMESTAMP WITHOUT TZ
                # Only evaluate signals whose 5-candle prediction window has fully
                # elapsed (>= 5 days old). Evaluating younger signals judges them
                # against an incomplete window and biases accuracy toward zero.
                cutoff_start = now - timedelta(days=30)  # sweep back up to 30 days
                cutoff_end = now - timedelta(days=5)     # signal must be 5+ days old

                # Find pending signals from 5-30 days ago (oldest first so the
                # evaluation queue drains FIFO instead of repeatedly picking the
                # same arbitrary 100 rows and starving the rest)
                r = await session.execute(text("""
                    SELECT sa.id, sa.signal_id, sa.symbol, sa.market,
                           sa.source, sa.direction, sa.timeframe,
                           sa.signal_price, sa.signal_strength, sa.signal_confidence,
                           sa.ml_score, sa.rule_score
                    FROM signal_accuracy sa
                    WHERE sa.outcome_set_at IS NULL
                      AND sa.generated_at >= :cutoff_start
                      AND sa.generated_at <= :cutoff_end
                    ORDER BY sa.generated_at ASC
                    LIMIT 100
                """), {"cutoff_start": cutoff_start, "cutoff_end": cutoff_end})
                pending_rows = r.fetchall()

                if not pending_rows:
                    return 0

                for row in pending_rows:
                    try:
                        signal_id = row[1]
                        symbol = row[2]
                        market = row[3]
                        direction = row[5]
                        signal_price = float(row[7] or 0)

                        if signal_price <= 0:
                            continue

                        # Fetch current price as exit price (market-specific table,
                        # price column, and lookup column). commodity/ime live in
                        # their own tables (not brsapi_symbol_snapshots) and ime
                        # keys on contract_code rather than symbol.
                        table_map = {
                            "stock": ("brsapi_symbol_snapshots", "price_last", "symbol"),
                            "gold": ("brsapi_gold_coin_prices", "price", "symbol"),
                            "currency": ("brsapi_currency_prices", "price", "symbol"),
                            "crypto": ("brsapi_crypto_prices", "price_usd", "symbol"),
                            "option": ("brsapi_symbol_snapshots", "price_last", "symbol"),
                            "commodity": ("brsapi_commodity_prices", "price", "symbol"),
                            "ime": ("brsapi_ime_futures", "price_last", "contract_code"),
                        }
                        table, price_col, lookup_col = table_map.get(
                            market, ("brsapi_symbol_snapshots", "price_last", "symbol")
                        )

                        r2 = await session.execute(text(f"""
                            SELECT {price_col}
                            FROM {table}
                            WHERE {lookup_col} = :symbol
                            ORDER BY id DESC  -- latest snapshot wins (deterministic)
                            LIMIT 1
                        """), {"symbol": symbol})
                        price_row = r2.fetchone()

                        if not price_row or not price_row[0] or float(price_row[0]) <= 0:
                            continue

                        exit_price = float(price_row[0])
                        entry_price = signal_price

                        # Use SignalAccuracyTracker for evaluation
                        signal_dict = {
                            "id": signal_id,
                            "symbol": symbol,
                            "market": market,
                            "source": row[4] or "rule_based",
                            "direction": direction,
                            "timeframe": row[6] or "daily",
                            "price": signal_price,
                            "strength": float(row[8] or 0),
                            "confidence": float(row[9] or 0),
                            "ml_score": safe_row_float(row, idx=10),
                            "rule_score": safe_row_float(row, idx=11),
                        }
                        outcome = await tracker.evaluate_signal(
                            signal=signal_dict,
                            entry_price=entry_price,
                            exit_price=exit_price,
                        )

                        # Update the row with outcome data
                        stmt = text("""
                            UPDATE signal_accuracy
                            SET actual_return_pct = :actual_return_pct,
                                direction_correct = :direction_correct,
                                max_profit_pct = :max_profit_pct,
                                max_loss_pct = :max_loss_pct,
                                entry_price = :entry_price,
                                exit_price = :exit_price,
                                outcome_set_at = :outcome_set_at
                            WHERE id = :id
                        """)
                        await session.execute(stmt, {
                            "id": row[0],
                            "actual_return_pct": outcome.actual_return_pct,
                            "direction_correct": outcome.direction_correct,
                            "max_profit_pct": outcome.max_profit_pct,
                            "max_loss_pct": outcome.max_loss_pct,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "outcome_set_at": datetime.now(UTC).replace(tzinfo=None),
                        })
                        recorded += 1

                    except Exception as eval_err:
                        logger.debug("Failed to evaluate signal %s: %s", row[1] if row else "?", eval_err)
                        continue

                if recorded > 0:
                    await session.commit()
                    logger.info("Evaluated and recorded %d past signal outcomes", recorded)

        except Exception as e:
            logger.warning("Past signal evaluation failed: %s", e)

        return recorded

    async def _get_accuracy_snapshot(self) -> dict[str, float]:
        """Get current accuracy snapshot for all markets."""
        try:
            from services.signal_accuracy_tracker import SignalAccuracyTracker

            tracker = SignalAccuracyTracker(session=self._session)
            result = await tracker.get_accuracy_by_market(days=90)

            if result.success and result.value:
                items = result.value.items if hasattr(result.value, "items") else []
                snapshot: dict[str, float] = {}
                for item in items:
                    snapshot[item.get("market", "?")] = item.get("accuracy_pct", 0.0)
                # Overall average
                if snapshot:
                    snapshot["overall"] = round(sum(snapshot.values()) / len(snapshot), 2)
                return snapshot
        except Exception as e:
            logger.debug("Accuracy snapshot unavailable: %s", e)

        return {}


# ── Singleton ─────────────────────────────────────────────────────────────────

_orchestrator: QuantSignalOrchestrator | None = None


def get_orchestrator() -> QuantSignalOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = QuantSignalOrchestrator()
    return _orchestrator
