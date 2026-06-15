from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import ModelStage


@dataclass
class ModelVersion(BaseEntity):
    model_name: str
    version: str
    stage: ModelStage = ModelStage.DEVELOPMENT
    description: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    artifact_path: str = ""
    framework: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        model_name: str,
        version: str,
        stage: ModelStage = ModelStage.DEVELOPMENT,
        description: str = "",
        metrics: dict[str, float] | None = None,
        parameters: dict[str, Any] | None = None,
        artifact_path: str = "",
        framework: str = "",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.model_name = model_name
        self.version = version
        self.stage = stage
        self.description = description
        self.metrics = metrics or {}
        self.parameters = parameters or {}
        self.artifact_path = artifact_path
        self.framework = framework
        self.is_active = is_active
        self.extra = extra or {}

    def promote_to_staging(self) -> None:
        self.stage = ModelStage.STAGING
        self.mark_updated()

    def promote_to_production(self) -> None:
        self.stage = ModelStage.PRODUCTION
        self.mark_updated()

    def archive(self) -> None:
        self.stage = ModelStage.ARCHIVED
        self.mark_updated()


@dataclass
class TrainingRun(BaseEntity):
    model_version_id: str
    status: str = "pending"
    start_time: datetime | None = None
    end_time: datetime | None = None
    epochs: int = 0
    accuracy: float = 0.0
    loss: float = 0.0
    val_accuracy: float = 0.0
    val_loss: float = 0.0
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    error_message: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        model_version_id: str,
        status: str = "pending",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        epochs: int = 0,
        accuracy: float = 0.0,
        loss: float = 0.0,
        val_accuracy: float = 0.0,
        val_loss: float = 0.0,
        hyperparameters: dict[str, Any] | None = None,
        metrics: dict[str, float] | None = None,
        error_message: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.model_version_id = model_version_id
        self.status = status
        self.start_time = start_time
        self.end_time = end_time
        self.epochs = epochs
        self.accuracy = accuracy
        self.loss = loss
        self.val_accuracy = val_accuracy
        self.val_loss = val_loss
        self.hyperparameters = hyperparameters or {}
        self.metrics = metrics or {}
        self.error_message = error_message
        self.extra = extra or {}

    def start(self) -> None:
        self.status = "running"
        self.start_time = datetime.now()
        self.mark_updated()

    def complete(self) -> None:
        self.status = "completed"
        self.end_time = datetime.now()
        self.mark_updated()

    def fail(self, error: str) -> None:
        self.status = "failed"
        self.end_time = datetime.now()
        self.error_message = error
        self.mark_updated()


@dataclass
class InferenceResult(BaseEntity):
    model_version_id: str
    instrument_id: str
    prediction: float = 0.0
    confidence: float = 0.0
    symbol: str = ""
    date: str = ""
    time: str = ""
    features: dict[str, float] = field(default_factory=dict)
    shap_values: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        model_version_id: str,
        instrument_id: str,
        prediction: float = 0.0,
        confidence: float = 0.0,
        symbol: str = "",
        date: str = "",
        time: str = "",
        features: dict[str, float] | None = None,
        shap_values: dict[str, float] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.model_version_id = model_version_id
        self.instrument_id = instrument_id
        self.prediction = prediction
        self.confidence = confidence
        self.symbol = symbol
        self.date = date
        self.time = time
        self.features = features or {}
        self.shap_values = shap_values or {}
        self.extra = extra or {}


@dataclass
class ModelMetrics:
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    mse: float = 0.0
    mae: float = 0.0
    r2_score: float = 0.0
    extra: dict[str, float] = field(default_factory=dict)
