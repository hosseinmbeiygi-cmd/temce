"""📺 TSE Tape Reading Engine — فرمول‌های واقعی میکرواستراکچر بورس تهران.

بخش ۳-الف معماری Enterprise سهام:
  - قدرت خریدار به فروشنده حقیقی تعدیل‌شده با حجم مبنا (فرمول استاندارد TSE)
  - سرانه خرید/فروش حقیقی به میلیون تومان
  - شاخص ورود/خروج پول هوشمند (کدهای بزرگ)
  - Order Book Imbalance در ۵ مظنه + شبیه‌ساز لغزش (Slippage)
  - شاخص رنج‌کشی دقایق پایانی (Close Manipulation / Δspread)
  - وضعیت حجم مبنا و حجم مشکوک (μ+3σ نسبت به میانگین ۲۰/۶۰ روزه)

همه توابع خالص (Pure) هستند تا بدون دیتابیس قابل تست باشند.
"""

from __future__ import annotations

import math
from typing import Any

# ── فرمول‌های بومی TSE ───────────────────────────────────────────────────────


def buyer_seller_power_ratio(
    real_buy_volume: float,
    real_buy_count: float,
    real_sell_volume: float,
    real_sell_count: float,
    total_volume: float,
    base_volume: float,
) -> float | None:
    """P_buyer = (VolBuy/CntBuy) / (VolSell/CntSell) × min(1, VolTotal/BaseVol).

    قدرت خریدار حقیقی تعدیل‌شده با حجم مبنا. خروجی:
      > 1 → خریداران حقیقی قوی‌تر (هر کد حقیقی خریدار بزرگ‌تر از فروشنده)
      < 1 → فروشندگان حقیقی قوی‌تر
      None → داده ناکافی
    """
    if real_buy_count <= 0 or real_sell_count <= 0:
        return None
    avg_buy = real_buy_volume / real_buy_count
    avg_sell = real_sell_volume / real_sell_count
    if avg_sell <= 0:
        return None
    ratio = avg_buy / avg_sell
    if base_volume > 0 and total_volume >= 0:
        ratio *= min(1.0, total_volume / base_volume)
    return ratio


def per_capita_toman(value_rial: float, count: float) -> float | None:
    """سرانه حقیقی به میلیون تومان: Value / (Count × 10^7).

    (۱ میلیون تومان = ۱۰ میلیون ریال = 10^7 ریال)
    """
    if count <= 0:
        return None
    return value_rial / (count * 10**7)


def smart_money_inflow(
    real_buy_value: float,
    real_sell_value: float,
    real_buy_count: float,
    real_sell_count: float,
    trade_value: float,
    *,
    per_capita_ratio_threshold: float = 5.0,
    min_buy_value_rial: float = 1_000_000_000.0,  # ۱۰۰ میلیون تومان
) -> str | None:
    """شاخص ورود/خروج پول هوشمند بر مبنای سرانه و ارزش.

    ورود پول هوشمند: سرانه خرید ≥ ۵× سرانه فروش AND ارزش خرید ≥ آستانه.
    خروجی: "inflow" | "outflow" | "neutral" | None (داده ناکافی)
    """
    buy_pc = per_capita_toman(real_buy_value, real_buy_count)
    sell_pc = per_capita_toman(real_sell_value, real_sell_count)
    if buy_pc is None or sell_pc is None:
        return None
    if sell_pc <= 0:
        return "inflow" if real_buy_value >= min_buy_value_rial else None
    if buy_pc >= per_capita_ratio_threshold * sell_pc and real_buy_value >= min_buy_value_rial:
        return "inflow"
    if (
        sell_pc >= per_capita_ratio_threshold * buy_pc
        and real_sell_value >= min_buy_value_rial
    ):
        return "outflow"
    return "neutral"


def close_manipulation_index(last_price: float, close_price: float) -> dict[str, Any] | None:
    """Δspread = (Last − Close) / Close × 100.

    تشخیص رنج‌کشی:
      - Δspread ≥ +3%  → "positive_manipulation" (ساخت پایانی مثبت فردا)
      - Δspread ≤ −3%  → "negative_manipulation" (تخلیه با حفظ پایانی)
      - بین آن‌ها     → "normal"
    """
    if close_price <= 0 or last_price <= 0:
        return None
    spread_pct = (last_price - close_price) / close_price * 100.0
    if spread_pct >= 3.0:
        kind = "positive_manipulation"
    elif spread_pct <= -3.0:
        kind = "negative_manipulation"
    else:
        kind = "normal"
    return {"spread_pct": round(spread_pct, 2), "kind": kind}


