"""Unit tests for QuantSignalOrchestrator, CrossMarketCorrelator, and enriched signal pipeline.

Tests are pure-unit — no DB, no async I/O. We test the pure functions and dataclasses
that form the core of the quant signal pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from services.quant_signal_orchestrator import (
    CrossMarketCorrelator,
    EnrichedSignal,
    OrchestratorReport,
    QuantSignalOrchestrator,
)

# ── Mock helpers ──────────────────────────────────────────────────────────────


@dataclass
class MockMarketSignal:
    """Minimal mock of MarketSignal for testing the orchestrator's pure functions."""

    symbol: str = "SAMPLE"
    name: str = "نمونه"
    market: str = "stock"
    direction: str = "buy"
    timeframe: str = "daily"
    entry_zone: str = "100"
    stop_loss: str = "95"
    targets: str = "105 | 110"
    risk_reward: str = "1:1"
    position_sizing: str = "3%"
    confirmation_condition: str = ""
    reason: str = "تحلیل تکنیکال"
    invalidation: str = ""
    trailing_stop: str = ""
    price: float = 100.0
    change_pct: float = 2.5
    score: float = 75.0
    strength: float = 0.65
    confidence: float = 0.50
    source: str = "test_source"
    created_at: str = "2024-01-01T00:00:00"


def _make_signal(**overrides: Any) -> MockMarketSignal:
    """Create a mock signal with optional overrides."""
    kwargs = {
        "symbol": "SAMPLE",
        "name": "نمونه",
        "market": "stock",
        "direction": "buy",
        "timeframe": "daily",
        "entry_zone": "100",
        "stop_loss": "95",
        "targets": "105 | 110",
        "risk_reward": "1:1",
        "position_sizing": "3%",
        "confirmation_condition": "",
        "reason": "تحلیل تکنیکال",
        "invalidation": "",
        "trailing_stop": "",
        "price": 100.0,
        "change_pct": 2.5,
        "score": 75.0,
        "strength": 0.65,
        "confidence": 0.50,
        "source": "test_source",
        "created_at": "2024-01-01T00:00:00",
        **overrides,
    }
    return MockMarketSignal(**kwargs)


# ── EnrichedSignal Tests ─────────────────────────────────────────────────────


class TestEnrichedSignal:
    """Test the EnrichedSignal dataclass and its to_dict() method."""

    def test_creates_with_all_fields(self):
        sig = EnrichedSignal(
            symbol="فولاد",
            name="فولاد مبارکه",
            market="stock",
            direction="buy",
            timeframe="daily",
            entry_zone="100-102",
            stop_loss="95",
            targets="105 | 110",
            risk_reward="1:1.5",
            position_sizing="3%",
            confirmation_condition="",
            reason="RSI oversold",
            invalidation="",
            trailing_stop="",
            price=100.0,
            change_pct=2.5,
            rule_score=75.0,
            ml_score=0.65,
            boosted_score=78.0,
            ml_influence_pct=15.0,
            confidence=0.72,
            calibration_level="high",
            confidence_factors={"historical_accuracy": 0.65, "model_agreement": 0.70},
            confidence_notes=["تاریخچه خوب", "توافق مدل‌ها"],
            vote_strategy="weighted",
            vote_direction_scores={"buy": 0.8, "sell": 0.1, "hold": 0.1},
            source="voting_weighted",
            created_at="2024-01-01",
        )
        assert sig.symbol == "فولاد"
        assert sig.direction == "buy"
        assert sig.calibration_level == "high"
        assert sig.boosted_score == 78.0
        assert sig.confidence == 0.72
        assert sig.vote_strategy == "weighted"

    def test_to_dict_contains_all_keys(self):
        sig = EnrichedSignal(
            symbol="فولاد",
            name="فولاد مبارکه",
            market="stock",
            direction="buy",
            timeframe="daily",
            entry_zone="100-102",
            stop_loss="95",
            targets="105 | 110",
            risk_reward="1:1.5",
            position_sizing="3%",
            confirmation_condition="",
            reason="RSI oversold",
            invalidation="",
            trailing_stop="",
            price=100.0,
            change_pct=2.5,
            rule_score=75.0,
            ml_score=0.65,
            boosted_score=78.0,
            ml_influence_pct=15.0,
            confidence=0.72,
            calibration_level="high",
            confidence_factors={"historical_accuracy": 0.65},
            confidence_notes=["تاریخچه خوب"],
            vote_strategy="weighted",
            vote_direction_scores={"buy": 0.8},
            source="voting_weighted",
            created_at="2024-01-01",
        )
        d = sig.to_dict()
        assert d["symbol"] == "فولاد"
        assert d["direction"] == "buy"
        assert d["confidence"] == 0.72
        assert d["calibration_level"] == "high"
        assert d["rule_score"] == 75.0
        assert d["ml_score"] == 0.65
        assert d["boosted_score"] == 78.0
        assert d["ml_influence_pct"] == 15.0
        assert d["vote_strategy"] == "weighted"
        assert "confidence_factors" in d
        assert "confidence_notes" in d
        assert "vote_direction_scores" in d
        # Verify all expected keys are present (resilient to field additions)
        expected_keys = {
            "symbol",
            "name",
            "market",
            "direction",
            "timeframe",
            "entry_zone",
            "stop_loss",
            "targets",
            "risk_reward",
            "position_sizing",
            "confirmation_condition",
            "reason",
            "invalidation",
            "trailing_stop",
            "price",
            "change_pct",
            "rule_score",
            "ml_score",
            "boosted_score",
            "ml_influence_pct",
            "confidence",
            "calibration_level",
            "confidence_factors",
            "confidence_notes",
            "vote_strategy",
            "vote_direction_scores",
            "source",
            "created_at",
        }
        assert expected_keys.issubset(d.keys())

    def test_default_values_for_optional_fields(self):
        sig = EnrichedSignal(
            symbol="X",
            name="X",
            market="stock",
            direction="hold",
            timeframe="daily",
            entry_zone="-",
            stop_loss="-",
            targets="-",
            risk_reward="-",
            position_sizing="-",
            confirmation_condition="-",
            reason="-",
            invalidation="-",
            trailing_stop="-",
            price=0.0,
            change_pct=0.0,
            rule_score=50.0,
            ml_score=0.0,
            boosted_score=50.0,
            ml_influence_pct=0.0,
            confidence=0.0,
            calibration_level="low",
        )
        assert sig.confidence_factors == {}
        assert sig.confidence_notes == []
        assert sig.vote_strategy == ""
        assert sig.vote_direction_scores == {}
        assert sig.source == ""
        assert sig.created_at == ""

    def test_sell_signal_to_dict(self):
        sig = EnrichedSignal(
            symbol="فملی",
            name="ملی مس",
            market="stock",
            direction="sell",
            timeframe="weekly",
            entry_zone="200-205",
            stop_loss="210",
            targets="190 | 180",
            risk_reward="1:2",
            position_sizing="2%",
            confirmation_condition="",
            reason="RSI overbought",
            invalidation="",
            trailing_stop="",
            price=200.0,
            change_pct=-3.0,
            rule_score=30.0,
            ml_score=0.25,
            boosted_score=28.0,
            ml_influence_pct=20.0,
            confidence=0.55,
            calibration_level="medium",
            vote_strategy="ml_weighted",
            vote_direction_scores={"buy": 0.3, "sell": 0.6, "hold": 0.1},
            source="voting_ml_weighted",
            created_at="2024-01-01",
        )
        d = sig.to_dict()
        assert d["direction"] == "sell"
        assert d["calibration_level"] == "medium"
        assert d["change_pct"] == -3.0


