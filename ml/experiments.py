from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.time import utc_now_naive

logger = get_logger(__name__)


class ExperimentTracker:
    def __init__(self) -> None:
        self._experiments: list[dict[str, Any]] = []

    def start_run(self, experiment_name: str, params: dict[str, Any] | None = None) -> str:
        run_id = f"{experiment_name}_{utc_now_naive().timestamp()}"
        self._experiments.append(
            {
                "run_id": run_id,
                "name": experiment_name,
                "params": params or {},
                "metrics": {},
                "status": "running",
                "started_at": utc_now_naive().isoformat(),
            }
        )
        logger.info("Started experiment run: %s", run_id)
        return run_id

    def log_metric(self, run_id: str, key: str, value: float) -> None:
        for exp in self._experiments:
            if exp["run_id"] == run_id:
                exp["metrics"][key] = value
                break

    def end_run(self, run_id: str, status: str = "completed") -> None:
        for exp in self._experiments:
            if exp["run_id"] == run_id:
                exp["status"] = status
                exp["finished_at"] = utc_now_naive().isoformat()
                break

    def get_runs(self, experiment_name: str | None = None) -> list[dict[str, Any]]:
        if experiment_name:
            return [e for e in self._experiments if e["name"] == experiment_name]
        return list(self._experiments)
