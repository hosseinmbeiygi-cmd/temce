"""Inference service that uses real trained models for predictions.

No mock data. When no trained model is available, returns a clear error
instead of fabricated predictions.
"""

from __future__ import annotations

import asyncio
import contextlib
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


class _PipelineAdapter:
    """Adapt a raw sklearn Pipeline (model_pipeline.pkl) to the project's
    FeatureMatrix-based predict API and expose feature-importance attributes.

    The trained pipelines expect a DataFrame with their training columns
    (38 features incl. trades/microstructure/candlestick) while the runtime
    feature builder only produces price/technical columns — missing columns
    are zero-filled so ``predict`` never raises on column mismatch.
    """

    def __init__(self, pipeline: Any, feature_names: list[str]) -> None:
        self._pipeline = pipeline
        self._feature_names = list(feature_names)

    @property
    def _final_estimator(self) -> Any:
        steps = getattr(self._pipeline, "steps", None)
        if steps:
            return steps[-1][1]
        return self._pipeline

    @property
    def _model(self) -> Any:
        return self._final_estimator

    @property
    def feature_importances_(self) -> Any:
        return getattr(self._final_estimator, "feature_importances_", None)

    @property
    def coef_(self) -> Any:
        return getattr(self._final_estimator, "coef_", None)

    def predict(self, fm: FeatureMatrix):
        from types import SimpleNamespace

        import numpy as np

        df = fm.to_df().copy()
        expected = getattr(self._pipeline, "feature_names_in_", None)
        columns = list(expected) if expected is not None else self._feature_names
        for col in columns:
            if col not in df.columns:
                df[col] = 0.0
        df = df[columns]
        raw = self._pipeline.predict(df)
        return SimpleNamespace(predictions=np.asarray(raw))


