from __future__ import annotations

from typing import Any

from core.logging import get_logger
from ml.models.deep.base_deep import BaseDeepModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class CNNModel(BaseDeepModel):
    def __init__(self, name: str = "cnn", params: dict[str, Any] | None = None) -> None:
        default_params = {
            "input_size": 10,
            "num_channels": [32, 64],
            "kernel_size": 3,
            "output_size": 1,
            "dropout": 0.2,
            "fc_hidden_size": 128,
            "task": "regression",
            "epochs": 100,
            "batch_size": 32,
            "learning_rate": 1e-3,
            "patience": 10,
        }
        merged = {**default_params, **(params or {})}
        super().__init__(name, merged)
        self._build_model(merged["input_size"])

    def _build_model(self, input_size: int, **kwargs: Any) -> None:
        torch = self._get_torch()

        num_channels = self.params.get("num_channels", [32, 64])
        kernel_size = self.params.get("kernel_size", 3)
        output_size = self.params.get("output_size", 1)
        dropout = self.params.get("dropout", 0.2)
        fc_hidden_size = self.params.get("fc_hidden_size", 128)
        task = self.params.get("task", "regression")

        class _CNNNet(torch.nn.Module):
            def __init__(self_inner: Any) -> None:
                super().__init__()
                layers: list[Any] = []
                in_channels = 1
                current_len = input_size
                for ch in num_channels:
                    layers.append(torch.nn.Conv1d(in_channels, ch, kernel_size, padding=kernel_size // 2))
                    layers.append(torch.nn.BatchNorm1d(ch))
                    layers.append(torch.nn.ReLU())
                    layers.append(torch.nn.MaxPool1d(2))
                    current_len = current_len // 2
                    in_channels = ch
                self_inner.conv_layers = torch.nn.Sequential(*layers)
                self_inner.flatten = torch.nn.Flatten()
                flat_size = in_channels * max(current_len, 1)
                self_inner.fc1 = torch.nn.Linear(flat_size, fc_hidden_size)
                self_inner.relu = torch.nn.ReLU()
                self_inner.dropout = torch.nn.Dropout(dropout)
                self_inner.fc2 = torch.nn.Linear(fc_hidden_size, output_size)

            def forward(self_inner: Any, x: Any) -> Any:
                if x.dim() == 2:
                    x = x.unsqueeze(1)
                x = self_inner.conv_layers(x)
                x = self_inner.flatten(x)
                x = self_inner.relu(self_inner.fc1(x))
                x = self_inner.dropout(x)
                return self_inner.fc2(x)

        self._nn_module = _CNNNet()
        self._task = task

    def _get_loss_function(self) -> Any:
        torch = self._get_torch()
        task = self.params.get("task", "regression")
        if task == "classification":
            return torch.nn.CrossEntropyLoss()
        return torch.nn.MSELoss()

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        super().fit(X, y, **kwargs)

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        torch = self._get_torch()
        self._get_device()
        self._nn_module.eval()
        X_tensor = self._prepare_tensors(X)
        with torch.no_grad():
            output = self._nn_module(X_tensor)
            if self.params.get("task") == "classification":
                predictions = output.argmax(dim=1).cpu().numpy().flatten()
            else:
                predictions = output.cpu().numpy().flatten()
        return PredictionResult(predictions=predictions, model_id=self.name)
