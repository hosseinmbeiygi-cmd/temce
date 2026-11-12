from __future__ import annotations

from typing import Any


class SVMModel:
    def __init__(self, kernel: str = "rbf", C: float = 1.0) -> None:  # noqa: N803
        self.kernel = kernel
        self.C = C
        self._model = None

    def fit(self, X: Any, y: Any) -> None:  # noqa: N803
        from sklearn.svm import SVC

        self._model = SVC(kernel=self.kernel, C=self.C)
        self._model.fit(X, y)

    def predict(self, X: Any) -> Any:  # noqa: N803
        if self._model is None:
            raise RuntimeError("Model not fitted")
        return self._model.predict(X)
