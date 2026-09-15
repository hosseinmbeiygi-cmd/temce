from __future__ import annotations

from enum import StrEnum


class MLTask(StrEnum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    FORECASTING = "forecasting"
    CLUSTERING = "clustering"
    ANOMALY_DETECTION = "anomaly_detection"
    RANKING = "ranking"


class ModelFramework(StrEnum):
    SKLEARN = "sklearn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"
    CATBOOST = "catboost"
    STATSMODELS = "statsmodels"


DEFAULT_TRAIN_TEST_SPLIT = 0.8
DEFAULT_VALIDATION_SPLIT = 0.1
DEFAULT_RANDOM_SEED = 42
DEFAULT_BATCH_SIZE = 2048
DEFAULT_LEARNING_RATE = 0.001
DEFAULT_N_ESTIMATORS = 100
DEFAULT_MAX_DEPTH = 6
DEFAULT_EARLY_STOPPING_ROUNDS = 10
MIN_TRAIN_SAMPLES = 100
MAX_MODEL_SIZE_MB = 500

FEATURE_GROUPS = (
    "price",
    "volume",
    "technical",
    "fundamental",
    "macro",
    "sentiment",
    "derived",
)
