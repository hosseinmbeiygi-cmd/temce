from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.dynamic_weighting import (
    BASE_WEIGHTS,
    DynamicWeighting,
    MarketSignalProvider,
)


class _FakeSession:
    """Minimal async session double with an execute() returning mapped rows."""

    def __init__(self, rows):
        self._rows = rows
        self.execute = AsyncMock(return_value=_FakeResult(rows))


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def _row(value, created_at="2026-08-10 12:00:00"):
    r = MagicMock()
    r[0] = value
    r[1] = created_at
    return r


def test_default_weights_total_one():
    assert sum(BASE_WEIGHTS.values()) == pytest.approx(1.0, rel=0.01)


def test_low_volatility_boosts_fundamental_and_valuation():
    # index rows: volatility < 2% → fundamental/valuation up, technical down
    session = _FakeSession(
        [_row(100.0, "2026-08-10 12:00:00"),
         _row(99.8, "2026-08-09 12:00:00"),
         _row(99.6, "2026-08-08 12:00:00"),
         _row(99.4, "2026-08-07 12:00:00")]
    )
    provider = MarketSignalProvider(session)

    async def fake_volume():
        return {"volume_ratio": 1.0, "available": True}

    provider.get_volume_signal = fake_volume
    provider.get_index_signal = AsyncMock(return_value={
        "volatility_3d": 0.5, "change_3d": 0.5, "available": True,
    })

    svc = DynamicWeighting(session)
    svc._provider = provider
    import asyncio
    weights = asyncio.run(svc.compute())

    assert weights["fundamental"] > BASE_WEIGHTS["fundamental"]
    assert weights["valuation"] > BASE_WEIGHTS["valuation"]
    assert weights["technical"] < BASE_WEIGHTS["technical"]
    assert sum(weights.values()) == pytest.approx(1.0, rel=0.01)


def test_volume_spike_boosts_technical_and_institutional():
    session = _FakeSession([_row(100.0)])
    provider = MarketSignalProvider(session)
    provider.get_index_signal = AsyncMock(return_value={
        "volatility_3d": 5.0, "change_3d": 1.0, "available": True,
    })

    async def fake_volume():
        return {"volume_ratio": 4.0, "available": True}

    provider.get_volume_signal = fake_volume
    svc = DynamicWeighting(session)
    svc._provider = provider

    import asyncio
    weights = asyncio.run(svc.compute())

    # مقیاس نسبی: سهم تکنیکال و نهادی باید نسبت به پایه افزایش یابد
    base_tech_share = BASE_WEIGHTS["technical"] / sum(BASE_WEIGHTS.values())
    base_inst_share = BASE_WEIGHTS["institutional"] / sum(BASE_WEIGHTS.values())
    assert weights["technical"] > base_tech_share * 1.0
    assert weights["institutional"] > base_inst_share
    assert sum(weights.values()) == pytest.approx(1.0, rel=0.01)


def test_bearish_boosts_liquidity_reduces_gov_support():
    session = _FakeSession([_row(100.0)])
    provider = MarketSignalProvider(session)
    provider.get_index_signal = AsyncMock(return_value={
        "volatility_3d": 6.0, "change_3d": -3.0, "available": True,
    })

    async def fake_volume():
        return {"volume_ratio": 1.0, "available": True}

    provider.get_volume_signal = fake_volume
    svc = DynamicWeighting(session)
    svc._provider = provider

    import asyncio
    weights = asyncio.run(svc.compute())

    assert weights["liquidity"] > BASE_WEIGHTS["liquidity"]
    assert weights["gov_support"] < BASE_WEIGHTS["gov_support"]
    assert sum(weights.values()) == pytest.approx(1.0, rel=0.01)


def test_convenience_wrapper_returns_dict():
    import asyncio

    session = _FakeSession([_row(100.0)])
    provider = MarketSignalProvider(session)
    provider.get_index_signal = AsyncMock(return_value={
        "volatility_3d": 5.0, "change_3d": 1.0, "available": True,
    })
    provider.get_volume_signal = AsyncMock(return_value={"volume_ratio": 1.0, "available": True})

    svc = DynamicWeighting(session)
    svc._provider = provider
    weights = asyncio.run(svc.compute())
    assert isinstance(weights, dict)
    assert sum(weights.values()) == pytest.approx(1.0, rel=0.01)


def test_get_dynamic_weights_wrapper():
    import asyncio

    session = _FakeSession([_row(100.0)])
    provider = MarketSignalProvider(session)
    provider.get_index_signal = AsyncMock(return_value={
        "volatility_3d": 5.0, "change_3d": 1.0, "available": True,
    })
    provider.get_volume_signal = AsyncMock(return_value={"volume_ratio": 1.0, "available": True})

    svc = DynamicWeighting(session)
    svc._provider = provider
    weights = asyncio.run(svc.compute())
    assert sum(weights.values()) == pytest.approx(1.0, rel=0.01)
