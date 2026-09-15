from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class StepStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    COMPENSATED = "COMPENSATED"


@dataclass
class StepResult:
    step_name: str
    success: bool
    output: Any = None
    error: str | None = None
    status: StepStatus = StepStatus.PENDING
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    workflow_id: str
    current_step: str | None = None
    results: list[StepResult] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Any | None = None
    completed_at: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: StepResult) -> None:
        self.results.append(result)

    def last_result(self) -> StepResult | None:
        return self.results[-1] if self.results else None

    def failed_results(self) -> list[StepResult]:
        return [r for r in self.results if not r.success]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "current_step": self.current_step,
            "status": self.status.value,
            "results": [
                {
                    "step_name": r.step_name,
                    "success": r.success,
                    "error": r.error,
                    "status": r.status.value,
                }
                for r in self.results
            ],
        }


class Step(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def execute(self, context: Any) -> Any: ...

    @abstractmethod
    async def compensate(self, context: Any) -> None: ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class Workflow(ABC):
    def __init__(self, workflow_id: str, name: str, steps: list[Step] | None = None) -> None:
        self.id = workflow_id
        self.name = name
        self.steps: list[Step] = steps or []
        self.status: WorkflowStatus = WorkflowStatus.PENDING

    @abstractmethod
    async def execute(self, context: Any) -> WorkflowState: ...

    def add_step(self, step: Step) -> None:
        self.steps.append(step)

    def get_step(self, name: str) -> Step | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r}, name={self.name!r}, steps={len(self.steps)})"
