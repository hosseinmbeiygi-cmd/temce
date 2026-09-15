from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from core.logging import get_logger


@dataclass
class WorkflowContext:
    workflow_id: str
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    logger: Any = field(default_factory=lambda: get_logger("orchestration.context"))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def merge(self, other_dict: dict[str, Any]) -> None:
        self.data.update(other_dict)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def update(self, other: WorkflowContext) -> None:
        self.data.update(other.data)
        self.metadata.update(other.metadata)

    def snapshot(self) -> WorkflowContext:
        return WorkflowContext(
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            data=dict(self.data),
            metadata=dict(self.metadata),
            logger=self.logger,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "data": dict(self.data),
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        return (
            f"WorkflowContext(workflow_id={self.workflow_id!r}, "
            f"correlation_id={self.correlation_id!r}, "
            f"data_keys={list(self.data.keys())})"
        )
