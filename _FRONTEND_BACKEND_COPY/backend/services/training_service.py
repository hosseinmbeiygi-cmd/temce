"""Training service that connects real market data to the ML pipeline.

Previously: mock data + in-memory runs.
Now: fetches actual OHLCV from DB → builds technical features → trains real
sklearn/xgboost models → saves artifacts → returns real metrics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd

# Ensure model classes are registered before use
import ml.models.shallow.linear_models  # noqa: F401 — registers linear_regression, logistic_regression
import ml.models.shallow.tree_models  # noqa: F401 — registers random_forest, xgboost
from core.logging import get_logger
from core.result import Result
from ml.artifacts import ArtifactManager
from ml.evaluation.metrics import MetricsCalculator
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, ModelArtifactMeta, TargetVector
from repositories.quote_repository import QuoteRepository

logger = get_logger(__name__)


class TrainingService:
    """Train ML models on real market data from the database."""

    def __init__(
        self, quote_repo: QuoteRepository | None = None, artifact_manager: ArtifactManager | None = None
    ) -> None:
        self.quote_repo = quote_repo
        self.artifact_manager = artifact_manager or ArtifactManager()
        self.price_features = PriceFeatures(window_sizes=[5, 10, 20])
        self.technical_features = TechnicalFeatures()
        self.metrics_calc = MetricsCalculator()
        self._runs: dict[str, dict[str, Any]] = {}

    async def _fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> Result[pd.DataFrame]:
        """Load daily OHLCV data for a symbol from the database."""
        if not self.quote_repo:
            return Result.fail("No database session — start the server with DB")

        try:
            from datetime import date as date_type

            sd = date_type.fromisoformat(start_date) if start_date else date_type(2024, 1, 1)
            ed = date_type.fromisoformat(end_date) if end_date else date_type.today()
        except ValueError:
            return Result.fail(f"Invalid date format: {start_date} / {end_date}")

        try:
            result = await self.quote_repo.get_range(symbol, sd, ed, timeframe="1d")
        except Exception as e:
            return Result.fail(f"DB query failed for {symbol}: {e}")

        if not result.success or not result.value:
            return Result.ok(pd.DataFrame())

        quotes = result.value
        rows = []
        for q in quotes:
            rows.append(
                {
                    "date": q.date,
                    "open": q.price_open or q.price_first or 0,
                    "high": q.price_high or q.price_max or 0,
                    "low": q.price_low or q.price_min or 0,
                    "close": q.price_close or q.price_last or 0,
                    "volume": q.volume or 0,
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            return Result.ok(df)

        df = df.sort_values("date").reset_index(drop=True)
        # Remove rows with zero close (no trade days)
        df = df[df["close"] > 0].reset_index(drop=True)
        return Result.ok(df)

    def _prepare_target(self, df: pd.DataFrame, horizon: int = 1) -> pd.Series:
        """Create a regression target: future price change percentage."""
        future_close = df["close"].shift(-horizon)
        target = (future_close - df["close"]) / df["close"]
        return target

    def _build_features(self, df: pd.DataFrame) -> tuple[FeatureMatrix, TargetVector]:
        """Build feature matrix and target vector from OHLCV data."""
        # Price-based features
        price_fm = self.price_features.compute(df)

        # Rename columns to match expected names
        feature_df = df.rename(
            columns={
                "open": "price_open",
                "high": "price_high",
                "low": "price_low",
                "close": "price_close",
                "volume": "volume",
            }
        )

        # Technical features
        tech_fm = self.technical_features.compute(feature_df)

        # Combine features
        combined_df = price_fm.to_df()
        tech_df = tech_fm.to_df()
        for col in tech_df.columns:
            if col not in combined_df.columns:
                combined_df[col] = tech_df[col]

        # Drop rows with NaN (from rolling windows)
        combined_df = combined_df.dropna().reset_index(drop=True)

        # Build target
        target_series = self._prepare_target(combined_df, horizon=1)
        combined_df = combined_df.iloc[: len(target_series)].reset_index(drop=True)
        target_series = target_series.iloc[: len(combined_df)]

        # Remove remaining NaN targets
        mask = target_series.notna()
        combined_df = combined_df[mask].reset_index(drop=True)
        target_series = target_series[mask].reset_index(drop=True)

        feature_names = [c for c in combined_df.columns if c not in ("date", "time", "symbol")]
        X = FeatureMatrix(data=combined_df[feature_names], feature_names=feature_names)
        y = TargetVector(data=target_series.values, name="next_return", task_type="regression")
        return X, y

    def _split_time_series(self, X: FeatureMatrix, y: TargetVector, train_ratio: float = 0.8):
        """Time-series split (no shuffle) to avoid look-ahead bias."""
        n = X.shape[0]
        split_idx = int(n * train_ratio)
        X_train = FeatureMatrix(
            data=X.data.iloc[:split_idx] if hasattr(X.data, "iloc") else X.data[:split_idx],
            feature_names=X.feature_names,
        )
        y_train = TargetVector(
            data=y.data[:split_idx] if hasattr(y.data, "__getitem__") else y.data[:split_idx],
            name=y.name,
            task_type=y.task_type,
        )
        X_val = FeatureMatrix(
            data=X.data.iloc[split_idx:] if hasattr(X.data, "iloc") else X.data[split_idx:],
            feature_names=X.feature_names,
        )
        y_val = TargetVector(
            data=y.data[split_idx:] if hasattr(y.data, "__getitem__") else y.data[split_idx:],
            name=y.name,
            task_type=y.task_type,
        )
        return X_train, X_val, y_train, y_val

    async def train_with_db_data(
        self,
        symbol: str,
        model_type: str = "xgboost",
        start_date: str = "",
        end_date: str = "",
        experiment_name: str = "",
    ) -> Result[dict[str, Any]]:
        """Fetch real data → build features → train model → save → return metrics."""
        # 1. Fetch data
        data_result = await self._fetch_ohlcv(symbol, start_date, end_date)
        if not data_result.success:
            return Result.fail(f"Data fetch failed: {data_result.error}")
        df = data_result.value
        if df.empty or len(df) < 30:
            return Result.fail(f"Not enough data for {symbol}: got {len(df)} rows (need ≥ 30)")

        # 2. Build features
        X, y = self._build_features(df)
        if X.shape[0] < 20:
            return Result.fail(f"Not enough valid samples after feature engineering: {X.shape[0]}")

        # 3. Split (time-series)
        X_train, X_val, y_train, y_val = self._split_time_series(X, y)

        # 4. Create model
        try:
            model = model_registry.create(model_type)
        except ValueError:
            available = model_registry.list_models()
            return Result.fail(f"Unknown model '{model_type}'. Available: {', '.join(available)}")

        # 5. Train
        try:
            logger.info(
                "Training %s on %s — %d train / %d val samples", model_type, symbol, X_train.shape[0], X_val.shape[0]
            )
            model.fit(X_train, y_train)

            # Evaluate on validation set
            preds = model.predict(X_val)
            metrics = self.metrics_calc.compute(y_val.values, preds.predictions, task="regression")
        except Exception as e:
            logger.exception("Training failed for %s/%s", symbol, model_type)
            return Result.fail(f"Training error: {e}")

        # 6. Save model artifact
        run_id = uuid.uuid4().hex[:12]
        meta = ModelArtifactMeta(
            model_id=f"{model_type}_{symbol}",
            version=f"v1-{run_id[:8]}",
            metrics=metrics,
            params=model.params,
            feature_names=X.feature_names,
            stage="development",
        )
        try:
            artifact_path = self.artifact_manager.save_model(model, meta)
            logger.info("Model saved to %s", artifact_path)
        except Exception as e:
            logger.warning("Could not save model artifact: %s", e)
            artifact_path = ""

        # 6b. Auto-refresh the ModelLoader cache so the freshly-trained
        #     artifact is picked up without a restart.
        self._invalidate_model_cache(symbol, model_type)

        # 7. Store run (use 'symbols' list for consistency with global service)
        run = {
            "id": run_id,
            "experiment_name": experiment_name or f"{model_type}-{symbol}-{datetime.now(UTC).strftime('%Y%m%d')}",
            "model_type": model_type,
            "symbol": symbol,
            "symbols": [symbol],
            "status": "completed",
            "metrics": metrics,
            "feature_names": X.feature_names,
            "artifact_path": artifact_path,
            "train_samples": X_train.shape[0],
            "val_samples": X_val.shape[0],
            "start_date": start_date,
            "end_date": end_date,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._runs[run_id] = run

        return Result.ok(run)

    @staticmethod
    def _invalidate_model_cache(symbol: str, algorithm: str) -> None:
        """Evict the freshly-retrained model from the ModelLoader LRU cache.

        Called after every successful retrain so the next
        ``get_model(symbol, algorithm)`` call loads the new artifact from disk
        instead of returning the stale in-memory copy.  Failure to invalidate
        is non-fatal — it only means one more stale read until the next call.
        """
        try:
            from ml.model_loader import get_model_loader

            get_model_loader().invalidate(symbol=symbol, algorithm=algorithm)
            logger.info("ModelLoader cache invalidated for %s/%s (auto-refresh)", symbol, algorithm)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not invalidate ModelLoader cache for %s/%s: %s", symbol, algorithm, e)

    async def train(self, model, dataset_config, **kwargs):
        """Original method: delegate to real Trainer (kept for compatibility)."""
        from ml.training.trainer import Trainer

        trainer = Trainer()
        return await trainer.train(model, dataset_config, **kwargs)

    async def start_training(
        self, experiment_name: str = "", model_type: str = "xgboost", symbols: list[str] | None = None
    ) -> Result[dict[str, Any]]:
        run_id = uuid.uuid4().hex[:12]
        run = {
            "id": run_id,
            "experiment_name": experiment_name,
            "model_type": model_type,
            "symbols": symbols or [],
            "status": "running",
            "metrics": {},
        }
        self._runs[run_id] = run
        return Result.ok(run)

    async def get_training_status(self, run_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(self._runs.get(run_id))

    async def list_runs(self) -> Result[list[dict[str, Any]]]:
        return Result.ok(list(self._runs.values()))

    async def cancel_run(self, run_id: str) -> Result[bool]:
        if run_id in self._runs:
            self._runs[run_id]["status"] = "cancelled"
            return Result.ok(True)
        return Result.fail("Run not found")

    async def get_metrics(self, run_id: str) -> Result[dict[str, Any]]:
        run = self._runs.get(run_id)
        if run:
            return Result.ok(run.get("metrics", {}))
        return Result.fail("Run not found")

    async def get_feature_importance(self, run_id: str) -> Result[dict[str, float]]:
        """Get feature importance for a completed training run."""
        run = self._runs.get(run_id)
        if not run:
            return Result.fail("Run not found")
        if run.get("status") != "completed":
            return Result.fail("Run not yet completed")

        artifact_path = run.get("artifact_path", "")
        if not artifact_path:
            return Result.fail("No artifact saved (run was simulated)")

        sym = run.get("symbol", "") or (run.get("symbols") or [""])[0]
        try:
            model, _ = self.artifact_manager.load_model(
                f"{run['model_type']}_{sym}",
                version="latest",
            )
        except Exception:
            return Result.fail("Could not load model artifact")

        importance = {}
        if hasattr(model, "feature_importances_"):
            feature_names = run.get("feature_names", [])
            importances = model.feature_importances_
            for i, name in enumerate(feature_names):
                if i < len(importances):
                    importance[name] = float(importances[i])
            # Sort by importance descending
            importance = dict(sorted(importance.items(), key=lambda x: -x[1]))
        elif hasattr(model, "coef_"):
            feature_names = run.get("feature_names", [])
            coefs = abs(model.coef_)
            if coefs.ndim > 1:
                coefs = coefs[0]
            for i, name in enumerate(feature_names):
                if i < len(coefs):
                    importance[name] = float(coefs[i])
            importance = dict(sorted(importance.items(), key=lambda x: -x[1]))

        return Result.ok(importance)
