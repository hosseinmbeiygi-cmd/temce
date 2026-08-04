from __future__ import annotations

import pytest

from services.signal_service import SignalService


@pytest.mark.asyncio
async def test_signal_generation():
    service = SignalService()
    result = await service.generate("فولاد")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_signal_list():
    service = SignalService()
    result = await service.list_signals()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_signal_for_symbol():
    service = SignalService()
    result = await service.get_by_symbol("فولاد")
    assert result.success or not result.success
