"""Walk-Forward Validator — validates signal strategies using rolling out-of-sample windows.

Splits historical data into multiple train/test windows, evaluates signal accuracy
on out-of-sample data, and reports robust performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.logging import get_logger
from core.result import Result
from ml.models.registry import model_registry
from ml.types import TargetVector
from services.signal_feature_pipeline import MarketFeatures, SignalFeaturePipeline

logger = get_logger(__name__)


@dataclass
class WalkForwardWindow:
    """Single train/test split in a walk-forward validation."""
    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_size: int = 0
    test_size: int = 0
    train_accuracy: float = 0.0
    test_accuracy: float = 0.0
    train_sharpe: float = 0.0
    test_sharpe: float = 0.0
    overfitting: float = 0.0  # train_acc - test_acc (lower is better)


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward validation results."""
    market: str
    model_name: str
    num_windows: int = 0
    avg_train_accuracy: float = 0.0
    avg_test_accuracy: float = 0.0
    avg_overfitting: float = 0.0
    min_test_accuracy: float = 0.0
    max_test_accuracy: float = 0.0
    std_test_accuracy: float = 0.0
    windows: list[dict[str, Any]] = field(default_factory=list)
    robustness_score: float = 0.0  # 0-1: how stable the model is across windows
    is_reliable: bool = False      # avg_test_accuracy > 0.55 and overfitting < 0.15

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "model_name": self.model_name,
            "num_windows": self.num_windows,
            "avg_train_accuracy_pct": round(self.avg_train_accuracy * 100, 2),
            "avg_test_accuracy_pct": round(self.avg_test_accuracy * 100, 2),
            "avg_overfitting_pct": round(self.avg_overfitting * 100, 2),
            "min_test_accuracy_pct": round(self.min_test_accuracy * 100, 2),
            "max_test_accuracy_pct": round(self.max_test_accuracy * 100, 2),
            "robustness_score": round(self.robustness_score, 3),
            "is_reliable": self.is_reliable,
            "windows": self.windows,
        }


