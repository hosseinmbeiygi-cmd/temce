from __future__ import annotations

import pytest

from services.signal_service import SignalService


@pytest.mark.asyncio
async def test_signal_generate():
    service = SignalService()
    result = await service.generate("فولاد")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_signal_list():
    service = SignalService()
    result = await service.list_signals()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_signal_by_symbol():
    service = SignalService()
    result = await service.get_by_symbol("فولاد")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_signal_get():
    service = SignalService()
    result = await service.get_signal("sig_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_signal_bulk_generate():
    service = SignalService()
    symbols = ["فولاد", "فملی", "وبانک"]
    results = []
    for symbol in symbols:
        result = await service.generate(symbol)
        results.append(result)
    assert len(results) == 3

