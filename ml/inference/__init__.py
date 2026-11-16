"""ML Inference module — legacy inference pipeline classes.

MLD-11: This module has no production callers. All live inference goes through
``ml.model_loader.ModelLoader`` (LRU-cached lazy load) and the signal pipeline
in ``services.ml_signal_connector``. The classes here are kept for reference
and test coverage only. Remove when the codebase no longer references them in
tests.
"""

from ml.inference.batch_predictor import BatchPredictor
from ml.inference.cache import ModelCache
from ml.inference.drift_detector import DriftDetector
from ml.inference.label_encoder import LabelEncoder
from ml.inference.logger import PredictionLogger
from ml.inference.pipeline import PredictionPipeline
from ml.inference.predictor import Predictor
from ml.inference.threshold_optimizer import ThresholdOptimizer
from ml.inference.validator import PredictionValidator

__all__ = [
    "Predictor",
    "BatchPredictor",
    "ModelCache",
    "PredictionPipeline",
    "PredictionValidator",
    "PredictionLogger",
    "ThresholdOptimizer",
    "DriftDetector",
    "LabelEncoder",
]