def base_volume_status(trade_volume: float, base_volume: float) -> dict[str, Any] | None:
    """وضعیت پر شدن حجم مبنا (سقف دامنه قیمت فردا)."""
    if base_volume <= 0:
        return None
    ratio = trade_volume / base_volume
    if ratio >= 1.0:
        state = "filled"        # حجم مبنا کامل شده — دامنه فردا باز است
    elif ratio >= 0.5:
        state = "filling"
    else:
        state = "low"
    return {"ratio": round(ratio, 3), "state": state}


def unusual_volume_ratio(current_volume: float, historical_volumes: list[float]) -> dict[str, Any] | None:
    """حجم مشکوک: حجم امروز نسبت به μ و σ میانگین ۲۰ روزه.

    حجم > μ + 3σ → "extreme" (احتمال رخداد مهم)
    حجم > 3×μ   → "high"
    """
    if len(historical_volumes) < 5 or current_volume <= 0:
        return None
    mu = sum(historical_volumes) / len(historical_volumes)
    if mu <= 0:
        return None
    variance = sum((v - mu) ** 2 for v in historical_volumes) / len(historical_volumes)
    sigma = math.sqrt(variance)
    ratio = current_volume / mu
    if sigma == 0:
        # σ صفر یعنی تاریخچه ثابت — فقط نسبت به میانگین سنجیده می‌شود
        level = "extreme" if ratio >= 5.0 else ("high" if ratio >= 3.0 else "normal")
    elif current_volume > mu + 3 * sigma:
        level = "extreme"
    elif ratio >= 3.0:
        level = "high"
    elif ratio >= 1.5:
        level = "elevated"
    else:
        level = "normal"
    return {"ratio": round(ratio, 2), "level": level}


# ── Order Book (L2) ──────────────────────────────────────────────────────────


def order_book_imbalance(bids: list[dict[str, Any]], asks: list[dict[str, Any]], levels: int = 5) -> float | None:
    """OBI = (ΣV_bid − ΣV_ask) / (ΣV_bid + ΣV_ask) در N سطح اول.

    +1 → صف خرید انباشته؛ −1 → فشار فروش. None → دفتر خالی.
    """
    bid_v = sum(float(b.get("volume") or 0) for b in bids[:levels])
    ask_v = sum(float(a.get("volume") or 0) for a in asks[:levels])
    total = bid_v + ask_v
    if total <= 0:
        return None
    return (bid_v - ask_v) / total


def queue_value(bids: list[dict[str, Any]], asks: list[dict[str, Any]], price_last: float) -> dict[str, Any] | None:
    """ارزش ریالی صف خرید/فروش و نسبت آن به ارزش معاملات سهم.

    صف = اولین مظنه (بهترین قیمت) — مبنای تابلوی صف TSE.
    """
    if not bids or not asks or price_last <= 0:
        return None
    best_bid = bids[0]
    best_ask = asks[0]
    bid_v = float(best_bid.get("volume") or 0) * float(best_bid.get("price") or 0)
    ask_v = float(best_ask.get("volume") or 0) * float(best_ask.get("price") or 0)
    total = bid_v + ask_v
    if total <= 0:
        return None
    return {
        "bid_queue_value": bid_v,
        "ask_queue_value": ask_v,
        "bid_queue_ratio": round(bid_v / total, 3),
        "state": "buy_queue" if bid_v / total >= 0.7 else ("sell_queue" if ask_v / total >= 0.7 else "balanced"),
    }


