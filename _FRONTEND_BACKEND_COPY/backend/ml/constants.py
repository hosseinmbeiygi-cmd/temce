from __future__ import annotations

from enum import StrEnum


class TaskType(StrEnum):
    REGRESSION = "regression"
    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    RANKING = "ranking"
    TIME_SERIES = "time_series"
    ANOMALY = "anomaly"


class ModelFamily(StrEnum):
    LINEAR = "linear"
    TREE = "tree"
    BOOSTING = "boosting"
    NEURAL = "neural"
    ENSEMBLE = "ensemble"
    SVM = "svm"
    TRANSFORMER = "transformer"


DEFAULT_METRICS_REGRESSION = ["mae", "rmse", "mape", "r2"]
DEFAULT_METRICS_CLASSIFICATION = ["accuracy", "precision", "recall", "f1", "auc"]
DEFAULT_METRICS_RANKING = ["ndcg", "map", "mrr"]

ARTIFACT_MODEL_FILE = "model.pkl"
ARTIFACT_SCALER_FILE = "scaler.pkl"
ARTIFACT_METADATA_FILE = "metadata.json"
ARTIFACT_FEATURES_FILE = "feature_names.json"
ARTIFACT_REPORT_FILE = "evaluation_report.json"
