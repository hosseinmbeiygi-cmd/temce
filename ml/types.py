from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class FeatureMatrix:
    data: Any = None
    feature_names: list[str] = field(default_factory=list)
    index: Any = None

    def __post_init__(self) -> None:
        if not self.feature_names:
            self.feature_names = list(self.data.columns) if hasattr(self.data, "columns") else []
        if self.index is None and hasattr(self.data, "index"):
            self.index = self.data.index

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape if hasattr(self.data, "shape") else (0, 0)

    @property
    def values(self):
        return self.data.values if hasattr(self.data, "values") else self.data

    def to_df(self):
        import pandas as pd

        if isinstance(self.data, pd.DataFrame):
            return self.data
        return pd.DataFrame(self.data)


@dataclass
class TargetVector:
    data: Any = None
    name: str = "target"
    task_type: str = "regression"

    @property
    def values(self):
        return self.data.values if hasattr(self.data, "values") else self.data

    @property
    def shape(self) -> tuple:
        return self.data.shape if hasattr(self.data, "shape") else (0,)


@dataclass
class PredictionResult:
    predictions: Any = None
    probabilities: Any = None
    model_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean(self) -> float:
        import numpy as np

        arr = np.asarray(self.predictions) if self.predictions is not None else np.array([])
        return float(np.mean(arr))

    @property
    def std(self) -> float:
        import numpy as np

        arr = np.asarray(self.predictions) if self.predictions is not None else np.array([])
        return float(np.std(arr))


@dataclass
class ModelArtifactMeta:
    model_id: str
    version: str
    path: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    stage: str = "development"
    # M1: content-addressable provenance
    artifact_hash: str = ""
    file_size_bytes: int = 0
    dataset_hash: str = ""
    python_version: str = ""
    library_versions: dict[str, str] = field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.stage == "production"


@dataclass
class SplitMeta:
    train_idx: Any = None
    val_idx: Any = None
    test_idx: Any = None

    def apply(
        self, features: FeatureMatrix, targets: TargetVector
    ) -> tuple[FeatureMatrix, FeatureMatrix, TargetVector, TargetVector, FeatureMatrix | None, TargetVector | None]:
        import pandas as pd

        X_train = (
            FeatureMatrix(data=features.data.iloc[self.train_idx])
            if isinstance(features.data, pd.DataFrame)
            else FeatureMatrix()
        )
        y_train = (
            TargetVector(data=targets.data.iloc[self.train_idx])
            if isinstance(targets.data, pd.Series)
            else TargetVector()
        )
        X_val = (
            FeatureMatrix(data=features.data.iloc[self.val_idx])
            if isinstance(features.data, pd.DataFrame)
            else FeatureMatrix()
        )
        y_val = (
            TargetVector(data=targets.data.iloc[self.val_idx])
            if isinstance(targets.data, pd.Series)
            else TargetVector()
        )
        X_test = None
        y_test = None
        if self.test_idx is not None:
            X_test = (
                FeatureMatrix(data=features.data.iloc[self.test_idx])
                if isinstance(features.data, pd.DataFrame)
                else None
            )
            y_test = (
                TargetVector(data=targets.data.iloc[self.test_idx]) if isinstance(targets.data, pd.Series) else None
            )
        return X_train, X_val, y_train, y_val, X_test, y_test
