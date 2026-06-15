from __future__ import annotations

from typing import Any

from core.logging import get_logger
from ml.models.deep.base_deep import BaseDeepModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class GRUModel(BaseDeepModel):
    def __init__(self, name: str = "gru", params: dict[str, Any] | None = None) -> None:
        default_params = {
            "input_size": 10,
            "hidden_size": 64,
            "num_layers": 2,
            "output_size": 1,
            "dropout": 0.1,
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

        hidden_size = self.params.get("hidden_size", 64)
        num_layers = self.params.get("num_layers", 2)
        output_size = self.params.get("output_size", 1)
        dropout = self.params.get("dropout", 0.1)

        class _GRUNet(torch.nn.Module):
            def __init__(self_inner: Any) -> None:
                super().__init__()
                self_inner.gru = torch.nn.GRU(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0.0,
                )
                self_inner.fc = torch.nn.Linear(hidden_size, output_size)

            def forward(self_inner: Any, x: Any) -> Any:
                if x.dim() == 2:
                    x = x.unsqueeze(1)
                gru_out, _ = self_inner.gru(x)
                last_hidden = gru_out[:, -1, :]
                return self_inner.fc(last_hidden)

        self._nn_module = _GRUNet()

    def _get_loss_function(self) -> Any:
        torch = self._get_torch()
        return torch.nn.MSELoss()

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        super().fit(X, y, **kwargs)

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        return super().predict(X)
