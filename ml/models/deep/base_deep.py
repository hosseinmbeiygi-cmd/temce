from __future__ import annotations

from abc import abstractmethod
from typing import Any

import numpy as np

from core.logging import get_logger
from ml.models.base import BaseModel
from ml.types import FeatureMatrix, PredictionResult, TargetVector

logger = get_logger(__name__)


class BaseDeepModel(BaseModel):
    def __init__(self, name: str = "", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        self._device = None
        self._nn_module = None
        self._optimizer = None
        self._loss_fn = None

    def _get_torch(self) -> Any:
        try:
            import torch

            return torch
        except ImportError:
            raise ImportError("PyTorch is required for deep learning models. Install with: pip install torch")

    def _get_device(self) -> Any:
        torch = self._get_torch()
        if self._device is None:
            device_name = self.params.get("device", "cpu")
            self._device = torch.device(device_name)
        return self._device

    def _get_training_params(self) -> dict[str, Any]:
        return {
            "epochs": self.params.get("epochs", 100),
            "batch_size": self.params.get("batch_size", 32),
            "learning_rate": self.params.get("learning_rate", 1e-3),
            "patience": self.params.get("patience", 10),
            "verbose": self.params.get("verbose", False),
        }

    def _prepare_tensors(self, X: FeatureMatrix, y: TargetVector | None = None) -> Any:
        torch = self._get_torch()
        device = self._get_device()
        X_tensor = torch.tensor(X.values, dtype=torch.float32).to(device)
        if y is not None:
            y_values = y.values.astype(np.float32).reshape(-1, 1)
            y_tensor = torch.tensor(y_values, dtype=torch.float32).to(device)
            return X_tensor, y_tensor
        return X_tensor

    def _create_dataloader(self, X_tensor: Any, y_tensor: Any, batch_size: int) -> Any:
        torch = self._get_torch()
        dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
        return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        torch = self._get_torch()
        device = self._get_device()
        training_params = self._get_training_params()
        epochs = kwargs.get("epochs", training_params["epochs"])
        batch_size = kwargs.get("batch_size", training_params["batch_size"])
        learning_rate = kwargs.get("learning_rate", training_params["learning_rate"])
        patience = kwargs.get("patience", training_params["patience"])
        verbose = kwargs.get("verbose", training_params["verbose"])

        X_tensor, y_tensor = self._prepare_tensors(X, y)
        dataloader = self._create_dataloader(X_tensor, y_tensor, batch_size)

        if self._nn_module is None:
            raise RuntimeError("Neural network module not initialized. Call _build_model first.")

        self._nn_module.to(device)
        self._nn_module.train()

        self._loss_fn = self._get_loss_function()
        self._optimizer = torch.optim.Adam(self._nn_module.parameters(), lr=learning_rate)

        best_loss = float("inf")
        best_state = None
        no_improve = 0

        for epoch in range(epochs):
            epoch_loss = 0.0
            batch_count = 0
            for X_batch, y_batch in dataloader:
                self._optimizer.zero_grad()
                output = self._nn_module(X_batch)
                loss = self._loss_fn(output, y_batch)
                loss.backward()
                self._optimizer.step()
                epoch_loss += loss.item()
                batch_count += 1

            avg_loss = epoch_loss / max(batch_count, 1)
            if avg_loss < best_loss:
                best_loss = avg_loss
                best_state = {k: v.cpu().clone() for k, v in self._nn_module.state_dict().items()}
                no_improve = 0
            else:
                no_improve += 1

            if verbose and (epoch + 1) % 10 == 0:
                logger.info("Epoch %d/%d, Loss: %.6f", epoch + 1, epochs, avg_loss)

            if no_improve >= patience:
                if verbose:
                    logger.info("Early stopping at epoch %d", epoch + 1)
                break

        if best_state is not None:
            self._nn_module.load_state_dict(best_state)
            self._nn_module.to(device)

        self._is_fitted = True
        logger.info("Training completed. Best loss: %.6f", best_loss)

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        torch = self._get_torch()
        self._get_device()
        if self._nn_module is None:
            raise RuntimeError("Model not initialized. Call fit() or load() before predict().")
        self._nn_module.eval()
        X_tensor = self._prepare_tensors(X)
        with torch.no_grad():
            output = self._nn_module(X_tensor)
            predictions = output.cpu().numpy().flatten()
        return PredictionResult(predictions=predictions, model_id=self.name)

    @abstractmethod
    def _build_model(self, input_size: int, **kwargs: Any) -> None: ...

    @abstractmethod
    def _get_loss_function(self) -> Any: ...

    def save(self, path: str) -> None:
        from core.paths import validate_safe_path
        torch = self._get_torch()
        safe = validate_safe_path(path)
        safe.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_state_dict": self._nn_module.state_dict(),
            "params": self.params,
            "name": self.name,
            "is_fitted": self._is_fitted,
        }
        torch.save(payload, str(safe))
        logger.info("Model saved to %s", safe)

    def load(self, path: str) -> None:
        from core.paths import validate_safe_path
        torch = self._get_torch()
        safe = validate_safe_path(path)
        payload = torch.load(str(safe), map_location="cpu", weights_only=False)
        self.params = payload.get("params", self.params)
        self.name = payload.get("name", self.name)
        input_size = self.params.get("input_size", 1)
        self._build_model(input_size)
        self._nn_module.load_state_dict(payload["model_state_dict"])
        self._nn_module.eval()
        self._is_fitted = payload.get("is_fitted", True)
        logger.info("Model loaded from %s", safe)
