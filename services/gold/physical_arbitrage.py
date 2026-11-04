"""موتور طلای فیزیکی — تبدیل مثقال، عیارسنجی، حباب سکه و آربیتراژ شمش/آب‌شده.

فرمول‌های مرجع (بازار طلای ایران):

  • ۱ مثقال = ۴٫۶۰۸۳ گرم طلای ۱۷ عیار (۷۰۵)
    Gram18 = (Mesghal_17_Price / 4.6083) * (750 / 705)

  • تبدیل وزن به معادل ۱۸ عیار:
    Real_Weight_Gram18 = Weight * (Assay / 750)

  • ارزش ذاتی سکه:
    Intrinsic = Ounce_USD * USD_IRR * (Net_Weight / 31.1035) * (900 / 999.9)

  • حباب سکه:
    Bubble = (Market_Price - Intrinsic) / Intrinsic * 100

  • آربیتراژ گواهی شمش بورس کالا (۹۹۵) با طلای آب‌شدهٔ تهران (۷۵۰)
    با ۰٫۱۵٪ کارمزد در هر طرف معامله.

همهٔ توابع pure هستند: بدون DB، بدون I/O و بدون side effect.
"""

from __future__ import annotations

import math
from typing import Any

# Import constants from single source of truth
from services.gold.constants import (
    _COIN_ALIASES,
    COIN_SPECS,
    GERAMI_MINTING_FEE_IRR,
    IME_BULLION_ASSAY,
    IME_EXCHANGE_FEE,
    MESGHAL_GRAMS,
    MIN_NET_SPREAD_PCT,
    PURITY_17K,
    PURITY_18K,
    PURITY_FINE,
    TROY_OUNCE_GRAMS,
)


def _require_positive(name: str, value: float) -> None:
    """اعتبارسنجی مشترک: باید عددی متناهی و بزرگ‌تر از صفر باشد."""
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {value!r}")


def _canonical_coin_key(raw_key: str) -> str | None:
    """نرمال‌سازی نماد سکه: ``IR_COIN_EMAMI`` / ``coin_half`` / ``bahar``."""
    key = str(raw_key).strip().lower().replace("-", "_").replace(" ", "_")
    for prefix in ("ir_coin_", "coin_", "ir_"):
        if key.startswith(prefix):
            key = key[len(prefix) :]
    return _COIN_ALIASES.get(key)


def calculate_gram18_from_mesghal(mesghal_price: float) -> float:
    """قیمت هر گرم طلای ۱۸ عیار از روی مظنهٔ مثقال ۱۷ عیار.

    ۱ مثقال = ۴٫۶۰۸۳ گرم طلای ۷۰۵؛ برای رسیدن به ۷۵۰ کافی است در
    نسبت ``750 / 705`` ضرب شود.
    """
    _require_positive("mesghal_price", mesghal_price)
    return mesghal_price / MESGHAL_GRAMS * (PURITY_18K / PURITY_17K)


def adjust_melted_by_assay(
    weight_grams: float, assay: int, base_gram18_price: float
) -> dict[str, Any]:
    """ارزش طلای آب‌شده با عیار دلخواه، بر پایهٔ قیمت گرم ۱۸ عیار.

    ``Real_Weight_Gram18 = Weight * (Assay / 750)`` و ارزش = وزن واقعی ×
    قیمت گرم ۱۸ عیار. عیار ۷۵۰ وزن را تغییر نمی‌دهد، عیار پایین‌تر وزن
    معادل را کم و عیار بالاتر آن را زیاد می‌کند.
    """
    if weight_grams is None or not math.isfinite(weight_grams) or weight_grams < 0:
        raise ValueError(f"weight_grams must be finite and >= 0, got {weight_grams!r}")
    if assay is None or not math.isfinite(assay) or assay <= 0:
        raise ValueError(f"assay must be a finite positive number, got {assay!r}")
    _require_positive("base_gram18_price", base_gram18_price)

    real_weight = weight_grams * (float(assay) / PURITY_18K)
    return {
        "weight_grams": float(weight_grams),
        "assay": int(assay),
        "real_weight_gram18": real_weight,
        "base_gram18_price_irr": float(base_gram18_price),
        "value_irr": real_weight * float(base_gram18_price),
    }


