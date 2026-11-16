"""Deterministic core of the alert engine: settings, analytics, risk, options, regime, notifier."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from services.alert_engine import analytics, notifier, options_view, regime, risk
from services.alert_engine.settings import (
    EngineSettings,
    NotificationPrefs,
    RiskSettings,
    SettingsError,
    loosens_risk,
    rial_to_toman,
)

T0 = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)
TODAY = date(2026, 11, 14)

# The real «موج» snapshot of 2026-11-14 (session closed locked at the lower limit).
MOJ = {
    "price_last": 115327.0, "price_close": 116358.0, "price_yesterday": 122688.0, "price_min": 115327.0,
    "price_max": 121207.0, "price_last_change_pct": -6.0, "trade_volume": 188100652, "trade_value": 21886966582314.0,
    "bid_price_1": 111628.0, "bid_volume_1": 200, "bid_count_1": 1, "bid_price_2": 111625.0, "bid_volume_2": 1810,
    "ask_price_1": 115327.0, "ask_volume_1": 2552342, "ask_count_1": 154, "ask_price_2": 115329.0, "ask_volume_2": 4751,
}
MOJ_LOW, MOJ_HIGH = 115327.0, 130049.0


def liquid_snap(last: float = 10_000.0, bid: float = 9_990.0, ask: float = 10_000.0) -> dict:
    return {"price_last": last, "price_close": last, "price_yesterday": last * 0.99, "price_min": last * 0.98,
            "price_max": last * 1.01, "trade_volume": 5_000_000, "trade_value": 5_000_000 * last * 0.995,
            "bid_price_1": bid, "bid_volume_1": 400_000, "ask_price_1": ask, "ask_volume_1": 300_000}


# ── settings ────────────────────────────────────────────────────────────────────────────

def test_default_budgets_match_the_agreed_starting_values() -> None:
    r = RiskSettings()
    assert r.capital_toman == 500_000_000 and r.currency == "IRT"
    assert r.budgets_toman(r.capital_toman) == {"per_trade_risk": 2_500_000, "daily_loss_stop": 7_500_000,
                                                 "drawdown_review": 25_000_000}
    assert (r.ceiling_for("favorable"), r.ceiling_for("neutral")) == (100, 60)
    assert r.ceiling_for("disrupted") == 0 and r.ceiling_for("anything-else") == 0


def test_rial_toman_conversion_is_central_and_exact() -> None:
    assert rial_to_toman(1_153_270) == 115_327 and rial_to_toman(None) is None and rial_to_toman(0) == 0


def test_settings_reject_unknown_keys_and_inconsistent_values() -> None:
    s = EngineSettings()
    with pytest.raises(SettingsError):
        s.merged({"risk": {"no_such_key": 1}})
    with pytest.raises(SettingsError):
        s.merged({"risk": {"ceiling_neutral_pct": 100, "ceiling_favorable_pct": 80}})
    with pytest.raises(SettingsError):
        s.merged({"risk": {"max_single_instrument_pct": 100}})  # needs explicit acceptance
    with pytest.raises(SettingsError):
        s.merged({"risk": {"mode": "live"}})
    with pytest.raises(SettingsError):
        s.merged({"notifications": {"quiet_start": "22:00"}})
    ok = s.merged({"risk": {"max_single_instrument_pct": 100, "full_single_allocation_accepted": True}})
    assert ok.risk.max_single_instrument_pct == 100


def test_loosening_is_detected_and_tightening_is_not() -> None:
    old = RiskSettings()
    assert loosens_risk(old, RiskSettings(per_trade_risk_pct=1.0)) == ["per_trade_risk_pct"]
    assert loosens_risk(old, RiskSettings(per_trade_risk_pct=0.25, daily_loss_stop_pct=1.0)) == []
    assert "halt_new_entries" in loosens_risk(RiskSettings(halt_new_entries=True), old)
    roundtrip = EngineSettings.from_dict(EngineSettings().to_dict())
    assert roundtrip == EngineSettings()


# ── analytics ───────────────────────────────────────────────────────────────────────────

def test_locked_sell_queue_is_detected_from_actual_limits() -> None:
    q = analytics.queue_state(MOJ, MOJ_LOW, MOJ_HIGH)
    assert q["state"] == "sell_queue" and q["volume"] == 2552342 and q["orders"] == 154
    # bids below the lower limit cannot trade today and are not executable depth
    assert analytics.executable_depth(MOJ, "bid", MOJ_LOW, MOJ_HIGH)["volume"] == 0


def test_queue_state_is_unknown_without_verified_limits() -> None:
    assert analytics.queue_state(MOJ, None, None)["state"] == "unknown"
    assert analytics.queue_state(liquid_snap(), 9_500, 10_500)["state"] == "none"
    buy = {"bid_price_1": 10_500.0, "bid_volume_1": 9_000_000, "bid_count_1": 300}
    assert analytics.queue_state(buy, 9_500, 10_500)["state"] == "buy_queue"


def test_zero_missing_and_invalid_are_distinct() -> None:
    assert analytics._num(0) == 0.0 and analytics._num(None) is None and analytics._num("x") is None
    assert analytics.validate_quote({"price_last": None}) == ["price_last missing"]
    assert analytics.validate_quote({"price_last": 0}) == ["price_last is not positive"]
    assert "price_last outside the day's min/max" in analytics.validate_quote(
        {"price_last": 120, "price_min": 100, "price_max": 110})
    assert analytics.validate_quote(liquid_snap()) == []
    assert analytics.spread({})["state"] == "empty"
    assert analytics.spread({"bid_price_1": 5, "bid_volume_1": 1})["state"] == "one_sided"
    assert analytics.spread({"bid_price_1": 11, "bid_volume_1": 1, "ask_price_1": 10, "ask_volume_1": 1})["state"] == "crossed"


def test_history_metrics_need_enough_clean_data() -> None:
    assert analytics.daily_volatility_pct([100.0, 101.0, 100.5]) is None
    closes = [100.0 * (1.01 if i % 2 else 0.99) ** 1 for i in range(40)]
    assert analytics.daily_volatility_pct(closes) == pytest.approx(2.03, abs=0.1)
    assert analytics.horizon_return_pct([100.0, 110.0], 5) is None
    # an unadjusted corporate action shows up as a discontinuity and truncates the usable stretch
    split = [1000.0] * 30 + [500.0] * 25
    assert analytics.discontinuities(split) == [30]
    m = analytics.market_metrics(liquid_snap(500.0, 499.0, 500.0), low_limit=470, high_limit=530,
                                 avg_daily_volume=1_000_000, closes=split)
    assert m["history_discontinuities"] == 1 and m["return_20d_pct"] == 0.0


# ── risk: ledger + portfolio ────────────────────────────────────────────────────────────

def entry(kind: str, when: datetime, **kw) -> dict:
    return {"entry_type": kind, "book": "actual", "executed_at": when, "fees_toman": 0.0, **kw}


def test_ledger_rejects_invalid_and_oversold_entries() -> None:
    with pytest.raises(risk.LedgerError):
        risk.validate_entry(entry("buy", T0, symbol="A", quantity=0, price_rial=100))
    with pytest.raises(risk.LedgerError):
        risk.validate_entry(entry("buy", T0, symbol="A", quantity=10.5, price_rial=100))
    with pytest.raises(risk.LedgerError):
        risk.validate_entry(entry("sell", T0, symbol="A", quantity=11, price_rial=100), {"A": 10})
    with pytest.raises(risk.LedgerError):
        risk.validate_entry({"entry_type": "transfer", "book": "actual"})
    risk.validate_entry(entry("sell", T0, symbol="A", quantity=4, price_rial=100), {"A": 10})  # partial fill is fine


def test_monitoring_without_ledger_entries_means_no_position_and_full_cash() -> None:
    state = risk.portfolio_state(RiskSettings(), [], {}, today=TODAY)
    assert state["positions"] == [] and state["cash_toman"] == 500_000_000 and state["exposure_toman"] == 0


def test_paper_and_actual_books_are_separate() -> None:
    entries = [{**entry("buy", T0, symbol="A", quantity=1000, price_rial=100_000), "book": "paper"}]
    assert risk.portfolio_state(RiskSettings(), entries, {}, today=TODAY)["positions"] == []
    assert len(risk.portfolio_state(RiskSettings(), entries, {}, today=TODAY, book="paper")["positions"]) == 1


def test_daily_loss_includes_unrealised_and_carried_positions() -> None:
    yesterday = T0 - timedelta(days=1)
    entries = [entry("buy", yesterday, symbol="A", quantity=20_000, price_rial=100_000, fees_toman=0)]  # 200M toman
    marks = {"A": {"price_rial": 95_000, "price_yesterday_rial": 100_000, "quality": "valid"}}
    state = risk.portfolio_state(RiskSettings(), entries, marks, today=TODAY)
    assert state["daily"]["pnl_toman"] == pytest.approx(-10_000_000)
    assert state["daily"]["loss_breached"] is True  # 10M > 7.5M
    assert "حد زیان روزانه" in " ".join(risk.new_entries_blocked(RiskSettings(), state))
    assert state["positions"][0]["quantity"] == 20_000  # still shown; no exit is assumed


def test_deposits_are_not_performance_and_drawdown_is_flow_adjusted() -> None:
    entries = [entry("deposit", T0, amount_toman=100_000_000)]
    state = risk.portfolio_state(RiskSettings(), entries, {}, today=TODAY, hwm_toman=500_000_000, hwm_flows_toman=0)
    assert state["equity_toman"] == 600_000_000 and state["daily"]["pnl_toman"] == 0
    assert state["drawdown"]["high_water_mark_toman"] == 600_000_000 and state["drawdown"]["pct"] == 0
    losing = [entry("buy", T0 - timedelta(days=3), symbol="A", quantity=40_000, price_rial=100_000)]
    marks = {"A": {"price_rial": 93_000, "price_yesterday_rial": 93_500, "quality": "valid"}}
    dd = risk.portfolio_state(RiskSettings(), losing, marks, today=TODAY, hwm_toman=500_000_000)
    assert dd["drawdown"]["pct"] == pytest.approx(5.6) and dd["drawdown"]["review_required"] is True


def test_unmarked_position_is_carried_at_cost_and_flagged() -> None:
    entries = [entry("buy", T0, symbol="A", quantity=1000, price_rial=100_000)]
    state = risk.portfolio_state(RiskSettings(), entries, {"A": {"price_rial": 90_000, "quality": "stale"}}, today=TODAY)
    assert state["equity_complete"] is False and state["unmarked_symbols"] == ["A"]
    assert state["positions"][0]["value_toman"] == 10_000_000 and state["positions"][0]["unrealized_pnl_toman"] is None


def size(state: dict, regime_name: str = "favorable", **kw) -> dict:
    args = {"symbol": "B", "entry_price_rial": 100_000.0, "daily_vol_pct": 2.0, "spread_pct": 0.1,
            "price_yesterday_rial": 100_000.0, "low_limit_rial": 95_000.0, "ask_depth_volume": 10_000_000,
            "avg_daily_volume": 1_000_000_000, "buy_fee": 0.002245, "sell_fee": 0.0023}
    args.update(kw)
    return risk.size_position(RiskSettings(), state=state, regime=regime_name, **args)


def test_sizing_uses_the_tightest_constraint_and_shared_cash() -> None:
    empty = risk.portfolio_state(RiskSettings(), [], {}, today=TODAY)
    s = size(empty)
    assert s["binding"] in ("risk_budget", "stress_gap") and s["units"] > 0
    assert s["planned_loss_toman"] <= 2_500_000
    # one capital pool: after a 280M position, a second idea sees only the remaining cash/ceiling
    held = [entry("buy", T0 - timedelta(days=1), symbol="A", quantity=28_000, price_rial=100_000)]
    marks = {"A": {"price_rial": 100_000, "price_yesterday_rial": 100_000, "quality": "valid"}}
    busy = risk.portfolio_state(RiskSettings(), held, marks, today=TODAY)
    neutral = size(busy, "neutral")
    assert neutral["constraints"]["regime_ceiling"] == 2_000  # 60% of 500M − 280M = 20M toman
    assert neutral["constraints"]["available_cash"] < size(empty)["constraints"]["available_cash"]
    assert size(busy, "unfavorable")["units"] == 0


def test_tight_stop_never_inflates_size_and_tiny_budget_means_no_trade() -> None:
    empty = risk.portfolio_state(RiskSettings(), [], {}, today=TODAY)
    calm, calmer = size(empty, daily_vol_pct=0.5), size(empty, daily_vol_pct=0.01)
    assert calm["stop_distance_pct"] == calmer["stop_distance_pct"] == 2.0
    assert calm["constraints"]["risk_budget"] == calmer["constraints"]["risk_budget"]
    pricey = size(empty, entry_price_rial=2_000_000_000.0, price_yesterday_rial=2_000_000_000.0, low_limit_rial=1_900_000_000.0)
    assert pricey["units"] == 0 and "نمی‌گنجد" in pricey["reason"]
    assert size(empty, daily_vol_pct=None)["units"] == 0
    thin = size(empty, ask_depth_volume=50)
    assert thin["binding"] == "visible_depth" and thin["units"] == 50
    assert "stress_gap (daily limits unavailable)" in size(empty, low_limit_rial=None)["not_measured"]


# ── options ─────────────────────────────────────────────────────────────────────────────

def opt_row(**kw) -> dict:
    row = {"symbol": "ضتست1", "option_type": "call", "strike_price": 10_000.0, "days_remaining": 30, "contract_size": 1000,
           "open_interest": 500, "price_last": 700.0, "trade_volume": 120, "bid_price_1": 690.0, "ask_price_1": 710.0}
    row.update(kw)
    return row


def test_no_options_unavailable_and_stale_are_different_states() -> None:
    kw = {"spot": 10_000.0, "rate": 0.3}
    assert options_view.summarize([], feed_state="none", **kw)["state"] == "none"
    assert options_view.summarize(None, feed_state="unavailable", **kw)["state"] == "unavailable"
    stale = options_view.summarize([opt_row()], feed_state="stale", **kw)
    assert stale["state"] == "stale" and stale["contracts"] == []
    assert options_view.summarize([opt_row()], feed_state="available", spot=None, rate=0.3)["state"] == "unavailable"


def test_iv_is_only_solved_from_valid_quotes() -> None:
    rows = [opt_row(), opt_row(symbol="wide", bid_price_1=300.0, ask_price_1=900.0),
            opt_row(symbol="onesided", bid_price_1=0.0), opt_row(symbol="expired", days_remaining=0),
            opt_row(symbol="put", option_type="put", bid_price_1=400.0, ask_price_1=420.0, trade_volume=60)]
    out = options_view.summarize(rows, spot=10_000.0, rate=0.3, feed_state="available")
    by = {c["symbol"]: c for c in out["contracts"]}
    assert 0.05 < by["ضتست1"]["iv"] < 3 and by["ضتست1"]["greeks"]["delta"] > 0
    assert by["wide"]["iv"] is None and "too wide" in by["wide"]["iv_reason"]
    assert by["onesided"]["iv"] is None and by["expired"]["iv"] is None
    assert out["summary"]["put_call_volume_ratio"] == pytest.approx(60 / 480)
    assert "descriptive only" in out["summary"]["ratio_note"] and "no options-trading" in out["scope"]


# ── regime ──────────────────────────────────────────────────────────────────────────────

def breadth(adv: float, med: float, heavy: float = 0.02, total: int = 1500) -> dict:
    return {"total": total, "advancers_share": adv, "decliners_share": 1 - adv, "median_change_pct": med,
            "down_4pct_share": heavy, "up_4pct_share": 0.02}


def test_regime_is_disrupted_without_trustworthy_market_data() -> None:
    assert regime.classify(None, data_state="valid")["regime"] == "disrupted"
    assert regime.classify(breadth(0.7, 1.0), data_state="stale")["regime"] == "disrupted"
    assert regime.classify(breadth(0.7, 1.0, total=50), data_state="valid")["regime"] == "disrupted"


def test_regime_uses_breadth_not_index_sign_and_resists_noise() -> None:
    assert regime.classify(breadth(0.70, 1.2), data_state="valid")["regime"] == "favorable"
    assert regime.classify(breadth(0.70, 1.2), data_state="valid", equal_weight_change_pct=-0.4)["regime"] == "neutral"
    assert regime.classify(breadth(0.62, 0.8), data_state="valid", previous="neutral")["regime"] == "neutral"  # hysteresis
    assert regime.classify(breadth(0.62, 0.8), data_state="valid", previous="favorable")["regime"] == "favorable"
    bad = regime.classify(breadth(0.30, -2.0, heavy=0.4), data_state="valid", previous="favorable")
    assert bad["regime"] == "unfavorable" and bad["experimental"] and not bad["calibrated"]  # no delay on deterioration
    out = regime.breadth_from_changes([1.0, -1.0, -5.0, 2.0])
    assert out["advancers_share"] == 0.5 and out["down_4pct_share"] == 0.25 and out["median_change_pct"] == 0.0


# ── notifier (pure parts) ───────────────────────────────────────────────────────────────

def test_quiet_hours_wrap_midnight_in_tehran_time() -> None:
    prefs = NotificationPrefs(telegram_enabled=True, quiet_start="22:00", quiet_end="07:00")
    late = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)   # 23:30 Tehran
    noon = datetime(2026, 11, 14, 8, 30, tzinfo=UTC)   # 12:00 Tehran
    assert notifier.in_quiet_hours(prefs, late) and not notifier.in_quiet_hours(prefs, noon)
    assert notifier.initial_telegram_state(prefs, "critical", late) == "suppressed_quiet"
    approved = NotificationPrefs(telegram_enabled=True, quiet_start="22:00", quiet_end="07:00", critical_during_quiet=True)
    assert notifier.initial_telegram_state(approved, "critical", late) == "queued"
    assert notifier.initial_telegram_state(approved, "opportunity", late) == "suppressed_quiet"
    assert notifier.initial_telegram_state(NotificationPrefs(), "critical", noon) == "not_requested"


def test_bot_token_never_survives_in_error_text() -> None:
    leaked = "Client error for url 'https://api.telegram.org/bot123456789:AAE-abc_DEF/sendMessage'"
    assert "AAE-abc_DEF" not in notifier.redact(leaked) and "bot<redacted>" in notifier.redact(leaked)
    from integrations.notifications.telegram_sender import _redact_token

    assert "AAE-abc_DEF" not in _redact_token(leaked)
