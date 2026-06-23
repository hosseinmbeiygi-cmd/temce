from __future__ import annotations

import time

import pytest

from services.inference_service import InferenceService


@pytest.mark.asyncio
@pytest.mark.performance
async def test_ml_inference_latency():
    service = InferenceService()
    latencies = []
    for _ in range(50):
        start = time.monotonic()
        await service.predict(
            model_id="test_model",
            features={"close": 15000, "volume": 5000000, "rsi": 65},
        )
        elapsed = (time.monotonic() - start) * 1000
        latencies.append(elapsed)
    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 200, f"Average inference latency {avg_latency:.2f}ms exceeds 200ms threshold"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_batch_inference():
    service = InferenceService()
    batch_size = 100
    start = time.monotonic()
    results = []
    for i in range(batch_size):
        result = await service.predict(
            model_id="test_model",
            features={"close": 15000 + i, "volume": 5000000, "rsi": 65},
        )
        results.append(result)
    elapsed = time.monotonic() - start
    throughput = batch_size / elapsed
    assert throughput > 10, f"Inference throughput {throughput:.2f} req/s below 10 req/s threshold"

