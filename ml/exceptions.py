from __future__ import annotations


class MLException(Exception):
    pass


class ModelNotFoundError(MLException):
    def __init__(self, model_id: str) -> None:
        super().__init__(f"Model not found: {model_id}")


class TrainingError(MLException):
    def __init__(self, message: str = "Training failed") -> None:
        super().__init__(message)


class InferenceError(MLException):
    def __init__(self, message: str = "Inference failed") -> None:
        super().__init__(message)


class DataValidationError(MLException):
    def __init__(self, message: str = "Data validation failed") -> None:
        super().__init__(message)
