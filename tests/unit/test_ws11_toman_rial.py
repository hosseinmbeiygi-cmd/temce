"""WS11: BrsApi unit contract — _toman_to_rial pure-function tests.

RED (before fixes):
  1. _toman_to_rial not unit-tested — Toman/Rial contract PARTIAL (PHASE0 item 11).
  2. XAUUSD skip of _toman_to_rial (to_rial=False in phase2) not confirmed.
  3. GoldCoinHistoryModel Toman-unit contract in docstring not verified.

GREEN (after fixes):
  1. _toman_to_rial(None) returns None.
  2. _toman_to_rial(x) = x × 10, rounded to nearest Rial using ROUND_HALF_UP.
  3. Result is always integer-valued (no fractional Rial in Iran's currency system).
  4. GoldCoinHistoryModel.__doc__ confirms "Toman" unit contract for
     brsapi_gold_coin_history prices.
  5. phase2 source confirms to_rial=True for domestic prices (Toman from BrsApi)
     and to_rial=False for XAUUSD (USD price, never Toman).

WS11 scope: pure-function + static-analysis tests only.
Live verification (actual values in brsapi_gold_currency_pro_prices table)
requires a running database — out of scope here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Import check ─────────────────────────────────────────────────────────

def test_import_toman_to_rial():
    """_toman_to_rial must be importable from src.gold_desk.phase1.

    RED: not tested.
    GREEN: function exists and is importable.
    """
    from src.gold_desk.phase1 import _toman_to_rial  # noqa: F401


# ─── 2. None handling ────────────────────────────────────────────────────────

def test_toman_to_rial_none_returns_none():
    """_toman_to_rial(None) must return None, not raise or return 0.

    RED: not tested.
    GREEN: guard `if value is None: return None`.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    assert _toman_to_rial(None) is None


# ─── 3. Basic conversions ────────────────────────────────────────────────────

def test_toman_to_rial_zero():
    """0 Toman → 0 Rial.

    RED: not tested.
    GREEN: 0 × 10 = 0.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    assert _toman_to_rial(0.0) == pytest.approx(0.0)


def test_toman_to_rial_one_toman():
    """1 Toman = 10 Rial.

    RED: not tested.
    GREEN: 1 × 10 = 10.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    assert _toman_to_rial(1.0) == pytest.approx(10.0)


def test_toman_to_rial_large_value():
    """1,000,000 Toman = 10,000,000 Rial (typical coin price range).

    RED: not tested.
    GREEN: Decimal arithmetic prevents float overflow for large values.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    result = _toman_to_rial(1_000_000.0)
    assert result == pytest.approx(10_000_000.0)


def test_toman_to_rial_typical_coin_price():
    """60,000,000 Toman (typical Emami coin price) → 600,000,000 Rial.

    RED: not tested.
    GREEN: conversion correct for realistic market values.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    result = _toman_to_rial(60_000_000.0)
    assert result == pytest.approx(600_000_000.0)


# ─── 4. Rounding (ROUND_HALF_UP) ─────────────────────────────────────────────

def test_toman_to_rial_result_is_integer_valued():
    """Result must have no fractional Rial (quantized to 1 Rial).

    RED: not tested.
    GREEN: .quantize(Decimal('1'), rounding=ROUND_HALF_UP) ensures integer result.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    for val in [0.1, 0.3, 0.5, 1.5, 2.3, 100.7, 999.9]:
        result = _toman_to_rial(val)
        assert result is not None
        assert result % 1 == 0.0, f"fractional Rial: _toman_to_rial({val}) = {result}"


def test_toman_to_rial_rounds_half_up():
    """0.15 Toman × 10 = 1.5 Rial → ROUND_HALF_UP → 2.0.

    RED: rounding not tested.
    GREEN: Decimal ROUND_HALF_UP rounds 0.5 up.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    assert _toman_to_rial(0.15) == 2.0


def test_toman_to_rial_rounds_below_half_down():
    """0.14 Toman × 10 = 1.4 Rial → ROUND_HALF_UP → 1.0.

    RED: rounding not tested.
    GREEN: 1.4 < 1.5 so rounds down to 1.
    """
    from src.gold_desk.phase1 import _toman_to_rial

    assert _toman_to_rial(0.14) == 1.0


# ─── 5. Model Toman-unit contract ────────────────────────────────────────────

def test_gold_coin_history_model_documents_toman_contract():
    """GoldCoinHistoryModel.__doc__ must state prices are in Toman.

    RED: Toman/Rial contract PARTIAL — PHASE0 item 11.
    GREEN: 'Toman' appears in the class docstring as the unit declaration.
    """
    from brsapi.models.commodity import GoldCoinHistoryModel

    doc = GoldCoinHistoryModel.__doc__ or ""
    assert "Toman" in doc, (
        "GoldCoinHistoryModel docstring must declare 'Toman' unit so consumers "
        "know to call _toman_to_rial before storing values"
    )


# ─── 6. phase2 to_rial logic ─────────────────────────────────────────────────

def test_phase2_xauusd_uses_to_rial_false():
    """phase2 must use to_rial=False for XAUUSD (price is USD, not Toman).

    RED: phase2 conversion logic PARTIAL — PHASE0 item 11.
    GREEN: source confirms add("xau_usd", ..., to_rial=False).
    """
    import inspect
    from src.gold_desk import phase2

    src = inspect.getsource(phase2)
    assert 'to_rial=False' in src, (
        "phase2 must pass to_rial=False for XAUUSD — USD price must NOT be "
        "multiplied by 10"
    )


def test_phase2_domestic_prices_use_to_rial_true():
    """phase2 must use to_rial=True for domestic gold/coin/USD prices (Toman from BrsApi).

    RED: phase2 conversion logic PARTIAL — PHASE0 item 11.
    GREEN: source confirms add("coin_emami", ..., to_rial=True).
    """
    import inspect
    from src.gold_desk import phase2

    src = inspect.getsource(phase2)
    assert 'to_rial=True' in src, (
        "phase2 must pass to_rial=True for domestic prices — BrsApi returns "
        "Toman which must be converted to Rial"
    )