def slippage_estimate(
    orders: list[dict[str, Any]],
    order_volume: float,
) -> dict[str, Any] | None:
    """شبیه‌ساز لغزش: اجرای حجم سنگین روی عمق مظنه‌ها.

    خروجی: میانگین قیمت اجرا، بدترین قیمت، لغزش درصدی نسبت به بهترین مظنه.
    None → حجم بیش از کل عمق بازار.
    """
    if order_volume <= 0 or not orders:
        return None
    remaining = order_volume
    notional = 0.0
    filled = 0.0
    worst_price = 0.0
    for level in orders:
        price = float(level.get("price") or 0)
        vol = float(level.get("volume") or 0)
        if price <= 0:
            continue
        take = min(remaining, vol)
        notional += take * price
        filled += take
        worst_price = price
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0 or filled <= 0:
        return None  # عمق کافی نیست
    best_price = float(orders[0].get("price") or 0)
    if best_price <= 0:
        return None
    avg_price = notional / filled
    slippage_pct = abs(avg_price - best_price) / best_price * 100.0
    return {
        "avg_exec_price": round(avg_price, 2),
        "worst_exec_price": worst_price,
        "slippage_pct": round(slippage_pct, 4),
        "filled_volume": filled,
    }


# ── Aggregate: تابلوی زنده کامل ──────────────────────────────────────────────


def compute_tape_reading(
    tape: dict[str, Any],
    bids: list[dict[str, Any]] | None = None,
    asks: list[dict[str, Any]] | None = None,
    volume_history_20d: list[float] | None = None,
) -> dict[str, Any]:
    """ماتریس کامل تابلوخوانی از یک اسنپ‌شات تابلو + دفتر سفارشات.

    ``tape`` فیلدهای استاندارد stock_live_tape را دارد.
    خروجی: dict کامل متریک‌ها + امتیاز ۰..۱۰۰ لایه تابلوخوانی.
    """
    bids = bids or []
    asks = asks or []
    real_buy_vol = float(tape.get("buy_real_volume") or 0)
    real_sell_vol = float(tape.get("sell_real_volume") or 0)
    real_buy_cnt = float(tape.get("buy_real_count") or 0)
    real_sell_cnt = float(tape.get("sell_real_count") or 0)
    real_buy_val = float(tape.get("buy_real_value") or 0)
    real_sell_val = float(tape.get("sell_real_value") or 0)
    total_vol = float(tape.get("trade_volume") or 0)
    base_vol = float(tape.get("base_volume") or 0)
    last_price = float(tape.get("last_price") or 0)
    close_price = float(tape.get("close_price") or 0)

    power_ratio = buyer_seller_power_ratio(
        real_buy_vol, real_buy_cnt, real_sell_vol, real_sell_cnt, total_vol, base_vol
    )
    percap_buy = per_capita_toman(real_buy_val, real_buy_cnt)
    percap_sell = per_capita_toman(real_sell_val, real_sell_cnt)
    smart_money = smart_money_inflow(
        real_buy_val, real_sell_val, real_buy_cnt, real_sell_cnt, close_price
    )
    manip = close_manipulation_index(last_price, close_price)
    basevol = base_volume_status(total_vol, base_vol)
    unusual = (
        unusual_volume_ratio(total_vol, volume_history_20d)
        if volume_history_20d
        else None
    )
    obi = order_book_imbalance(bids, asks) if (bids and asks) else None
    queue = queue_value(bids, asks, last_price) if (bids and asks) else None

    # ── امتیاز لایه تابلوخوانی ۰..۱۰۰ ──
    score = 50.0
    if power_ratio is not None:
        if power_ratio >= 1.5:
            score += 20
        elif power_ratio >= 1.1:
            score += 12
        elif power_ratio <= 0.67:
            score -= 20
        elif power_ratio <= 0.9:
            score -= 12
    if smart_money == "inflow":
        score += 15
    elif smart_money == "outflow":
        score -= 15
    if obi is not None:
        score += max(-10.0, min(10.0, obi * 15.0))
    if manip is not None and manip["kind"] == "negative_manipulation":
        score -= 10
    elif manip is not None and manip["kind"] == "positive_manipulation":
        score += 5  # رنج‌کشی مثبت سیگنال ضعیف صعودی است
    if basevol is not None and basevol["state"] == "filled" and (tape.get("close_change_pct") or 0) > 0:
        score += 8
    score = max(0.0, min(100.0, score))

    return {
        "buyer_power_ratio": power_ratio,
        "percapita_buy_mnt": percap_buy,
        "percapita_sell_mnt": percap_sell,
        "smart_money": smart_money,
        "close_manipulation": manip,
        "base_volume": basevol,
        "unusual_volume": unusual,
        "order_book_imbalance": obi,
        "queue": queue,
        "slippage_buy_1pct_volume": (
            slippage_estimate(asks, total_vol * 0.01) if asks and total_vol else None
        ),
        "tape_score": round(score, 1),
    }
