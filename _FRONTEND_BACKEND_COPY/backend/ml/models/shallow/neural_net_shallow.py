from __future__ import annotations

from typing import Any


class ShallowNeuralNet:
    def __init__(self, hidden_size: int = 64, learning_rate: float = 0.01) -> None:
        self.hidden_size = hidden_size
        self.learning_rate = learning_rate
        self._model = None

    def fit(self, X: Any, y: Any) -> None:
        from sklearn.neural_network import MLPClassifier

        self._model = MLPClassifier(
            hidden_layer_sizes=(self.hidden_size,),
            learning_rate_init=self.learning_rate,
            max_iter=500,
        )
        self._model.fit(X, y)

    def predict(self, X: Any) -> Any:
        if self._model is None:
            raise RuntimeError("Model not fitted")
        return self._model.predict(X)
