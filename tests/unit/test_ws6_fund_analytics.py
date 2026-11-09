"""WS6: Fund analytics — static fee registry for Iranian gold ETFs.

RED (before fixes):
  1. Module src.gold_desk.fund_registry does not exist — all tests ImportError.
  2. No GET /gold/funds endpoint in api.py.

GREEN (after fixes):
  1. src/gold_desk/fund_registry.py created with FundFeeInfo dataclass,
     FUND_REGISTRY dict, get_fund_fee(), list_funds().
  2. GET /gold/funds endpoint added to api.py.

WS6 scope note: "microstructure" gap (intraday order book depth) is deferred
until a live order-book data source is confirmed. Only the fee matrix is
implemented here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Module importable ────────────────────────────────────────────────────

def test_import_fund_registry():
    """Module must be importable.

    RED: src/gold_desk/fund_registry.py does not exist.
    GREEN: module created with FundFeeInfo, FUND_REGISTRY, get_fund_fee, list_funds.
    """
    from src.gold_desk.fund_registry import (  # noqa: F401
        FUND_REGISTRY,
        FundFeeInfo,
        get_fund_fee,
        list_funds,
    )


# ─── 2. FundFeeInfo dataclass ─────────────────────────────────────────────────

def test_fund_fee_info_has_required_fields():
    """FundFeeInfo must carry symbol, display_name, subscription_fee_pct,
    redemption_fee_pct, annual_mgmt_fee_pct, and data_source.

    RED: class does not exist.
    GREEN: frozen dataclass with all fields.
    """
    from src.gold_desk.fund_registry import FundFeeInfo

    info = FundFeeInfo(
        symbol="عیار",
        display_name="صندوق طلای مفید",
        subscription_fee_pct=0.001,
        redemption_fee_pct=0.001,
        annual_mgmt_fee_pct=0.5,
        data_source="fipiran",
    )
    assert info.symbol == "عیار"
    assert info.display_name
    assert info.subscription_fee_pct >= 0
    assert info.redemption_fee_pct >= 0
    assert info.annual_mgmt_fee_pct >= 0


def test_fund_fee_info_to_dict():
    """to_dict() must include all fields and fees as percentages (not fractions).

    RED: method does not exist.
    GREEN: returns dict with all fields; fee values are percentages (e.g. 0.5 means 0.5%).
    """
    from src.gold_desk.fund_registry import FundFeeInfo

    info = FundFeeInfo(
        symbol="عیار",
        display_name="صندوق طلای مفید",
        subscription_fee_pct=0.001,
        redemption_fee_pct=0.001,
        annual_mgmt_fee_pct=0.5,
        data_source="fipiran",
    )
    d = info.to_dict()
    assert "symbol" in d
    assert "display_name" in d
    assert "subscription_fee_pct" in d
    assert "redemption_fee_pct" in d
    assert "annual_mgmt_fee_pct" in d
    assert "data_source" in d


# ─── 3. Registry completeness ─────────────────────────────────────────────────

def test_fund_registry_is_non_empty():
    """FUND_REGISTRY must have at least one entry.

    RED: registry does not exist.
    GREEN: dict with known Iranian gold ETF symbols.
    """
    from src.gold_desk.fund_registry import FUND_REGISTRY

    assert len(FUND_REGISTRY) >= 1, "FUND_REGISTRY must have at least one entry"


def test_fund_registry_entries_have_valid_fees():
    """Every registry entry must have non-negative fees within reasonable bounds.

    Fee caps:
    - subscription/redemption: each < 5% (Iranian gold ETFs are ≤ 0.5% per SEO rules)
    - annual management fee: < 10% per year

    RED: registry does not exist.
    GREEN: all entries pass validation.
    """
    from src.gold_desk.fund_registry import FUND_REGISTRY

    for symbol, info in FUND_REGISTRY.items():
        assert info.symbol == symbol, (
            f"FUND_REGISTRY key {symbol!r} must match info.symbol={info.symbol!r}"
        )
        assert info.display_name, f"empty display_name for {symbol!r}"
        assert 0 <= info.subscription_fee_pct < 5.0, (
            f"{symbol}: subscription_fee_pct={info.subscription_fee_pct} out of [0, 5)"
        )
        assert 0 <= info.redemption_fee_pct < 5.0, (
            f"{symbol}: redemption_fee_pct={info.redemption_fee_pct} out of [0, 5)"
        )
        assert 0 <= info.annual_mgmt_fee_pct < 10.0, (
            f"{symbol}: annual_mgmt_fee_pct={info.annual_mgmt_fee_pct} out of [0, 10)"
        )
        assert info.data_source, f"empty data_source for {symbol!r}"


# ─── 4. Lookup functions ─────────────────────────────────────────────────────

def test_get_fund_fee_returns_known_symbol():
    """get_fund_fee(known_symbol) must return FundFeeInfo, not None.

    RED: function does not exist.
    GREEN: returns entry for every symbol in FUND_REGISTRY.
    """
    from src.gold_desk.fund_registry import FUND_REGISTRY, get_fund_fee

    for symbol in FUND_REGISTRY:
        result = get_fund_fee(symbol)
        assert result is not None, f"get_fund_fee({symbol!r}) returned None for a known symbol"
        assert result.symbol == symbol


def test_get_fund_fee_returns_none_for_unknown():
    """get_fund_fee(unknown) must return None, not raise.

    RED: function does not exist.
    GREEN: returns None for unrecognised symbol.
    """
    from src.gold_desk.fund_registry import get_fund_fee

    assert get_fund_fee("UNKNOWN_XYZ_9999") is None


def test_list_funds_returns_all_entries():
    """list_funds() must return all entries in FUND_REGISTRY as a list.

    RED: function does not exist.
    GREEN: list length matches registry size.
    """
    from src.gold_desk.fund_registry import FUND_REGISTRY, list_funds

    funds = list_funds()
    assert isinstance(funds, list), "list_funds() must return a list"
    assert len(funds) == len(FUND_REGISTRY), (
        f"list_funds() returned {len(funds)} items but registry has {len(FUND_REGISTRY)}"
    )


# ─── 5. Microstructure deferred ───────────────────────────────────────────────

def test_microstructure_deferral_note_exists():
    """Module must carry a MICROSTRUCTURE_DEFERRED constant (documents the gap).

    RED: constant does not exist.
    GREEN: MICROSTRUCTURE_DEFERRED = True in module.
    """
    from src.gold_desk.fund_registry import MICROSTRUCTURE_DEFERRED

    assert MICROSTRUCTURE_DEFERRED is True, (
        "MICROSTRUCTURE_DEFERRED must be True to document the deferred gap"
    )
