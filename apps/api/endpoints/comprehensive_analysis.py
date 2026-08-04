from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_brsapi_query_service
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _calc_support_resistance(history: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [h.get("close", 0) or 0 for h in history if h.get("close")]
    highs = [h.get("high", 0) or 0 for h in history if h.get("high")]
    lows = [h.get("low", 0) or 0 for h in history if h.get("low")]
    if not closes:
        return {"support1": 0, "support2": 0, "resistance1": 0, "resistance2": 0}

    current = closes[-1]
    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)

    return {
        "resistance2": round(recent_high * 1.05),
        "resistance1": round(recent_high),
        "current_price": round(current),
        "support1": round(recent_low),
        "support2": round(recent_low * 0.95),
    }


def _calc_moving_averages(closes: list[float]) -> dict[str, float | None]:
    if not closes:
        return {"sma_20": None, "sma_50": None, "sma_200": None}
    sma20 = sum(closes[-20:]) / min(len(closes[-20:]), 20) if len(closes) >= 20 else None
    sma50 = sum(closes[-50:]) / min(len(closes[-50:]), 50) if len(closes) >= 50 else None
    sma200 = sum(closes[-200:]) / min(len(closes[-200:]), 200) if len(closes) >= 200 else None
    return {"sma_20": round(sma20) if sma20 else None, "sma_50": round(sma50) if sma50 else None, "sma_200": round(sma200) if sma200 else None}


def _calc_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses += abs(diff)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _calc_macd(closes: list[float]) -> dict[str, Any]:
    if len(closes) < 26:
        return {"macd": None, "signal": None, "histogram": None, "signal_type": "neutral"}
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = ema12[-1] - ema26[-1] if ema12 and ema26 else 0
    signal_line = _ema([ema12[i] - ema26[i] for i in range(len(ema12))], 9)[-1] if len(ema12) >= 9 else 0
    if macd_line > signal_line:
        signal_type = "buy"
    elif macd_line < signal_line:
        signal_type = "sell"
    else:
        signal_type = "neutral"
    return {"macd": round(macd_line, 1), "signal": round(signal_line, 1), "histogram": round(macd_line - signal_line, 1), "signal_type": signal_type}


def _ema(data: list[float], period: int) -> list[float]:
    if len(data) < period:
        return []
    multiplier = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append((price - result[-1]) * multiplier + result[-1])
    return result


def _calc_bollinger(closes: list[float], period: int = 20) -> dict[str, Any]:
    if len(closes) < period:
        return {"upper": None, "middle": None, "lower": None, "band_width": None}
    sma = sum(closes[-period:]) / period
    variance = sum((c - sma) ** 2 for c in closes[-period:]) / period
    std = math.sqrt(variance)
    return {
        "upper": round(sma + 2 * std, 1),
        "middle": round(sma, 1),
        "lower": round(sma - 2 * std, 1),
        "band_width": round((2 * std) / sma * 100, 2) if sma else 0,
    }


def _calc_fibonacci(high: float, low: float) -> dict[str, float]:
    diff = high - low
    return {
        "level_0": round(low),
        "level_236": round(high - diff * 0.236),
        "level_382": round(high - diff * 0.382),
        "level_500": round(high - diff * 0.5),
        "level_618": round(high - diff * 0.618),
        "level_786": round(high - diff * 0.786),
        "level_100": round(high),
    }


def _calc_cagr(values: list[float], years: float) -> float | None:
    if len(values) < 2 or values[0] <= 0:
        return None
    return round(((values[-1] / values[0]) ** (1 / years) - 1) * 100, 2)


