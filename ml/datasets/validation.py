from __future__ import annotations

from typing import Any

from core.result import Result


class DatasetValidator:
    def has_missing_values(self, data: Any) -> bool:
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            return bool(data.isnull().any().any())
        return False

    def has_infinite_values(self, data: Any) -> bool:
        import numpy as np

        arr = np.asarray(data)
        return bool(np.any(np.isinf(arr)))

    def validate(self, features: Any, targets: Any) -> Result[bool]:
        if self.has_missing_values(features):
            return Result.fail("Features contain missing values")
        if self.has_infinite_values(features):
            return Result.fail("Features contain infinite values")
        if len(features) != len(targets):
            return Result.fail("Features and targets length mismatch")
        return Result.ok(True)
