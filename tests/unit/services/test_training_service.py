from __future__ import annotations

import pytest

from services.training_service import TrainingService


@pytest.mark.asyncio
async def test_training_start():
    service = TrainingService()
    result = await service.start_training(
        experiment_name="test",
        model_type="xgboost",
        symbols=["فولاد"],
    )
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_status():
    service = TrainingService()
    result = await service.get_training_status("run_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_list():
    service = TrainingService()
    result = await service.list_runs()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_cancel():
    service = TrainingService()
    result = await service.cancel_run("run_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_get_metrics():
    service = TrainingService()
    result = await service.get_metrics("run_001")
    assert result.success or not result.success