def _generate_scenarios(current_price: float, support1: float, resistance1: float, rsi: float | None) -> dict[str, Any]:
    bullish_target = round(resistance1 * 1.08)
    bearish_target = round(support1 * 0.95)
    base_target = round((bullish_target + bearish_target) / 2)
    stop_loss = round(support1 * 0.97)
    risk = current_price - stop_loss
    reward_bull = bullish_target - current_price
    rr_bull = round(reward_bull / risk, 2) if risk > 0 else 0

    # Adjust probabilities based on RSI
    if rsi is not None:
        if rsi < 30:
            bull_prob, base_prob, bear_prob = 45, 40, 15
        elif rsi > 70:
            bull_prob, base_prob, bear_prob = 15, 35, 50
        else:
            bull_prob, base_prob, bear_prob = 30, 45, 25
    else:
        bull_prob, base_prob, bear_prob = 30, 45, 25

    return {
        "bullish": {
            "probability": bull_prob,
            "target_price": bullish_target,
            "potential_return": round((bullish_target / current_price - 1) * 100, 1),
            "description": "خوش‌بینانه",
        },
        "base": {
            "probability": base_prob,
            "target_price": base_target,
            "potential_return": round((base_target / current_price - 1) * 100, 1),
            "description": "واقع‌گرایانه",
        },
        "bearish": {
            "probability": bear_prob,
            "target_price": bearish_target,
            "potential_return": round((bearish_target / current_price - 1) * 100, 1),
            "description": "بدبینانه",
        },
        "risk_management": {
            "stop_loss": stop_loss,
            "stop_loss_pct": round((current_price - stop_loss) / current_price * 100, 1),
            "risk_to_reward": rr_bull if rr_bull > 0 else 0,
            "max_position_size_pct": 4 if rr_bull >= 2 else 2,
        },
    }


def _calc_peg(pe: float, eps_growth_pct: float | None) -> float | None:
    if pe <= 0 or eps_growth_pct is None or eps_growth_pct <= 0:
        return None
    return round(pe / eps_growth_pct, 2)


def _estimate_eps_growth(financials: list[dict[str, Any]]) -> float | None:
    if len(financials) < 2:
        return None
    eps_values = [f.get("eps", 0) or 0 for f in financials if f.get("eps")]
    if len(eps_values) < 2:
        return None
    current, previous = eps_values[0], eps_values[-1]
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def _assess_trend(closes: list[float]) -> str:
    if len(closes) < 5:
        return "خنثی"
    recent = closes[-5:]
    if all(recent[i] <= recent[i + 1] for i in range(4)):
        return "صعودی"
    if all(recent[i] >= recent[i + 1] for i in range(4)):
        return "نزولی"
    return "خنثی"


def _volume_analysis(history: list[dict[str, Any]]) -> dict[str, Any]:
    volumes = [h.get("volume", 0) or 0 for h in history if h.get("volume")]
    if not volumes:
        return {"avg_volume": 0, "last_volume": 0, "volume_ratio": 0}
    avg_vol = sum(volumes) / len(volumes)
    last_vol = volumes[-1]
    return {"avg_volume": round(avg_vol), "last_volume": last_vol, "volume_ratio": round(last_vol / avg_vol, 2) if avg_vol > 0 else 0}