class WalkForwardValidator:
    """Walk-forward validation for signal strategies and ML models."""

    def __init__(self) -> None:
        self._pipeline = SignalFeaturePipeline()

    @staticmethod
    def _evaluate_predictions(pred_result: Any, target_vector: TargetVector) -> float:
        """Evaluate prediction accuracy: count correct direction predictions."""
        if target_vector.data is None:
            return 0.5
        correct = 0
        total = 0
        for i in range(len(target_vector.data)):
            pred_val = float(pred_result.mean) if pred_result.predictions is not None else 0.5
            actual = float(target_vector.data.iloc[i]) if hasattr(target_vector.data, "iloc") else 0
            correct += 1 if (pred_val > 0.5 and actual > 0) or (pred_val <= 0.5 and actual <= 0) else 0
            total += 1
        return correct / max(total, 1)

    async def validate_model(
        self,
        market: str,
        model_name: str,
        feature_sequence: list[MarketFeatures],
        targets: list[float] | None = None,
        closes: list[float] | None = None,
        num_windows: int = 5,
        train_ratio: float = 0.7,
    ) -> Result[WalkForwardResult]:
        """Run walk-forward validation for a model on market data.

        Args:
            market: market type (stock, gold, etc.)
            model_name: model name in ModelRegistry (xgboost, lstm, etc.)
            feature_sequence: list of MarketFeatures (time-ordered)
            targets: list of target values (same length as feature_sequence);
                     legacy precomputed-label path — ignored when ``closes`` given
            closes: full chronological close-price array the features were built
                    from; preferred label source (labels derived internally,
                    see ``SignalFeaturePipeline.prepare_training_data``)
            num_windows: number of rolling windows
            train_ratio: proportion of each window used for training
        """
        try:
            n = len(feature_sequence)
            if n < 100:
                return Result.err(f"Not enough data: need at least 100 samples, got {n}")

            window_size = n // num_windows
            train_size = int(window_size * train_ratio)

            windows: list[WalkForwardWindow] = []
            all_test_accuracies: list[float] = []
            all_overfittings: list[float] = []

            for w in range(num_windows):
                start = w * window_size
                train_end_idx = start + train_size
                test_start_idx = train_end_idx
                test_end_idx = min(start + window_size, n)

                if test_end_idx <= test_start_idx or train_end_idx > n:
                    break

                # Prepare train data
                train_features = feature_sequence[start:train_end_idx]
                train_targets = targets[start:train_end_idx] if targets is not None else None

                # Prepare test data
                test_features = feature_sequence[test_start_idx:test_end_idx]
                test_targets = targets[test_start_idx:test_end_idx] if targets is not None else None

                # Convert to ML format
                fm_train, tv_train = SignalFeaturePipeline.prepare_training_data(
                    train_features,
                    closes=closes,
                    targets=train_targets,
                    sequence_length=min(20, len(train_features) - 1)
                )
                fm_test, tv_test = SignalFeaturePipeline.prepare_training_data(
                    test_features,
                    closes=closes,
                    targets=test_targets,
                    sequence_length=min(20, len(test_features) - 1)
                )

                if fm_train.data is None or fm_train.data.empty:
                    continue
                if fm_test.data is None or fm_test.data.empty:
                    continue

                # Train
                try:
                    model = model_registry.create(model_name, params={
                        "epochs": 10, "input_size": len(fm_train.feature_names)
                    })
                    model.fit(fm_train, tv_train)

                    # Predict on train
                    train_pred = model.predict(fm_train)
                    train_acc = self._evaluate_predictions(train_pred, tv_train)

                    # Predict on test
                    test_pred = model.predict(fm_test)
                    test_acc = self._evaluate_predictions(test_pred, tv_test)

                    overfitting = train_acc - test_acc
                    all_test_accuracies.append(test_acc)
                    all_overfittings.append(overfitting)

                    window = WalkForwardWindow(
                        window_index=w + 1,
                        train_start=str(train_features[0].timestamp) if train_features else "",
                        train_end=str(train_features[-1].timestamp) if train_features else "",
                        test_start=str(test_features[0].timestamp) if test_features else "",
                        test_end=str(test_features[-1].timestamp) if test_features else "",
                        train_size=len(train_features),
                        test_size=len(test_features),
                        train_accuracy=train_acc,
                        test_accuracy=test_acc,
                        overfitting=overfitting,
                    )
                    windows.append(window)

                except Exception as model_err:
                    logger.warning("Window %d model failed: %s", w + 1, model_err)
                    continue

            if not windows:
                return Result.err("No windows completed successfully")

            # Aggregate
            result = WalkForwardResult(
                market=market,
                model_name=model_name,
                num_windows=len(windows),
                windows=[{
                    "window": w.window_index,
                    "train_acc_pct": round(w.train_accuracy * 100, 2),
                    "test_acc_pct": round(w.test_accuracy * 100, 2),
                    "overfitting_pct": round(w.overfitting * 100, 2),
                    "train_size": w.train_size,
                    "test_size": w.test_size,
                } for w in windows],
            )

            result.avg_train_accuracy = np.mean([w.train_accuracy for w in windows])
            result.avg_test_accuracy = np.mean([w.test_accuracy for w in windows])
            result.avg_overfitting = np.mean([w.overfitting for w in windows])
            result.min_test_accuracy = min(all_test_accuracies) if all_test_accuracies else 0
            result.max_test_accuracy = max(all_test_accuracies) if all_test_accuracies else 0
            result.std_test_accuracy = np.std(all_test_accuracies, ddof=1) if len(all_test_accuracies) > 1 else 0

            # Robustness score (0-1): based on how stable test accuracy is
            if result.avg_test_accuracy > 0:
                stability = 1.0 - min(1.0, result.std_test_accuracy / max(result.avg_test_accuracy, 0.001))
                overfitting_penalty = 1.0 - min(1.0, result.avg_overfitting * 2)
                result.robustness_score = stability * 0.5 + overfitting_penalty * 0.5
            else:
                result.robustness_score = 0.0

            # Average test Sharpe across windows (must be positive for a usable model)
            avg_test_sharpe = np.mean([w.test_sharpe for w in windows]) if windows else 0.0

            result.is_reliable = (
                result.avg_test_accuracy > 0.58 and
                result.avg_overfitting < 0.10 and
                result.robustness_score > 0.5 and
                avg_test_sharpe > 0.5
            )

            return Result.ok(result)

        except Exception as e:
            logger.error("Walk-forward validation failed: %s", e, exc_info=True)
            return Result.err(str(e))

    async def validate_multiple_models(
        self,
        market: str,
        feature_sequence: list[MarketFeatures],
        targets: list[float] | None = None,
        closes: list[float] | None = None,
        model_names: list[str] | None = None,
        num_windows: int = 5,
    ) -> Result[list[WalkForwardResult]]:
        """Run walk-forward validation for multiple models and compare."""
        if model_names is None:
            model_names = ["xgboost", "random_forest", "lstm"]

        results: list[WalkForwardResult] = []

        for model_name in model_names:
            r = await self.validate_model(
                market=market,
                model_name=model_name,
                feature_sequence=feature_sequence,
                targets=targets,
                closes=closes,
                num_windows=num_windows,
            )
            if r.success:
                results.append(r.value)

        # Sort by test accuracy descending
        results.sort(key=lambda x: x.avg_test_accuracy, reverse=True)

        return Result.ok(results)
