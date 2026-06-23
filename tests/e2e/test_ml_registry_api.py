from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_ml_models_list(client: AsyncClient):
    response = await client.get("/api/v1/ml/models")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_ml_predict(client: AsyncClient):
    payload = {"symbol": "فولاد", "model_name": "test_model", "features": {}}
    response = await client.post("/api/v1/ml/predict", json=payload)
    assert response.status_code in (200, 401, 422)


@pytest.mark.asyncio
async def test_ml_train(client: AsyncClient):
    payload = {
        "experiment_name": "e2e_test",
        "model_type": "xgboost",
        "symbols": ["فولاد"],
    }
    response = await client.post("/api/v1/ml/train", json=payload)
    assert response.status_code in (200, 201, 401, 422)

