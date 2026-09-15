"""تست pricer + bubbler."""

from __future__ import annotations

import pytest

from src.gold_desk import pricer
from src.gold_desk.bubbler import calc_bubble

XAU = 2750.0
USD = 68000.0
AED = 18520.0  # ~ USD / 3.6725

# مقادیر صحیح مورد انتظار
EXPECTED_GOLD_18K_PER_GRAM = (XAU * USD) / 31.1034768 * (750.0 / 999.9)
EXPECTED_COIN_EMAMI = (XAU * USD) / 31.1034768 * (900.0 / 999.9) * 8.133 + 80_000


# ── pricer ──────────────────────────────────────────────────────


def test_base_24k():
    v = pricer.base_24k_per_gram(XAU, USD)
    assert abs(v - (XAU * USD) / 31.1034768) < 1e-6


def test_gold_18k():
    v = pricer.fair_gold_18k(XAU, USD)
    assert abs(v - EXPECTED_GOLD_18K_PER_GRAM) < 1.0


def test_gold_24k():
    v = pricer.fair_gold_24k(XAU, USD)
    assert abs(v - (XAU * USD) / 31.1034768) < 1.0


def test_coin_emami():
    v = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    assert abs(v - EXPECTED_COIN_EMAMI) < 10.0  # tolerance for minting cost


def test_coin_bahar_same_as_emami():
    """سکه بهار و امامی وزن یکسان دارند."""
    a = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    b = pricer.fair_coin("IR_COIN_BAHAR", XAU, USD)
    assert abs(a - b) < 0.01


def test_coin_half_half_of_emami():
    """نیم سکه ≈ نصف تمام."""
    full = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    half = pricer.fair_coin("IR_COIN_HALF", XAU, USD)
    # minting cost روی هر دو هست پس تفاوت ~0
    assert abs(full - 2 * half) < 50_000  # 50k minting cost


def test_invalid_input():
    with pytest.raises(ValueError):
        pricer.base_24k_per_gram(0, USD)
    with pytest.raises(ValueError):
        pricer.base_24k_per_gram(XAU, -1)


def test_unknown_symbol():
    with pytest.raises(ValueError):
        pricer.fair_value("INVALID_SYM", XAU, USD)


def test_fair_value_dispatch():
    assert pricer.fair_value("IR_GOLD_18K", XAU, USD) == pricer.fair_gold_18k(XAU, USD)
    assert pricer.fair_value("IR_GOLD_24K", XAU, USD) == pricer.fair_gold_24k(XAU, USD)
    assert pricer.fair_value("IR_COIN_EMAMI", XAU, USD) == pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)


# ── bubbler ─────────────────────────────────────────────────────


def test_bubble_positive():
    """market > fair → bubble مثبت."""
    fair = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    market = fair * 1.10  # 10% بالاتر
    r = calc_bubble("IR_COIN_EMAMI", market, fair, XAU)
    assert abs(r.bubble_pct - 10.0) < 0.01
    assert r.bubble_abs > 0


def test_bubble_zero():
    fair = 100.0
    r = calc_bubble("IR_GOLD_18K", 100.0, fair, XAU)
    assert r.bubble_pct == 0.0
    assert r.bubble_abs == 0.0


def test_bubble_negative():
    fair = 100.0
    r = calc_bubble("IR_GOLD_18K", 95.0, fair, XAU)
    assert r.bubble_pct < 0
    assert r.bubble_abs < 0


def test_implied_usd_reasonable():
    """implied_usd برای طلای 18k بدون حباب ≈ USD بازار."""
    # استفاده از طلای 18K که minting ندارد
    fair = pricer.fair_gold_18k(XAU, USD)
    market = fair  # بدون حباب
    r = calc_bubble("IR_GOLD_18K", market, fair, XAU)
    # tolerance < 1%
    assert abs(r.implied_usd - USD) / USD < 0.01


def test_implied_usd_coin_above_market():
    """برای سکه، به‌دلیل minting cost، implied_usd کمی بالاتر است."""
    fair = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    market = fair  # بدون حباب سفته‌بازی
    r = calc_bubble("IR_COIN_EMAMI", market, fair, XAU)
    # implied_usd بالاتر از USD بازار است (minting باعث بالاتر رفتن می‌شود)
    assert r.implied_usd > USD


def test_implied_usd_high_bubble():
    """اگه حباب 20% باشه، implied_usd بالاتر از USD بازار."""
    fair = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    market = fair * 1.20
    r = calc_bubble("IR_COIN_EMAMI", market, fair, XAU)
    assert r.implied_usd > USD * 1.10  # حداقل 10% بالاتر
