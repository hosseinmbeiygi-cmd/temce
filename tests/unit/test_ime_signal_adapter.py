"""Tests for the IME signal adapter (سند v5.0 §4 + §20.2).

Covers the MarketSignal → PricingCandidate conversion, the conversion to
MarketState, the kill-switch integration, and the batch flow.
"""

from __future__ import annotations

from types import SimpleNamespace

from services.ime_signal_adapter import (
    IME_MARKETS,
    AdapterResult,
    _build_market_state,
    _infer_strategy_type,
    _infer_tick_size,
    _parse_persian_number,
    convert_signal,
    convert_signals,
    filter_ime_market_signals,
    market_signal_to_candidate,
)
from services.ime_signal_factory import RejectCode, SignalMaturity, StrategyType
from services.kill_switch import KillSwitch


def _signal(
    market: str = "option",
    symbol: str = "IRO1BMLT0001",
    price: float = 1_000_000.0,
    confidence: float = 0.7,
    strength: float = 0.6,
    direction: str = "buy",
    stop_loss: str = "950,000",
) -> SimpleNamespace:
    return SimpleNamespace(
        market=market,
        symbol=symbol,
        name="اختیار فولاد",
        price=price,
        change_pct=0.0,
        score=70.0,
        strength=strength,
        confidence=confidence,
        direction=direction,
        source="option_chain_v1",
        created_at="2026-08-29T00:00:00Z",
        entry_zone=str(price),
        stop_loss=stop_loss,
        targets="1,100,000",
        risk_reward="2.0",
        position_sizing="",
        confirmation_condition="",
        reason="",
        invalidation="",
        trailing_stop="",
        timeframe="daily",
    )


def _reset_kill_switch():
    KillSwitch.reset_singleton()
    from services import kill_switch as ks

    ks._LOCAL_STATE.update({"killed": False, "by": "", "reason": "", "at": 0.0})


class TestParsePersianNumber:
    def test_ascii_digits(self):
        assert _parse_persian_number("975000") == 975000.0
        assert _parse_persian_number("1,234,567") == 1234567.0

    def test_persian_digits(self):
        assert _parse_persian_number("۹۷۵,۰۰۰") == 975000.0

    def test_with_unit(self):
        assert _parse_persian_number("975,000 ریال") == 975000.0
        assert _parse_persian_number("(5.0%)") == 5.0

    def test_invalid(self):
        assert _parse_persian_number("") is None
        assert _parse_persian_number(None) is None
        assert _parse_persian_number("abc") is None

    def test_native_numbers(self):
        assert _parse_persian_number(42) == 42.0
        assert _parse_persian_number(3.14) == 3.14


class TestInferStrategyType:
    def test_ime_uses_calendar_arb(self):
        assert _infer_strategy_type("ime", "buy") is StrategyType.CALENDAR_ARB

    def test_option_uses_iv_mean_reversion(self):
        assert _infer_strategy_type("option", "buy") is StrategyType.IV_MEAN_REVERSION
        assert _infer_strategy_type("option", "sell") is StrategyType.IV_MEAN_REVERSION


class TestInferTickSize:
    def test_high_value(self):
        assert _infer_tick_size(50_000_000) == 10_000.0
        assert _infer_tick_size(5_000_000) == 1_000.0
        assert _infer_tick_size(50_000) == 100.0
        assert _infer_tick_size(500) == 1.0

    def test_zero_or_negative(self):
        assert _infer_tick_size(0) == 1.0
        assert _infer_tick_size(-1) == 1.0


class TestBuildMarketState:
    def test_extracts_price_and_stop(self):
        sig = _signal(price=1_000_000.0, stop_loss="950,000")
        state = _build_market_state(sig)
        assert state.proposed_price == 1_000_000.0
        assert state.stop_loss_distance > 0
        # stop is 5% below entry → stop_loss_distance ≈ 50_000
        assert 30_000 < state.stop_loss_distance < 60_000

    def test_safe_defaults_for_missing_stop(self):
        sig = _signal(stop_loss="")
        state = _build_market_state(sig)
        # Falls back to 2% default
        assert state.stop_loss_distance > 0


