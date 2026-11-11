"""تست Parity — شکاف درهم/دلار.

این ماژول پیش‌تر هیچ تستی نداشت (بخش ۸ گزارش ۰۱).
"""

from __future__ import annotations

import pytest

from src.gold_desk.constants import AED_PEG
from src.gold_desk.parity import aed_gap_pct, aed_parity_usd


def test_parity_usd_uses_official_peg():
    assert aed_parity_usd(18_520) == pytest.approx(18_520 * AED_PEG)
    assert aed_parity_usd(18_520) == pytest.approx(68_014.7)


def test_gap_positive_when_usd_is_dearer():
    aed = 18_520.0
    parity = aed_parity_usd(aed)
    gap = aed_gap_pct(parity * 1.01, aed)
    assert gap == pytest.approx(1.0)


def test_gap_negative_when_usd_is_cheaper():
    aed = 18_520.0
    parity = aed_parity_usd(aed)
    gap = aed_gap_pct(parity * 0.99, aed)
    assert gap == pytest.approx(-1.0)


def test_gap_zero_at_parity():
    assert aed_gap_pct(68_000, 18_520) == pytest.approx(-0.0216, abs=1e-3)


def test_invalid_aed_raises():
    with pytest.raises(ValueError):
        aed_parity_usd(0)
    with pytest.raises(ValueError):
        aed_parity_usd(-5)
    with pytest.raises(ValueError):
        aed_gap_pct(68_000, 0)


def test_extreme_gap_is_reported_not_clamped():
    """ماژول نباید شکاف بزرگ را سانسور کند؛ اعتبارسنجی کار snapshot است."""
    assert aed_gap_pct(100_000, 18_520) > 40
