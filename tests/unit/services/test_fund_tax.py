"""Unit tests for tax rules (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.fund_tax import (  # noqa: E402
    TAX_TYPES,
    TRANSFER_TAX_RATE,
    compute_tax,
    transfer_tax,
    transfer_tax_from_trades,
)


def test_transfer_tax_rate_is_half_percent() -> None:
    assert TRANSFER_TAX_RATE == 0.005
    assert transfer_tax(1_000_000_000) == pytest.approx(5_000_000)


def test_transfer_tax_rejects_negative() -> None:
    with pytest.raises(ValueError):
        transfer_tax(-1)


def test_compute_tax_transfer_not_exempt() -> None:
    result = compute_tax("TRANSFER_05", 2_000_000_000)
    assert result["exempt"] is False
    assert result["tax_amount"] == pytest.approx(10_000_000)
    assert result["exemption_ref"] == "ARTICLE-143-MOKARRAR"


def test_compute_tax_cgt_is_exempt() -> None:
    result = compute_tax("CGT", 5_000_000_000)
    assert result["exempt"] is True
    assert result["tax_amount"] == 0.0


def test_compute_tax_deposit_interest_exempt() -> None:
    result = compute_tax("DEPOSIT_INTEREST", 1_000_000)
    assert result["exempt"] is True
    assert result["tax_amount"] == 0.0


def test_compute_tax_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        compute_tax("UNKNOWN", 100)


def test_compute_tax_negative_base_raises() -> None:
    with pytest.raises(ValueError):
        compute_tax("TRANSFER_05", -100)


def test_tax_types_are_complete() -> None:
    assert set(TAX_TYPES) == {
        "TRANSFER_05",
        "CGT",
        "DEPOSIT_INTEREST",
        "VAT",
        "FUND_INCOME",
    }


def test_transfer_tax_from_trades_only_sells() -> None:
    trades = [
        {"side": "BUY", "value": 1_000_000},
        {"side": "SELL", "value": 2_000_000},
        {"side": "SELL", "quantity": 10, "price": 100_000},
    ]
    result = transfer_tax_from_trades(trades)
    assert result["trade_count"] == 2
    assert result["base_amount"] == 3_000_000
    assert result["tax_amount"] == pytest.approx(15_000)


def test_transfer_tax_from_trades_empty_is_zero() -> None:
    result = transfer_tax_from_trades([])
    assert result["base_amount"] == 0
    assert result["tax_amount"] == 0
    assert result["trade_count"] == 0


def test_transfer_tax_from_trades_negative_raises() -> None:
    with pytest.raises(ValueError):
        transfer_tax_from_trades([{"side": "SELL", "value": -1}])
