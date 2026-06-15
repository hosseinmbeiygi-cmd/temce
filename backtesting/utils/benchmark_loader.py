from __future__ import annotations


class BenchmarkLoader:
    def __init__(self) -> None:
        self._data: dict[str, list[float]] = {}

    def load_from_csv(self, filepath: str, column: str = "close") -> list[float]:
        import csv

        values: list[float] = []
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    values.append(float(row[column]))
                except (KeyError, ValueError):
                    continue
        self._data[filepath] = values
        return values

    def load_from_list(self, name: str, values: list[float]) -> None:
        self._data[name] = values

    def get(self, name: str) -> list[float]:
        return self._data.get(name, [])

    def compute_returns(self, name: str) -> list[float]:
        values = self.get(name)
        if len(values) < 2:
            return []
        return [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values))]

    def clear(self) -> None:
        self._data.clear()
