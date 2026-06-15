from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkflowContext:
    workflow_id: str
    name: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    step_name: str
    success: bool
    data: Any = None
    error: str | None = None
    duration_s: float = 0.0


@dataclass
class ExecutionPlan:
    steps: list[str]
    parallel_groups: list[list[str]] = field(default_factory=list)


@dataclass
class CompensationAction:
    step_name: str
    action: str = "rollback"
    data: dict[str, Any] = field(default_factory=dict)
