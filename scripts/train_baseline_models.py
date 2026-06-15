#!/usr/bin/env python
from __future__ import annotations

import asyncio

from core.logging import get_logger
from services.training_service import TrainingService

logger = get_logger(__name__)


BASELINE_CONFIGS = [
    {"name": "xgboost_price_direction", "model_type": "xgboost", "target": "direction"},
    {"name": "lightgbm_price_direction", "model_type": "lightgbm", "target": "direction"},
    {"name": "random_forest_volatility", "model_type": "random_forest", "target": "volatility"},
]


async def train_baselines() -> int:
    service = TrainingService()
    count = 0
    for config in BASELINE_CONFIGS:
        logger.info("Training baseline: %s (%s)", config["name"], config["model_type"])
        result = await service.start_training(
            experiment_name="baselines",
            model_type=config["model_type"],
            symbols=["فولاد", "فملی", "وبانک", "کگل", "خودرو", "شستا", "شپنا"],
            target=config["target"],
        )
        if result.success:
            count += 1
            logger.info("Baseline %s started: %s", config["name"], result.value)
        else:
            logger.error("Failed to start baseline %s: %s", config["name"], result.error)
    return count


async def main() -> None:
    count = await train_baselines()
    logger.info("Done. %d baseline training jobs started.", count)


if __name__ == "__main__":
    asyncio.run(main())
