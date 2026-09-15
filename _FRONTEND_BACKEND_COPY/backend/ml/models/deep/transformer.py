from __future__ import annotations

import math
from typing import Any

from core.logging import get_logger
from ml.models.deep.base_deep import BaseDeepModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class TransformerModel(BaseDeepModel):
    def __init__(self, name: str = "transformer", params: dict[str, Any] | None = None) -> None:
        default_params = {
            "input_size": 10,
            "d_model": 64,
            "nhead": 4,
            "num_encoder_layers": 2,
            "dim_feedforward": 256,
            "dropout": 0.1,
            "output_size": 1,
            "max_seq_len": 512,
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

        d_model = self.params.get("d_model", 64)
        nhead = self.params.get("nhead", 4)
        num_encoder_layers = self.params.get("num_encoder_layers", 2)
        dim_feedforward = self.params.get("dim_feedforward", 256)
        dropout = self.params.get("dropout", 0.1)
        output_size = self.params.get("output_size", 1)
        max_seq_len = self.params.get("max_seq_len", 512)

        class _PositionalEncoding(torch.nn.Module):
            def __init__(self_inner: Any, d_model_val: int, max_len: int = 512) -> None:
                super().__init__()
                pe = torch.zeros(max_len, d_model_val)
                position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
                div_term = torch.exp(torch.arange(0, d_model_val, 2).float() * (-math.log(10000.0) / d_model_val))
                pe[:, 0::2] = torch.sin(position * div_term)
                pe[:, 1::2] = torch.cos(position * div_term)
                pe = pe.unsqueeze(0)
                self_inner.register_buffer("pe", pe)

            def forward(self_inner: Any, x: Any) -> Any:
                seq_len = x.size(1)
                return x + self_inner.pe[:, :seq_len, :]

        class _TransformerNet(torch.nn.Module):
            def __init__(self_inner: Any) -> None:
                super().__init__()
                self_inner.input_projection = torch.nn.Linear(input_size, d_model)
                self_inner.pos_encoder = _PositionalEncoding(d_model, max_seq_len)
                encoder_layer = torch.nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=nhead,
                    dim_feedforward=dim_feedforward,
                    dropout=dropout,
                    batch_first=True,
                )
                self_inner.transformer_encoder = torch.nn.TransformerEncoder(
                    encoder_layer, num_layers=num_encoder_layers
                )
                self_inner.fc_out = torch.nn.Linear(d_model, output_size)
                self_inner.dropout = torch.nn.Dropout(dropout)

            def forward(self_inner: Any, x: Any) -> Any:
                if x.dim() == 2:
                    x = x.unsqueeze(1)
                x = self_inner.input_projection(x)
                x = self_inner.pos_encoder(x)
                x = self_inner.transformer_encoder(x)
                x = x[:, -1, :]
                x = self_inner.dropout(x)
                return self_inner.fc_out(x)

        self._nn_module = _TransformerNet()

    def _get_loss_function(self) -> Any:
        torch = self._get_torch()
        return torch.nn.MSELoss()

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        super().fit(X, y, **kwargs)

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        return super().predict(X)
