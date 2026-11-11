"""تست محاسبات بازده — اسمی / XIRR / واقعی / دلاری."""

from __future__ import annotations

from datetime import date

import pytest

from src.gold_desk.returns import (
    ReturnsError,
    deflate,
    nominal_pnl,
    to_usd,
    xirr,
)


def test_nominal_pnl_withdrawals_add():
    assert nominal_pnl(ending_value=120, contributions=100, withdrawals=30) == 50


def test_xirr_doubling_over_365_days():
    d0, d1 = date(2023, 1, 1), date(2024, 1, 1)  # exactly 365 days
    assert xirr([(d0, -100.0), (d1, 200.0)]) == pytest.approx(1.0, abs=1e-9)


def test_real_and_usd_returns_are_zero_when_deflators_double():
    d0, d1 = date(2023, 1, 1), date(2024, 1, 1)
    flows = [(d0, -100.0), (d1, 200.0)]
    real = deflate(flows, {d0: 100.0, d1: 200.0}, base=d0)  # prices doubled -> real return 0
    assert xirr(real) == pytest.approx(0.0, abs=1e-9)
    usd = to_usd(flows, {d0: 10.0, d1: 20.0})  # FX doubled -> USD return 0
    assert xirr(usd) == pytest.approx(0.0, abs=1e-9)


def test_xirr_consumes_a_one_shot_iterator_once():
    d0, d1 = date(2023, 1, 1), date(2024, 1, 1)
    assert xirr(iter([(d0, -100.0), (d1, 200.0)])) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize(
    "flows",
    [
        [],
        [(date(2023, 1, 1), -100.0), (date(2024, 1, 1), -50.0)],
        [(date(2023, 1, 1), 100.0), (date(2024, 1, 1), 50.0)],
        [(date(2023, 1, 1), -100.0)],
    ],
)
def test_xirr_without_both_signs_raises(flows):
    with pytest.raises(ReturnsError):
        xirr(flows)


def test_xirr_bad_bracket_raises():
    with pytest.raises(ReturnsError):
        xirr([(date(2023, 1, 1), -100.0), (date(2024, 1, 1), 200.0)], lo=2.0, hi=1.0)


def test_xirr_non_finite_flow_raises():
    with pytest.raises(ReturnsError):
        xirr([(date(2023, 1, 1), float("nan")), (date(2024, 1, 1), 200.0)])


def test_deflate_missing_cpi_date_raises():
    d0, d1 = date(2023, 1, 1), date(2024, 1, 1)
    with pytest.raises(ReturnsError):
        deflate([(d0, -1.0)], {d1: 100.0}, base=d1)


def test_deflate_non_positive_cpi_raises():
    d0 = date(2023, 1, 1)
    with pytest.raises(ReturnsError):
        deflate([(d0, -1.0)], {d0: 0.0}, base=d0)


def test_to_usd_missing_fx_date_raises():
    d0, d1 = date(2023, 1, 1), date(2024, 1, 1)
    with pytest.raises(ReturnsError):
        to_usd([(d0, -1.0), (d1, 1.0)], {d0: 10.0})


def test_to_usd_non_positive_fx_raises():
    d0 = date(2023, 1, 1)
    with pytest.raises(ReturnsError):
        to_usd([(d0, -1.0)], {d0: 0.0})
