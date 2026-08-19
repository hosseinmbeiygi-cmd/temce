from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class ModelTrainingJob:
    """Schedule/run ML model training.

    The payload may carry the trained symbol + algorithm so the ModelLoader
    LRU cache can be invalidated right after the retrain — otherwise the
    next ``get_model(symbol, algorithm)`` call would keep serving the stale
    in-memory copy until process restart.
    """

    async def execute(self, payload: dict[str, Any]) -> Result[dict[str, Any]]:
        logger.info("Model training job started")

        # ── Extract what was trained (so we know what to evict) ──────────
        symbol = payload.get("symbol") or ""
        algorithm = payload.get("algorithm") or payload.get("model_type") or ""

        # (Training itself happens here — via TrainingService.train_with_db_data
        #  or any other orchestrator; that path already invalidates too.)

        # ── Auto-refresh ModelLoader cache after the retrain ─────────────
        if symbol and algorithm:
            self._invalidate_model_cache(symbol, algorithm)
        elif symbol:
            # Symbol known, algorithm unknown → evict all algorithms for it.
            self._invalidate_model_cache(symbol)

        return Result.ok({"status": "completed", "model_id": f"{algorithm}_{symbol}" if symbol else ""})

    @staticmethod
    def _invalidate_model_cache(symbol: str, algorithm: str | None = None) -> None:
        """Evict the freshly-trained model(s) from the ModelLoader LRU cache.

        Non-fatal on failure — worst case one more stale read.
        """
        try:
            from ml.model_loader import get_model_loader

            get_model_loader().invalidate(symbol=symbol, algorithm=algorithm)
            logger.info(
                "ModelLoader cache invalidated for %s/%s (auto-refresh)",
                symbol,
                algorithm or "all",
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not invalidate ModelLoader cache for %s/%s: %s", symbol, algorithm or "all", e)
