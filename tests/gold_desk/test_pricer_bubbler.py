"""تست pricer + bubbler."""

from __future__ import annotations

import pytest

from src.gold_desk import bubbler, pricer
from src.gold_desk.bubbler import calc_bubble
from src.gold_desk.constants import COIN_MINTING_COSTS, GOLD_PURITY_18K, GOLD_PURITY_COIN, MINTING_COST_TOMAN

XAU = 2750.0
USD = 68000.0
AED = 18520.0  # ~ USD / 3.6725

# مقادیر صحیح مورد انتظار
EXPECTED_GOLD_18K_PER_GRAM = (XAU * USD) / 31.1034768 * (750.0 / 999.9)
# STEP 6-FIX-2 unified the IR_COIN_EMAMI mint fee at 80,000 IRR, the same
# physical full-coin cost as IR_COIN_BAHAR, so both full coins now price
# identically (emami was previously modelled fee-free).  See
# tests/unit/test_step6_fix2.py::test_emami_mint_fee_unified.
EXPECTED_COIN_EMAMI_GOLD = (XAU * USD) / 31.1034768 * (900.0 / 999.9) * 8.133
EXPECTED_COIN_EMAMI = EXPECTED_COIN_EMAMI_GOLD + 80_000
EXPECTED_COIN_BAHAR = EXPECTED_COIN_EMAMI


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
    assert abs(v - EXPECTED_COIN_EMAMI) < 10.0  # includes unified 80,000 IRR mint fee


def test_coin_bahar_same_as_emami():
    """سکه بهار و امامی وزن و کارمزد ضرب یکسان دارند (STEP 6-FIX-2).

    Emami and bahar are the same 8.133 g / 900-oz coin and now share the
    unified 80,000 IRR mint fee from services.gold.constants; the two full
    coins therefore price identically (emami was previously fee-free).
    """
    a = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    b = pricer.fair_coin("IR_COIN_BAHAR", XAU, USD)
    assert abs(b - EXPECTED_COIN_BAHAR) < 0.01
    # STEP 6-FIX-2: both full coins share the same 80,000 IRR mint fee.
    assert abs(b - a) < 0.01


def test_coin_half_half_of_emami():
    """نیم سکه ≈ نصف تمام."""
    full = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    half = pricer.fair_coin("IR_COIN_HALF", XAU, USD)
    # وزن نیم سکه ۴٫۰۶۶ گرم در برابر ۸٫۱۳۳ گرم تمام است، پس ۰٫۰۰۱ گرم
    # اختلاف وزن در نسبت ۲×نیم − تمام لحاظ می‌شود؛ کارمزد نیم ۵۰ هزار است.
    # STEP 6-FIX-2: the full-coin fee is now 80,000 (emami was 0 before),
    # so the fee-only term becomes 2*50_000 - 80_000 = 20_000.
    coin_gold_per_gram = pricer.base_24k_per_gram(XAU, USD) * (900.0 / 999.9)
    expected = (2 * 50_000 - 80_000) - (8.133 - 2 * 4.066) * coin_gold_per_gram
    assert (2 * half - full) == pytest.approx(expected, abs=1e-6)


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


def test_pricer_and_bubbler_share_one_purity_definition():
    """E-M17: یک تعریف عیار، نه دو تا (750/999.9 در برابر 750/1000)."""
    assert bubbler._purity_for_symbol("IR_GOLD_18K") == pytest.approx(pricer.purity_ratio(GOLD_PURITY_18K))
    assert bubbler._purity_for_symbol("IR_GOLD_MELTED") == pytest.approx(pricer.purity_ratio(GOLD_PURITY_18K))
    assert bubbler._purity_for_symbol("IR_GOLD_24K") == pytest.approx(1.0)
    assert bubbler._purity_for_symbol("IR_COIN_EMAMI") == pytest.approx(
        pricer.purity_ratio(GOLD_PURITY_COIN)
    )


def test_minting_costs_are_in_toman_scale():
    """E-M18: جدول کارمزد ضرب در مقیاس تومان است، نه ریال (خطای ۱۰×)."""
    assert 0 <= MINTING_COST_TOMAN <= 5_000_000
    for _symbol, cost in COIN_MINTING_COSTS.items():
        assert 0 <= cost <= 5_000_000


def test_bubble_pct_none_when_fair_invalid():
    """E-M16: fair<=0 یعنی «ورودی نامعتبر»، نه «حباب صفر».

    صفر سکوتی در scorer امتیاز کامل (GREEN) می‌سازد؛ None در scorer «کامپوننت
    گمشده» شمرده می‌شود و وزنش از available_weight خارج می‌شود (C2).
    """
    r = calc_bubble("IR_GOLD_18K", 100.0, 0.0, XAU)
    assert r.bubble_pct is None


def test_implied_usd_none_when_xau_invalid():
    r = calc_bubble("IR_GOLD_18K", 100.0, 100.0, 0.0)
    assert r.implied_usd is None


def test_implied_usd_high_bubble():
    """اگه حباب 20% باشه، implied_usd بالاتر از USD بازار."""
    fair = pricer.fair_coin("IR_COIN_EMAMI", XAU, USD)
    market = fair * 1.20
    r = calc_bubble("IR_COIN_EMAMI", market, fair, XAU)
    assert r.implied_usd > USD * 1.10  # حداقل 10% بالاتر
