from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrainingRunConfig:
    model_name: str = ""
    model_version: str = ""
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    optimizer: str = "adam"
    loss_function: str = "mse"
    validation_split: float = 0.2
    test_split: float = 0.1
    early_stopping_patience: int = 10
    feature_set_id: str = ""
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