@router.get("/{symbol}/comprehensive-analysis")
async def comprehensive_analysis(
    symbol: str,
    brsapi=Depends(get_brsapi_query_service),
):
    """تحلیل جامع ۳۶۰ درجه نماد — ترکیب ۷ بعد تحلیل"""
    try:
        snap = await brsapi.get_enriched_symbol_detail(symbol)
        history_raw = await brsapi.get_symbol_history(symbol, limit=200)
        holders = await brsapi.get_shareholders(symbol)
        announcements = await brsapi.get_recent_announcements(symbol=symbol, limit=10)

        if not snap:
            snap = await brsapi.get_symbol_snapshot(symbol)

        # ── Extract core data ──
        price_last = snap.get("price_last", 0) or 0
        price_yesterday = snap.get("price_yesterday", 0) or 0
        snap.get("price_close", 0) or 0
        price_min = snap.get("price_min", 0) or 0
        price_max = snap.get("price_max", 0) or price_last
        eps = snap.get("eps", 0) or 0
        pe = snap.get("pe_ratio", 0) or 0
        group_pe = snap.get("group_pe_ratio", 0) or 0
        market_cap = snap.get("market_value", 0) or 0
        shares_count = snap.get("shares_count", 0) or 0
        free_float = snap.get("free_float_pct", 0) or 0
        sector = snap.get("sector", "")
        sub_sector = snap.get("sub_sector", "")
        price_change_pct = ((price_last - price_yesterday) / price_yesterday * 100) if price_yesterday > 0 else 0

        # ── History processing ──
        history = []
        for h in history_raw if isinstance(history_raw, list) else []:
            if isinstance(h, dict):
                history.append(h)

        closes = [h.get("close", price_last) or price_last for h in history]
        highs = [h.get("high", price_max) or price_max for h in history]
        lows = [h.get("low", price_min) or price_min for h in history]

        if not closes:
            closes = [price_last]
        if not highs:
            highs = [price_max]
        if not lows:
            lows = [price_min]

        current_price = price_last or closes[-1] if closes else 0

        # ── 1. MACRO & INDUSTRY ──
        macro = {
            "sector": sector,
            "sub_sector": sub_sector,
            "market": snap.get("market", ""),
            "board": snap.get("board", ""),
            "state": snap.get("state", ""),
            "free_float_pct": free_float,
            "market_cap": market_cap,
            "shares_count": shares_count,
            "base_volume": snap.get("base_volume", 0),
        }

        # ── 2. DEEP FUNDAMENTAL ──
        revenue = snap.get("estimated_revenue", 0) or 0
        net_profit = eps * shares_count if shares_count > 0 else 0
        ps_ratio = snap.get("ps_ratio", 0) or (market_cap / revenue if revenue > 0 else 0)
        eps_growth = _estimate_eps_growth([])  # will be calculated from financials if available
        debt_to_equity = snap.get("debt_to_equity", 0) or 0
        current_ratio = snap.get("current_ratio", 0) or 0

        fundamental = {
            "eps": eps,
            "pe": round(pe, 2),
            "group_pe": round(group_pe, 2),
            "ps_ratio": round(ps_ratio, 2) if ps_ratio else 0,
            "pb_ratio": snap.get("pb_ratio", 0),
            "peg_ratio": _calc_peg(pe, eps_growth),
            "eps_growth_pct": eps_growth,
            "market_cap": market_cap,
            "net_profit_estimate": net_profit,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "free_float_pct": free_float,
            "shares_count": shares_count,
            "price_change_pct": round(price_change_pct, 2),
        }

        # ── 3. ADVANCED VALUATION ──
        high_52w = max(highs[-252:]) if len(highs) >= 252 else max(highs) if highs else current_price
        low_52w = min(lows[-252:]) if len(lows) >= 252 else min(lows) if lows else current_price
        position_pct = round((current_price - low_52w) / (high_52w - low_52w) * 100, 1) if high_52w > low_52w else 50

        valuation = {
            "current_price": round(current_price),
            "high_52w": round(high_52w),
            "low_52w": round(low_52w),
            "position_in_52w_pct": position_pct,
            "pe_vs_group": pe - group_pe if group_pe > 0 else 0,
            "estimated_fair_value": round(eps * group_pe) if eps > 0 and group_pe > 0 else 0,
        }

        # ── 4. TECHNICAL ──
        sr = _calc_support_resistance(history)
        ma = _calc_moving_averages(closes)
        rsi = _calc_rsi(closes)
        macd = _calc_macd(closes)
        bb = _calc_bollinger(closes)
        fib = _calc_fibonacci(max(highs[-60:]) if len(highs) >= 60 else max(highs) or current_price,
                              min(lows[-60:]) if len(lows) >= 60 else min(lows) or current_price)
        vol = _volume_analysis(history)
        trend = _assess_trend(closes)

        technical = {
            "trend": trend,
            "rsi_14": rsi,
            "rsi_signal": "oversold" if rsi and rsi < 30 else "overbought" if rsi and rsi > 70 else "neutral",
            "macd": macd,
            "bollinger": bb,
            "moving_averages": ma,
            "support_resistance": sr,
            "fibonacci": fib,
            "volume": vol,
            "high_52w": round(high_52w),
            "low_52w": round(low_52w),
        }

        # ── 5. ORDER FLOW & OWNERSHIP ──
        buy_real_volume = snap.get("buy_real_volume", 0) or 0
        sell_real_volume = snap.get("sell_real_volume", 0) or 0
        buy_legal_volume = snap.get("buy_legal_volume", 0) or 0
        sell_legal_volume = snap.get("sell_legal_volume", 0) or 0
        total_trade_volume = buy_real_volume + sell_real_volume + buy_legal_volume + sell_legal_volume

        real_net = buy_real_volume - sell_real_volume
        legal_net = buy_legal_volume - sell_legal_volume

        ownership = {
            "real_net": real_net,
            "legal_net": legal_net,
            "real_buy_pct": round(buy_real_volume / total_trade_volume * 100, 1) if total_trade_volume > 0 else 0,
            "legal_buy_pct": round(buy_legal_volume / total_trade_volume * 100, 1) if total_trade_volume > 0 else 0,
            "total_trade_volume": total_trade_volume,
            "holders_count": len(holders) if holders else 0,
            "top_holders": [
                {"name": h.get("shareholder_name", ""), "pct": h.get("percent", 0)}
                for h in (holders or [])[:5]
            ],
        }

        # ── 6. CATALYSTS & RISKS ──
        catalysts = {
            "recent_announcements": [
                {
                    "title": a.get("title", ""),
                    "date": a.get("date_publish", ""),
                    "audit_status": a.get("audit_status", ""),
                }
                for a in (announcements or [])[:5]
            ],
            "positive_signals": [],
            "negative_risks": [],
        }

        # Auto-detect signals/risks
        if rsi and rsi < 30:
            catalysts["positive_signals"].append("اشباع فروش — احتمال برگشت قیمت")
        if rsi and rsi > 70:
            catalysts["negative_risks"].append("اشباع خرید — احتمال اصلاح قیمت")
        if macd.get("signal_type") == "buy":
            catalysts["positive_signals"].append("MACD سیگنال خرید داده است")
        if macd.get("signal_type") == "sell":
            catalysts["negative_risks"].append("MACD سیگنال فروش داده است")
        if current_price <= sr.get("support1", current_price):
            catalysts["negative_risks"].append("قیمت در نزدیکی حمایت — ریسک شکست")
        if price_change_pct < -5:
            catalysts["negative_risks"].append(f"کاهش شدید قیمت ({abs(round(price_change_pct, 1))}%) در آخرین روز معاملاتی")
        if pe > 0 and group_pe > 0 and pe > group_pe * 1.3:
            catalysts["negative_risks"].append(f"P/E سهم ({pe}) بالاتر از میانگین صنعت ({group_pe})")
        if pe > 0 and group_pe > 0 and pe < group_pe * 0.7:
            catalysts["positive_signals"].append(f"P/E سهم ({pe}) پایین‌تر از میانگین صنعت ({group_pe}) — ارزندگی نسبی")
        if eps < 0:
            catalysts["negative_risks"].append("شرکت زیان‌ده است (EPS منفی)")
        if free_float < 10:
            catalysts["negative_risks"].append(f"شناوری پایین ({free_float}%) — نقدشوندگی محدود")

        # ── 7. SCENARIOS & RISK MANAGEMENT ──
        scenarios = _generate_scenarios(current_price, sr.get("support1", current_price), sr.get("resistance1", current_price), rsi)

        # ── Dashboard Summary ──
        signal = "buy" if rsi and rsi < 30 else "sell" if rsi and rsi > 70 else "hold"
        if macd.get("signal_type") != "neutral" and rsi and rsi < 50:
            signal = macd.get("signal_type")

        dashboard = {
            "signal": signal,
            "fair_value": valuation.get("estimated_fair_value", 0),
            "fair_value_vs_price_pct": round((valuation.get("estimated_fair_value", 0) / current_price - 1) * 100, 1) if current_price > 0 and valuation.get("estimated_fair_value", 0) > 0 else 0,
            "best_catalyst": catalysts["positive_signals"][0] if catalysts["positive_signals"] else "—",
            "worst_risk": catalysts["negative_risks"][0] if catalysts["negative_risks"] else "—",
            "stop_loss": scenarios["risk_management"]["stop_loss"],
            "bullish_target": scenarios["bullish"]["target_price"],
            "max_position_pct": scenarios["risk_management"]["max_position_size_pct"],
            "technical_status": f"{'اشباع فروش' if rsi and rsi < 30 else 'اشباع خرید' if rsi and rsi > 70 else 'خنثی'} | روند {trend}",
            "analysis_date": datetime.now().isoformat(),
        }

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "company_name": snap.get("name", f"شرکت {symbol}"),
                "macro": macro,
                "fundamental": fundamental,
                "valuation": valuation,
                "technical": technical,
                "ownership": ownership,
                "catalysts": catalysts,
                "scenarios": scenarios,
                "dashboard": dashboard,
            },
        }
    except Exception as exc:
        logger.exception("Comprehensive analysis failed for %s", symbol)
        return {"success": False, "error": {"message": str(exc)}}
