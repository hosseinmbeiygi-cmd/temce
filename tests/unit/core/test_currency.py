"""Unit tests for :mod:`core.currency` (rial ⇄ toman).

The conversion must stay exact: money that goes through ``float`` accumulates
binary representation error, and ``None`` must survive the round trip so an
unavailable price does not silently become ``0``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.config import Settings
from core.currency import (
    CURRENCY_RIAL,
    CURRENCY_TOMAN,
    RIAL_PER_TOMAN,
    rial_to_toman,
    rial_to_toman_float,
    toman_to_rial,
)


def test_unit_codes_and_ratio() -> None:
    assert CURRENCY_TOMAN == "TMN"
    assert CURRENCY_RIAL == "IRR"
    assert Decimal("10") == RIAL_PER_TOMAN


def test_rial_to_toman_divides_by_ten() -> None:
    assert rial_to_toman(1_234_500) == Decimal("123450")
    assert rial_to_toman(Decimal("12345")) == Decimal("1234.5")


def test_toman_to_rial_multiplies_by_ten() -> None:
    assert toman_to_rial(123_450) == Decimal("1234500")
    assert toman_to_rial(Decimal("1234.5")) == Decimal("12345")


@pytest.mark.parametrize("value", [None, ""])
def test_none_is_propagated(value: object) -> None:
    assert rial_to_toman(value) is None  # type: ignore[arg-type]
    assert toman_to_rial(None) is None


@pytest.mark.parametrize("raw", [0, 1, 999, 1_234_567_890])
def test_round_trip_is_lossless(raw: int) -> None:
    toman = rial_to_toman(raw)
    assert toman is not None
    assert toman_to_rial(toman) == Decimal(raw)


def test_round_trip_keeps_fractional_rial() -> None:
    toman = rial_to_toman(Decimal("10.7"))
    assert toman == Decimal("1.07")
    assert toman_to_rial(toman) == Decimal("10.7")


def test_exact_decimal_arithmetic_not_binary_float() -> None:
    # 0.1 + 0.2 == 0.30000000000000004 in binary floating point; in decimal the
    # toman conversion of 3 rial must be exactly 0.3, not 0.3-ish.
    assert rial_to_toman(3) == Decimal("0.3")
    assert toman_to_rial(Decimal("0.3")) == Decimal("3.0")
    # Summing in toman equals converting the rial sum: no drift in either path.
    one, two, three = (rial_to_toman(v) for v in (1, 2, 3))
    assert one is not None and two is not None and three is not None
    assert one + two == three


def test_string_input_with_thousands_separator() -> None:
    assert rial_to_toman("1,234,500") == Decimal("123450")
    assert toman_to_rial("1,234.5") == Decimal("12345.0")


def test_float_input_is_converted_through_str() -> None:
    # str() keeps the value the caller wrote; the naive Decimal(0.1) would not.
    assert toman_to_rial(0.1) == Decimal("1.0")


def test_rounding_only_when_requested() -> None:
    # Exact by default — a fractional toman price is kept, not silently dropped.
    assert rial_to_toman(12345) == Decimal("1234.5")
    # Display rounding is opt-in and uses ROUND_HALF_UP.
    assert rial_to_toman(12345, places=0) == Decimal("1235")
    assert rial_to_toman(12344, places=0) == Decimal("1234")
    assert toman_to_rial(Decimal("1234.55"), places=0) == Decimal("12346")


def test_float_presentation_helper() -> None:
    assert rial_to_toman_float(1_234_500) == 123_450.0
    # JSON payloads must not break on a missing price.
    assert rial_to_toman_float(None) == 0.0
    assert rial_to_toman_float(None, default=None) is None


def test_negative_amounts_are_supported() -> None:
    # Fees, adjustments and short P&L legitimately go negative.
    assert rial_to_toman(-1_000) == Decimal("-100")
    assert toman_to_rial(-100) == Decimal("-1000")


def test_bool_is_rejected() -> None:
    with pytest.raises(TypeError):
        rial_to_toman(True)


def test_non_finite_is_rejected() -> None:
    with pytest.raises(ValueError):
        rial_to_toman(float("nan"))
    with pytest.raises(ValueError):
        toman_to_rial(Decimal("Infinity"))


def test_invalid_places_is_rejected() -> None:
    with pytest.raises(ValueError):
        rial_to_toman(100, places=-1)


def test_default_currency_setting_is_toman() -> None:
    field = Settings.model_fields["default_currency"]
    assert field.default == "TOMAN"
    # The environment variable keeps the requested name.
    assert field.alias == "DEFAULT_CURRENCY"


def test_default_currency_can_be_overridden() -> None:
    assert Settings(DEFAULT_CURRENCY="RIAL").default_currency == "RIAL"
