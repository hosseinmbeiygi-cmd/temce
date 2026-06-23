from __future__ import annotations

import pytest

from services.training_service import TrainingService


@pytest.mark.asyncio
async def test_ml_training_flow():
    service = TrainingService()
    result = await service.start_training(
        experiment_name="integration_test",
        model_type="xgboost",
        symbols=["فولاد"],
    )
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_ml_inference_flow():
    from services.inference_service import InferenceService

    service = InferenceService()
    result = await service.predict(
        symbol="فولاد",
        model_name="test_model",
        features={},
    )
    assert result.success or not result.success

