"""Antigravity Signal Engine — تولید سیگنال ساختاریافته با تمام متریک‌ها.

ترکیب: NAV Premium + Coin Bubble + Arbitrage + Dollar-Adjusted + Futures Risk + Kill-Switch
خروجی: AntigravitySignal (Output Schema استاندارد)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from .assets import ETF_ASSETS
from .calculations import (
    FuturesRiskCalculator,
    calculate_coin_bubble,
    calculate_dollar_adjusted_return,
    calculate_nav_premium,
    scan_gold_arbitrage,
)
from .kill_switch import KillSwitchStatus, evaluate_kill_switch
from .signal_schema import (
    AntigravitySignal,
    LeverageAndMargin,
    SignalAction,
    SignalAsset,
    SignalMetrics,
    build_trade_parameters,
    risk_level_from_health,
)


def _confidence_from_signals(
    nav_signal: str,
    bubble_signal: str,
    arbitrage_action: str,
    kill_status: str,
) -> float:
    """امتیاز اطمینان 0-1 بر اساس همگرایی سیگنال‌ها."""
    if kill_status == "ACTIVE":
        return 0.0
    score = 0.5  # base
    # NAV هم‌جهت
    if nav_signal == "BUY":
        score += 0.15
    elif nav_signal == "SELL":
        score -= 0.15
    # Bubble هم‌جهت
    if bubble_signal == "BUY":
        score += 0.15
    elif bubble_signal == "SELL":
        score -= 0.10
    # Arbitrage تأیید
    if arbitrage_action == "BUY_ETF_SELL_PHYSICAL":
        score += 0.10
    elif arbitrage_action == "BUY_PHYSICAL_SELL_ETF":
        score -= 0.05
    if kill_status == "WARNING":
        score -= 0.15
    return max(0.0, min(1.0, round(score, 2)))


def _decide_action(
    nav_signal: str,
    bubble_signal: str,
    kill_status: str,
) -> Literal["BUY", "SELL", "HOLD", "CLOSE"]:
    if kill_status == "ACTIVE":
        return "CLOSE"
    # همگرایی BUY
    if nav_signal == "BUY" and bubble_signal in ("BUY", "NEUTRAL"):
        return "BUY"
    if bubble_signal == "BUY" and nav_signal in ("BUY", "NEUTRAL"):
        return "BUY"
    # همگرایی SELL
    if nav_signal == "SELL" or bubble_signal == "SELL":
        # اگر هر دو SELL => SELL قوی، اگر یکی SELL و دیگری NEUTRAL => HOLD محتاط
        if nav_signal == "SELL" and bubble_signal == "SELL":
            return "SELL"
        if nav_signal == "SELL" and bubble_signal == "NEUTRAL":
            return "SELL"
        if bubble_signal == "SELL" and nav_signal == "NEUTRAL":
            return "SELL"
        # تضاد BUY vs SELL => HOLD
        return "HOLD"
    return "HOLD"


def generate_antigravity_signal(
    *,
    etf_name: str,  # کلید ETF_ASSETS: زرافشان/لوتوس/گوهر/ثامان
    market_price: float,
    nav: float,
    coin_price_irr: float,
    gold_oz_usd: float,
    usd_rate: float,
    # برای آربیتراژ
    etf_price_per_gram: float | None = None,
    physical_gold_price_per_gram: float | None = None,
    # برای بازده دلاری
    entry_value_irr: float | None = None,
    entry_usd_rate: float | None = None,
    # برای آتی
    leverage: int = 1,
    position_type: str = "LONG",
    equity: float | None = None,
    # برای Kill-Switch
    kill_switch_status: KillSwitchStatus | None = None,
    ounce_change_2h_pct: float | None = None,
    usd_change_2h_pct: float | None = None,
) -> AntigravitySignal:
    """تولید سیگنال کامل Antigravity.

    تمام محاسبات با فرمول‌های دقیق spec انجام می‌شود.
    """
    etf_info = ETF_ASSETS.get(etf_name)
    if not etf_info:
        raise ValueError(f"unknown ETF: {etf_name}. Valid: {list(ETF_ASSETS.keys())}")

    # 1. NAV Premium
    nav_res = calculate_nav_premium(market_price, nav)

    # 2. Coin Bubble
    bubble_res = calculate_coin_bubble(coin_price_irr, gold_oz_usd, usd_rate)

    # 3. Arbitrage (اختیاری)
    arb_res = None
    if etf_price_per_gram and physical_gold_price_per_gram:
        arb_res = scan_gold_arbitrage(etf_price_per_gram, physical_gold_price_per_gram)

    # 4. Dollar-Adjusted (اختیاری)
    dollar_res = None
    if entry_value_irr and entry_usd_rate:
        dollar_res = calculate_dollar_adjusted_return(entry_value_irr, market_price, entry_usd_rate, usd_rate)

    # 5. Kill-Switch
    if kill_switch_status is None:
        kill_switch_status = evaluate_kill_switch(
            ounce_change_2h_pct=ounce_change_2h_pct,
            usd_change_2h_pct=usd_change_2h_pct,
        )

    # 6. Futures Risk (اگر اهرمی)
    liq_price: float | None = None
    health: float | None = None
    risk_level: str = "LOW"
    if leverage > 1:
        calc = FuturesRiskCalculator(leverage=leverage)
        liq_price = calc.calculate_liquidation_price(market_price, position_type)
        if equity is not None:
            # تخمین position_value = market_price * contract_size (10 سکه)
            position_value = market_price * 10  # ساده‌سازی؛ در واقع should be per contract
            used_margin = position_value * calc.initial_margin_ratio
            health = calc.health_ratio(equity, used_margin)
        risk_level = risk_level_from_health(health, leverage)

    # 7. تصمیم و اطمینان
    arb_action = arb_res.action if arb_res else "NO_ARBITRAGE"
    action = _decide_action(nav_res.signal, bubble_res.signal, kill_switch_status.status)
    confidence = _confidence_from_signals(nav_res.signal, bubble_res.signal, arb_action, kill_switch_status.status)

    # 8. سطوح معاملاتی (بر اساس ATR ساده 1.5% و R/R 2:1)
    # BUY: SL -3%, TP1 +3%, TP2 +6%  |  SELL: SL +3%, TP1 -3%, TP2 -5%
    if action == "BUY":
        sl = market_price * 0.97
        tp1 = market_price * 1.03
        tp2 = market_price * 1.06
        timeframe: Literal["SCALP", "INTRADAY", "SWING", "LONG_TERM"] = "SWING"
    elif action == "SELL":
        sl = market_price * 1.03
        tp1 = market_price * 0.97
        tp2 = market_price * 0.94
        timeframe = "INTRADAY"
    else:  # HOLD/CLOSE
        sl = market_price * 0.97
        tp1 = market_price * 1.02
        tp2 = market_price * 1.04
        timeframe = "SWING"
        if action == "CLOSE":
            confidence = 0.95  # خروج اضطراری با اطمینان بالا

    # اگر Kill-Switch ACTIVE => بستن با SL نزدیک
    if kill_switch_status.status == "ACTIVE":
        timeframe = "SCALP"
        sl = market_price * 0.99 if action == "CLOSE" else sl

    trade_params = build_trade_parameters(market_price, sl, tp1, tp2)

    # 9. Rationale
    parts: list[str] = []
    parts.append(f"NAV: {nav_res.reason}")
    parts.append(f"حباب سکه: {bubble_res.reason}")
    if arb_res:
        parts.append(f"آربیتراژ: {arb_res.strategy} (خالص {arb_res.net_spread_pct:+.2f}%)")
    if dollar_res:
        parts.append(
            f"بازده دلاری مورد انتظار: {dollar_res.dollar_roi_pct:+.2f}% (ریالی {dollar_res.irr_roi_pct:+.2f}%)"
        )
    if kill_switch_status.status != "NORMAL":
        parts.append(f"⚠️ Kill-Switch {kill_switch_status.status}: {kill_switch_status.reason}")
    if leverage > 1 and liq_price:
        parts.append(
            f"اهرم {leverage}x — لیکوئید: {liq_price:,.0f} — سلامت: {health:.2f}"
            if health
            else f"اهرم {leverage}x — لیکوئید: {liq_price:,.0f}"
        )
    rationale = " | ".join(parts)

    # 10. ساخت خروجی نهایی
    return AntigravitySignal(
        timestamp=datetime.now(UTC),
        asset=SignalAsset(
            symbol=etf_info["symbol"],
            market="TSE",
            current_price=market_price,
        ),
        signal=SignalAction(action=action, confidence_score=confidence, timeframe=timeframe),
        trade_parameters=trade_params,
        metrics=SignalMetrics(
            nav_premium_pct=round(nav_res.premium_pct, 2),
            coin_bubble_pct=round(bubble_res.bubble_pct, 2),
            gold_usd_correlation=None,  # نیاز به سری زمانی 30 روزه
            dollar_adjusted_expected_roi=dollar_res.dollar_roi_pct if dollar_res else None,
            gross_spread_pct=arb_res.gross_spread_pct if arb_res else None,
            net_spread_pct=arb_res.net_spread_pct if arb_res else None,
        ),
        leverage_and_margin=LeverageAndMargin(
            leverage=leverage,
            liquidation_price=round(liq_price, 0) if liq_price else None,
            health_ratio=round(health, 2) if health and health != float("inf") else None,
            risk_level=risk_level,  # type: ignore
        ),
        rationale=rationale,
        kill_switch_status=kill_switch_status.status,  # type: ignore
    )
