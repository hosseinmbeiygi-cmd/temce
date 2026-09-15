from __future__ import annotations

import math
from decimal import Decimal

TROY_OUNCE_GRAMS = Decimal("31.1034768")

# قیمت منصفانه طلای داخلی (ریال) — بدون حباب
# FV = XAU_USD * USD_IRR / 31.1035 * purity * unit_conversion
# واحد: XAU=USD/ounce, USD_IRR=IRR, خروجی=IRR/gram


def fair_value_gold_irr(
    xau_usd: float | Decimal,
    usd_irr: float | Decimal,
    purity: float = 0.75,
) -> Decimal:
    xau = Decimal(str(xau_usd))
    usd = Decimal(str(usd_irr))
    pur = Decimal(str(purity))
    if xau <= 0 or usd <= 0:
        raise ValueError("xau_usd and usd_irr must be positive")
    return (xau * usd / TROY_OUNCE_GRAMS * pur).quantize(Decimal("1"))


def premium_log(local_price: float | Decimal, fair_value: float | Decimal) -> float:
    """لگاریتم پریمیوم: log(P_local) - log(FV) — برای مدل‌سازی."""
    lp = float(local_price)
    fv = float(fair_value)
    if lp <= 0 or fv <= 0:
        return 0.0
    return math.log(lp) - math.log(fv)


def premium_from_log(fair_value: float | Decimal, premium_log_val: float) -> Decimal:
    fv = float(fair_value)
    return Decimal(str(math.exp(math.log(fv) + premium_log_val))).quantize(Decimal("1"))
