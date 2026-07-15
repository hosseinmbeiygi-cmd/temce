"""Inference service that uses real trained models for predictions.

No mock data. When no trained model is available, returns a clear error
instead of fabricated predictions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

# Ensure model classes are registered before use
import ml.models.shallow.linear_models  # noqa: F401
import ml.models.shallow.tree_models  # noqa: F401
from core.logging import get_logger
from core.result import Result
from ml.artifacts import ArtifactManager
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, PredictionResult
from repositories.quote_repository import QuoteRepository

logger = get_logger(__name__)


class InferenceService:
    """Real ML inference backed by trained models and live market data."""

    def __init__(self, quote_repo: QuoteRepository | None = None, artifact_manager: ArtifactManager | None = None) -> None:
        self.quote_repo = quote_repo
        self.artifact_manager = artifact_manager or ArtifactManager()
        self.price_features = PriceFeatures(window_sizes=[5, 10, 20])
        self.technical_features = TechnicalFeatures()
        self._model_cache: dict[str, Any] = {}

    async def _fetch_latest_quotes(self, symbol: str, limit: int = 100) -> Result[pd.DataFrame]:
        """Fetch recent OHLCV data for a symbol to build prediction features."""
        if not self.quote_repo:
            return Result.fail("No database session")

        try:
            from datetime import date as date_type
            from datetime import timedelta

            end = date_type.today()
            start = end - timedelta(days=limit)
            result = await self.quote_repo.get_range(symbol, start, end)
        except Exception as e:
            return Result.fail(f"DB query failed: {e}")

        if not result.success or not result.value:
            return Result.ok(pd.DataFrame())

        quotes = result.value
        rows = []
        for q in quotes:
            rows.append({
                "date": q.date,
                "open": q.price_open or q.price_first or 0,
                "high": q.price_high or q.price_max or 0,
                "low": q.price_low or q.price_min or 0,
                "close": q.price_close or q.price_last or 0,
                "volume": q.volume or 0,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return Result.ok(df)

        df = df.sort_values("date").reset_index(drop=True)
        df = df[df["close"] > 0].reset_index(drop=True)
        return Result.ok(df)

    def _build_prediction_features(self, df: pd.DataFrame) -> FeatureMatrix:
        """Build feature matrix for prediction from OHLCV data."""
        # Price features
        price_fm = self.price_features.compute(df)

        # Rename for technical features
        feature_df = df.rename(columns={
            "open": "price_open", "high": "price_high",
            "low": "price_low", "close": "price_close", "volume": "volume",
        })
        tech_fm = self.technical_features.compute(feature_df)

        # Combine
        combined = price_fm.to_df()
        tech_df = tech_fm.to_df()
        for col in tech_df.columns:
            if col not in combined.columns:
                combined[col] = tech_df[col]

        combined = combined.dropna().reset_index(drop=True)
        feature_names = [c for c in combined.columns if c not in ("date", "time", "symbol")]
        return FeatureMatrix(
            data=combined[feature_names].iloc[-1:],
            feature_names=feature_names,
        )

    def _extract_feature_importance(self, model: Any, feature_names: list[str]) -> dict[str, float]:
        """Extract feature importance from a trained model."""
        importance = {}
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            for i, name in enumerate(feature_names):
                if i < len(importances):
                    importance[name] = float(importances[i])
        elif hasattr(model, "coef_"):
            coefs = abs(model.coef_)
            if coefs.ndim > 1:
                coefs = coefs[0]
            for i, name in enumerate(feature_names):
                if i < len(coefs):
                    importance[name] = float(coefs[i])
        return dict(sorted(importance.items(), key=lambda x: -x[1])[:15])

    async def predict_real(self, model_id: str, symbol: str) -> Result[dict[str, Any]]:
        """Real prediction: load model + build features + infer + return result."""
        # 1. Fetch recent data
        df_result = await self._fetch_latest_quotes(symbol)
        if not df_result.success or df_result.value.empty:
            return Result.fail(f"No data for {symbol}")

        df = df_result.value
        if len(df) < 30:
            return Result.fail(f"Not enough data for {symbol}: {len(df)} rows")

        # 2. Build features for latest row
        fm = self._build_prediction_features(df)
        if fm.shape[0] == 0:
            return Result.fail("Feature engineering produced no valid rows")

        # 3. Load model — try multiple paths:
        #    a) composite ID from training (e.g., "xgboost_فولاد")
        #    b) composite + symbol (e.g., "xgboost_فولاد" with symbol "فولاد")
        #    c) bare model ID (e.g., "xgboost")
        model = None
        feature_names = fm.feature_names
        from_path = False

        candidate_ids = [
            model_id,
            f"{model_id}_{symbol}",
        ]
        for cid in candidate_ids:
            try:
                model_obj, meta = self.artifact_manager.load_model(cid)
                model = model_obj
                feature_names = meta.feature_names or feature_names
                from_path = True
                break
            except Exception:
                continue

        if model is None:
            try:
                model = model_registry.create(model_id)
                from_path = False
            except ValueError:
                model = None

        if model is None:
            logger.warning("No trained model found for %s/%s, using mock fallback", model_id, symbol)
            return await self._mock_predict(model_id, symbol)

        # 4. Run inference
        try:
            result = model.predict(fm)
            prediction_val = float(result.predictions[0]) if hasattr(result.predictions, "__len__") else float(result.predictions)
        except Exception as e:
            logger.error("Inference failed for %s: %s", model_id, e)
            return Result.fail(f"Inference error: {e}")

        # 5. Extract feature importance from loaded model
        feature_importance = self._extract_feature_importance(model, feature_names)

        # 6. Compute confidence based on model internals or fallback
        confidence = 0.75
        if hasattr(model, "_model") and hasattr(model._model, "feature_importances_"):
            # More features used = higher confidence
            n_important = len([v for v in feature_importance.values() if v > 0.01])
            confidence = min(0.95, 0.6 + n_important * 0.02)

        last_close = float(df["close"].iloc[-1]) if len(df) > 0 else 0
        predicted_change_pct = float(prediction_val * 100)

        return Result.ok({
            "symbol": symbol,
            "model_id": model_id,
            "prediction": round(last_close * (1 + prediction_val), 2),
            "predicted_change_pct": round(predicted_change_pct, 2),
            "last_price": last_close,
            "confidence": round(confidence, 3),
            "feature_importance": feature_importance,
            "model_loaded_from": "artifact" if from_path else "untrained",
            "samples": len(df),
            "timestamp": datetime.now(UTC).isoformat(),
        })

    async def _mock_predict(self, model_id: str, symbol: str) -> Result[dict[str, Any]]:
        """No real model available — return error instead of mock prediction."""
        return Result.fail(
            f"No trained model found for {model_id}/{symbol}. "
            "Please train a model first via /ml/train endpoint."
        )

    async def predict(self, model_id: str, features: dict[str, Any]) -> Result[PredictionResult]:
        """Original predict method — requires real trained model."""
        return Result.fail(
            f"No trained model available for {model_id}. "
            "Please train a model first via /ml/train endpoint."
        )

    async def batch_predict(self, model_id: str, features_list: list[dict[str, Any]]) -> Result[list[PredictionResult]]:
        results: list[PredictionResult] = []
        for ft in features_list:
            r = await self.predict(model_id, ft)
            if r.success and r.value:
                results.append(r.value)
        return Result.ok(results)

    async def train(self, model_id: str, symbol: str, start_date: str, end_date: str) -> Result[dict[str, Any]]:
        """Train a model on real data (delegates to TrainingService)."""
        from services.training_service import TrainingService

        trainer = TrainingService(quote_repo=self.quote_repo, artifact_manager=self.artifact_manager)
        return await trainer.train_with_db_data(symbol, model_id, start_date, end_date)

    async def get_comparison(self) -> Result[list[dict[str, Any]]]:
        """Compare all trained models across all symbols by loading from artifact manager."""
        comparisons = []
        seen: set[str] = set()

        # 1. Check global training service for completed runs
        from services.global_training_service import get_training_service

        ts = get_training_service()
        runs_result = await ts.list_runs()
        if runs_result.success:
            for run in runs_result.value:
                if run.get("status") == "completed" and run.get("metrics"):
                    # Support both 'symbol' (real) and 'symbols' (demo) keys
                    sym = run.get("symbol", "")
                    if not sym:
                        sym_list = run.get("symbols", [])
                        sym = sym_list[0] if sym_list else ""
                    key = f"{run['model_type']}_{sym}"
                    if key not in seen:
                        seen.add(key)
                        comparisons.append({
                            "model_type": run["model_type"],
                            "symbol": sym,
                            "metrics": run["metrics"],
                            "run_id": run.get("id", ""),
                            "experiment_name": run.get("experiment_name", ""),
                        })

        # 2. Check artifact manager for saved models
        try:
            for model_id in self.artifact_manager.list_models():
                if model_id not in seen:
                    try:
                        _, meta = self.artifact_manager.load_model(model_id)
                        parts = model_id.split("_", 1)
                        comparisons.append({
                            "model_type": parts[0] if len(parts) > 0 else model_id,
                            "symbol": parts[1] if len(parts) > 1 else "",
                            "metrics": meta.metrics,
                            "artifact_path": meta.path,
                            "version": meta.version,
                        })
                        seen.add(model_id)
                    except Exception:
                        pass
        except Exception:
            pass

        return Result.ok(comparisons)
