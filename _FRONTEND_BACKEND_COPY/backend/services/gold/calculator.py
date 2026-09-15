"""Gold pure-math calculators — no DB, no I/O, fully unit-testable.

Implements the formulas from the Antigravity Gold prompt:

  • NAV Premium/Discount for gold ETFs
  • Coin bubble (سکه بهار آزادی vs intrinsic value from ounce)
  • Dollar-adjusted return (Alpha vs USD inflation hedge)

All functions are pure: same inputs → same outputs, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Physical constants (Iranian coin gold) ────────────────────────
TROY_OUNCE_GRAM = 31.1035  # grams per troy ounce
COIN_BAHAR_WEIGHT_G = 8.133  # grams
COIN_BAHAR_PURITY = 0.915  # 900/1000 + minting fee factor

# ETF (NAV Premium/Discount) — این آستانه‌ها درصدی منطقی هستند
ETF_PREMIUM_SELL_THRESHOLD = 2.0  # +%  → SELL signal
ETF_DISCOUNT_BUY_THRESHOLD = -1.0  # -%  → BUY signal

# Coin bubble — بازار ایران به‌طور ساختاری حباب 300-1000% دارد
# (تقاضای سفته‌بازی + محدودیت عرضه فیزیکی + کنترل قیمت دولتی طلا)
# آستانه‌های واقع‌بینانه:
#  - خنثی: حباب در بازه نرمال (300% الی 700%)
#  - SELL: حباب بیش از 700% (اشباع تقاضا / فرصت فروش)
#  - BUY: حباب کمتر از 300% (سکه ارزان‌تر از حد معمول)
COIN_BUBBLE_SELL_THRESHOLD = 700.0
COIN_BUBBLE_BUY_THRESHOLD = 300.0


@dataclass(frozen=True)
class NavPremiumResult:
    premium_pct: float
    signal: str  # BUY / SELL / NEUTRAL
    reason: str


@dataclass(frozen=True)
class CoinBubbleResult:
    coin_intrinsic_irr: float
    coin_market_irr: float
    bubble_pct: float
    signal: str
    reason: str


@dataclass(frozen=True)
class DollarAdjustedResult:
    irr_roi_pct: float
    dollar_roi_pct: float
    usd_growth_pct: float
    alpha_vs_usd: float
    is_beating_inflation: bool


def calculate_nav_premium(market_price: float, nav: float) -> NavPremiumResult:
    """پرمیوم/دیسکانت صندوق نسبت به NAV (درصد)."""
    if nav <= 0:
        raise ValueError("nav must be > 0")
    premium_pct = ((market_price - nav) / nav) * 100.0

    if premium_pct > ETF_PREMIUM_SELL_THRESHOLD:
        signal = "SELL"
        reason = f"صندوق {premium_pct:.2f}% بیش از NAV معامله می‌شود (اشباع خرید)"
    elif premium_pct < ETF_DISCOUNT_BUY_THRESHOLD:
        signal = "BUY"
        reason = f"صندوق {abs(premium_pct):.2f}% زیر NAV معامله می‌شود (فرصت خرید)"
    else:
        signal = "NEUTRAL"
        reason = f"صندوق در محدوده منطقی NAV معامله می‌شود ({premium_pct:+.2f}%)"

    return NavPremiumResult(
        premium_pct=round(premium_pct, 2),
        signal=signal,
        reason=reason,
    )


def calculate_coin_bubble(
    coin_price_irr: float,
    gold_oz_usd: float,
    usd_irr: float,
    weight_g: float = COIN_BAHAR_WEIGHT_G,
    purity: float = COIN_BAHAR_PURITY,
) -> CoinBubbleResult:
    """حباب/تخفیف سکه نسبت به ارزش ذاتی از اونس جهانی.

    نکته: بازار ایران به‌طور ساختاری حباب 200-1000% دارد.
    آستانه‌های SELL=600%, BUY=200% برای تشخیص نوسان غیرعادی هستند.
    """
    if any(x <= 0 for x in (coin_price_irr, gold_oz_usd, usd_irr)):
        raise ValueError("prices must be > 0")
    coin_intrinsic = (gold_oz_usd / TROY_OUNCE_GRAM) * weight_g * purity * usd_irr
    bubble_pct = ((coin_price_irr - coin_intrinsic) / coin_intrinsic) * 100.0

    if bubble_pct > COIN_BUBBLE_SELL_THRESHOLD:
        signal = "SELL"
        reason = f"سکه {bubble_pct:.1f}% حباب دارد — اشباع تقاضا (فروش فیزیکی / خرید اونس)"
    elif bubble_pct < COIN_BUBBLE_BUY_THRESHOLD:
        signal = "BUY"
        reason = f"سکه {bubble_pct:.1f}% حباب دارد — ارزان‌تر از حد معمول (خرید فیزیکی)"
    else:
        signal = "NEUTRAL"
        reason = f"سکه در بازه نرمال بازار ایران معامله می‌شود ({bubble_pct:+.1f}%)"

    return CoinBubbleResult(
        coin_intrinsic_irr=round(coin_intrinsic, 2),
        coin_market_irr=round(coin_price_irr, 2),
        bubble_pct=round(bubble_pct, 2),
        signal=signal,
        reason=reason,
    )


def calculate_dollar_adjusted_return(
    entry_value_irr: float,
    current_value_irr: float,
    entry_usd_rate: float,
    current_usd_rate: float,
) -> DollarAdjustedResult:
    """بازده واقعی تعدیل‌شده با نرخ دلار (Alpha)."""
    if entry_usd_rate <= 0 or current_usd_rate <= 0:
        raise ValueError("usd rates must be > 0")
    if entry_value_irr <= 0 or current_value_irr <= 0:
        raise ValueError("values must be > 0")

    usd_entry = entry_value_irr / entry_usd_rate
    usd_current = current_value_irr / current_usd_rate
    dollar_roi_pct = ((usd_current - usd_entry) / usd_entry) * 100.0
    irr_roi_pct = ((current_value_irr - entry_value_irr) / entry_value_irr) * 100.0
    usd_growth_pct = ((current_usd_rate - entry_usd_rate) / entry_usd_rate) * 100.0

    return DollarAdjustedResult(
        irr_roi_pct=round(irr_roi_pct, 2),
        dollar_roi_pct=round(dollar_roi_pct, 2),
        usd_growth_pct=round(usd_growth_pct, 2),
        alpha_vs_usd=round(dollar_roi_pct, 2),
        is_beating_inflation=dollar_roi_pct > 0,
    )


# ── Thin async wrapper for service consumers ──────────────────────


class GoldCalculator:
    """Facade for the pure functions; useful when a service needs them."""

    @staticmethod
    def nav_premium(market_price: float, nav: float) -> dict[str, Any]:
        return calculate_nav_premium(market_price, nav).__dict__

    @staticmethod
    def coin_bubble(
        coin_price_irr: float,
        gold_oz_usd: float,
        usd_irr: float,
        weight_g: float = COIN_BAHAR_WEIGHT_G,
        purity: float = COIN_BAHAR_PURITY,
    ) -> dict[str, Any]:
        return calculate_coin_bubble(coin_price_irr, gold_oz_usd, usd_irr, weight_g, purity).__dict__

    @staticmethod
    def dollar_adjusted_return(
        entry_value_irr: float,
        current_value_irr: float,
        entry_usd_rate: float,
        current_usd_rate: float,
    ) -> dict[str, Any]:
        return calculate_dollar_adjusted_return(
            entry_value_irr, current_value_irr, entry_usd_rate, current_usd_rate
        ).__dict__
