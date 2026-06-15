from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class BacktestScenario:
    def __init__(self, name: str = "") -> None:
        self.name = name

    def get_config(self) -> dict[str, Any]:
        return {
            "strategy": self.name,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "capital": 1_000_000_000,
        }


class DailyRebalanceScenario(BacktestScenario):
    def get_config(self) -> dict[str, Any]:
        return {**super().get_config(), "rebalance_frequency": "daily"}


class EventDrivenScenario(BacktestScenario):
    def get_config(self) -> dict[str, Any]:
        return {**super().get_config(), "execution": "event_driven"}