class TestMarketSignalToCandidate:
    def test_creates_pricing_candidate(self):
        sig = _signal(confidence=0.8, strength=0.7, price=1_000_000.0)
        cand = market_signal_to_candidate(signal=sig)
        assert cand.candidate_id
        assert sig.symbol in cand.instrument_keys
        assert cand.market_price == 1_000_000.0
        assert cand.strategy_type is StrategyType.IV_MEAN_REVERSION
        assert cand.model_confidence == 0.8
        assert 0 <= cand.data_quality <= 1.0
        assert cand.input_data_timestamp is not None

    def test_ime_uses_calendar_arb(self):
        sig = _signal(market="ime", confidence=0.5, price=2_000_000.0)
        cand = market_signal_to_candidate(signal=sig)
        assert cand.strategy_type is StrategyType.CALENDAR_ARB

    def test_zero_confidence(self):
        sig = _signal(confidence=0.0)
        cand = market_signal_to_candidate(signal=sig)
        # data_quality should be 0.5 default, model_confidence 0
        assert cand.model_confidence == 0.0
        assert 0.0 <= cand.data_quality <= 1.0


class TestFilterImeMarketSignals:
    def test_filters_option_and_ime(self):
        sigs = [
            _signal(market="option"),
            _signal(market="ime"),
            _signal(market="stock"),
            _signal(market="gold"),
        ]
        filtered = filter_ime_market_signals(sigs)
        assert len(filtered) == 2
        assert {s.market for s in filtered} == {"option", "ime"}

    def test_handles_missing_market_attr(self):
        # If a signal has no .market attribute, it's filtered out
        sigs = [_signal(market="stock"), SimpleNamespace(), _signal(market="option")]
        filtered = filter_ime_market_signals(sigs)
        assert len(filtered) == 1
        assert filtered[0].market == "option"


class TestConvertSignal:
    def setup_method(self):
        _reset_kill_switch()

    async def test_non_ime_market_returns_data_alert(self):
        sig = _signal(market="stock")
        result = await convert_signal(sig)
        assert result.maturity is SignalMaturity.DATA_ALERT
        assert result.reject_code is RejectCode.REJECTED_DATA_STALE
        assert "not in IME" in result.rejection_reason
        assert result.trade_card is None

    async def test_ime_market_high_confidence_releases(self):
        sig = _signal(market="ime", confidence=0.8, price=2_000_000.0)
        result = await convert_signal(sig)
        # ime maps to calendar_arb; with reasonable confidence + price, score
        # should be in the high tier and the card should be issued
        assert result.is_releasable, f"rejection_reason={result.rejection_reason}, reject={result.reject_code}"
        assert result.trade_card is not None

    async def test_low_confidence_may_reject(self):
        # 0 confidence + 0 strength → very low score → likely rejected on
        # cost or risk gates
        sig = _signal(market="option", confidence=0.0, price=0.0, stop_loss="")
        result = await convert_signal(sig)
        # Either DATA_ALERT (rejected) or TRADE_CARD is acceptable;
        # we just verify the adapter doesn't crash and the result is well-formed
        assert isinstance(result, AdapterResult)
        assert result.market == "option"

    async def test_kill_switch_blocks_release(self):
        sig = _signal(market="ime", confidence=0.9, price=2_000_000.0)
        # Activate kill switch via the async API (we're already in a loop)
        await KillSwitch().kill("admin", "test halt")
        result = await convert_signal(sig)
        assert result.maturity is SignalMaturity.DATA_ALERT
        assert "kill switch" in (result.rejection_reason or "")

    async def test_batch_convert(self):
        sigs = [
            _signal(market="option"),
            _signal(market="ime"),
            _signal(market="stock"),
        ]
        results = await convert_signals(sigs)
        assert len(results) == 3
        assert results[0].market == "option"
        assert results[1].market == "ime"
        assert results[2].market == "stock"  # filtered to DATA_ALERT


class TestToDict:
    async def test_adapter_result_to_dict(self):
        sig = _signal(market="ime", confidence=0.8)
        result = await convert_signal(sig)
        d = result.to_dict()
        assert "market" in d
        assert "symbol" in d
        assert "maturity" in d
        assert "is_releasable" in d
        if result.is_releasable:
            assert d["trade_card"] is not None
            assert "card_id" in d["trade_card"]
            assert "legs" in d["trade_card"]
            assert "net_edge" in d["trade_card"]


class TestImeMarketsConstant:
    def test_markets(self):
        assert frozenset({"option", "ime"}) == IME_MARKETS
