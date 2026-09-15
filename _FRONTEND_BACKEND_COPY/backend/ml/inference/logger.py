from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class PredictionLogger:
    def log_prediction(self, input_data: Any, prediction: Any, metadata: dict[str, Any] | None = None) -> None:
        logger.info("Prediction made | input_shape=%s output=%s", getattr(input_data, "shape", "N/A"), prediction)

    def log_error(self, input_data: Any, error: Exception) -> None:
        logger.error("Prediction failed | error=%s", error)
