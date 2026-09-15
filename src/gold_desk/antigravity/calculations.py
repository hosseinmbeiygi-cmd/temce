"""موتور محاسباتی Antigravity — پیاده‌سازی دقیق فرمول‌های پرامپت جامع.

همه ضرایب مطابق spec: وزن 8.133g، عیار 0.915، اونس 31.1035g
"""

from __future__ import annotations

from dataclasses import dataclass

# ── 1. NAV Premium/Discount ───────────────────────────────────────


@dataclass(frozen=True)
class NavPremiumResult:
    premium_pct: float
    signal: str  # BUY | SELL | NEUTRAL
    reason: str


def calculate_nav_premium(market_price: float, nav: float) -> NavPremiumResult:
    """محاسبه پرمیوم/دیسکانت صندوق نسبت به NAV — دقیقاً طبق spec."""
    if nav <= 0:
        raise ValueError(f"NAV must be >0, got {nav}")
    premium_pct = ((market_price - nav) / nav) * 100

    if premium_pct > 2:
        signal = "SELL"
        reason = f"صندوق {premium_pct:.2f}% بیش از NAV معامله می‌شود (اشباع خرید)"
    elif premium_pct < -1:
        signal = "BUY"
        reason = f"صندوق {abs(premium_pct):.2f}% زیر NAV معامله می‌شود (فرصت خرید)"
    else:
        signal = "NEUTRAL"
        reason = f"صندوق در محدوده منطقی NAV معامله می‌شود ({premium_pct:+.2f}%)"

    return NavPremiumResult(premium_pct=premium_pct, signal=signal, reason=reason)


# ── 2. حباب سکه ───────────────────────────────────────────────────


@dataclass(frozen=True)
class CoinBubbleResult:
    coin_intrinsic: float
    coin_actual: float
    bubble_pct: float
    signal: str  # BUY | SELL | NEUTRAL
    reason: str


# ثابت‌های spec
_TROY_OZ_GRAMS: float = 31.1035
_COIN_WEIGHT_GRAMS: float = 8.133
_COIN_PURITY: float = 0.915


def calculate_coin_bubble(
    coin_price_irr: float,
    gold_oz_usd: float,
    usd_rate: float,
) -> CoinBubbleResult:
    """محاسبه حباب/دیسکانت سکه — دقیقاً فرمول spec."""
    coin_gold_weight_oz = _COIN_WEIGHT_GRAMS / _TROY_OZ_GRAMS
    coin_intrinsic = gold_oz_usd * coin_gold_weight_oz * _COIN_PURITY * usd_rate
    bubble_pct = ((coin_price_irr - coin_intrinsic) / coin_intrinsic) * 100 if coin_intrinsic > 0 else 0.0

    if bubble_pct > 5:
        signal = "SELL"
        reason = f"سکه {bubble_pct:.2f}% حباب دارد (فروش فیزیکی / خرید اونس)"
    elif bubble_pct < -3:
        signal = "BUY"
        reason = f"سکه {abs(bubble_pct):.2f}% تخفیف دارد (خرید فیزیکی)"
    else:
        signal = "NEUTRAL"
        reason = f"سکه در محدوده منطقی معامله می‌شود ({bubble_pct:+.2f}%)"

    return CoinBubbleResult(
        coin_intrinsic=coin_intrinsic,
        coin_actual=coin_price_irr,
        bubble_pct=bubble_pct,
        signal=signal,
        reason=reason,
    )


# ── 3. Margin / Futures Risk ─────────────────────────────────────


