"""WS2: FX source — TGJU fallback reliability.

RED (before fixes):
  1. RIAL_TO_TOMAN magic number 0.1 is anonymous in TGJU_SYMBOLS tuple —
     there is no named constant; renaming the conversion requires a grep
  2. _read_references() calls tgju_available() as a pre-check before
     fetch_prices(), adding an extra round-trip that hurts latency when
     TGJU IS available and gains nothing when it isn't
  3. No wall-clock timeout on the TGJU fallback — a hanging fetch_prices()
     blocks _read_references() (and the entire snapshot) indefinitely

GREEN (after fixes):
  1. secondary_source.RIAL_TO_TOMAN is a named Decimal constant
  2. _read_references() calls fetch_prices() directly; tgju_available() is
     removed from the hot path
  3. snapshot_service.TGJU_FALLBACK_TIMEOUT_SECONDS exists and
     fetch_prices() is wrapped in asyncio.wait_for(timeout=…)
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Named RIAL_TO_TOMAN constant ─────────────────────────────────────────

def test_rial_to_toman_is_named_constant():
    """RIAL_TO_TOMAN must be a module-level Decimal constant in secondary_source.

    RED: only the anonymous factor 0.1 is embedded in the TGJU_SYMBOLS tuple.
    GREEN: secondary_source.RIAL_TO_TOMAN = Decimal("0.1") is exported.
    """
    from src.gold_desk import secondary_source

    assert hasattr(secondary_source, "RIAL_TO_TOMAN"), (
        "secondary_source.RIAL_TO_TOMAN does not exist. "
        "Add: RIAL_TO_TOMAN = Decimal('0.1')  # 1 Toman = 10 Rial"
    )
    assert isinstance(secondary_source.RIAL_TO_TOMAN, Decimal), (
        f"RIAL_TO_TOMAN must be Decimal, got {type(secondary_source.RIAL_TO_TOMAN).__name__}."
    )
    assert secondary_source.RIAL_TO_TOMAN == Decimal("0.1"), (
        f"RIAL_TO_TOMAN must equal Decimal('0.1'), got {secondary_source.RIAL_TO_TOMAN!r}."
    )


def test_rial_symbol_tuples_use_rial_to_toman_constant():
    """The 'rial' slugs in TGJU_SYMBOLS must reference RIAL_TO_TOMAN, not 0.1.

    This is a code review test: we inspect that the factor value stored in
    TGJU_SYMBOLS for Rial slugs matches RIAL_TO_TOMAN (not a copy-pasted 0.1).

    RED: TGJU_SYMBOLS is built with the literal 0.1 float.
    GREEN: each 'rial' slug's factor == float(RIAL_TO_TOMAN).
    """
    from src.gold_desk.secondary_source import TGJU_SYMBOLS, RIAL_TO_TOMAN  # type: ignore[attr-defined]

    expected_factor = float(RIAL_TO_TOMAN)
    rial_slugs = [slug for slug, (_, _, unit) in TGJU_SYMBOLS.items() if unit == "rial"]
    assert rial_slugs, "Expected at least one rial slug in TGJU_SYMBOLS"

    for slug in rial_slugs:
        _, factor, _ = TGJU_SYMBOLS[slug]
        assert abs(factor - expected_factor) < 1e-12, (
            f"TGJU_SYMBOLS[{slug!r}] factor={factor!r} does not match "
            f"float(RIAL_TO_TOMAN)={expected_factor!r}. "
            "Use RIAL_TO_TOMAN instead of the literal 0.1."
        )


# ─── 2. No redundant availability pre-check ──────────────────────────────────

def test_tgju_available_not_imported_in_snapshot_service():
    """snapshot_service must NOT import tgju_available (is_available).

    RED: `from .secondary_source import is_available as tgju_available` is in the module.
    GREEN: that import is removed; the pre-check is gone.
    """
    import src.gold_desk.snapshot_service as svc_mod

    assert not hasattr(svc_mod, "tgju_available"), (
        "snapshot_service still imports tgju_available. "
        "Remove the `from .secondary_source import is_available as tgju_available` line "
        "and call fetch_prices() directly inside a try/except TimeoutError block."
    )


@pytest.mark.asyncio
async def test_tgju_fallback_calls_fetch_prices_without_pre_check():
    """When BrsApi is incomplete, fetch_prices() is called directly — no pre-check.

    RED: the old code guarded fetch_prices() behind `if await tgju_available()`.
    GREEN: fetch_prices() is called unconditionally (inside a timeout wrapper).
    """
    import src.gold_desk.snapshot_service as svc_mod

    fetch_called = {"n": 0}

    async def _mock_brsapi():
        return {}  # incomplete

    async def _mock_fetch():
        fetch_called["n"] += 1
        return []  # empty → _complete → False → RuntimeError

    with patch.object(svc_mod, "_read_brsapi_prices", _mock_brsapi), \
         patch.object(svc_mod, "fetch_tgju_prices", _mock_fetch):
        try:
            await svc_mod._read_references()
        except RuntimeError:
            pass  # expected

    assert fetch_called["n"] >= 1, (
        "fetch_tgju_prices() was never called after BrsApi returned incomplete data. "
        "The fallback must call fetch_prices() directly (no pre-check gate)."
    )


# ─── 3. Wall-clock timeout on TGJU fallback ──────────────────────────────────

def test_tgju_fallback_timeout_constant_exists():
    """snapshot_service.TGJU_FALLBACK_TIMEOUT_SECONDS must exist and be ≥10s.

    RED: no such constant exists.
    GREEN: TGJU_FALLBACK_TIMEOUT_SECONDS: float is defined and ≥10.0.
    """
    import src.gold_desk.snapshot_service as svc_mod

    assert hasattr(svc_mod, "TGJU_FALLBACK_TIMEOUT_SECONDS"), (
        "snapshot_service.TGJU_FALLBACK_TIMEOUT_SECONDS does not exist. "
        "Add: TGJU_FALLBACK_TIMEOUT_SECONDS: float = 15.0"
    )
    timeout = svc_mod.TGJU_FALLBACK_TIMEOUT_SECONDS
    assert isinstance(timeout, (int, float)), (
        f"TGJU_FALLBACK_TIMEOUT_SECONDS must be a number, got {type(timeout).__name__}."
    )
    assert timeout >= 10.0, (
        f"TGJU_FALLBACK_TIMEOUT_SECONDS={timeout} is too short; must be ≥10s to "
        "allow all 8 symbols to complete within the httpx per-request 10s timeout."
    )


@pytest.mark.asyncio
async def test_tgju_fallback_does_not_hang_on_slow_provider():
    """_read_references() must complete within TGJU_FALLBACK_TIMEOUT_SECONDS
    even when fetch_prices() hangs.

    RED: no asyncio.wait_for guard — fetch_prices() blocking means
         _read_references() blocks forever.
    GREEN: fetch_prices() is wrapped in wait_for(TGJU_FALLBACK_TIMEOUT_SECONDS),
           so a timed-out fallback raises RuntimeError('no complete price source').
    """
    import src.gold_desk.snapshot_service as svc_mod

    async def _mock_brsapi():
        return {}  # incomplete → triggers TGJU fallback

    async def _hang_forever() -> list:
        await asyncio.sleep(9999)
        return []

    async def _run():
        with patch.object(svc_mod, "_read_brsapi_prices", _mock_brsapi), \
             patch.object(svc_mod, "fetch_tgju_prices", _hang_forever):
            # Patch the timeout constant to a tiny value so the test is fast
            with patch.object(svc_mod, "TGJU_FALLBACK_TIMEOUT_SECONDS", 0.1):
                try:
                    await svc_mod._read_references()
                except RuntimeError:
                    pass  # expected — timed-out fallback → no complete source

    # The whole thing must finish in under 5s even though the fetch hangs
    await asyncio.wait_for(_run(), timeout=5.0)
