from __future__ import annotations

from itertools import product
from typing import Any


class ParameterGrid:
    def __init__(self) -> None:
        self._params: dict[str, list[Any]] = {}

    def add(self, name: str, values: list[Any]) -> None:
        self._params[name] = values

    def generate(self) -> list[dict[str, Any]]:
        if not self._params:
            return [{}]
        keys = list(self._params.keys())
        value_combos = product(*[self._params[k] for k in keys])
        return [dict(zip(keys, combo, strict=False)) for combo in value_combos]

    def sample(self, n: int) -> list[dict[str, Any]]:
        import random

        all_combos = self.generate()
        if len(all_combos) <= n:
            return all_combos
        return random.sample(all_combos, n)

    @property
    def param_count(self) -> int:
        return len(self._params)

    def clear(self) -> None:
        self._params.clear()