class FuturesRiskCalculator:
    """محاسبه‌گر ریسک و مارجین برای معاملات آتی سکه — دقیقاً طبق spec."""

    def __init__(self, leverage: int = 10):
        self.leverage = leverage
        self.initial_margin_ratio = 1 / leverage  # 10%
        self.maintenance_margin_ratio = 0.05  # 5%

    def calculate_liquidation_price(self, entry_price: float, position_type: str) -> float:
        margin_buffer = self.initial_margin_ratio - self.maintenance_margin_ratio
        if position_type.upper() == "LONG":
            return entry_price * (1 - margin_buffer)
        else:  # SHORT
            return entry_price * (1 + margin_buffer)

    def health_ratio(self, equity: float, used_margin: float) -> float:
        if used_margin == 0:
            return float("inf")
        return equity / used_margin

    def margin_call_alert(
        self,
        current_price: float,
        entry_price: float,
        position_type: str,
        equity: float,
        position_value: float,
    ) -> dict:
        liq_price = self.calculate_liquidation_price(entry_price, position_type)

        if position_type.upper() == "LONG":
            distance_to_liq = ((current_price - liq_price) / current_price) * 100 if current_price else 0
        else:
            distance_to_liq = ((liq_price - current_price) / current_price) * 100 if current_price else 0

        used_margin = position_value * self.initial_margin_ratio
        health = self.health_ratio(equity, used_margin)

        if health < 1.2:
            alert_level = "CRITICAL"
            message = f"⚠️ کال‌مارجین نزدیک است! فاصله تا لیکوئید: {distance_to_liq:.2f}%"
        elif health < 2.0:
            alert_level = "WARNING"
            message = f"⚡ هشدار مارجین. نسبت سلامت: {health:.2f}"
        else:
            alert_level = "SAFE"
            message = f"✅ پوزیشن سالم. نسبت سلامت: {health:.2f}"

        return {
            "alert_level": alert_level,
            "message": message,
            "liquidation_price": liq_price,
            "distance_to_liq_pct": distance_to_liq,
            "health_ratio": health,
        }


# ── 4. بازده دلاری ────────────────────────────────────────────────


@dataclass(frozen=True)
class DollarAdjustedResult:
    irr_roi_pct: float
    dollar_roi_pct: float
    usd_growth_pct: float
    alpha_vs_usd: float
    usd_entry_value: float
    usd_current_value: float
    is_beating_inflation: bool


def calculate_dollar_adjusted_return(
    entry_value_irr: float,
    current_value_irr: float,
    entry_usd_rate: float,
    current_usd_rate: float,
) -> DollarAdjustedResult:
    """بازده تعدیل‌شده دلاری — KPI اصلی."""
    if entry_usd_rate <= 0 or current_usd_rate <= 0:
        raise ValueError("USD rates must be >0")
    usd_entry = entry_value_irr / entry_usd_rate
    usd_current = current_value_irr / current_usd_rate

    dollar_roi_pct = ((usd_current - usd_entry) / usd_entry) * 100 if usd_entry else 0
    irr_roi_pct = ((current_value_irr - entry_value_irr) / entry_value_irr) * 100 if entry_value_irr else 0
    usd_growth_pct = ((current_usd_rate - entry_usd_rate) / entry_usd_rate) * 100

    return DollarAdjustedResult(
        irr_roi_pct=round(irr_roi_pct, 2),
        dollar_roi_pct=round(dollar_roi_pct, 2),
        usd_growth_pct=round(usd_growth_pct, 2),
        alpha_vs_usd=round(dollar_roi_pct, 2),
        usd_entry_value=round(usd_entry, 2),
        usd_current_value=round(usd_current, 2),
        is_beating_inflation=dollar_roi_pct > 0,
    )


# ── 5. موتور آربیتراژ طلا ────────────────────────────────────────


@dataclass(frozen=True)
class ArbitrageResult:
    gross_spread_pct: float
    net_spread_pct: float
    action: str  # BUY_ETF_SELL_PHYSICAL | BUY_PHYSICAL_SELL_ETF | NO_ARBITRAGE
    strategy: str


def scan_gold_arbitrage(
    etf_price_per_gram: float,
    physical_gold_price_per_gram: float,
    transaction_cost_pct: float = 0.003,
) -> ArbitrageResult:
    """شناسایی آربیتراژ بین ETF/گواهی و طلای فیزیکی."""
    if etf_price_per_gram <= 0:
        raise ValueError("etf_price_per_gram must be >0")
    price_spread_pct = ((physical_gold_price_per_gram - etf_price_per_gram) / etf_price_per_gram) * 100
    net_spread_pct = price_spread_pct - (transaction_cost_pct * 100)

    if net_spread_pct > 1.5:
        action = "BUY_ETF_SELL_PHYSICAL"
        strategy = "خرید صندوق طلا در بورس و فروش طلای آب‌شده در بازار فیزیکی"
    elif net_spread_pct < -1.5:
        action = "BUY_PHYSICAL_SELL_ETF"
        strategy = "خرید طلای فیزیکی و فروش/ردیم واحدهای صندوق طلا"
    else:
        action = "NO_ARBITRAGE"
        strategy = "اختلاف قیمت کمتر از هزینه تراکنش است؛ آربیتراژ توجیه‌پذیر نیست."

    return ArbitrageResult(
        gross_spread_pct=round(price_spread_pct, 2),
        net_spread_pct=round(net_spread_pct, 2),
        action=action,
        strategy=strategy,
    )
