"""Unit tests for tiered NAV allocation pure logic (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.fund_class_nav import (  # noqa: E402
    allocate_guaranteed,
    allocate_leveraged,
    allocate_simple,
    percentile,
)


def test_allocate_simple_proportional() -> None:
    result = allocate_simple(1_000_000, {"ORDINARY": 600, "PREFERRED": 400})
    assert result["ORDINARY"]["net_assets"] == pytest.approx(600_000)
    assert result["PREFERRED"]["net_assets"] == pytest.approx(400_000)
    assert result["ORDINARY"]["nav_per_unit"] == pytest.approx(1000)


def test_allocate_simple_rejects_zero_units() -> None:
    with pytest.raises(ValueError):
        allocate_simple(1_000_000, {"ORDINARY": 0})


def test_allocate_leveraged_within_band_is_pro_rata() -> None:
    # base: 100 units × 1000 = 100k ordinary، 100k preferred؛ بازده کل ۳۲٪
    total = 264_000.0  # (200k × 1.32)
    result = allocate_leveraged(
        total, ordinary_units=100, preferred_units=100,
        floor_rate=0.30, ceiling_rate=0.35, days=365, par_value=1000,
    )
    assert result["classes"]["ORDINARY"]["net_assets"] == pytest.approx(132_000)
    assert result["classes"]["PREFERRED"]["net_assets"] == pytest.approx(132_000)
    assert result["classes"]["ORDINARY"]["transfer_amount"] == pytest.approx(0)


def test_allocate_leveraged_below_floor_transfers_to_ordinary() -> None:
    total = 220_000.0  # بازده کل ۱۰٪
    result = allocate_leveraged(
        total, ordinary_units=100, preferred_units=100,
        floor_rate=0.30, ceiling_rate=0.35, days=365, par_value=1000,
    )
    ordinary = result["classes"]["ORDINARY"]
    preferred = result["classes"]["PREFERRED"]
    assert ordinary["net_assets"] == pytest.approx(130_000)  # کف ۳۰٪
    assert preferred["net_assets"] == pytest.approx(90_000)
    assert ordinary["transfer_amount"] == pytest.approx(20_000)  # از ممتاز به عادی
    assert preferred["transfer_amount"] == pytest.approx(-20_000)


def test_allocate_leveraged_above_ceiling_transfers_to_preferred() -> None:
    total = 300_000.0  # بازده کل ۵۰٪
    result = allocate_leveraged(
        total, ordinary_units=100, preferred_units=100,
        floor_rate=0.30, ceiling_rate=0.35, days=365, par_value=1000,
    )
    ordinary = result["classes"]["ORDINARY"]
    preferred = result["classes"]["PREFERRED"]
    assert ordinary["net_assets"] == pytest.approx(135_000)  # سقف ۳۵٪
    assert preferred["net_assets"] == pytest.approx(165_000)
    assert ordinary["transfer_amount"] == pytest.approx(-15_000)


def test_allocate_leveraged_rejects_invalid_params() -> None:
    with pytest.raises(ValueError):
        allocate_leveraged(100_000, 0, 100, 0.3, 0.35)
    with pytest.raises(ValueError):
        allocate_leveraged(100_000, 100, 100, 0.4, 0.3)


def test_allocate_leveraged_impairment_clamps_preferred() -> None:
    total = 50_000.0  # افت شدید
    result = allocate_leveraged(
        total, ordinary_units=100, preferred_units=100,
        floor_rate=0.30, ceiling_rate=0.35, days=365, par_value=1000,
    )
    assert result["classes"]["PREFERRED"]["net_assets"] == pytest.approx(0)
    assert "preferred_class_impaired" in result["warnings"]


def test_allocate_guaranteed_below_par_marks_warning() -> None:
    result = allocate_guaranteed(80_000, ordinary_units=100, preferred_units=50, guarantee_par=1000)
    assert result["classes"]["ORDINARY"]["net_assets"] == pytest.approx(80_000)
    assert result["classes"]["PREFERRED"]["net_assets"] == pytest.approx(0)
    assert "guarantee_not_fully_covered" in result["warnings"]


def test_allocate_guaranteed_caps_ordinary_at_par() -> None:
    result = allocate_guaranteed(200_000, ordinary_units=100, preferred_units=50, guarantee_par=1000)
    assert result["classes"]["ORDINARY"]["net_assets"] == pytest.approx(100_000)
    assert result["classes"]["PREFERRED"]["net_assets"] == pytest.approx(100_000)


def test_percentile_interpolates() -> None:
    values = [float(i) for i in range(1, 101)]
    assert percentile(values, 50) == pytest.approx(50.5)
    assert percentile(values, 95) == pytest.approx(95.05)
    assert percentile([], 95) is None
    assert percentile([7.0], 95) == 7.0
