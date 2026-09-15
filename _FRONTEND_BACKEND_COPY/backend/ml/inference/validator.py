from __future__ import annotations

from typing import Any


class PredictionValidator:
    def validate_input(self, data: Any, expected_features: list[str] | None = None) -> bool:
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            if expected_features and not all(f in data.columns for f in expected_features):
                return False
        return True

    def validate_output(self, prediction: Any) -> bool:
        import numpy as np

        if np.any(np.isnan(prediction)):
            return False
        return not np.any(np.isinf(prediction))
