"""Unit tests for the unified engine — فاز ۰.

Fixed inputs from the task: XAU=3998, USD_IRR=2,695,000.

The same physical price has two display scales:

* Rial scale  : USD_IRR = 2,695,000 → 18k gram = 259,834,800.09 Rial
* Toman scale : USD_TOMAN =   269,500 → 18k gram =  25,983,480.01 Toman

BrsApi's raw payload declares ``unit="تومان"`` for gold/currency, so the API
contract exposes Toman. The engine is scale-agnostic; the tests below pin both
scales and prove they differ by exactly 10×. Regression guard: the old
duplicate applied purity twice (``750/999.9`` **and** ``0.75``), returning
~194,876,100 instead of ~259,834,800 (Rial scale).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.gold_desk.antigravity.engine import (
    calculate_bubble_abs,
    calculate_bubble_pct,
    calculate_coin_intrinsic,
    calculate_implied_usd,
    calculate_pure_gold_18k,
    calculate_snapshot_fields,
)
from src.gold_desk.bubbler import _pure_gold_weight
from src.gold_desk.constants import (
    COIN_MINTING_COSTS,
    COIN_WEIGHTS,
    GOLD_PURITY_18K,
    GOLD_PURITY_24K,
    GOLD_PURITY_COIN,
    MINTING_COST_TOMAN,
    TROY_OUNCE_GRAMS,
)
from src.gold_desk.pricer import fair_coin, fair_gold_18k, round_to_rial

XAU_USD = 3998.0
USD_RIAL = 2_695_000.0
USD_TOMAN = 269_500.0
SYMBOL = "IR_COIN_EMAMI"
AS_OF = datetime(2026, 10, 18, 20, 41, 3, 358000, tzinfo=UTC)

BASE_24K_RIAL = (XAU_USD * USD_RIAL) / TROY_OUNCE_GRAMS
EXPECTED_GOLD_18K_RIAL = BASE_24K_RIAL * (GOLD_PURITY_18K / GOLD_PURITY_24K)
EXPECTED_GOLD_18K_TOMAN = EXPECTED_GOLD_18K_RIAL / 10.0

COIN_MINT_TOMAN = COIN_MINTING_COSTS.get(SYMBOL, MINTING_COST_TOMAN)
COIN_GOLD_RIAL = (
    COIN_WEIGHTS[SYMBOL] * (GOLD_PURITY_COIN / GOLD_PURITY_24K) * BASE_24K_RIAL
)
EXPECTED_COIN_RIAL = COIN_GOLD_RIAL + COIN_MINT_TOMAN * 10.0
EXPECTED_COIN_TOMAN = EXPECTED_COIN_RIAL / 10.0


@pytest.fixture(name="rial_inputs")
def fixture_rial_inputs():
    return {"xau_usd": XAU_USD, "usd_irt": USD_RIAL}


@pytest.fixture(name="toman_inputs")
def fixture_toman_inputs():
    return {"xau_usd": XAU_USD, "usd_irt": USD_TOMAN}


def test_base_24k_matches_expected_order_of_magnitude():
    """پایهٔ ۲۴ عیار در مقیاس ریال: XAU × USD_IRR / 31.1034768."""
    assert BASE_24K_RIAL == pytest.approx(346_411_755.4858, abs=0.01)


def test_calculate_pure_gold_18k_rial(rial_inputs):
    """گرم ۱۸ با ورودی ریالی: ۲۵۹٬۸۳۴٬۸۰۰ ریال (نه ۱۹۴٬۸۷۶٬۱۰۰)."""
    result = calculate_pure_gold_18k(rial_inputs["xau_usd"], rial_inputs["usd_irt"])

    assert result == pytest.approx(259_834_800.0944, abs=0.01)
    assert result == pytest.approx(EXPECTED_GOLD_18K_RIAL, rel=1e-12)
    # Regression: double-purity produced exactly 0.75× this value.
    assert result != pytest.approx(194_876_100.07, abs=1.0)


def test_calculate_pure_gold_18k_toman(toman_inputs):
    """همان فرمول در مقیاس تومان = یک‌دهم مقدار ریالی (قرارداد API)."""
    result = calculate_pure_gold_18k(toman_inputs["xau_usd"], toman_inputs["usd_irt"])

    assert result == pytest.approx(EXPECTED_GOLD_18K_TOMAN, rel=1e-12)
    assert result == pytest.approx(25_983_480.00944, abs=0.01)
    assert result == pytest.approx(
        calculate_pure_gold_18k(XAU_USD, USD_RIAL) / 10.0, rel=1e-12
    )


def test_24k_and_18k_share_one_purity_definition(toman_inputs):
    """۲۴ عیار = پایه؛ ۱۸ عیار = پایه × 750/999.9 (بدون ۰.۷۵ دوباره)."""
    from src.gold_desk.pricer import fair_gold_24k

    xau, usd = toman_inputs["xau_usd"], toman_inputs["usd_irt"]
    assert fair_gold_24k(xau, usd) == pytest.approx((xau * usd) / TROY_OUNCE_GRAMS)
    assert fair_gold_18k(xau, usd) / fair_gold_24k(xau, usd) == pytest.approx(
        GOLD_PURITY_18K / GOLD_PURITY_24K
    )
    assert calculate_pure_gold_18k(xau, usd) == pytest.approx(fair_gold_18k(xau, usd))


def test_calculate_coin_intrinsic_rial(rial_inputs):
    """سکه امامی ۸.۱۳۳ گرم / ۹۰۰ + ۸۰۰٬۰۰۰ ریال کارمزد (۸۰٬۰۰۰ تومان)."""
    result = calculate_coin_intrinsic(
        SYMBOL, rial_inputs["xau_usd"], rial_inputs["usd_irt"], unit="rial"
    )

    assert result == pytest.approx(2_536_683_715.0009, abs=0.01)
    assert result == pytest.approx(EXPECTED_COIN_RIAL, rel=1e-12)
    assert result == pytest.approx(
        fair_coin(SYMBOL, rial_inputs["xau_usd"], rial_inputs["usd_irt"], unit="rial"),
        rel=1e-12,
    )


def test_calculate_coin_intrinsic_toman(toman_inputs):
    """همان سکه در تومان: کارمزد ۸۰٬۰۰۰ تومان، نه ۸۰٬۰۰۰ ریال."""
    result = calculate_coin_intrinsic(
        SYMBOL, toman_inputs["xau_usd"], toman_inputs["usd_irt"]
    )

    assert result == pytest.approx(253_668_371.50009, abs=0.01)
    assert result == pytest.approx(EXPECTED_COIN_TOMAN, rel=1e-12)
    assert result / calculate_coin_intrinsic(
        SYMBOL, XAU_USD, USD_RIAL, unit="rial"
    ) == pytest.approx(0.1, rel=1e-12)


@pytest.mark.parametrize(
    ("symbol", "weight", "mint_toman"),
    [
        ("IR_COIN_EMAMI", 8.133, 80_000.0),
        ("IR_COIN_HALF", 4.066, 50_000.0),
        ("IR_COIN_QUARTER", 2.033, 35_000.0),
        ("IR_COIN_GERAMI", 1.010, 15_000.0),
    ],
)
def test_coin_family_weights_and_mint(symbol, weight, mint_toman):
    """تمام/نیم/ربع/گرمی: وزن و کارمزد canonical، یک فرمول."""
    expected = (
        weight * (GOLD_PURITY_COIN / GOLD_PURITY_24K) * BASE_24K_RIAL
        + mint_toman * 10.0
    )
    result = calculate_coin_intrinsic(symbol, XAU_USD, USD_RIAL, unit="rial")
    assert result == pytest.approx(expected, rel=1e-12)
    assert COIN_WEIGHTS[symbol] == weight
    assert COIN_MINTING_COSTS[symbol] == mint_toman


def test_coin_intrinsic_rejects_unknown_symbol(rial_inputs):
    with pytest.raises(ValueError):
        calculate_coin_intrinsic(
            "IR_COIN_UNKNOWN", rial_inputs["xau_usd"], rial_inputs["usd_irt"]
        )


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        calculate_pure_gold_18k(0, USD_RIAL)
    with pytest.raises(ValueError):
        calculate_pure_gold_18k(XAU_USD, -1)


def test_calculate_bubble_pct_and_amount():
    """حباب٪ = (بازار − ذاتی)/ذاتی×۱۰۰ و حباب مقداری = بازار − ذاتی."""
    assert calculate_bubble_pct(150_000, 120_000) == pytest.approx(25.0)
    assert calculate_bubble_pct(100_000, 120_000) == pytest.approx(-16.666666666666664)
    assert calculate_bubble_pct(120_000, 120_000) == pytest.approx(0.0)
    assert calculate_bubble_pct(100_000, 0) is None

    assert calculate_bubble_abs(150_000, 120_000) == pytest.approx(30_000)
    assert calculate_bubble_abs(100_000, 120_000) == pytest.approx(-20_000)
    assert calculate_bubble_abs(100_000, 0) is None


def test_calculate_implied_usd_is_inverse_of_the_same_rate(rial_inputs):
    """اگر بازار = ارزش ذاتی باشد، implied USD باید همان USD ورودی باشد."""
    xau = rial_inputs["xau_usd"]
    fair = calculate_pure_gold_18k(xau, USD_RIAL)
    implied = calculate_implied_usd(fair, "IR_GOLD_18K", xau)

    assert implied == pytest.approx(USD_RIAL, rel=1e-12)
    expected = (fair * TROY_OUNCE_GRAMS) / (_pure_gold_weight("IR_GOLD_18K") * xau)
    assert implied == pytest.approx(expected, rel=1e-12)

    # سکه: کارمزد ضرب باعث می‌شود implied کمی بالاتر از نرخ بازار باشد.
    coin_fair = calculate_coin_intrinsic(SYMBOL, xau, USD_RIAL, unit="rial")
    coin_implied = calculate_implied_usd(coin_fair, SYMBOL, xau)
    assert coin_implied > USD_RIAL
    assert coin_implied == pytest.approx(USD_RIAL, rel=5e-4)

    assert calculate_implied_usd(coin_fair, SYMBOL, 0) is None


def test_round_to_rial_half_up():
    """گرد کردن نهایی ریالی، ROUND_HALF_UP (نه banker's rounding)."""
    assert round_to_rial(1.5, "rial") == 2.0
    assert round_to_rial(2.5, "rial") == 3.0
    assert round_to_rial(1.25, "toman") == 1.3
    assert round_to_rial(25_983_480.05, "toman") == pytest.approx(25_983_480.1)
    assert round_to_rial(259_834_800.0944, "rial") == 259_834_800.0
    assert round_to_rial(4165.175, "ounce") == 4165.18


def test_calculate_snapshot_fields_rial(rial_inputs):
    """فیلدهای قرارداد با ورودی ریالی و کیفیت صریح."""
    fair = calculate_pure_gold_18k(XAU_USD, USD_RIAL)
    market = fair * 1.05
    fields = calculate_snapshot_fields(
        rial_inputs["xau_usd"],
        rial_inputs["usd_irt"],
        market,
        "IR_GOLD_18K",
        source="brsapi",
        quality="LIVE",
        as_of=AS_OF,
        unit="rial",
    )

    assert {"value", "unit", "asOf", "source", "quality", "bubble_abs"} <= fields.keys()
    assert fields["unit"] == "rial"
    assert fields["source"] == "brsapi"
    assert fields["quality"] == "LIVE"
    assert fields["asOf"] == AS_OF.isoformat()
    assert fields["value"] == 259_834_800.0
    assert fields["bubble_abs"] == pytest.approx(12_991_740.0, abs=0.1)
    assert fields["bubble_pct"] == pytest.approx(5.0, rel=1e-9)
    # بازار ۵٪ بالاتر از ذاتی است، پس نرخ دلار ضمنی هم ۵٪ بالاتر است.
    assert fields["implied_usd"] == pytest.approx(USD_RIAL * 1.05, rel=1e-12)


def test_calculate_snapshot_fields_toman_and_default_quality(toman_inputs):
    """قرارداد snapshot تومان است؛ quality پیش‌فرض DELAYED (نه LIVE)."""
    fair = calculate_pure_gold_18k(XAU_USD, USD_TOMAN)
    fields = calculate_snapshot_fields(
        toman_inputs["xau_usd"],
        toman_inputs["usd_irt"],
        fair,
        "IR_GOLD_18K",
        as_of=AS_OF,
    )

    assert fields["unit"] == "toman"
    assert fields["quality"] == "DELAYED"
    assert fields["value"] == pytest.approx(25_983_480.0, abs=1e-9)
    assert fields["bubble_pct"] == pytest.approx(0.0, abs=1e-12)


def test_snapshot_fields_metadata_is_caller_supplied():
    """quality/source را caller می‌دهد تا دادهٔ کهنه LIVE برچسب نخورد."""
    fields = calculate_snapshot_fields(
        XAU_USD,
        USD_TOMAN,
        14_000_000,
        SYMBOL,
        source="tgju",
        quality="DELAYED",
    )
    assert fields["source"] == "tgju"
    assert fields["quality"] == "DELAYED"

    with pytest.raises(ValueError):
        calculate_snapshot_fields(XAU_USD, USD_TOMAN, 14_000_000, SYMBOL, quality="fallback")
    with pytest.raises(ValueError):
        calculate_snapshot_fields(XAU_USD, USD_TOMAN, 14_000_000, SYMBOL, source="mixed")
    with pytest.raises(ValueError):
        calculate_snapshot_fields(XAU_USD, USD_TOMAN, 14_000_000, SYMBOL, unit="kilogram")


def test_coin_snapshot_fields_reject_ounce_unit():
    """سکه واحد اونس ندارد؛ fail-closed به‌جای عدد بی‌معنا."""
    with pytest.raises(ValueError):
        calculate_snapshot_fields(XAU_USD, USD_TOMAN, 250_000_000, SYMBOL, unit="ounce")
