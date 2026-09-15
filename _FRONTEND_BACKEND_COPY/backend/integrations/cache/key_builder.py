from __future__ import annotations

from typing import Any


class KeyBuilder:
    def __init__(self, prefix: str = "imp", separator: str = ":"):
        self._prefix = prefix
        self._separator = separator

    def build(self, *parts: str, **tags: str) -> str:
        segments = [self._prefix]
        segments.extend(str(p) for p in parts if p)
        suffix = self._separator.join(f"{k}={v}" for k, v in sorted(tags.items()))
        if suffix:
            segments.append(suffix)
        return self._separator.join(segments)

    def quote_key(self, instrument_id: str, timeframe: str = "1d") -> str:
        return self.build("quotes", instrument_id, timeframe)

    def signal_key(self, instrument_id: str, strategy: str = "") -> str:
        return self.build("signals", instrument_id, strategy) if strategy else self.build("signals", instrument_id)

    def instrument_key(self, instrument_id: str) -> str:
        return self.build("instruments", instrument_id)

    def recommendation_key(self, instrument_id: str) -> str:
        return self.build("recommendations", instrument_id)

    def analysis_key(self, instrument_id: str, analysis_type: str) -> str:
        return self.build("analysis", instrument_id, analysis_type)

    def lock_key(self, resource: str) -> str:
        return self.build("locks", resource)

    def job_key(self, job_id: str) -> str:
        return self.build("jobs", job_id)

    def pattern(self, *parts: str) -> str:
        return self.build(*parts) + "*"

    def __call__(self, *parts: str, **tags: str) -> str:
        return self.build(*parts, **tags)

    def serialize(self, data: dict[str, Any]) -> str:
        import json

        return json.dumps(data, ensure_ascii=False, default=str)
