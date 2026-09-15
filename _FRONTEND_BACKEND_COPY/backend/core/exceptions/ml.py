from __future__ import annotations

from core.exceptions import AppError


class MLError(AppError):
    def __init__(self, message: str = "ML error", code: str = "ML_ERROR") -> None:
        super().__init__(message=message, code=code)


class ModelNotFoundError(MLError):
    def __init__(self, model_name: str = "", version: str | None = None) -> None:
        msg = f"Model '{model_name}' not found" + (f" version {version}" if version else "")
        super().__init__(message=msg, code="MODEL_NOT_FOUND")


class TrainingError(MLError):
    def __init__(self, message: str = "Model training failed", details: dict | None = None) -> None:
        super().__init__(message=message, code="TRAINING_ERROR")


class InferenceError(MLError):
    def __init__(self, message: str = "Model inference failed", model: str | None = None) -> None:
        super().__init__(message=message, code="INFERENCE_ERROR")


class FeatureStoreError(MLError):
    def __init__(self, message: str = "Feature store error") -> None:
        super().__init__(message=message, code="FEATURE_STORE_ERROR")


class DataDriftDetected(MLError):
    def __init__(self, message: str = "Data drift detected", features: list[str] | None = None) -> None:
        super().__init__(message=message, code="DATA_DRIFT_DETECTED")


class ExperimentError(MLError):
    def __init__(self, message: str = "Experiment tracking error") -> None:
        super().__init__(message=message, code="EXPERIMENT_ERROR")
