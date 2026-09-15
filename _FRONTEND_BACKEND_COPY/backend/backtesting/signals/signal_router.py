from __future__ import annotations

from typing import Any

from backtesting.signals.signal_models import Signal, SignalModel


class SignalRouter:
    def __init__(self) -> None:
        self._routes: dict[str, list[SignalModel]] = {}

    def register(self, instrument_id: str, model: SignalModel) -> None:
        self._routes.setdefault(instrument_id, []).append(model)

    def unregister(self, instrument_id: str, model: SignalModel) -> None:
        models = self._routes.get(instrument_id, [])
        if model in models:
            models.remove(model)

    def route(self, instrument_id: str, data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        for model in self._routes.get(instrument_id, []):
            signal = model.generate(data)
            if signal:
                signals.append(signal)
        return signals

    def route_all(self, data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        for instrument_id in self._routes:
            signals.extend(self.route(instrument_id, data))
        return signals

    def clear(self) -> None:
        self._routes.clear()