def calculate_coin_bubbles(
    ounce_usd: float,
    usd_irr: float,
    coin_prices: dict[str, float],
    *,
    gerami_minting_fee_irr: float = GERAMI_MINTING_FEE_IRR,
) -> dict[str, dict[str, Any]]:
    """حباب/تخفیف هر قطع سکه نسبت به ارزش ذاتی فلزش.

    ارزش ذاتی از اونس جهانی و نرخ آزاد دلار ساخته می‌شود؛ سکهٔ گرمی
    کارمزد ضرب هم دارد. قطع‌های غایب در ``coin_prices`` نادیده گرفته
    می‌شوند تا یک فید ناقص کل محاسبه را از کار نیندازد.
    """
    _require_positive("ounce_usd", ounce_usd)
    _require_positive("usd_irr", usd_irr)
    if (
        gerami_minting_fee_irr is None
        or not math.isfinite(gerami_minting_fee_irr)
        or gerami_minting_fee_irr < 0
    ):
        raise ValueError("gerami_minting_fee_irr must be finite and >= 0")

    gold_per_gram_fine = (ounce_usd * usd_irr) / TROY_OUNCE_GRAMS
    bubbles: dict[str, dict[str, Any]] = {}

    for raw_key, market_price in coin_prices.items():
        coin = _canonical_coin_key(raw_key)
        if coin is None or coin in bubbles:
            continue

        _require_positive(f"coin_prices[{raw_key!r}]", market_price)

        spec = COIN_SPECS[coin]
        weight_grams = spec["weight_grams"]
        purity = spec["purity"]
        # Use mint_fee_irr from coin spec (single source of truth).
        # Override with gerami_minting_fee_irr if explicitly provided.
        minting_fee = spec.get("mint_fee_irr", 0.0)
        if coin == "gerami":
            minting_fee = gerami_minting_fee_irr

        gold_value = gold_per_gram_fine * weight_grams * ((purity * 1000) / PURITY_FINE)
        intrinsic = gold_value + minting_fee

        bubble_pct = (market_price - intrinsic) / intrinsic * 100.0
        bubbles[coin] = {
            "weight_grams": weight_grams,
            "purity": purity,
            "gold_value_irr": gold_value,
            "minting_fee_irr": minting_fee,
            "intrinsic_value_irr": intrinsic,
            "market_price_irr": float(market_price),
            "bubble_pct": bubble_pct,
            "is_discount": bubble_pct < 0,
        }

    return bubbles


def calculate_ime_vs_melted_arbitrage(
    ime_cert_price_irr: float, melted_gram18_price_irr: float
) -> dict[str, Any]:
    """آربیتراژ گواهی شمش بورس کالا در برابر طلای آب‌شدهٔ تهران.

    گواهی شمش با عیار ۹۹۵ معامله می‌شود، پس قیمت آب‌شدهٔ ۷۵۰ با نسبت
    ``995 / 750`` هم‌مقیاس می‌شود. سپس ۰٫۱۵٪ کارمزد فروش گواهی و
    ۰٫۱۵٪ کارمزد خرید آب‌شده از اسپرد کسر می‌شود.

    اسپرد مثبت = گواهی گران‌تر از فیزیکی → خرید آب‌شده و فروش گواهی.
    """
    _require_positive("ime_cert_price_irr", ime_cert_price_irr)
    _require_positive("melted_gram18_price_irr", melted_gram18_price_irr)

    assay_factor = IME_BULLION_ASSAY / PURITY_18K
    melted_equivalent = melted_gram18_price_irr * assay_factor

    gross_spread_pct = (ime_cert_price_irr - melted_equivalent) / melted_equivalent * 100.0

    cert_net_proceeds = ime_cert_price_irr * (1.0 - IME_EXCHANGE_FEE)
    melted_purchase_cost = melted_equivalent * (1.0 + IME_EXCHANGE_FEE)
    net_spread_pct = (cert_net_proceeds - melted_purchase_cost) / melted_purchase_cost * 100.0

    if net_spread_pct >= MIN_NET_SPREAD_PCT:
        action = "BUY_MELTED_SELL_IME_CERT"
        strategy = "خرید طلای آب‌شدهٔ تهران و فروش گواهی شمش در بورس کالا"
    elif net_spread_pct <= -MIN_NET_SPREAD_PCT:
        action = "BUY_IME_CERT_SELL_MELTED"
        strategy = "خرید گواهی شمش و فروش طلای آب‌شدهٔ فیزیکی"
    else:
        action = "NO_ARBITRAGE"
        strategy = "اسپرد خالص پس از کارمزد ۰٫۱۵٪ در هر طرف، توجیه‌پذیر نیست."

    return {
        "ime_cert_price_irr": float(ime_cert_price_irr),
        "melted_gram18_price_irr": float(melted_gram18_price_irr),
        "melted_equivalent_fine_irr": melted_equivalent,
        "assay_factor": assay_factor,
        "gross_spread_pct": gross_spread_pct,
        "net_spread_pct": net_spread_pct,
        "fee_pct": IME_EXCHANGE_FEE * 100.0,
        "total_fee_pct": IME_EXCHANGE_FEE * 200.0,
        "action": action,
        "strategy": strategy,
        "is_profitable": action != "NO_ARBITRAGE",
    }
