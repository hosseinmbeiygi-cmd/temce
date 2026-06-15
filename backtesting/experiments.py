from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class BacktestExperiment:
    def __init__(self) -> None:
        self._runs: list[dict[str, Any]] = []

    def start_run(self, strategy_name: str, params: dict[str, Any]) -> str:
        run_id = f"bt_{strategy_name}_{datetime.utcnow().timestamp()}"
        self._runs.append(
            {
                "run_id": run_id,
                "strategy": strategy_name,
                "params": params,
                "status": "running",
                "started_at": datetime.utcnow().isoformat(),
            }
        )
        return run_id

    def end_run(self, run_id: str, result: Any) -> None:
        for run in self._runs:
            if run["run_id"] == run_id:
                run["status"] = "completed"
                run["result"] = result
                run["finished_at"] = datetime.utcnow().isoformat()
                break

    def compare(self, run_ids: list[str]) -> list[dict[str, Any]]:
        return [r for r in self._runs if r["run_id"] in run_ids]
