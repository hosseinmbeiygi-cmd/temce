from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any


class SimulationLogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class SimulationLogEntry:
    timestamp: datetime
    level: SimulationLogLevel
    category: str
    message: str
    simulation_step: int = 0
    instrument_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class SimulationLogger:
    def __init__(
        self,
        name: str = "backtest.simulation",
        min_level: SimulationLogLevel = SimulationLogLevel.DEBUG,
        max_entries: int = 0,
    ) -> None:
        self._logger = logging.getLogger(name)
        self._entries: list[SimulationLogEntry] = []
        self._min_level = min_level
        self._max_entries = max_entries
        self._step = 0
        self._handlers: list[Callable[[SimulationLogEntry], None]] = []

    @property
    def entries(self) -> list[SimulationLogEntry]:
        return list(self._entries)

    @property
    def step(self) -> int:
        return self._step

    def set_step(self, step: int) -> None:
        self._step = step

    def add_handler(self, handler: Callable[[SimulationLogEntry], None]) -> None:
        self._handlers.append(handler)

    def _log(
        self,
        level: SimulationLogLevel,
        category: str,
        message: str,
        instrument_id: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        if level < self._min_level:
            return
        entry = SimulationLogEntry(
            timestamp=datetime.now(UTC),
            level=level,
            category=category,
            message=message,
            simulation_step=self._step,
            instrument_id=instrument_id,
            extra=extra or {},
        )
        self._entries.append(entry)
        if self._max_entries and len(self._entries) > self._max_entries:
            self._entries.pop(0)
        log_method = {
            SimulationLogLevel.DEBUG: self._logger.debug,
            SimulationLogLevel.INFO: self._logger.info,
            SimulationLogLevel.WARNING: self._logger.warning,
            SimulationLogLevel.ERROR: self._logger.error,
            SimulationLogLevel.CRITICAL: self._logger.critical,
        }.get(level, self._logger.info)
        log_method("[%s] %s%s: %s", category, instrument_id + " " if instrument_id else "", f"step_{self._step}", message)
        for handler in self._handlers:
            handler(entry)

    def debug(self, category: str, message: str, instrument_id: str = "", **extra: Any) -> None:
        self._log(SimulationLogLevel.DEBUG, category, message, instrument_id, extra)

    def info(self, category: str, message: str, instrument_id: str = "", **extra: Any) -> None:
        self._log(SimulationLogLevel.INFO, category, message, instrument_id, extra)

    def warning(self, category: str, message: str, instrument_id: str = "", **extra: Any) -> None:
        self._log(SimulationLogLevel.WARNING, category, message, instrument_id, extra)

    def error(self, category: str, message: str, instrument_id: str = "", **extra: Any) -> None:
        self._log(SimulationLogLevel.ERROR, category, message, instrument_id, extra)

    def critical(self, category: str, message: str, instrument_id: str = "", **extra: Any) -> None:
        self._log(SimulationLogLevel.CRITICAL, category, message, instrument_id, extra)

    def log_order_rejected(self, order_id: str, reason: str, instrument_id: str = "", **extra: Any) -> None:
        self.error("ORDER_REJECTED", f"Order {order_id} rejected: {reason}", instrument_id, order_id=order_id, reason=reason, **extra)

    def log_data_mismatch(self, field: str, expected: Any, actual: Any, instrument_id: str = "", **extra: Any) -> None:
        self.warning("DATA_MISMATCH", f"Field {field}: expected={expected} actual={actual}", instrument_id, field=field, expected=str(expected), actual=str(actual), **extra)

    def log_calibration_issue(self, param: str, value: float, reason: str, instrument_id: str = "", **extra: Any) -> None:
        self.warning("CALIBRATION", f"Parameter {param}={value} issue: {reason}", instrument_id, param=param, value=value, reason=reason, **extra)

    def log_fill_issue(self, order_id: str, filled_qty: int, requested_qty: int, instrument_id: str = "", **extra: Any) -> None:
        self.info("FILL", f"Order {order_id} filled {filled_qty}/{requested_qty}", instrument_id, order_id=order_id, filled=filled_qty, requested=requested_qty, **extra)

    def log_slippage(self, instrument_id: str, expected_price: float, actual_price: float, **extra: Any) -> None:
        self.debug("SLIPPAGE", f"Price slippage: expected={expected_price:.2f} actual={actual_price:.2f}", instrument_id, expected=expected_price, actual=actual_price, **extra)

    def get_errors(self) -> list[SimulationLogEntry]:
        return [e for e in self._entries if e.level >= SimulationLogLevel.ERROR]

    def get_warnings(self) -> list[SimulationLogEntry]:
        return [e for e in self._entries if e.level == SimulationLogLevel.WARNING]

    def get_by_category(self, category: str) -> list[SimulationLogEntry]:
        return [e for e in self._entries if e.category == category]

    def clear(self) -> None:
        self._entries.clear()

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        categories: dict[str, int] = {}
        for entry in self._entries:
            counts[entry.level.name] = counts.get(entry.level.name, 0) + 1
            categories[entry.category] = categories.get(entry.category, 0) + 1
        return {"counts": counts, "categories": categories, "total": len(self._entries)}
