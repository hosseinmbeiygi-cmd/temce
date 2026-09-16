"""🎯 TSE Quant Signal Engine — امتیاز کامپوزیت ۵لایه + نسخه معاملاتی.

بخش ۳-ج معماری Enterprise سهام:
  Score = w_tape·S_tape + w_tech·S_tech + w_fund·S_fund + w_peer·S_peer + w_macro·S_macro
  (0.35 / 0.25 / 0.20 / 0.10 / 0.10 — قابل تنظیم)

خروجی نسخه معاملاتی:
  - action: strong_buy | accumulate | hold | reduce | sell
  - حد ضرر پویا: max(حمایت ساختاری، Entry − k×ATR14) — Chandelier-style
  - سه تارگت: فیبوناچی اکستنشن + مقاومت‌های پیوت
  - R/R filter: سیگنال‌های زیر ۲.۵ رد می‌شوند (به hold تنزل)
  - Position Sizing: Fractional Kelly Criterion (f = (p(b+1)−1)/b × fraction)
  - Market Regime: high_volume | eroding | falling (تغییر وزن‌ها)

No Look-Ahead: همه ورودی‌ها تا «امروز» محاسبه شده‌اند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ENGINE_VERSION = "stock-v2.0.0"

# ── وزن‌های پیش‌فرض (بر اساس رژیم بازار قابل تغییر) ─────────────────────────

BASE_WEIGHTS = {
    "tape": 0.35,
    "tech": 0.25,
    "fund": 0.20,
    "peer": 0.10,
    "macro": 0.10,
}

REGIME_WEIGHTS = {
    # در بازار پرحجم تکنیکال و تابلو مهم‌تر؛ در ریزشی بنیاد و پول نقد
    "high_volume": {"tape": 0.38, "tech": 0.27, "fund": 0.17, "peer": 0.08, "macro": 0.10},
    "eroding": {"tape": 0.33, "tech": 0.22, "fund": 0.23, "peer": 0.12, "macro": 0.10},
    "falling": {"tape": 0.30, "tech": 0.20, "fund": 0.27, "peer": 0.13, "macro": 0.10},
}

ACTIONS = [
    ("strong_buy", 80.0),
    ("accumulate", 65.0),
    ("hold", 50.0),
    ("reduce", 35.0),
    ("sell", 0.0),
]


def detect_market_regime(
    index_close_change_pct: float | None,
    market_total_value: float | None,
    market_avg_value_20d: float | None,
) -> str:
    """رژیم بازار بر اساس بازدهی شاخص و حجم کل.

    - high_volume: ارزش معاملات ≥ 1.2× میانگین ۲۰ روزه
    - falling:     شاخص کل زیر صفر
    - eroding:     بقیه حالت‌ها (فرسایشی)
    """
    if market_total_value and market_avg_value_20d and market_avg_value_20d > 0:
        if market_total_value >= 1.2 * market_avg_value_20d:
            return "high_volume"
    if index_close_change_pct is not None and index_close_change_pct < -0.5:
        return "falling"
    return "eroding"


@dataclass
class LayerInputs:
    """ورودی‌های هر لایه — همه ۰..۱۰۰؛ None = داده ناکافی → ۵۰ خنثی."""

    tape_score: float | None = None
    tech_score: float | None = None
    fund_score: float | None = None      # P/E نسبی، رشد فروش ماهانه، کیفیت سود
    peer_score: float | None = None      # رتبه در صنعت
    macro_score: float | None = None     # شکاف دلار، YTM اخزا، رژیم


@dataclass
class SignalResult:
    action: str
    composite_score: float
    layer_scores: dict[str, float]
    weights_used: dict[str, float]
    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    targets: list[float | None]
    risk_reward: float | None
    kelly_fraction: float | None
    position_size_pct: float | None
    market_regime: str
    reasons_pro: list[str] = field(default_factory=list)
    reasons_con: list[str] = field(default_factory=list)
    rr_filtered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "composite_score": round(self.composite_score, 1),
            "layer_scores": {k: round(v, 1) for k, v in self.layer_scores.items()},
            "weights_used": self.weights_used,
            "entry": [self.entry_low, self.entry_high],
            "stop_loss": self.stop_loss,
            "targets": self.targets,
            "risk_reward": round(self.risk_reward, 2) if self.risk_reward else None,
            "kelly_fraction": round(self.kelly_fraction, 4) if self.kelly_fraction else None,
            "position_size_pct": round(self.position_size_pct, 2) if self.position_size_pct else None,
            "market_regime": self.market_regime,
            "reasons_pro": self.reasons_pro,
            "reasons_con": self.reasons_con,
            "rr_filtered": self.rr_filtered,
            "engine_version": ENGINE_VERSION,
        }


def _scale(value: float | None) -> float:
    return 50.0 if value is None else max(0.0, min(100.0, value))


def compute_tech_score(snapshot: dict[str, Any]) -> float:
    """امتیاز تکنیکال از اسنپ‌شات اندیکاتورها."""
    score = 50.0
    rsi = snapshot.get("rsi_14")
    if rsi is not None:
        if 45 <= rsi <= 65:
            score += 8        # ناحیه سالم صعودی
        elif rsi > 75:
            score -= 12       # اشباع خرید
        elif rsi < 25:
            score += 5        # اشباع فروش (بازگشت احتمالی)
        elif rsi < 35:
            score -= 5
    div = snapshot.get("rsi_divergence")
    if div == "RD+":
        score += 12
    elif div == "RD-":
        score -= 12
    if snapshot.get("macd_cross") == "bullish_cross":
        score += 10
    elif snapshot.get("macd_cross") == "bearish_cross":
        score -= 10
    ich = snapshot.get("ichimoku") or {}
    if ich.get("state") == "above_kumo":
        score += 10
    elif ich.get("state") == "below_kumo":
        score -= 10
    if ich.get("tk_cross") == "tk_bullish":
        score += 5
    elif ich.get("tk_cross") == "tk_bearish":
        score -= 5
    if snapshot.get("squeeze") == "squeeze":
        score += 6  # انفجار بالقوه — خنثی مثبت
    if snapshot.get("ema_cross") == "golden":
        score += 12
    elif snapshot.get("ema_cross") == "death":
        score -= 12
    tas = snapshot.get("trend_alignment_score")
    if tas is not None:
        score += (tas - 50.0) * 0.15
    return max(0.0, min(100.0, score))


def estimate_fund_score(
    pe_ttm: float | None,
    pe_industry_median: float | None,
    monthly_sales_mom_pct: float | None,
    monthly_sales_yoy_pct: float | None,
) -> float:
    """امتیاز بنیادی سبک — P/E نسبی + مومنتوم فروش ماهانه."""
    score = 50.0
    if pe_ttm is not None and pe_ttm > 0:
        if pe_industry_median and pe_industry_median > 0:
            rel = pe_ttm / pe_industry_median
            if rel <= 0.7:
                score += 20
            elif rel <= 0.9:
                score += 10
            elif rel >= 1.4:
                score -= 15
            elif rel >= 1.1:
                score -= 7
        elif pe_ttm <= 5:
            score += 10
        elif pe_ttm >= 30:
            score -= 10
    if monthly_sales_mom_pct is not None:
        if monthly_sales_mom_pct >= 15:
            score += 12
        elif monthly_sales_mom_pct >= 5:
            score += 6
        elif monthly_sales_mom_pct <= -15:
            score -= 12
    if monthly_sales_yoy_pct is not None:
        if monthly_sales_yoy_pct >= 30:
            score += 12
        elif monthly_sales_yoy_pct <= -20:
            score -= 12
    return max(0.0, min(100.0, score))


def fibonacci_targets(
    swing_low: float, swing_high: float, entry: float
) -> list[float]:
    """سه تارگت با فیبوناچی اکستنشن از سوینگ اخیر (بدون آینده‌نگری)."""
    if swing_high <= swing_low or entry <= 0:
        return [None, None, None]  # type: ignore[return-value]
    rng = swing_high - swing_low
    t1 = entry + rng * 0.618  # اکستنشن محافظه‌کارانه
    t2 = entry + rng * 1.000
    t3 = entry + rng * 1.618  # Runner
    return [round(t1, 0), round(t2, 0), round(t3, 0)]


def kelly_position_size(
    win_probability: float,
    win_loss_ratio: float,
    fractional_multiplier: float = 0.5,
    max_position_pct: float = 10.0,
) -> tuple[float | None, float | None]:
    """Fractional Kelly: f* = (p(b+1) − 1)/b × fraction.

    خروجی: (kelly_fraction، درصد پوزیشن از پرتفوی). p یا b نامعتبر → (None, None).
    """
    if not (0 < win_probability < 1) or win_loss_ratio <= 0:
        return (None, None)
    kelly = (win_probability * (win_loss_ratio + 1.0) - 1.0) / win_loss_ratio
    kelly *= fractional_multiplier
    kelly = max(0.0, kelly)
    position_pct = min(kelly * 100.0, max_position_pct)
    return (kelly, position_pct)


def compute_composite_signal(
    layers: LayerInputs,
    price_last: float,
    price_close: float,
    atr_14: float | None,
    structural_support: float | None,
    swing_low: float | None,
    swing_high: float | None,
    market_regime: str = "eroding",
    win_probability: float | None = None,
    win_loss_ratio: float | None = None,
    stop_atr_mult: float = 2.5,
    min_rr: float = 2.5,
) -> SignalResult:
    """تجمیع نهایی — سیگنال + مدیریت ریسک کامل."""
    weights = REGIME_WEIGHTS.get(market_regime, BASE_WEIGHTS)

    layer_scores = {
        "tape": _scale(layers.tape_score),
        "tech": _scale(layers.tech_score) if layers.tech_score is None else min(100.0, max(0.0, layers.tech_score)),
        "fund": _scale(layers.fund_score),
        "peer": _scale(layers.peer_score),
        "macro": _scale(layers.macro_score),
    }
    # tech_score محاسبه‌شده توسط compute_tech_score مستقیماً پاس داده می‌شود
    if layers.tech_score is not None:
        layer_scores["tech"] = max(0.0, min(100.0, layers.tech_score))

    composite = sum(weights[k] * layer_scores[k] for k in weights)
    composite = max(0.0, min(100.0, composite))

    action = "hold"
    for a, threshold in ACTIONS:
        if composite >= threshold:
            action = a
            break

    # ── Entry / Stop / Targets ──
    entry = price_close if price_close > 0 else price_last
    entry_low = round(entry * 0.995, 0)     # −0.5٪
    entry_high = round(entry * 1.015, 0)    # +1.5٪
    stop_loss = None
    if entry > 0:
        atr_stop = entry - stop_atr_mult * atr_14 if atr_14 and atr_14 > 0 else None
        candidates = [c for c in (structural_support, atr_stop) if c is not None and c < entry]
        stop_loss = round(max(candidates), 0) if candidates else None

    targets: list[float | None] = [None, None, None]
    if swing_low is not None and swing_high is not None and entry > 0:
        targets = fibonacci_targets(swing_low, swing_high, entry)

    risk_reward = None
    if stop_loss and stop_loss < entry and targets[0]:
        risk = entry - stop_loss
        reward = targets[0] - entry
        if risk > 0:
            risk_reward = reward / risk

    # R/R filter: سیگنال خرید با R/R کم از آستانه → hold
    rr_filtered = False
    if action in ("strong_buy", "accumulate") and risk_reward is not None and risk_reward < min_rr:
        action = "hold"
        rr_filtered = True

    # ── Position Sizing (Kelly) ──
    kelly_frac, position_pct = (None, None)
    if action in ("strong_buy", "accumulate"):
        p = win_probability
        b = win_loss_ratio or risk_reward
        if p is None and risk_reward is not None:
            # فرض محافظه‌کارانه: p=0.45 برای سیگنال‌های خرید
            p = 0.45
        if p is not None and b is not None and b > 0:
            kelly_frac, position_pct = kelly_position_size(p, b)

    # ── دلایل شفاف ──
    reasons_pro: list[str] = []
    reasons_con: list[str] = []
    if layer_scores["tape"] >= 65:
        reasons_pro.append(f"جریان نقدینگی قوی (امتیاز تابلو: {layer_scores['tape']:.0f})")
    elif layer_scores["tape"] <= 35:
        reasons_con.append(f"فشار فروش در تابلو (امتیاز تابلو: {layer_scores['tape']:.0f})")
    if layer_scores["tech"] >= 65:
        reasons_pro.append(f"تاییدیه تکنیکال ({layer_scores['tech']:.0f})")
    elif layer_scores["tech"] <= 35:
        reasons_con.append(f"تکنیکال ضعیف ({layer_scores['tech']:.0f})")
    if layer_scores["fund"] >= 65:
        reasons_pro.append(f"بنیاد مناسب ({layer_scores['fund']:.0f})")
    elif layer_scores["fund"] <= 35:
        reasons_con.append(f"ارزش‌گذاری سنگین یا فروش ضعیف ({layer_scores['fund']:.0f})")
    if risk_reward is not None:
        reasons_pro.append(f"نسبت ریسک/ریوارد: {risk_reward:.1f}")
    if rr_filtered:
        reasons_con.append(f"R/R زیر {min_rr} — سیگنال خرید به نگهداری تنزل یافت")
    if market_regime == "falling":
        reasons_con.append("رژیم بازار: ریزشی — ریسک سیستماتیک بالا")

    return SignalResult(
        action=action,
        composite_score=round(composite, 1),
        layer_scores=layer_scores,
        weights_used=weights,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=round(risk_reward, 2) if risk_reward else None,
        kelly_fraction=kelly_frac,
        position_size_pct=position_pct,
        market_regime=market_regime,
        reasons_pro=reasons_pro[:5],
        reasons_con=reasons_con[:5],
        rr_filtered=rr_filtered,
    )
