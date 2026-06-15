from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("orchestration.checkpoints")


@dataclass
class Checkpoint:
    workflow_id: str
    step_name: str
    state: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    step_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "step_name": self.step_name,
            "state": self.state,
            "created_at": self.created_at,
            "step_index": self.step_index,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"Checkpoint(workflow_id={self.workflow_id!r}, step_name={self.step_name!r}, created_at={self.created_at})"
        )


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._store: dict[str, list[Checkpoint]] = {}

    async def save(self, checkpoint: Checkpoint) -> None:
        wf_id = checkpoint.workflow_id
        if wf_id not in self._store:
            self._store[wf_id] = []
        self._store[wf_id].append(checkpoint)
        logger.info(f"Saved checkpoint for workflow {wf_id} at step {checkpoint.step_name}")

    async def load(self, workflow_id: str) -> Checkpoint | None:
        checkpoints = self._store.get(workflow_id, [])
        if not checkpoints:
            return None
        return checkpoints[-1]

    async def list_checkpoints(self, workflow_id: str) -> list[Checkpoint]:
        return list(self._store.get(workflow_id, []))

    async def delete(self, workflow_id: str) -> bool:
        if workflow_id in self._store:
            del self._store[workflow_id]
            logger.info(f"Deleted checkpoints for workflow {workflow_id}")
            return True
        return False

    async def delete_step(self, workflow_id: str, step_name: str) -> bool:
        if workflow_id not in self._store:
            return False
        before = len(self._store[workflow_id])
        self._store[workflow_id] = [c for c in self._store[workflow_id] if c.step_name != step_name]
        after = len(self._store[workflow_id])
        return before != after

    def count(self, workflow_id: str) -> int:
        return len(self._store.get(workflow_id, []))

    def clear(self) -> None:
        self._store.clear()


class CheckpointManager:
    def __init__(self, store: InMemoryCheckpointStore | None = None) -> None:
        self.store = store or InMemoryCheckpointStore()

    async def save_checkpoint(
        self,
        workflow_id: str,
        step_name: str,
        state: dict[str, Any],
        step_index: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            workflow_id=workflow_id,
            step_name=step_name,
            state=dict(state),
            step_index=step_index,
            metadata=metadata or {},
        )
        await self.store.save(checkpoint)
        return checkpoint

    async def load_checkpoint(self, workflow_id: str) -> Checkpoint | None:
        return await self.store.load(workflow_id)

    async def list_checkpoints(self, workflow_id: str) -> list[Checkpoint]:
        return await self.store.list_checkpoints(workflow_id)

    async def get_latest_checkpoint(self, workflow_id: str) -> Checkpoint | None:
        return await self.store.load(workflow_id)

    async def get_checkpoint_before_step(self, workflow_id: str, step_name: str) -> Checkpoint | None:
        checkpoints = await self.store.list_checkpoints(workflow_id)
        for c in reversed(checkpoints):
            if c.step_name != step_name:
                return c
        return None

    async def has_checkpoints(self, workflow_id: str) -> bool:
        checkpoints = await self.store.list_checkpoints(workflow_id)
        return len(checkpoints) > 0

    async def clear_checkpoints(self, workflow_id: str) -> bool:
        return await self.store.delete(workflow_id)

    async def save_workflow_state(
        self,
        workflow_id: str,
        current_step: str,
        workflow_data: dict[str, Any],
        step_index: int = 0,
    ) -> Checkpoint:
        state = {
            "current_step": current_step,
            "workflow_data": workflow_data,
        }
        return await self.save_checkpoint(
            workflow_id=workflow_id,
            step_name=current_step,
            state=state,
            step_index=step_index,
        )