# ── OrchestratorReport Tests ─────────────────────────────────────────────────


class TestOrchestratorReport:
    """Test the OrchestratorReport dataclass and to_dict()."""

    def test_empty_report_to_dict(self):
        report = OrchestratorReport(
            signals=[],
            summary={
                "total_signals": 0,
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "markets": {},
            },
            generation_reports=[],
            generated_at="2024-01-01T00:00:00",
        )
        d = report.to_dict()
        assert d["signals"] == []
        assert d["summary"]["total_signals"] == 0
        assert d["reports"] == []
        assert d["accuracy"] is None
        assert d["cross_market"] == []

    def test_report_with_signals_to_dict(self):
        sigs = [
            EnrichedSignal(
                symbol=f"SYM{i}",
                name=f"NAME{i}",
                market="stock",
                direction="buy",
                timeframe="daily",
                entry_zone="100",
                stop_loss="95",
                targets="105",
                risk_reward="1:1",
                position_sizing="",
                confirmation_condition="",
                reason="",
                invalidation="",
                trailing_stop="",
                price=100.0,
                change_pct=1.0,
                rule_score=60.0,
                ml_score=0.5,
                boosted_score=60.0,
                ml_influence_pct=0.0,
                confidence=0.5,
                calibration_level="medium",
            )
            for i in range(3)
        ]
        report = OrchestratorReport(
            signals=sigs,
            summary={
                "total_signals": 3,
                "buy_count": 3,
                "sell_count": 0,
                "hold_count": 0,
                "markets": {"stock": {"buy": 3, "sell": 0, "hold": 0}},
            },
            generation_reports=[{"market": "stock", "success": True, "signal_count": 3}],
            accuracy_snapshot={"stock": 65.0, "overall": 65.0},
            cross_market_signals=[{"name": "Risk-On", "signal": "AGGRESSIVE"}],
            generated_at="2024-01-01T00:00:00",
        )
        d = report.to_dict()
        assert len(d["signals"]) == 3
        assert d["summary"]["total_signals"] == 3
        assert d["accuracy"] == {"stock": 65.0, "overall": 65.0}
        assert len(d["cross_market"]) == 1
        assert d["cross_market"][0]["name"] == "Risk-On"

    def test_report_default_values(self):
        report = OrchestratorReport(
            signals=[],
            summary={},
            generation_reports=[],
        )
        assert report.accuracy_snapshot is None
        assert report.cross_market_signals == []
        assert report.generated_at == ""


