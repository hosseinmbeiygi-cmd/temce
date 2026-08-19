"""ML-Signal Connector — bridges the ModelRegistry with the MultiMarketSignalEngine.

Trains ML models on historical signal data, then uses them to predict
direction and confidence for new signals alongside rule-based analysis.

Model loading is delegated to ``ModelLoader`` (``ml/model_loader.py``) which
provides bounded LRU caching so at most 20 hot models stay in memory.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from ml.model_loader import ModelLoader, get_model_loader
from ml.models.registry import model_registry
from services.signal_feature_pipeline import MarketFeatures, SignalFeaturePipeline

# ── Heuristic Fallback Models ──────────────────────────────────────────────
# Simple trend-based and momentum-based models used when no trained ML models exist.
# These give the signal pipeline SOMETHING to work with instead of returning
# all-neutral predictions (which collapse the ML branch of the voting system).


def _heuristic_trend_predict(closes: list[float]) -> dict[str, Any]:
    """Simple trend-following heuristic.

    - Short MA > Long MA by > threshold → buy
    - Long MA > Short MA by > threshold → sell
    - Otherwise → hold
    Returns prediction dict matching MLSignalConnector output format.
    """
    if not closes or len(closes) < 10:
        return {"direction": "hold", "direction_scores": {"buy": 0.5, "sell": 0.5, "hold": 0.5},
                "confidence": 0.0, "ml_score": 0.5, "models_used": ["heuristic_trend"]}

    prices = [c for c in closes if c and c > 0]
    if len(prices) < 10:
        return {"direction": "hold", "direction_scores": {"buy": 0.5, "sell": 0.5, "hold": 0.5},
                "confidence": 0.0, "ml_score": 0.5, "models_used": ["heuristic_trend"]}

    short_ma = sum(prices[-5:]) / 5.0
    long_ma = sum(prices[-20:]) / 20.0 if len(prices) >= 20 else sum(prices[-10:]) / 10.0

    ratio = (short_ma - long_ma) / max(long_ma, 0.001)

    if ratio > 0.02:  # 2% above long MA → buy
        confidence = min(0.6, abs(ratio) * 5)
        return {"direction": "buy", "direction_scores": {"buy": 0.6 + confidence * 0.3, "sell": 0.3, "hold": 0.4},
                "confidence": round(confidence, 3), "ml_score": round(0.5 + ratio, 3),
                "models_used": ["heuristic_trend"], "note": "trend_following"}
    elif ratio < -0.02:  # 2% below long MA → sell
        confidence = min(0.6, abs(ratio) * 5)
        return {"direction": "sell", "direction_scores": {"buy": 0.3, "sell": 0.6 + confidence * 0.3, "hold": 0.4},
                "confidence": round(confidence, 3), "ml_score": round(0.5 - abs(ratio), 3),
                "models_used": ["heuristic_trend"], "note": "trend_following"}
    else:
        # Mean reversion: if ratio is small, check if recent move was extreme
        recent_ret = (prices[-1] - prices[-5]) / max(prices[-5], 0.001) if len(prices) >= 5 else 0
        if abs(recent_ret) > 0.03:  # 3% move in 5 days → possible reversal
            if recent_ret > 0:
                return {"direction": "sell", "direction_scores": {"buy": 0.4, "sell": 0.55, "hold": 0.5},
                        "confidence": 0.35, "ml_score": 0.45, "models_used": ["heuristic_mean_reversion"],
                        "note": "mean_reversion"}
            else:
                return {"direction": "buy", "direction_scores": {"buy": 0.55, "sell": 0.4, "hold": 0.5},
                        "confidence": 0.35, "ml_score": 0.45, "models_used": ["heuristic_mean_reversion"],
                        "note": "mean_reversion"}

    return {"direction": "hold", "direction_scores": {"buy": 0.45, "sell": 0.45, "hold": 0.55},
            "confidence": 0.2, "ml_score": 0.45, "models_used": ["heuristic_neutral"],
            "note": "no_clear_signal"}

logger = get_logger(__name__)


class MLSignalConnector:
    """Connects ML models to the signal generation pipeline.

    Usage:
        connector = MLSignalConnector()
        prediction = await connector.predict("فولاد", "stock", features)
        signal_boost = connector.get_signal_boost(prediction, rule_based_signal)
    """

    # Default model config per market
    DEFAULT_MODELS: dict[str, list[dict[str, Any]]] = {
        "stock": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.35},
            {"model_name": "lstm", "task": "regression", "weight": 0.30},
            {"model_name": "random_forest", "task": "classification", "weight": 0.20},
            {"model_name": "transformer", "task": "regression", "weight": 0.15},
        ],
        "gold": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.40},
            {"model_name": "lstm", "task": "regression", "weight": 0.35},
            {"model_name": "gru", "task": "regression", "weight": 0.25},
        ],
        "currency": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.45},
            {"model_name": "lstm", "task": "regression", "weight": 0.30},
            {"model_name": "linear_regression", "task": "regression", "weight": 0.25},
        ],
        "crypto": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.30},
            {"model_name": "lstm", "task": "regression", "weight": 0.35},
            {"model_name": "transformer", "task": "regression", "weight": 0.35},
        ],
        "option": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.40},
            {"model_name": "random_forest", "task": "classification", "weight": 0.35},
            {"model_name": "linear_regression", "task": "regression", "weight": 0.25},
        ],
        "commodity": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.40},
            {"model_name": "lstm", "task": "regression", "weight": 0.35},
            {"model_name": "gru", "task": "regression", "weight": 0.25},
        ],
        "ime": [
            {"model_name": "xgboost", "task": "classification", "weight": 0.40},
            {"model_name": "linear_regression", "task": "regression", "weight": 0.30},
            {"model_name": "random_forest", "task": "classification", "weight": 0.30},
        ],
    }

    def __init__(self, model_loader: ModelLoader | None = None) -> None:
        self._pipeline = SignalFeaturePipeline()
        self._model_loader = model_loader or get_model_loader()
        self._trained_models: dict[str, dict[str, Any]] = {}  # market -> {model_name: model_instance}

    async def predict(
        self,
        features: MarketFeatures,
        market: str,
        closes: list[float] | None = None,
    ) -> Result[dict[str, Any]]:
        """Run prediction using all trained models for the given market.

        Args:
            features: MarketFeatures from SignalFeaturePipeline
            market: Market type (stock, gold, crypto, etc.)
            closes: Optional close prices for heuristic fallback.
                    If not provided, tries to extract from MarketFeatures.

        Returns:
            {direction, confidence, ml_score, model_breakdown}
        """
        models_config = self.DEFAULT_MODELS.get(market, self.DEFAULT_MODELS["stock"])
        trained = self._trained_models.get(market, {})

        if not trained:
            # Lazy-load from ModelLoader — try each configured algorithm.
            model_name = None
            model_obj = None
            for cfg in models_config:
                mn = cfg["model_name"]
                # Try to guess the symbol from features (or fall back to market name).
                sym = getattr(features, "symbol", market)
                obj = await self._model_loader.get_model(symbol=sym, algorithm=mn)
                if obj is not None:
                    model_name = mn
                    model_obj = obj
                    trained[mn] = obj
                    break

            if model_obj is not None:
                self._trained_models.setdefault(market, {})[model_name] = model_obj
                logger.info(
                    "Lazy-loaded model %s for '%s' from ModelLoader cache",
                    model_name, market,
                )
            else:
                # Fallback: use heuristic trend-following + mean reversion
                if not closes:
                    try:
                        closes = getattr(features, 'closes', [])
                    except Exception:
                        closes = []

                if closes and len(closes) >= 10:
                    logger.info("No trained models for '%s'. Using heuristic fallback.", market)
                    return Result.ok(_heuristic_trend_predict(closes))

                logger.info("No trained models for '%s' and insufficient price data. Returning neutral.", market)
                return Result.ok({
                    "direction_scores": {"buy": 0.5, "sell": 0.5, "hold": 0.5},
                    "confidence": 0.0,
                    "ml_score": 0.5,
                    "models_used": [],
                    "note": "no_trained_models_no_data",
                })

        fm = features.to_feature_matrix()

        buy_scores: list[float] = []
        sell_scores: list[float] = []
        hold_scores: list[float] = []
        confidences: list[float] = []
        model_breakdown: list[dict[str, Any]] = []
        total_weight = 0.0

        for model_cfg in models_config:
            model_name = model_cfg["model_name"]
            weight = model_cfg.get("weight", 0.25)
            model = trained.get(model_name)

            if model is None or not model.is_fitted:
                continue

            try:
                result = model.predict(fm)

                # Convert prediction to direction scores
                pred_value = float(result.mean) if result.predictions is not None else 0.5

                # Normalize to direction scores
                if model_cfg["task"] == "classification":
                    # Binary: output is probability of UP
                    buy_scores.append(pred_value * weight)
                    sell_scores.append((1 - pred_value) * weight)
                    hold_scores.append(0.5 * weight * 0.5)
                else:
                    # Regression: positive = buy, negative = sell
                    norm_score = 0.5 + pred_value  # shift to 0-1 range
                    norm_score = max(0.0, min(1.0, norm_score))
                    buy_scores.append(norm_score * weight)
                    sell_scores.append((1 - norm_score) * weight)
                    hold_scores.append(0.5 * (1 - abs(norm_score - 0.5) * 2) * weight)

                confidence_val = min(1.0, max(0.0, abs(pred_value)))
                confidences.append(confidence_val * weight)
                total_weight += weight

                model_breakdown.append({
                    "model": model_name,
                    "prediction": round(pred_value, 4),
                    "confidence": round(confidence_val, 3),
                    "weight": weight,
                })
            except Exception as model_err:
                logger.warning("Model %s prediction failed: %s", model_name, model_err)

        if total_weight == 0:
            return Result.ok({
                "direction_scores": {"buy": 0.5, "sell": 0.5, "hold": 0.5},
                "confidence": 0.0,
                "ml_score": 0.5,
                "models_used": [],
                "note": "all_models_failed",
            })

        # Weighted average
        final_buy = sum(buy_scores) / total_weight
        final_sell = sum(sell_scores) / total_weight
        final_hold = sum(hold_scores) / total_weight
        avg_confidence = sum(confidences) / total_weight

        # Final direction
        if final_buy > final_sell and final_buy > final_hold:
            direction = "buy"
            ml_score = final_buy
        elif final_sell > final_buy and final_sell > final_hold:
            direction = "sell"
            ml_score = final_sell
        else:
            direction = "hold"
            ml_score = final_hold

        return Result.ok({
            "direction": direction,
            "direction_scores": {
                "buy": round(final_buy, 3),
                "sell": round(final_sell, 3),
                "hold": round(final_hold, 3),
            },
            "confidence": round(avg_confidence, 3),
            "ml_score": round(ml_score, 3),
            "models_used": [m["model"] for m in model_breakdown],
            "model_breakdown": model_breakdown,
        })

    def get_signal_boost(self, ml_prediction: dict[str, Any], rule_signal_score: float) -> dict[str, Any]:
        """Combine ML prediction with rule-based signal score.

        Returns:
            {boosted_score, boosted_confidence, ml_influence_pct}
        """
        ml_score = ml_prediction.get("ml_score", 0.5)
        ml_confidence = ml_prediction.get("confidence", 0.0)

        # Weight depends on ML confidence: low confidence = low influence
        ml_weight = ml_confidence * 0.7  # ML contributes up to 70% (was 40% — fix #4)
        rule_weight = 1.0 - ml_weight

        boosted_score = rule_weight * rule_signal_score + ml_weight * (ml_score * 100)
        boosted_confidence = rule_weight * 0.5 + ml_weight * ml_confidence

        return {
            "boosted_score": round(boosted_score, 2),
            "boosted_confidence": round(boosted_confidence, 3),
            "ml_contribution": round(ml_score, 3),
            "ml_influence_pct": round(ml_weight * 100, 1),
            "rule_contribution": round(rule_signal_score, 2),
            "ml_direction": ml_prediction.get("direction", "hold"),
        }

    def get_accuracy_by_market(self, market: str) -> float:
        """Get the current accuracy for ML models in a market (for adaptive weighting)."""
        # In production, this would query the DB for actual accuracy metrics
        return 0.55  # default baseline

    def get_trained_models_info(self) -> dict[str, list[str]]:
        """List all currently trained and loaded models by market."""
        return {
            market: list(models.keys())
            for market, models in self._trained_models.items()
        }

    def load_models_from_disk(self, market_filter: str | None = None) -> dict[str, int]:
        """Load trained model artifacts from disk into _trained_models.

        Searches the ArtifactManager for saved models matching DEFAULT_MODELS config
        and loads them for use in predict().

        Returns {market: models_loaded} dict.
        """
        from ml.artifacts import ArtifactManager

        loaded: dict[str, int] = {}
        am = ArtifactManager()
        saved_models = am.list_models()

        markets = [market_filter] if market_filter else list(self.DEFAULT_MODELS.keys())

        for market in markets:
            configs = self.DEFAULT_MODELS.get(market, [])
            market_loaded = 0

            for cfg in configs:
                model_name = cfg["model_name"]
                # Artifact is saved as "{model_type}_{symbol}" — try to find ANY symbol for this model_type+market
                for saved_id in saved_models:
                    if saved_id.startswith(f"{model_name}_"):
                        try:
                            model_obj, _meta = am.load_model(saved_id, version="latest")
                            if hasattr(model_obj, "is_fitted") and model_obj.is_fitted:
                                self._trained_models.setdefault(market, {})[model_name] = model_obj
                                market_loaded += 1
                                logger.info("Loaded %s for market '%s' from %s", model_name, market, saved_id)
                                break  # found one for this model_name, done
                        except Exception as e:
                            logger.debug("Could not load %s: %s", saved_id, e)

            loaded[market] = market_loaded
            if market_loaded > 0:
                logger.info("Loaded %d models for market '%s'", market_loaded, market)

        return loaded

    async def train_for_market(
        self,
        market: str,
        feature_sequence: list[MarketFeatures],
        targets: list[float],
        model_names: list[str] | None = None,
    ) -> Result[dict[str, Any]]:
        """Train ML models for a specific market on historical feature data."""

        if model_names is None:
            model_names = [cfg["model_name"] for cfg in self.DEFAULT_MODELS.get(market, self.DEFAULT_MODELS["stock"])]

        _, sequence_length = feature_sequence[0].shape if feature_sequence else (0, 0)

        # Prepare training data
        fm, tv = SignalFeaturePipeline.prepare_training_data(feature_sequence, targets, sequence_length=min(20, len(feature_sequence) - 1))

        if fm.data is None or fm.data.empty:
            return Result.fail("Not enough data to train")

        trained_count = 0
        errors: list[str] = []

        for model_name in model_names:
            try:
                model = model_registry.create(model_name, params={"epochs": 10, "input_size": len(fm.feature_names)})
                model.fit(fm, tv)
                self._trained_models.setdefault(market, {})[model_name] = model
                trained_count += 1
                logger.info("Trained %s model for market '%s'", model_name, market)
            except Exception as e:
                errors.append(f"{model_name}: {e}")
                logger.warning("Failed to train %s for %s: %s", model_name, market, e)

        return Result.ok({
            "market": market,
            "trained": trained_count,
            "total_requested": len(model_names),
            "errors": errors,
        })
