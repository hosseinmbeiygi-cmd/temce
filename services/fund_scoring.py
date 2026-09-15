"""FundScoringEngine — deterministic quant scoring for Iranian funds.

این ماژوب تنها جایی است که «امتیاز» و «سیگنال» صندوق تولید می‌شود.
لایه LLM (FundChatExplainer) فقط تفسیر می‌کند؛ امتیاز اختراع نمی‌کند.

وزن‌دهی بر اساس نوع صندوق (پرامپت تحلیلگر):
  - اهرمی:      Liquidity Spiral 20 | P/NAV 15 | Drawdown 15 | Beta/Hidden Lev 15 | Tenure 10 | TER/Turnover 10
                (+85 مجموع)
  - طلا/کالا:   β_FX 20 | P/NAV 20 | همبستگی طلا 15 | اسپرد/نقدشوندگی 15 | TER 10
                (+80 مجموع)
  - درآمد ثابت: ثبات NAV/Duration 25 | β نرخ بهره 20 | اعتبار نهاد 20 | TER 15
                (+80 مجموع)
  - سهامی:      آلفا/IR 20 | Capture 15 | Style Drift 15 | Turnover/TER 15 | Behavior Gap/Persistence 15
                (+80 مجموع)

Overrideهای شرطی (غیرقابل نقض):
  - bubble > +3٪  → سقف سیگنال «اجتناب از خرید» (حتی با امتیاز بالا)
  - bubble < -2٪  → کاندید ورود (در صورت سلامت باقی ابعاد)
  - news_risk==HIGH  → هشدار ریسک اجباری
  - spread > 1٪  → جریمه اجباری امتیاز نقدشوندگی
  - اهرم بالا یا Liquidity Spiral بالا → هرگز «خرید قوی»
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── وزن‌ها ──────────────────────────────────────────────────────────────────
# پرامپت تحلیلگر: وزن‌های اصلی هر گروه جمع ۸۰٪. بقیه (۲۰٪) برای ابعاد مکمل.
# موتور لایه‌های اضافی را با وزن کمتر اعمال می‌کند ولی اگر داده موجود نبود، خنثی (50) در نظر می‌گیرد.

WEIGHTS: dict[str, dict[str, float]] = {
    # اهرمی: اصل ۸۵٪ (پرامپت) + ۱۵٪ تکمیلی
    "leveraged": {
        # اصلی (جمع ۸۵)
        "liquidity_spiral": 20.0,
        "p_nav": 15.0,
        "drawdown": 15.0,
        "beta_hidden_lev": 15.0,
        "tenure": 10.0,
        "ter_turnover": 10.0,
        # تکمیلی (جمع ۱۵)
        "behavior_gap": 7.0,
        "spread_liquidity": 5.0,
        "news_risk": 3.0,
    },
    # طلا/کالا: اصل ۸۰٪ + ۲۰٪ تکمیلی
    "gold": {
        # اصلی
        "fx_beta": 20.0,
        "p_nav": 20.0,
        "gold_corr": 15.0,
        "spread_liquidity": 15.0,
        "ter": 10.0,
        # تکمیلی
        "drawdown": 8.0,
        "behavior_gap": 5.0,
        "tenure": 4.0,
        "news_risk": 3.0,
    },
    # درآمد ثابت: اصل ۸۰٪ + ۲۰٪
    "fixed_income": {
        # اصلی
        "nav_stability": 25.0,
        "rate_beta": 20.0,
        "issuer_credit": 20.0,
        "ter": 15.0,
        # تکمیلی
        "spread_liquidity": 10.0,
        "tenure": 5.0,
        "drawdown": 3.0,
        "news_risk": 2.0,
    },
    # سهامی: اصل ۸۰٪ + ۲۰٪
    "equity": {
        # اصلی
        "alpha_ir": 20.0,
        "capture": 15.0,
        "style_drift": 15.0,
        "turnover_ter": 15.0,
        "behavior_persistence": 15.0,
        # تکمیلی
        "drawdown": 8.0,
        "spread_liquidity": 5.0,
        "tenure": 4.0,
        "news_risk": 3.0,
    },
    # مختلط: ترکیب سهامی + درآمد ثابت
    "mixed": {
        "alpha_ir": 10.0,
        "nav_stability": 12.0,
        "issuer_credit": 10.0,
        "rate_beta": 10.0,
        "capture": 10.0,
        "style_drift": 10.0,
        "turnover_ter": 10.0,
        "behavior_persistence": 10.0,
        "ter": 8.0,
        "spread_liquidity": 5.0,
        "drawdown": 3.0,
        "news_risk": 2.0,
    },
    # بخشی: الگوی سهامی با β_FX
    "sector": {
        "alpha_ir": 18.0,
        "capture": 12.0,
        "style_drift": 15.0,
        "turnover_ter": 15.0,
        "behavior_persistence": 10.0,
        "drawdown": 10.0,
        "spread_liquidity": 8.0,
        "tenure": 5.0,
        "fx_beta": 4.0,
        "news_risk": 3.0,
    },
    # شاخصی: Tracking + TER مهم
    "index": {
        "tracking_diff": 20.0,
        "ter": 20.0,
        "turnover_ter": 15.0,
        "spread_liquidity": 15.0,
        "drawdown": 10.0,
        "capture": 8.0,
        "tenure": 5.0,
        "nav_stability": 4.0,
        "news_risk": 3.0,
    },
}

# ── آستانه‌های سیگنال ────────────────────────────────────────────────────────

SIGNAL_LEVELS = [
    ("STRONG_BUY", "خرید قوی", 80),
    ("BUY", "خرید", 65),
    ("HOLD", "نگهداری", 50),
    ("REDUCE", "احتیاط", 35),
    ("AVOID", "اجتناب", 0),
]

# گروه‌هایی که اصلاً نباید «خرید قوی» بگیرند
NEVER_STRONG_BUY = {"leveraged"}  # اهرم بالا + Liquidity Spiral بالا


@dataclass
class FundMetrics:
    """داده‌های خام ورودی — صفر به‌معنای «نامعلوم/غیرقابل محاسبه»."""

    symbol: str
    name: str = ""
    fund_type: str = "equity"  # leveraged|gold|fixed_income|equity|mixed|sector|index
    market: str = "tse"  # tse|ime

    # قیمت و NAV
    price_last: float = 0.0
    nav: float = 0.0
    nav_source: str = ""  # "nav_record" | "" (تقریبی)
    nav_date: str = ""
    nav_change_pct: float = 0.0
    price_change_pct: float = 0.0  # bubble

    # نقدشوندگی
    trade_volume: float = 0.0
    trade_value: float = 0.0
    shares_count: float = 0.0
    market_value: float = 0.0
    buy_real_volume: float = 0.0
    sell_real_volume: float = 0.0
    sell_legal_volume: float = 0.0
    buy_legal_volume: float = 0.0

    # ریسک و بازده
    max_drawdown: float = 0.0  # درصد (مثبت)
    volatility: float = 0.0  # σ سالانه
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    upside_capture: float = 0.0
    downside_capture: float = 0.0
    return_1m: float = 0.0
    return_3m: float = 0.0
    return_6m: float = 0.0
    return_12m: float = 0.0
    return_36m: float = 0.0

    # ساختار
    ter: float = 0.0  # total expense ratio
    turnover: float = 0.0
    active_share: float = 0.0
    style_drift: float = 0.0
    tracking_difference: float = 0.0
    tenure_years: float = 0.0
    hhi: float = 0.0

    # رفتاری / کوانت
    behavior_gap: float = 0.0
    persistence: float = 0.0
    liquidity_spiral: float = 0.0  # 0..100
    hidden_leverage: float = 0.0  # 0..100
    redemption_pressure: float = 0.0  # 0..100
    nav_stability: float = 0.0  # 0..100
    duration: float = 0.0
    rate_beta: float = 0.0
    issuer_credit: float = 0.0  # 0..100
    fx_beta: float = 0.0
    gold_corr: float = 0.0  # -1..1
    spread_pct: float = 0.0  # bid-ask spread درصد

    # متغیرهای کلان (از context)
    market_macro_risk: float = 0.0  # 0..100
    news_risk: str = "LOW"  # LOW|MEDIUM|HIGH

    # extra
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FundScoreResult:
    """خروجی قطعی موتور امتیازدهی."""

    symbol: str
    fund_type: str
    score: float  # 0..100
    signal: str  # STRONG_BUY|BUY|HOLD|REDUCE|AVOID
    signal_label: str  # فارسی
    confidence: str  # HIGH|MEDIUM|LOW (بر اساس coverage داده)
    layer_scores: dict[str, float]  # نمره هر زیرلایه (0..100)
    applied_weights: dict[str, float]  # وزن‌های استفاده‌شده
    overrides: list[str]  # شرح overrideهای اعمال‌شده
    risks: list[str]  # هشدارها
    bubble: dict[str, Any]  # {p_nav, group_avg, status}
    reasons: list[str]  # ۳ تا ۵ دلیل کوتاه عددی
    invalidation: str  # شرایط ابطال سیگنال
    disclaimer: str = "این تحلیل توصیه سرمایه‌گذاری نیست."

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund": self.symbol,
            "fund_type": self.fund_type,
            "score": round(self.score, 1),
            "signal": self.signal,
            "signal_label": self.signal_label,
            "confidence": self.confidence,
            "layer_scores": {k: round(v, 1) for k, v in self.layer_scores.items()},
            "applied_weights": self.applied_weights,
            "overrides": self.overrides,
            "risks": self.risks,
            "bubble": self.bubble,
            "reason_vector": self.reasons,
            "invalidation": self.invalidation,
            "disclaimer": self.disclaimer,
        }


# ── توابع کمکی نرمال‌سازی ───────────────────────────────────────────────────


def _clip(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _score_return_pct(pct: float) -> float:
    """بازدهی خام → 0..100 (0% = 50، +20% = 80، -10% = 30)."""
    # piecewise linear
    if pct >= 30:
        return 95.0
    if pct >= 20:
        return 80.0 + (pct - 20) * 1.5
    if pct >= 10:
        return 65.0 + (pct - 10) * 1.5
    if pct >= 0:
        return 50.0 + pct * 1.5
    if pct >= -10:
        return 50.0 + pct * 2.0  # -10% → 30
    if pct >= -30:
        return 30.0 + (pct + 10) * 1.0
    return 10.0


def _score_drawdown(dd_pct: float) -> float:
    """Drawdown مثبت → نمره 100 - dd (dd=5% → 95، dd=30% → 70)."""
    if dd_pct <= 0:
        return 100.0
    if dd_pct >= 50:
        return 20.0
    if dd_pct >= 20:
        return 50.0 - (dd_pct - 20) * 1.0
    return 100.0 - dd_pct * 1.5


def _score_sharpe(s: float) -> float:
    if s >= 2:
        return 95.0
    if s >= 1:
        return 70.0 + (s - 1) * 25.0
    if s >= 0:
        return 50.0 + s * 20.0
    if s >= -1:
        return 50.0 + s * 20.0
    return 30.0


def _score_sortino(s: float) -> float:
    return _score_sharpe(s)  # same curve


def _score_calmar(c: float) -> float:
    if c >= 1.5:
        return 95.0
    if c >= 0.5:
        return 60.0 + (c - 0.5) * 35.0
    if c >= 0:
        return 50.0 + c * 20.0
    return 30.0 + max(c * 20.0, -20.0)


def _score_ir(ir: float) -> float:
    if ir >= 1.5:
        return 95.0
    if ir >= 0.5:
        return 60.0 + (ir - 0.5) * 35.0
    if ir >= 0:
        return 50.0 + ir * 20.0
    return 30.0


def _score_capture(up: float, down: float) -> float:
    """ترکیب capture: up بالا + down پایین بهتر است."""
    up_s = _clip(up, 0, 200) / 2.0  # 100 → 50، 150 → 75
    down_s = 100.0 - _clip(down, 0, 200) / 2.0  # 100 → 50، 50 → 75
    return up_s * 0.5 + down_s * 0.5


def _score_style_drift(sd: float) -> float:
    """drift کمتر = بهتر. 0 → 95، 20% → 60، 50%+ → 30."""
    if sd <= 5:
        return 95.0
    if sd <= 20:
        return 80.0 - (sd - 5)
    if sd <= 50:
        return 60.0 - (sd - 20) * 1.0
    return 30.0


def _score_ter(ter: float) -> float:
    """کارمزد پایین = بهتر. 0.5% → 90، 2% → 50، 4%+ → 20."""
    if ter <= 0.5:
        return 95.0
    if ter <= 2.0:
        return 90.0 - (ter - 0.5) * 26.67
    if ter <= 4.0:
        return 50.0 - (ter - 2.0) * 15.0
    return 20.0


def _score_turnover(t: float) -> float:
    """turnover 50% = 70، 200% = 30، >300% = 10."""
    if t <= 50:
        return 85.0
    if t <= 200:
        return 85.0 - (t - 50) * 0.366  # 50→85, 200→29
    if t <= 400:
        return 30.0 - (t - 200) * 0.05
    return 10.0


def _score_liquidity_spiral(v: float) -> float:
    """کمتر = بهتر."""
    return _clip(100.0 - v, 0, 100)


def _score_beta_hidden_lev(v: float) -> float:
    return _clip(100.0 - v, 0, 100)


def _score_tenure(years: float) -> float:
    if years >= 5:
        return 90.0
    if years >= 2:
        return 70.0 + (years - 2) * 6.67
    if years >= 0.5:
        return 50.0 + (years - 0.5) * 26.67
    return 30.0 + years * 40.0


def _score_nav_stability(s: float) -> float:
    return _clip(s, 0, 100)


def _score_rate_beta(b: float) -> float:
    """برای درآمد ثابت: |beta| کمتر = بهتر."""
    return _clip(100.0 - abs(b) * 50.0, 0, 100)


def _score_issuer_credit(c: float) -> float:
    return _clip(c, 0, 100)


def _score_fx_beta(b: float) -> float:
    """برای طلا: |fx_beta| زیاد = مثبت (طلا در برابر دلار)."""
    # فرض: fx_beta > 0 یعنی همبستگی با دلار → برای صندوق طلای ایرانی که قیمت دلار بالا می‌رود
    # نمره: 0..1 → 50..100
    return _clip(50.0 + b * 50.0, 0, 100)


def _score_gold_corr(c: float) -> float:
    return _clip((c + 1) * 50.0, 0, 100)


def _score_spread(spread_pct: float) -> float:
    """اسپرد > 1٪ جریمه شدید."""
    if spread_pct <= 0.2:
        return 95.0
    if spread_pct <= 0.5:
        return 85.0
    if spread_pct <= 1.0:
        return 65.0
    if spread_pct <= 2.0:
        return 35.0
    return 15.0


def _score_tracking_diff(td: float) -> float:
    if td <= 0.5:
        return 95.0
    if td <= 2.0:
        return 80.0 - (td - 0.5) * 20.0
    if td <= 5.0:
        return 50.0 - (td - 2.0) * 10.0
    return 20.0


def _score_behavior_gap(g: float) -> float:
    return _clip(100.0 - abs(g) * 5.0, 0, 100)


def _score_persistence(p: float) -> float:
    return _clip(p, 0, 100)


# ── محاسبه اصلی ─────────────────────────────────────────────────────────────


def _calc_bubble(price: float, nav: float) -> float | None:
    if not price or not nav or nav <= 0:
        return None
    return ((price - nav) / nav) * 100.0


def _detect_fund_group(fund_type: str, name: str) -> str:
    """نگاشت fund_type + نام فارسی به گروه وزنی."""
    name_l = (name or "").lower()
    if "اهرمی" in name_l or "اهرم" in name_l or "leveraged" in (fund_type or "").lower():
        return "leveraged"
    if "طلا" in name_l or "gold" in (fund_type or "").lower() or "سکه" in name_l:
        return "gold"
    if "درآمد ثابت" in name_l or "fixed" in (fund_type or "").lower() or fund_type == "درآمد ثابت":
        return "fixed_income"
    if "مختلط" in name_l or "mixed" in (fund_type or "").lower():
        return "mixed"
    if "شاخصی" in name_l or "index" in (fund_type or "").lower():
        return "index"
    if "بخشی" in name_l or "sector" in (fund_type or "").lower() or "کالا" in name_l:
        return "sector"
    return "equity"


def _data_coverage(m: FundMetrics, group: str) -> tuple[float, str]:
    """درصد فیلدهای غیرخالی → confidence."""
    fields: list[float] = [
        m.nav,
        m.price_last,
        m.trade_volume,
        m.market_value,
        m.max_drawdown,
        m.sharpe,
        m.ter,
        m.turnover,
        m.tenure_years,
    ]
    # فیلدهای وابسته به گروه
    if group == "leveraged":
        fields += [m.liquidity_spiral, m.hidden_leverage]
    elif group == "gold":
        fields += [m.fx_beta, m.gold_corr]
    elif group == "fixed_income":
        fields += [m.nav_stability, m.rate_beta, m.issuer_credit]
    elif group in ("equity", "sector", "mixed"):
        fields += [m.alpha_ir if hasattr(m, "alpha_ir") else m.information_ratio, m.upside_capture]
    elif group == "index":
        fields += [m.tracking_difference, m.ter]
    covered = sum(1 for f in fields if f)
    pct = covered / max(len(fields), 1)
    if pct >= 0.7:
        return pct, "HIGH"
    if pct >= 0.4:
        return pct, "MEDIUM"
    return pct, "LOW"


def compute_fund_score(m: FundMetrics, group_avg_bubble: float | None = None) -> FundScoreResult:
    """ورودی: متریک‌های خام صندوق. خروجی: امتیاز + سیگنال + ریسک + JSON-ready."""
    group = _detect_fund_group(m.fund_type, m.name)
    weights = WEIGHTS.get(group, WEIGHTS["equity"])
    coverage_pct, confidence = _data_coverage(m, group)

    overrides: list[str] = []
    risks: list[str] = []

    # ── محاسبه امتیاز هر زیرلایه (0..100) ──
    layers: dict[str, float] = {}

    # بازدهی (اگر وزن دارد)
    if "alpha_ir" in weights:
        # سهامی/مختلط/بخشی/شاخصی
        ret_12 = _score_return_pct(m.return_12m)
        layers["alpha_ir"] = _score_ir(m.information_ratio)
    if "behavior_persistence" in weights:
        # صفر یعنی نامعلوم — نمره خنثی
        layers["behavior_persistence"] = _score_persistence(m.persistence) if m.persistence else 50.0
    if "behavior_gap" in weights:
        layers["behavior_gap"] = _score_behavior_gap(m.behavior_gap) if m.behavior_gap else 50.0

    # Drawdown
    if "drawdown" in weights:
        layers["drawdown"] = _score_drawdown(m.max_drawdown)
    else:
        _score_drawdown(m.max_drawdown)

    # Capture (سهامی/مختلط/بخشی/شاخصی)
    if "capture" in weights:
        layers["capture"] = _score_capture(m.upside_capture, m.downside_capture)

    # Style drift
    if "style_drift" in weights:
        layers["style_drift"] = _score_style_drift(m.style_drift)

    # TER / Turnover
    if "ter" in weights:
        layers["ter"] = _score_ter(m.ter)
    if "ter_turnover" in weights:
        # ترکیب: 60٪ TER + 40٪ Turnover
        layers["ter_turnover"] = 0.6 * _score_ter(m.ter) + 0.4 * _score_turnover(m.turnover)
    if "turnover_ter" in weights:
        layers["turnover_ter"] = 0.4 * _score_ter(m.ter) + 0.6 * _score_turnover(m.turnover)
    if "ter_turnover" in weights or "turnover_ter" in weights:
        pass

    # Tracking diff
    if "tracking_diff" in weights:
        layers["tracking_diff"] = _score_tracking_diff(m.tracking_difference)

    # Tenure
    if "tenure" in weights:
        layers["tenure"] = _score_tenure(m.tenure_years)

    # P/NAV Bubble
    if "p_nav" in weights:
        # bubble 0% → 75 (متعادل)، منفی → بهتر، مثبت → بدتر
        bubble_local = _calc_bubble(m.price_last, m.nav) or 0
        bubble_score = 75.0 - bubble_local * 5.0
        layers["p_nav"] = _clip(bubble_score, 0, 100)

    # Liquidity Spiral (اهرمی)
    if "liquidity_spiral" in weights:
        layers["liquidity_spiral"] = _score_liquidity_spiral(m.liquidity_spiral)
        if m.liquidity_spiral > 60:
            risks.append(f"Liquidity Spiral بالا: {m.liquidity_spiral:.0f}/100")

    # Beta / Hidden Leverage (اهرمی)
    if "beta_hidden_lev" in weights:
        layers["beta_hidden_lev"] = _score_beta_hidden_lev(m.hidden_leverage)
        if m.hidden_leverage > 30:
            risks.append(f"اهرم پنهان بالا: {m.hidden_leverage:.0f}/100")

    # β_FX (طلا)
    if "fx_beta" in weights:
        layers["fx_beta"] = _score_fx_beta(m.fx_beta)

    # همبستگی طلا
    if "gold_corr" in weights:
        layers["gold_corr"] = _score_gold_corr(m.gold_corr)

    # اسپرد / نقدشوندگی
    if "spread_liquidity" in weights:
        spread_score = _score_spread(m.spread_pct)
        # اگر trade_value > 5B خوب
        liq_score = (
            100.0
            if m.trade_value >= 5e9
            else (70.0 if m.trade_value >= 1e9 else (40.0 if m.trade_value >= 1e8 else 20.0))
        )
        layers["spread_liquidity"] = 0.5 * spread_score + 0.5 * liq_score

    # ثبات NAV / Duration (درآمد ثابت)
    if "nav_stability" in weights:
        layers["nav_stability"] = _score_nav_stability(m.nav_stability)

    # β نرخ بهره
    if "rate_beta" in weights:
        layers["rate_beta"] = _score_rate_beta(m.rate_beta)

    # اعتبار نهاد
    if "issuer_credit" in weights:
        layers["issuer_credit"] = _score_issuer_credit(m.issuer_credit)

    # News risk
    if "news_risk" in weights:
        if m.news_risk == "HIGH":
            layers["news_risk"] = 25.0
            risks.append("هشدار ریسک خبری بالا — رویداد با اهمیت در جریان است")
        elif m.news_risk == "MEDIUM":
            layers["news_risk"] = 55.0
        else:
            layers["news_risk"] = 90.0

    # ── محاسبه امتیاز نهایی ──
    total_weight = 0.0
    weighted_sum = 0.0
    for k, w in weights.items():
        v = layers.get(k, 50.0)  # default 50 (خنثی)
        weighted_sum += v * w
        total_weight += w

    if total_weight > 0:
        base_score = weighted_sum / total_weight
    else:
        base_score = 50.0

    score = _clip(base_score, 0, 100)

    # ── Override 1: bubble > +3٪ → سقف AVOID ──
    bubble_now = _calc_bubble(m.price_last, m.nav)
    bubble_status = "balanced"
    if bubble_now is not None:
        if bubble_now > 3.0:
            score = min(score, 32.0)
            overrides.append(f"bubble={bubble_now:+.1f}٪>3% → سقف AVOID")
            bubble_status = "high_bubble"
        elif bubble_now < -2.0:
            overrides.append(f"bubble={bubble_now:+.1f}٪<-2% → کاندید ورود")
            bubble_status = "discounted"
        else:
            bubble_status = "balanced"

    # ── Override 2: spread > 1% → جریمه نقدشوندگی ──
    if m.spread_pct > 1.0:
        # کاهش ۱۰ امتیازی از نمره spread_liquidity
        if "spread_liquidity" in layers:
            layers["spread_liquidity"] = max(0, layers["spread_liquidity"] - 15)
        score = max(0, score - 5)
        overrides.append(f"spread={m.spread_pct:.1f}٪>1% → جریمه نقدشوندگی")
        risks.append(f"اسپرد بالای ‎{m.spread_pct:.1f}٪ — هزینه ورود/خروج زیاد")

    # ── Override 3: news_risk HIGH → هشدار اجباری (نه امتیاز) ──
    if m.news_risk == "HIGH":
        risks.append("⚠️ ریسک خبری بالا — قبل از تصمیم، آخرین اطلاعیه‌ها را بررسی کنید")

    # ── Override 4: اهرم بالا + Liquidity Spiral بالا → ممنوعیت STRONG_BUY ──
    never_strong_buy = group in NEVER_STRONG_BUY or m.liquidity_spiral > 70 or m.hidden_leverage > 50

    # ── تعیین سیگنال از امتیاز ──
    signal = "HOLD"
    signal_label = "نگهداری"
    for code, label_fa, threshold in SIGNAL_LEVELS:
        if score >= threshold:
            signal = code
            signal_label = label_fa
            break

    if never_strong_buy and signal == "STRONG_BUY":
        signal = "BUY"
        signal_label = "خرید"
        overrides.append("اهرم/Liquidity Spiral بالا → STRONG_BUY به BUY کاهش یافت")

    # ── Bubble info برای خروجی ──
    bubble_info = {
        "p_nav": f"{bubble_now:+.2f}٪" if bubble_now is not None else "—",
        "group_avg": f"{group_avg_bubble:+.2f}٪" if group_avg_bubble is not None else "—",
        "status": bubble_status,
    }

    # ── Reason Vector (۳-۵ دلیل کوتاه عددی) ──
    reasons: list[str] = []

    # ۱. حباب
    if bubble_now is not None and abs(bubble_now) > 0.5:
        if bubble_now > 3:
            reasons.append(f"P/NAV {bubble_now:+.1f}٪ — حباب بالای ‎+۳٪")
        elif bubble_now < -2:
            reasons.append(f"P/NAV {bubble_now:+.1f}٪ — تخفیف، کاندید ورود")
        else:
            reasons.append(f"P/NAV {bubble_now:+.1f}٪ — متعادل")

    # ۲. بهترین لایه
    if layers:
        best_layer = max(layers.items(), key=lambda kv: kv[1])
        if best_layer[1] >= 70:
            reasons.append(f"قوت: {best_layer[0]}={best_layer[1]:.0f}")

    # ۳. بدترین لایه
    if layers:
        worst_layer = min(layers.items(), key=lambda kv: kv[1])
        if worst_layer[1] <= 40:
            reasons.append(f"ضعف: {worst_layer[0]}={worst_layer[1]:.0f}")

    # ۴. عملکرد
    if m.return_12m and abs(m.return_12m) > 5:
        reasons.append(f"بازدهی ۱۲ماهه {m.return_12m:+.1f}٪")

    # ۵. ریسک‌های بحرانی
    if m.liquidity_spiral > 60:
        reasons.append(f"Liquidity Spiral={m.liquidity_spiral:.0f} (بالا)")
    if m.hidden_leverage > 30:
        reasons.append(f"اهرم پنهان={m.hidden_leverage:.0f}")
    if m.spread_pct > 1.0:
        reasons.append(f"اسپرد={m.spread_pct:.1f}٪ (بالا)")

    reasons = reasons[:5]

    # ── Invalidation ──
    inv_parts: list[str] = []
    if bubble_now is not None and bubble_now > 0:
        inv_parts.append(f"P/NAV به زیر {bubble_now - 2:+.1f}٪ بازگردد")
    if m.liquidity_spiral > 50:
        inv_parts.append("Liquidity Spiral زیر ۴۰ بیاید")
    if m.news_risk == "HIGH":
        inv_parts.append("خبر/اطلاعیه مهم منتشر شد")
    inv_parts.append("تغییر اساسی در ترکیب دارایی")
    invalidation = " · ".join(inv_parts) if inv_parts else "تغییر در شرایط بازار یا ترکیب صندوق"

    return FundScoreResult(
        symbol=m.symbol,
        fund_type=group,
        score=score,
        signal=signal,
        signal_label=signal_label,
        confidence=confidence,
        layer_scores=layers,
        applied_weights=weights,
        overrides=overrides,
        risks=risks,
        bubble=bubble_info,
        reasons=reasons,
        invalidation=invalidation,
    )