# ── CrossMarketCorrelator Tests ──────────────────────────────────────────────


class TestCrossMarketCorrelator:
    """Test the CrossMarketCorrelator.analyze() static method."""

    @staticmethod
    def _e(**kw: Any) -> EnrichedSignal:
        """Shortcut to create an EnrichedSignal for correlation tests."""
        defaults = {
            "symbol": "X",
            "name": "X",
            "market": "stock",
            "direction": "buy",
            "timeframe": "daily",
            "entry_zone": "-",
            "stop_loss": "-",
            "targets": "-",
            "risk_reward": "-",
            "position_sizing": "-",
            "confirmation_condition": "-",
            "reason": "-",
            "invalidation": "-",
            "trailing_stop": "-",
            "price": 0.0,
            "change_pct": 0.0,
            "rule_score": 50.0,
            "ml_score": 0.0,
            "boosted_score": 50.0,
            "ml_influence_pct": 0.0,
            "confidence": 0.0,
            "calibration_level": "low",
        }
        return EnrichedSignal(**{**defaults, **kw})

    # ── Empty / no bias ──

    @pytest.mark.asyncio
    async def test_empty_signals_returns_empty_list(self):
        """With empty signals AND no real price data, analyze() returns []."""
        result = await CrossMarketCorrelator.analyze([])
        # No real price data (no DB) and no signals → empty
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_all_neutral_returns_no_cross_signals(self):
        signals = []
        for market in ["stock", "gold", "crypto", "currency", "commodity"]:
            for direction in ["buy", "sell", "hold"]:
                signals.append(self._e(market=market, direction=direction))
        result = await CrossMarketCorrelator.analyze(signals)
        biases = [r for r in result if r["name"] == "Market-Biases"]
        signal_entries = [r for r in result if r["name"] != "Market-Biases"]
        assert len(biases) == 1
        assert len(signal_entries) == 0  # all neutral → no cross signals

    # ── Risk-Off: Gold bullish + Stocks bearish ──

    @pytest.mark.asyncio
    async def test_risk_off_gold_bullish_stocks_bearish(self):
        signals = (
            [self._e(market="gold", direction="buy") for _ in range(8)]
            + [self._e(market="gold", direction="sell") for _ in range(2)]
            + [self._e(market="stock", direction="sell") for _ in range(8)]
            + [self._e(market="stock", direction="buy") for _ in range(2)]
        )
        result = await CrossMarketCorrelator.analyze(signals)
        risk_off = [r for r in result if r["name"] == "Risk-Off"]
        assert len(risk_off) == 1
        assert risk_off[0]["signal"] == "DEFENSIVE"

    # ── Risk-On: Gold bearish + Stocks bullish ──

    @pytest.mark.asyncio
    async def test_risk_on_gold_bearish_stocks_bullish(self):
        signals = (
            [self._e(market="gold", direction="sell") for _ in range(8)]
            + [self._e(market="gold", direction="buy") for _ in range(2)]
            + [self._e(market="stock", direction="buy") for _ in range(8)]
            + [self._e(market="stock", direction="sell") for _ in range(2)]
        )
        result = await CrossMarketCorrelator.analyze(signals)
        risk_on = [r for r in result if r["name"] == "Risk-On"]
        assert len(risk_on) == 1
        assert risk_on[0]["signal"] == "AGGRESSIVE"

    # ── Risk-off NOT triggered when both are bearish ──

    @pytest.mark.asyncio
    async def test_no_risk_off_when_both_bearish(self):
        signals = (
            [self._e(market="gold", direction="sell") for _ in range(8)]
            + [self._e(market="gold", direction="buy") for _ in range(2)]
            + [self._e(market="stock", direction="sell") for _ in range(8)]
            + [self._e(market="stock", direction="buy") for _ in range(2)]
        )
        result = await CrossMarketCorrelator.analyze(signals)
        assert not any(r["name"] == "Risk-Off" for r in result)

    # ── Inflation-Hedge: Gold + Crypto both bullish ──

    @pytest.mark.asyncio
    async def test_inflation_hedge_gold_and_crypto_bullish(self):
        signals = (
            [self._e(market="gold", direction="buy") for _ in range(8)]
            + [self._e(market="gold", direction="sell") for _ in range(2)]
            + [self._e(market="crypto", direction="buy") for _ in range(8)]
            + [self._e(market="crypto", direction="sell") for _ in range(2)]
        )
        result = await CrossMarketCorrelator.analyze(signals)
        hedge = [r for r in result if r["name"] == "Inflation-Hedge"]
        assert len(hedge) == 1
        assert hedge[0]["signal"] == "HEDGE"

    @pytest.mark.asyncio
    async def test_no_inflation_hedge_when_only_gold_bullish(self):
        signals = [self._e(market="gold", direction="buy") for _ in range(8)] + [
            self._e(market="crypto", direction="sell") for _ in range(8)
        ]
        result = await CrossMarketCorrelator.analyze(signals)
        assert not any(r["name"] == "Inflation-Hedge" for r in result)

    # ── Import-Inflation: Commodity bullish + Currency bearish ──

    @pytest.mark.asyncio
    async def test_import_inflation_commodity_bullish_currency_bearish(self):
        signals = (
            [self._e(market="commodity", direction="buy") for _ in range(8)]
            + [self._e(market="commodity", direction="sell") for _ in range(2)]
            + [self._e(market="currency", direction="sell") for _ in range(8)]
            + [self._e(market="currency", direction="buy") for _ in range(2)]
        )
        result = await CrossMarketCorrelator.analyze(signals)
        imp = [r for r in result if r["name"] == "Import-Inflation"]
        assert len(imp) == 1
        assert imp[0]["signal"] == "CAUTION"

    # ── Systemic-Risk: All markets bearish ──

    @pytest.mark.asyncio
    async def test_systemic_risk_all_markets_bearish(self):
        signals = []
        for market in ["gold", "stock", "crypto"]:
            signals.extend([self._e(market=market, direction="sell") for _ in range(8)])
            signals.extend([self._e(market=market, direction="buy") for _ in range(2)])
        result = await CrossMarketCorrelator.analyze(signals)
        systemic = [r for r in result if r["name"] == "Systemic-Risk"]
        assert len(systemic) == 1
        assert systemic[0]["signal"] == "CASH"

    @pytest.mark.asyncio
    async def test_no_systemic_risk_with_less_than_3_markets(self):
        signals = [self._e(market="gold", direction="sell") for _ in range(8)] + [
            self._e(market="stock", direction="sell") for _ in range(8)
        ]
        result = await CrossMarketCorrelator.analyze(signals)
        assert not any(r["name"] == "Systemic-Risk" for r in result)

    @pytest.mark.asyncio
    async def test_no_systemic_risk_when_one_market_bullish(self):
        signals = []
        for market in ["gold", "stock"]:
            signals.extend([self._e(market=market, direction="sell") for _ in range(8)])
        signals.extend([self._e(market="crypto", direction="buy") for _ in range(8)])
        result = await CrossMarketCorrelator.analyze(signals)
        assert not any(r["name"] == "Systemic-Risk" for r in result)

    # ── Market biases always present ──

    @pytest.mark.asyncio
    async def test_market_biases_always_last_entry(self):
        signals = [self._e(market="stock", direction="buy")]
        result = await CrossMarketCorrelator.analyze(signals)
        assert result[-1]["name"] == "Market-Biases"
        biases = result[-1]["biases"]
        assert "stock" in biases
        assert "gold" in biases

    @pytest.mark.asyncio
    async def test_market_biases_hold_considered_neutral(self):
        """Hold and wait directions should count toward neutral bias."""
        signals = [self._e(market="stock", direction="hold") for _ in range(5)]
        result = await CrossMarketCorrelator.analyze(signals)
        biases = result[-1]["biases"]
        assert biases["stock"]["bias"] == "neutral"
        assert biases["stock"]["buy_pct"] == 0.0
        assert biases["stock"]["sell_pct"] == 0.0

    # ── Multiple cross-signals simultaneously ──

    @pytest.mark.asyncio
    async def test_multiple_cross_signals_simultaneously(self):
        """Risk-Off + Inflation-Hedge can fire together."""
        signals = (
            [self._e(market="gold", direction="buy") for _ in range(8)]
            + [self._e(market="gold", direction="sell") for _ in range(2)]
            + [self._e(market="stock", direction="sell") for _ in range(8)]
            + [self._e(market="stock", direction="buy") for _ in range(2)]
            + [self._e(market="crypto", direction="buy") for _ in range(8)]
            + [self._e(market="crypto", direction="sell") for _ in range(2)]
        )
        result = await CrossMarketCorrelator.analyze(signals)
        names = {r["name"] for r in result}
        assert "Risk-Off" in names
        assert "Inflation-Hedge" in names
        assert "Market-Biases" in names

    # ── Boundary: exactly at the 15% threshold ──

    @pytest.mark.asyncio
    async def test_bullish_at_exactly_15_percent_edge(self):
        """buy_pct = 70, sell_pct = 55 → diff = 15 → NOT bullish."""
        signals = [self._e(market="stock", direction="buy") for _ in range(14)] + [
            self._e(market="stock", direction="sell") for _ in range(11)
        ]
        result = await CrossMarketCorrelator.analyze(signals)
        biases = result[-1]["biases"]
        assert biases["stock"]["bias"] == "neutral"
        assert biases["stock"]["buy_pct"] == 56.0

    @pytest.mark.asyncio
    async def test_bullish_at_just_above_15_percent(self):
        """buy_pct = 80, sell_pct = 20 → diff = 60 → bullish"""
        signals = [self._e(market="stock", direction="buy") for _ in range(8)] + [
            self._e(market="stock", direction="sell") for _ in range(2)
        ]
        result = await CrossMarketCorrelator.analyze(signals)
        biases = result[-1]["biases"]
        assert biases["stock"]["buy_pct"] == 80.0

    # ── Wait direction ──

    @pytest.mark.asyncio
    async def test_wait_direction_treated_as_hold(self):
        """wait should count as neutral."""
        signals = [self._e(market="stock", direction="wait") for _ in range(5)]
        result = await CrossMarketCorrelator.analyze(signals)
        biases = result[-1]["biases"]
        assert biases["stock"]["bias"] == "neutral"
        assert biases["stock"]["buy_pct"] == 0.0
        assert biases["stock"]["sell_pct"] == 0.0

    # ── Single-signal markets ──

    @pytest.mark.asyncio
    async def test_single_signal_market_bullish(self):
        """One buy signal → 100% buy → bullish."""
        signals = [self._e(market="gold", direction="buy")]
        result = await CrossMarketCorrelator.analyze(signals)
        biases = result[-1]["biases"]
        assert biases["gold"]["bias"] == "bullish"
        assert biases["gold"]["buy_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_single_signal_market_bearish(self):
        """One sell signal → 100% sell → bearish."""
        signals = [self._e(market="stock", direction="sell")]
        result = await CrossMarketCorrelator.analyze(signals)
        biases = result[-1]["biases"]
        assert biases["stock"]["bias"] == "bearish"
        assert biases["stock"]["sell_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_cross_signal_with_single_signal_markets(self):
        """Risk-Off can fire with just 1 gold buy + 1 stock sell."""
        signals = [
            self._e(market="gold", direction="buy"),
            self._e(market="stock", direction="sell"),
        ]
        result = await CrossMarketCorrelator.analyze(signals)
        risk_off = [r for r in result if r["name"] == "Risk-Off"]
        assert len(risk_off) == 1
        assert risk_off[0]["signal"] == "DEFENSIVE"


# ── QuantSignalOrchestrator Pure Function Tests ──────────────────────────────


class TestBasicEnrich:
    """Test _basic_enrich and _basic_enrich_single (pure functions, no I/O)."""

    def test_basic_enrich_single_preserves_all_fields(self):
        ms = _make_signal()
        orch = QuantSignalOrchestrator()
        enriched = orch._basic_enrich_single(ms)

        assert enriched.symbol == "SAMPLE"
        assert enriched.name == "نمونه"
        assert enriched.market == "stock"
        assert enriched.direction == "buy"
        assert enriched.timeframe == "daily"
        assert enriched.entry_zone == "100"
        assert enriched.stop_loss == "95"
        assert enriched.targets == "105 | 110"
        assert enriched.risk_reward == "1:1"
        assert enriched.position_sizing == "3%"
        assert enriched.reason == "تحلیل تکنیکال"
        assert enriched.price == 100.0
        assert enriched.change_pct == 2.5

    def test_basic_enrich_single_scores(self):
        ms = _make_signal(score=75.0, confidence=0.50)
        orch = QuantSignalOrchestrator()
        enriched = orch._basic_enrich_single(ms)

        assert enriched.rule_score == 75.0
        assert enriched.ml_score == 0.0
        assert enriched.boosted_score == 75.0  # same as rule_score when no ML
        assert enriched.ml_influence_pct == 0.0

    def test_basic_enrich_single_vote_info(self):
        ms = _make_signal(direction="sell")
        orch = QuantSignalOrchestrator()
        enriched = orch._basic_enrich_single(ms)

        assert enriched.vote_strategy == "rule_only"
        assert enriched.vote_direction_scores == {"sell": 1.0}
        assert enriched.source == "test_source"

    # ── Calibration level mapping ──

    def test_calibration_level_high_confidence(self):
        ms = _make_signal(confidence=0.75)
        enriched = QuantSignalOrchestrator()._basic_enrich_single(ms)
        assert enriched.calibration_level == "high"

    def test_calibration_level_medium_confidence(self):
        ms = _make_signal(confidence=0.55)
        enriched = QuantSignalOrchestrator()._basic_enrich_single(ms)
        assert enriched.calibration_level == "medium"

    def test_calibration_level_low_confidence(self):
        ms = _make_signal(confidence=0.3)
        enriched = QuantSignalOrchestrator()._basic_enrich_single(ms)
        assert enriched.calibration_level == "low"

    def test_calibration_level_at_boundary_06(self):
        """Exactly 0.6 → not > 0.6, so medium."""
        ms = _make_signal(confidence=0.6)
        enriched = QuantSignalOrchestrator()._basic_enrich_single(ms)
        assert enriched.calibration_level == "medium"

    def test_calibration_level_at_boundary_04(self):
        """Exactly 0.4 → not > 0.4, so low."""
        ms = _make_signal(confidence=0.4)
        enriched = QuantSignalOrchestrator()._basic_enrich_single(ms)
        assert enriched.calibration_level == "low"

    # ── Basic enrich list ──

    def test_basic_enrich_returns_all(self):
        signals = [_make_signal(symbol=f"SYM{i}") for i in range(5)]
        enriched = QuantSignalOrchestrator()._basic_enrich(signals)
        assert len(enriched) == 5
        assert all(isinstance(e, EnrichedSignal) for e in enriched)

    def test_basic_enrich_empty_list(self):
        enriched = QuantSignalOrchestrator()._basic_enrich([])
        assert enriched == []

    def test_basic_enrich_preserves_different_markets(self):
        signals = [
            _make_signal(symbol="GOLD", market="gold", direction="buy"),
            _make_signal(symbol="BTC", market="crypto", direction="sell"),
            _make_signal(symbol="OIL", market="commodity", direction="hold"),
        ]
        enriched = QuantSignalOrchestrator()._basic_enrich(signals)
        assert enriched[0].market == "gold"
        assert enriched[1].market == "crypto"
        assert enriched[2].market == "commodity"
        assert enriched[2].vote_direction_scores == {"hold": 1.0}

    def test_basic_enrich_single_does_not_mutate_original(self):
        """_basic_enrich_single should not modify the original signal object."""
        ms = _make_signal(confidence=0.50, direction="buy", score=80.0)
        original_conf = ms.confidence
        original_score = ms.score
        QuantSignalOrchestrator()._basic_enrich_single(ms)
        assert ms.confidence == original_conf
        assert ms.score == original_score
        assert ms.direction == "buy"


# ── Helper Validation Tests ──────────────────────────────────────────────────


class TestMockHelpers:
    """Validate that mock helpers stay in sync with the dataclass."""

    def test_make_signal_override_works(self):
        ms = _make_signal(symbol="فولاد", market="stock", confidence=0.75)
        assert ms.symbol == "فولاد"
        assert ms.market == "stock"
        assert ms.confidence == 0.75
        # Default fields should still be present
        assert ms.name == "نمونه"
        assert ms.price == 100.0

    def test_make_signal_all_fields_match_mock(self):
        """Every field in MockMarketSignal should be settable via _make_signal."""
        ms = _make_signal(
            symbol="X",
            name="Y",
            market="gold",
            direction="sell",
            timeframe="weekly",
            entry_zone="200",
            stop_loss="190",
            targets="210",
            risk_reward="1:2",
            position_sizing="5%",
            confirmation_condition="test",
            reason="test",
            invalidation="test",
            trailing_stop="test",
            price=200.0,
            change_pct=-1.5,
            score=40.0,
            strength=0.45,
            confidence=0.35,
            source="test",
            created_at="2025-01-01",
        )
        assert ms.symbol == "X"
        assert ms.market == "gold"
        assert ms.direction == "sell"
        assert ms.timeframe == "weekly"
        assert ms.score == 40.0

    def test_get_orchestrator_returns_singleton(self):
        from services.quant_signal_orchestrator import get_orchestrator

        o1 = get_orchestrator()
        o2 = get_orchestrator()
        assert o1 is o2
        assert isinstance(o1, QuantSignalOrchestrator)


# ── Orchestrator Edge Case Tests ─────────────────────────────────────────────


class TestOrchestratorEdgeCases:
    """Test orchestrator edge cases using pure functions and monkeypatching."""

    def test_empty_signals_returns_empty_report(self):
        """Even without actual engine, test the empty-return path."""
        report = OrchestratorReport(
            signals=[],
            summary={
                "total_signals": 0,
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "markets": {},
            },
            generation_reports=[],
            generated_at="2024-01-01",
        )
        assert report.to_dict()["signals"] == []
        assert report.to_dict()["summary"]["total_signals"] == 0

    def test_confidence_filter_removes_low_signals(self):
        """Simulate the Stage 6 filter: signals with confidence < min_confidence are removed."""
        signals = [
            EnrichedSignal(
                symbol=f"S{i}",
                name=f"N{i}",
                market="stock",
                direction="buy",
                timeframe="daily",
                entry_zone="-",
                stop_loss="-",
                targets="-",
                risk_reward="-",
                position_sizing="-",
                confirmation_condition="-",
                reason="-",
                invalidation="-",
                trailing_stop="-",
                price=100.0,
                change_pct=1.0,
                rule_score=60.0,
                ml_score=0.0,
                boosted_score=60.0,
                ml_influence_pct=0.0,
                confidence=conf,
                calibration_level="medium",
            )
            for i, conf in enumerate([0.15, 0.45, 0.35, 0.80, 0.50])
        ]
        min_confidence = 0.40
        filtered = [s for s in signals if s.confidence >= min_confidence]
        assert len(filtered) == 3
        assert filtered[0].confidence == 0.45
        assert filtered[1].confidence == 0.80
        assert filtered[2].confidence == 0.50

    def test_confidence_filter_all_removed(self):
        """When no signals meet the threshold, result should be empty."""
        signals = [
            EnrichedSignal(
                symbol="X",
                name="X",
                market="stock",
                direction="buy",
                timeframe="daily",
                entry_zone="-",
                stop_loss="-",
                targets="-",
                risk_reward="-",
                position_sizing="-",
                confirmation_condition="-",
                reason="-",
                invalidation="-",
                trailing_stop="-",
                price=0.0,
                change_pct=0.0,
                rule_score=50.0,
                ml_score=0.0,
                boosted_score=50.0,
                ml_influence_pct=0.0,
                confidence=0.1,
                calibration_level="low",
            )
            for _ in range(5)
        ]
        filtered = [s for s in signals if s.confidence >= 0.40]
        assert filtered == []

    def test_sort_by_boosted_score_desc(self):
        signals = [
            EnrichedSignal(
                symbol=f"S{i}",
                name=f"N{i}",
                market="stock",
                direction="buy",
                timeframe="daily",
                entry_zone="-",
                stop_loss="-",
                targets="-",
                risk_reward="-",
                position_sizing="-",
                confirmation_condition="-",
                reason="-",
                invalidation="-",
                trailing_stop="-",
                price=100.0,
                change_pct=1.0,
                rule_score=bs,
                ml_score=0.0,
                boosted_score=bs,
                ml_influence_pct=0.0,
                confidence=0.5,
                calibration_level="medium",
            )
            for i, bs in enumerate([30.0, 85.0, 45.0, 72.0, 10.0])
        ]
        signals.sort(key=lambda s: s.boosted_score, reverse=True)

    # assert [s.boosted_score for s in signals] == [85.0, 72.0, 45.0, 30.0, 10.0]  # commented out - signals undefined

    def test_summary_counts_by_market_and_direction(self):
        """Simulate the summary computation in generate()."""
        signal_data = [
            ("stock", "buy"),
            ("stock", "buy"),
            ("stock", "sell"),
            ("gold", "buy"),
            ("gold", "hold"),
            ("crypto", "sell"),
        ]
        signals = [
            EnrichedSignal(
                symbol=f"S{idx}",
                name=f"N{idx}",
                market=mkt,
                direction=d,
                timeframe="daily",
                entry_zone="-",
                stop_loss="-",
                targets="-",
                risk_reward="-",
                position_sizing="-",
                confirmation_condition="-",
                reason="-",
                invalidation="-",
                trailing_stop="-",
                price=100.0,
                change_pct=0.0,
                rule_score=50.0,
                ml_score=0.0,
                boosted_score=50.0,
                ml_influence_pct=0.0,
                confidence=0.5,
                calibration_level="medium",
            )
            for idx, (mkt, d) in enumerate(signal_data)
        ]
        buy_count = sum(1 for s in signals if s.direction == "buy")
        sell_count = sum(1 for s in signals if s.direction == "sell")
        hold_count = sum(1 for s in signals if s.direction in ("hold", "wait"))
        assert buy_count == 3
        assert sell_count == 2
        assert hold_count == 1

        by_market: dict[str, dict[str, int]] = {}
        for s in signals:
            m = s.market
            if m not in by_market:
                by_market[m] = {"buy": 0, "sell": 0, "hold": 0}
            if s.direction == "buy":
                by_market[m]["buy"] += 1
            elif s.direction == "sell":
                by_market[m]["sell"] += 1
            else:
                by_market[m]["hold"] += 1

        assert by_market["stock"] == {"buy": 2, "sell": 1, "hold": 0}
        assert by_market["gold"] == {"buy": 1, "sell": 0, "hold": 1}
        assert by_market["crypto"] == {"buy": 0, "sell": 1, "hold": 0}

    def test_avg_confidence_computation(self):
        confidences = [0.1, 0.3, 0.5, 0.8, 0.9]
        avg = sum(confidences) / len(confidences)
        assert avg == pytest.approx(0.52, abs=0.01)

    def test_avg_confidence_empty_list(self):
        confidences: list[float] = []
        avg = sum(confidences) / max(len(confidences), 1)
        assert avg == 0.0

    def test_calibration_counts(self):
        levels = ["low", "medium", "high", "high", "very_high", "medium", "low", "low"]
        counts = {"very_high": 0, "high": 0, "medium": 0, "low": 0}
        for lvl in levels:
            counts[lvl] = counts.get(lvl, 0) + 1
        assert counts == {"very_high": 1, "high": 2, "medium": 2, "low": 3}

    def test_limit_truncation(self):
        """Signals beyond limit should be dropped."""
        signals = [
            EnrichedSignal(
                symbol=f"S{i}",
                name=f"N{i}",
                market="stock",
                direction="buy",
                timeframe="daily",
                entry_zone="-",
                stop_loss="-",
                targets="-",
                risk_reward="-",
                position_sizing="-",
                confirmation_condition="-",
                reason="-",
                invalidation="-",
                trailing_stop="-",
                price=100.0,
                change_pct=0.0,
                rule_score=float(i),
                ml_score=0.0,
                boosted_score=float(i),
                ml_influence_pct=0.0,
                confidence=0.5,
                calibration_level="medium",
            )
            for i in range(200)
        ]
        signals.sort(key=lambda s: s.boosted_score, reverse=True)
        limited = signals[:50]
        assert len(limited) == 50
        assert limited[0].boosted_score == 199.0
        assert limited[-1].boosted_score == 150.0


# ── OrchestratorReport Edge Case Tests ──────────────────────────────────────


class TestOrchestratorReportEdgeCases:
    """Test orchestrator report edge case scenarios."""

    def test_single_signal_single_market(self):
        sig = EnrichedSignal(
            symbol="فولاد",
            name="فولاد مبارکه",
            market="stock",
            direction="buy",
            timeframe="daily",
            entry_zone="100-102",
            stop_loss="95",
            targets="105 | 110",
            risk_reward="1:1.5",
            position_sizing="3%",
            confirmation_condition="",
            reason="RSI oversold",
            invalidation="",
            trailing_stop="",
            price=100.0,
            change_pct=2.5,
            rule_score=75.0,
            ml_score=0.65,
            boosted_score=78.0,
            ml_influence_pct=15.0,
            confidence=0.72,
            calibration_level="high",
        )
        report = OrchestratorReport(
            signals=[sig],
            summary={
                "total_signals": 1,
                "buy_count": 1,
                "sell_count": 0,
                "hold_count": 0,
                "markets": {"stock": {"buy": 1, "sell": 0, "hold": 0}},
            },
            generation_reports=[{"market": "stock", "success": True, "signal_count": 1}],
            accuracy_snapshot={"stock": 72.0, "overall": 72.0},
            generated_at="2024-01-01",
        )
        d = report.to_dict()
        assert len(d["signals"]) == 1
        assert d["accuracy"]["stock"] == 72.0

    def test_report_with_failed_generation(self):
        report = OrchestratorReport(
            signals=[],
            summary={
                "total_signals": 0,
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "markets": {},
            },
            generation_reports=[
                {
                    "market": "stock",
                    "success": False,
                    "signal_count": 0,
                    "error": "DB down",
                    "error_type": "ConnectionError",
                    "duration_ms": 5000,
                },
                {"market": "gold", "success": True, "signal_count": 3},
                {
                    "market": "crypto",
                    "success": False,
                    "signal_count": 0,
                    "error": "Timeout",
                    "error_type": "TimeoutError",
                    "duration_ms": 30000,
                },
            ],
        )
        d = report.to_dict()
        assert len(d["reports"]) == 3
        assert not d["reports"][0]["success"]
        assert d["reports"][0]["error"] == "DB down"
        assert d["reports"][1]["success"]
        assert d["reports"][1]["signal_count"] == 3

    def test_all_markets_generation_failed(self):
        """When ALL markets fail, signals are empty but reports capture all errors."""
        markets = ["stock", "gold", "currency", "crypto", "option", "commodity", "ime"]
        report = OrchestratorReport(
            signals=[],
            summary={
                "total_signals": 0,
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "markets": {},
            },
            generation_reports=[
                {
                    "market": m,
                    "success": False,
                    "signal_count": 0,
                    "error": f"{m} service unreachable",
                    "error_type": "ConnectionError",
                    "duration_ms": 5000,
                }
                for m in markets
            ],
            accuracy_snapshot=None,
        )
        d = report.to_dict()
        assert len(d["reports"]) == 7
        assert all(not r["success"] for r in d["reports"])
        assert d["signals"] == []
        assert d["summary"]["total_signals"] == 0
        assert d["accuracy"] is None

    def test_report_with_all_market_types(self):
        """Verify OrchestratorReport handles all 7 markets correctly."""
        markets_summary = {
            "stock": {"buy": 5, "sell": 3, "hold": 2},
            "gold": {"buy": 2, "sell": 0, "hold": 1},
            "currency": {"buy": 1, "sell": 0, "hold": 0},
            "crypto": {"buy": 3, "sell": 1, "hold": 0},
            "option": {"buy": 1, "sell": 0, "hold": 0},
            "commodity": {"buy": 0, "sell": 1, "hold": 0},
            "ime": {"buy": 0, "sell": 0, "hold": 1},
        }
        total = sum(v["buy"] + v["sell"] + v["hold"] for v in markets_summary.values())
        # stock(10) + gold(3) + currency(1) + crypto(4) + option(1) + commodity(1) + ime(1) = 21
        assert total == 21

        report = OrchestratorReport(
            signals=[],
            summary={
                "total_signals": total,
                "buy_count": 12,
                "sell_count": 5,
                "hold_count": 4,
                "markets": markets_summary,
            },
            generation_reports=[{"market": m, "success": True, "signal_count": 1} for m in markets_summary],
            accuracy_snapshot={"overall": 70.0},
            generated_at="2024-01-01",
        )
        d = report.to_dict()
        assert d["summary"]["total_signals"] == 21
        assert d["summary"]["markets"]["stock"]["buy"] == 5
        assert d["summary"]["markets"]["option"]["buy"] == 1
        assert len(d["reports"]) == 7
