"""Self-check test — calculators بدون نیاز به DB / BrsApi.

اجرا: python -m services.gold.test_self_check
"""

from __future__ import annotations

import contextlib
import sys

from services.gold.calculator import (
    calculate_coin_bubble,
    calculate_dollar_adjusted_return,
    calculate_nav_premium,
)
from services.gold.futures_risk import FuturesRiskCalculator


def test_nav_premium():
    # NAV برابر → premium صفر → NEUTRAL
    n = calculate_nav_premium(100, 100)
    assert n.signal == "NEUTRAL" and n.premium_pct == 0.0

    # 10% بالای NAV → SELL
    n = calculate_nav_premium(110, 100)
    assert n.signal == "SELL" and n.premium_pct == 10.0

    # 2% زیر NAV → BUY
    n = calculate_nav_premium(98, 100)
    assert n.signal == "BUY" and n.premium_pct == -2.0

    # 0.5% بالا → NEUTRAL
    n = calculate_nav_premium(100.5, 100)
    assert n.signal == "NEUTRAL"

    print("✓ nav_premium: 4 cases passed")


def test_coin_bubble():
    # بازار نرمال ایران (حباب 400-700%)
    b = calculate_coin_bubble(400_000_000, 2500, 70_000)
    assert 400 < b.bubble_pct < 1000, f"unexpected bubble: {b.bubble_pct}"

    # حباب خیلی بالا
    b = calculate_coin_bubble(700_000_000, 2500, 70_000)
    assert b.signal == "SELL"

    # حباب پایین (خرید)
    b = calculate_coin_bubble(150_000_000, 2500, 70_000)
    assert b.signal == "BUY"

    # validation
    with contextlib.suppress(ValueError):
        calculate_coin_bubble(-1, 2500, 70_000)
        raise AssertionError("should have raised")

    print("✓ coin_bubble: 4 cases passed")


def test_dollar_adjusted():
    # IRR رشد 20%، دلار رشد 20% → alpha صفر
    d = calculate_dollar_adjusted_return(1_000_000_000, 1_200_000_000, 50_000, 60_000)
    assert d.irr_roi_pct == 20.0
    assert d.usd_growth_pct == 20.0
    assert d.dollar_roi_pct == 0.0
    assert not d.is_beating_inflation

    # IRR رشد 20%، دلار رشد 10% → alpha مثبت (~9%)
    d = calculate_dollar_adjusted_return(1_000_000_000, 1_200_000_000, 50_000, 55_000)
    assert d.dollar_roi_pct > 0
    assert d.is_beating_inflation

    print("✓ dollar_adjusted: 2 cases passed")


def test_futures_risk():
    c = FuturesRiskCalculator(leverage=10)
    # LONG 10x
    r = c.calculate(300_000_000, "LONG", 1, 305_000_000, 50_000_000)
    assert r.liquidation_price == 285_000_000
    assert r.initial_margin == 300_000_000
    assert r.maintenance_margin == 150_000_000
    assert r.recommended_stop_loss is not None
    assert r.unrealized_pnl_irr == 50_000_000

    # SHORT 10x
    r = c.calculate(300_000_000, "SHORT", 1, 295_000_000, 50_000_000)
    assert r.liquidation_price == 315_000_000
    assert r.unrealized_pnl_irr == 50_000_000

    # بدون current_price → health=None
    r = c.calculate(300_000_000, "LONG", 1)
    assert r.health_ratio is None
    assert r.liquidation_price == 285_000_000

    # leverage نامعتبر
    with contextlib.suppress(ValueError):
        FuturesRiskCalculator(leverage=0)
        raise AssertionError("should raise")

    print("✓ futures_risk: 4 cases passed")


if __name__ == "__main__":
    test_nav_premium()
    test_coin_bubble()
    test_dollar_adjusted()
    test_futures_risk()
    print("\n✅ all self-checks passed")
    sys.exit(0)

