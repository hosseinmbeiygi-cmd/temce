"""The recommendation contract: scope gates, data gates, entry rules, position management."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from services.alert_engine import analytics, decision, risk
from services.alert_engine.settings import RiskSettings

NOW = datetime(2026, 11, 14, 7, 0, tzinfo=UTC)
TODAY = date(2026, 11, 14)
UP = [100.0 * 1.004 ** i for i in range(60)]          # steady uptrend, ~0.4%/day
DOWN = [100.0 * 0.996 ** i for i in range(60)]


def identity(category: str = "equity", supported: bool = True, **kw) -> dict:
    base = {"symbol": "تست", "name": "شرکت تست", "ins_id": "1", "isin": "IRO1TEST0001", "category": category,
            "category_label": category, "market": "بورس", "supported": supported, "trading_state": "مجاز",
            "limitations": [], "support_note": "پشتیبانی نمی‌شود" if not supported else None}
    base.update(kw)
    return base


def cov(**status: str) -> dict:
    out = {k: {"status": "valid", "detail": ""} for k in ("quote", "history", "market_breadth", "official_nav")}
    for key, value in status.items():
        out[key] = {"status": value, "detail": ""}
    return out


def snap(last: float = 10_000.0, bid: float = 9_995.0, ask: float = 10_000.0, vwap: float = 9_950.0) -> dict:
    return {"price_last": last, "price_close": last, "price_yesterday": 9_900.0, "price_min": 9_800.0, "price_max": 10_100.0,
            "trade_volume": 6_000_000, "trade_value": 6_000_000 * vwap, "bid_price_1": bid, "bid_volume_1": 500_000,
            "ask_price_1": ask, "ask_volume_1": 400_000}


def metrics(s: dict | None = None, closes: list[float] | None = None, low: float = 9_405.0, high: float = 10_395.0) -> dict:
    return analytics.market_metrics(s or snap(), low_limit=low, high_limit=high, avg_daily_volume=5_000_000, closes=closes or UP)


def portfolio(entries: list[dict] | None = None, marks: dict | None = None) -> dict:
    return risk.portfolio_state(RiskSettings(), entries or [], marks or {}, today=TODAY)


def ctx(**kw) -> dict:
    settings = kw.pop("settings", RiskSettings())
    m = kw.pop("metrics", metrics())
    pf = kw.pop("portfolio", portfolio())
    reg = kw.pop("regime", "favorable")
    base = {"identity": identity(), "coverage": cov(), "metrics": m, "regime": {"regime": reg, "reasons": ["test"]},
            "options": {"state": "none"}, "nav": None, "position": None, "portfolio": pf, "blocked": [],
            "settings": settings, "now": NOW, "market_open": True, "events": []}
    base.update(kw)
    if "sizing" not in base and m is not None and base["position"] is None:
        base["sizing"] = risk.size_position(
            settings, state=pf, regime=reg, symbol="تست", entry_price_rial=m["spread"]["ask"] or m["price_last"],
            daily_vol_pct=m["daily_volatility_pct"], spread_pct=m["spread"]["pct"], price_yesterday_rial=m["price_yesterday"],
            low_limit_rial=m["low_limit"], ask_depth_volume=m["ask_depth"]["volume"], avg_daily_volume=5_000_000,
            buy_fee=0.003712, sell_fee=0.0088)
    return base


def test_unsupported_instrument_reports_the_limitation_instead_of_an_analysis() -> None:
    rec = decision.build(ctx(identity=identity("rights", supported=False)))
    assert rec["state"] == "unsupported" and rec["entry"] is None and rec["reasons"] == ["پشتیبانی نمی‌شود"]


def test_option_contract_never_yields_a_trade_recommendation() -> None:
    rec = decision.build(ctx(identity=identity("option")))
    assert rec["state"] == "restricted" and rec["entry"] is None


def test_stale_or_missing_critical_data_blocks_entry_and_says_why() -> None:
    for gap in ({"quote": "stale"}, {"history": "missing"}, {"market_breadth": "stale"}, {"quote": "invalid"}):
        rec = decision.build(ctx(coverage=cov(**gap)))
        assert rec["state"] == "insufficient_data" and rec["entry"] is None
        assert next(iter(gap)) in rec["reasons"][0]
    assert decision.build(ctx(metrics=None))["state"] == "insufficient_data"
    # a stale NAV is non-critical: reported as missing information, not a block
    rec = decision.build(ctx(coverage=cov(official_nav="stale")))
    assert rec["state"] != "insufficient_data" and any("official_nav" in x for x in rec["missing"])


def test_conditional_entry_requires_every_condition_and_is_labelled_paper() -> None:
    rec = decision.build(ctx())
    assert rec["state"] == "conditional_entry" and rec["mode"] == "paper"
    assert rec["entry"]["units"] > 0 and rec["entry"]["planned_loss_toman"] <= 2_500_000
    assert rec["targets"] is None and rec["confidence"]["level"] == "low"
    assert "probability" not in rec and rec["invalidation_conditions"] and rec["supporting"]
    assert datetime.fromisoformat(rec["valid_until"]) - NOW == timedelta(minutes=15)


def test_conflicting_evidence_is_preserved_and_blocks_instead_of_being_outvoted() -> None:
    # strong trend + regime + volume in favour, but price below session VWAP → still waits
    rec = decision.build(ctx(metrics=metrics(snap(vwap=10_050.0))))
    assert rec["state"] == "await_confirmation"
    assert any(e["factor"] == "trend" for e in rec["supporting"]) and any(e["factor"] == "intraday_flow" for e in rec["opposing"])
    assert any("میانگین وزنی" in c for c in rec["activation_conditions"])
    assert decision.build(ctx(metrics=metrics(closes=DOWN)))["state"] == "await_confirmation"


def test_wide_spread_and_closed_market_only_wait() -> None:
    wide = decision.build(ctx(metrics=metrics(snap(bid=9_700.0))))
    assert wide["state"] == "await_confirmation" and any(e["factor"] == "liquidity" for e in wide["opposing"])
    closed = decision.build(ctx(market_open=False))
    assert closed["state"] == "await_confirmation" and "بازار بسته" in closed["activation_conditions"][0]


def test_locked_sell_queue_halt_and_risk_controls_mean_no_trade() -> None:
    locked = snap(last=9_405.0, bid=9_300.0, ask=9_405.0, vwap=9_600.0)
    assert decision.build(ctx(metrics=metrics(locked)))["state"] == "no_trade"
    buy_locked = {**snap(last=10_395.0, bid=10_395.0, vwap=10_300.0), "ask_price_1": 0, "ask_volume_1": 0}
    waiting = decision.build(ctx(metrics=metrics(buy_locked)))
    assert waiting["state"] == "await_confirmation" and "صف خرید" in waiting["reasons"][0] and waiting["entry"] is None
    assert decision.build(ctx(identity=identity(trading_state="ممنوع-متوقف")))["state"] == "no_trade"
    assert decision.build(ctx(regime="unfavorable"))["state"] == "no_trade"
    blocked = decision.build(ctx(blocked=["daily-loss threshold breached"]))
    assert blocked["state"] == "no_trade" and blocked["reasons"] == ["daily-loss threshold breached"]
    expensive = snap(last=3e9, bid=2.999e9, ask=3e9, vwap=2.9e9)
    rec = decision.build(ctx(metrics=metrics(expensive, low=2.8e9, high=3.2e9)))
    assert rec["state"] == "no_trade" and "نمی‌گنجد" in rec["reasons"][0]


def held(qty: float = 10_000, price: float = 10_000.0, last: float = 10_000.0) -> tuple[dict, dict]:
    entries = [{"entry_type": "buy", "book": "actual", "symbol": "تست", "quantity": qty, "price_rial": price,
                "fees_toman": 0.0, "executed_at": NOW - timedelta(days=2)}]
    pf = portfolio(entries, {"تست": {"price_rial": last, "price_yesterday_rial": 9_900.0, "quality": "valid"}})
    return pf["positions"][0], pf


def test_confirmed_position_in_a_locked_queue_is_involuntary_not_a_hold_recommendation() -> None:
    pos, pf = held(last=9_405.0)
    locked = snap(last=9_405.0, bid=9_300.0, ask=9_405.0, vwap=9_600.0)
    rec = decision.build(ctx(position=pos, portfolio=pf, metrics=metrics(locked)))
    assert rec["state"] == "exit_infeasible" and rec["subject"] == "confirmed_position"
    assert rec["exit_assessment"]["class"] == "C" and rec["exit_assessment"]["share_of_position_at_visible_bids"] == 0
    assert "دلیلِ مطلوب بودن نگهداری نیست" in rec["reasons"][0]
    assert rec["exit_assessment"]["overnight"]["gap_scenario"]["loss_toman"] > 0


def test_stop_hit_recommends_exit_but_never_records_one() -> None:
    pos, pf = held(qty=100_000, last=9_600.0)  # 100M toman position, 4M toman open loss
    rec = decision.build(ctx(position=pos, portfolio=pf, metrics=metrics(snap(last=9_600.0, bid=9_595.0, ask=9_600.0))))
    assert rec["state"] == "exit" and rec["exit_assessment"]["class"] == "A"
    assert pf["positions"][0]["quantity"] == 100_000 and "تأیید اجرا" in rec["reasons"][0]
    assert any("بودجهٔ ریسک" in x for x in rec["portfolio_implications"])  # 4M open loss > 2.5M budget


def test_healthy_position_holds_and_partial_exit_capacity_is_stated() -> None:
    pos, pf = held(qty=2_000_000, price=10_000.0)  # far larger than the visible bids
    pf["cash_toman"] = 0
    rec = decision.build(ctx(position=pos, portfolio=pf))
    assert rec["state"] == "hold" and rec["exit_assessment"]["share_of_position_at_visible_bids"] == 0.25
    stale = decision.build(ctx(position=pos, portfolio=pf, coverage=cov(quote="stale")))
    assert stale["state"] == "insufficient_data" and stale["exit_assessment"]["class"] == "D"
    weak = decision.build(ctx(position=pos, portfolio=pf, metrics=metrics(snap(vwap=10_080.0), closes=DOWN)))
    assert weak["state"] == "reduce"