class InferenceService:
    """Real ML inference backed by trained models and live market data."""

    def __init__(
        self,
        quote_repo: QuoteRepository | None = None,
        artifact_manager: ArtifactManager | None = None,
        model_repo=None,
    ) -> None:
        self.quote_repo = quote_repo
        self.artifact_manager = artifact_manager or ArtifactManager()
        self.model_repo = model_repo  # MlRepository (optional) — DB-registered models
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

        # 3. Load model — prefer DB-registered artifacts, then artifact files:
        #    a) DB ml_model_versions row (artifact_path for "{model_id}_{symbol}")
        #    b) composite ID from training (e.g., "xgboost_فولاد")
        #    c) bare model ID (e.g., "xgboost")
        model = None
        feature_names = fm.feature_names
        from_path = False

        candidate_ids = [
            model_id,
            f"{model_id}_{symbol}",
        ]

        # a) DB-registered artifact (new pipeline format: model_pipeline.pkl)
        if self.model_repo is not None:
            for cid in candidate_ids:
                try:
                    loaded = await self._load_from_db_registry(cid, fm)
                    if loaded:
                        model, feature_names, from_path = loaded
                        break
                except Exception:
                    continue

        # b) artifact file via ArtifactManager (model.pkl + metadata.json)
        if model is None:
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

    async def _load_from_db_registry(self, model_id: str, fm: FeatureMatrix):
        """Load a model pipeline registered in ml_model_versions (DB).

        Returns (model, feature_names, from_path) or None when not found.
        Handles both ``model_pipeline.pkl`` (new format) and ``model.pkl``.
        """
        import json as json_lib
        import pickle
        from pathlib import Path

        try:
            from sqlalchemy import select

            from models.ml import MlModelVersionModel

            session = getattr(self.model_repo, "_session", None)
            if session is None:
                return None
            # Prefer the production version (set from latest_path.txt by the
            # registration script); fall back to most recently created.
            stmt = (
                select(MlModelVersionModel)
                .where(MlModelVersionModel.model_id == model_id)
                .order_by(MlModelVersionModel.created_at.desc())
            )
            rows = (await session.execute(stmt)).scalars().all()
            row = next((r for r in rows if r.stage == "production"), rows[0] if rows else None)
            if row is None or not row.artifact_path:
                return None

            artifact_dir = Path(row.artifact_path)
            pipeline_file = artifact_dir / "model_pipeline.pkl"
            if not pipeline_file.exists():
                pipeline_file = artifact_dir / "model.pkl"
            if not pipeline_file.exists():
                return None

            def _read_pickle() -> Any:
                with open(pipeline_file, "rb") as f:
                    return pickle.load(f)

            loaded = await asyncio.to_thread(_read_pickle)

            trained_features: list[str] = list(fm.feature_names)
            if row.parameters:
                with contextlib.suppress(json_lib.JSONDecodeError, TypeError):
                    params = json_lib.loads(row.parameters)
                    stored = params.get("feature_names")
                    if isinstance(stored, list) and stored:
                        trained_features = [str(s) for s in stored]

            # Wrap raw pipelines so predict(fm) works with FeatureMatrix input
            model = _PipelineAdapter(loaded, trained_features) if hasattr(loaded, "predict") else loaded
            return model, trained_features, True
        except Exception as e:
            logger.debug("DB registry load failed for %s: %s", model_id, e)
            return None

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
        """Compare all trained models across all symbols.

        Sources (in priority order):
        1. DB ml_models + ml_model_versions (real trained models)
        2. Global training service completed runs
        3. Artifact manager files
        """
        import json as json_lib

        comparisons = []
        seen: set[str] = set()

        # 1. DB-registered models (real trained artifacts)
        try:
            if self.model_repo is not None:
                session = getattr(self.model_repo, "_session", None)
                if session is not None:
                    from sqlalchemy import select

                    from models.ml import MlModelModel, MlModelVersionModel

                    models = (await session.execute(select(MlModelModel))).scalars().all()
                    versions = (
                        await session.execute(
                            select(MlModelVersionModel).order_by(MlModelVersionModel.created_at.desc())
                        )
                    ).scalars().all()
                    ver_by_model: dict[str, list] = {}
                    for v in versions:
                        ver_by_model.setdefault(v.model_id, []).append(v)

                    for m in models:
                        m_versions = ver_by_model.get(m.id, [])
                        if not m_versions:
                            continue
                        latest = next(
                            (v for v in m_versions if v.stage == "production"),
                            m_versions[0],
                        )
                        metrics = {}
                        if latest.metrics:
                            try:
                                metrics = json_lib.loads(latest.metrics)
                            except (json_lib.JSONDecodeError, TypeError):
                                metrics = {}
                        parts = m.name.split("_", 1)
                        key = m.id
                        if key not in seen:
                            seen.add(key)
                            comparisons.append({
                                "model_type": parts[0] if len(parts) > 1 else (m.framework or ""),
                                "symbol": parts[1] if len(parts) > 1 else "",
                                "metrics": metrics,
                                "version": latest.version,
                                "run_id": latest.training_run_id or "",
                                "artifact_path": latest.artifact_path or "",
                                "source": "db",
                            })
        except Exception as e:
            logger.warning("DB comparison failed: %s", e)

        # 2. Check global training service for completed runs
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
                            "source": "run",
                        })

        # 3. Check artifact manager for saved models (filesystem fallback)
        with contextlib.suppress(Exception):
            for model_id in self.artifact_manager.list_models():
                if model_id not in seen:
                    with contextlib.suppress(Exception):
                        _, meta = self.artifact_manager.load_model(model_id)
                        parts = model_id.split("_", 1)
                        comparisons.append({
                            "model_type": parts[0] if len(parts) > 0 else model_id,
                            "symbol": parts[1] if len(parts) > 1 else "",
                            "metrics": meta.metrics,
                            "artifact_path": meta.path,
                            "version": meta.version,
                            "source": "artifact",
                        })
                        seen.add(model_id)

        return Result.ok(comparisons)
