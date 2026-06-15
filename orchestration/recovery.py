from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from orchestration.checkpoints import Checkpoint, CheckpointManager

logger = get_logger("orchestration.recovery")


@dataclass
class RecoveryAction:
    action_type: str
    step_name: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "step_name": self.step_name,
            "description": self.description,
            "params": self.params,
            "priority": self.priority,
        }


@dataclass
class RecoveryPlan:
    workflow_id: str
    actions: list[RecoveryAction] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class RecoveryManager:
    def __init__(
        self,
        checkpoint_manager: CheckpointManager | None = None,
    ) -> None:
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self._recovery_history: dict[str, list[RecoveryAction]] = {}

    async def recover_from_failure(
        self,
        workflow_id: str,
        error: Exception,
        context: Any | None = None,
    ) -> RecoveryPlan:
        logger.info(f"Recovering workflow {workflow_id} from failure: {error}")
        checkpoint = await self.checkpoint_manager.load_checkpoint(workflow_id)
        if checkpoint is None:
            logger.warning(f"No checkpoint found for workflow {workflow_id}")
            return RecoveryPlan(workflow_id=workflow_id, metadata={"error": str(error)})
        plan = RecoveryPlan(
            workflow_id=workflow_id,
            metadata={
                "error": str(error),
                "from_checkpoint": checkpoint.step_name,
            },
        )
        action = RecoveryAction(
            action_type="replay_from_checkpoint",
            step_name=checkpoint.step_name,
            description=f"Replay workflow from checkpoint at step {checkpoint.step_name}",
            params={"checkpoint": checkpoint.to_dict()},
            priority=1,
        )
        plan.actions.append(action)
        if self._should_compensate(error):
            comp_action = RecoveryAction(
                action_type="compensate",
                step_name=checkpoint.step_name,
                description=f"Compensate up to step {checkpoint.step_name}",
                params={"checkpoint": checkpoint.to_dict()},
                priority=0,
            )
            plan.actions.append(comp_action)
        if self._should_restart(error):
            restart_action = RecoveryAction(
                action_type="restart",
                step_name="",
                description="Restart workflow from the beginning",
                params={},
                priority=2,
            )
            plan.actions.append(restart_action)
        plan.actions.sort(key=lambda a: a.priority)
        if workflow_id not in self._recovery_history:
            self._recovery_history[workflow_id] = []
        self._recovery_history[workflow_id].extend(plan.actions)
        logger.info(f"Created recovery plan for workflow {workflow_id} with {len(plan.actions)} actions")
        return plan

    async def replay_from_checkpoint(
        self,
        workflow_id: str,
        checkpoint: Checkpoint | None = None,
    ) -> Checkpoint | None:
        if checkpoint is None:
            checkpoint = await self.checkpoint_manager.load_checkpoint(workflow_id)
        if checkpoint is None:
            logger.warning(f"No checkpoint available for replay of workflow {workflow_id}")
            return None
        logger.info(f"Replaying workflow {workflow_id} from checkpoint at step {checkpoint.step_name}")
        await self.checkpoint_manager.save_checkpoint(
            workflow_id=workflow_id,
            step_name=checkpoint.step_name,
            state=checkpoint.state,
            step_index=checkpoint.step_index,
            metadata={"replayed_from": checkpoint.created_at},
        )
        return checkpoint

    def get_recovery_plan(self, workflow_id: str) -> RecoveryPlan | None:
        history = self._recovery_history.get(workflow_id, [])
        if not history:
            return None
        plan = RecoveryPlan(
            workflow_id=workflow_id,
            actions=list(history),
            metadata={"source": "history"},
        )
        return plan

    def get_recovery_history(self, workflow_id: str) -> list[RecoveryAction]:
        return list(self._recovery_history.get(workflow_id, []))

    def clear_history(self, workflow_id: str) -> None:
        self._recovery_history.pop(workflow_id, None)

    def _should_compensate(self, error: Exception) -> bool:
        if isinstance(error, (TimeoutError, ConnectionError, OSError)):
            return True
        error_str = str(error).lower()
        keywords = ["timeout", "connection", "network", "transient", "deadlock"]
        return any(kw in error_str for kw in keywords)

    def _should_restart(self, error: Exception) -> bool:
        if isinstance(error, MemoryError, SystemError):
            return True
        error_str = str(error).lower()
        keywords = ["out of memory", "corrupt", "fatal"]
        return any(kw in error_str for kw in keywords)

    async def execute_recovery(
        self,
        workflow_id: str,
        plan: RecoveryPlan,
        workflow_runner: Any | None = None,
        context: Any | None = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for action in sorted(plan.actions, key=lambda a: a.priority):
            logger.info(f"Executing recovery action: {action.action_type} for step {action.step_name}")
            if action.action_type == "replay_from_checkpoint":
                cp = action.params.get("checkpoint")
                checkpoint_obj = None
                if cp:
                    checkpoint_obj = Checkpoint(
                        workflow_id=cp["workflow_id"],
                        step_name=cp["step_name"],
                        state=cp["state"],
                        created_at=cp.get("created_at", 0),
                        step_index=cp.get("step_index", 0),
                    )
                result = await self.replay_from_checkpoint(workflow_id, checkpoint_obj)
                results[action.action_type] = result is not None
            elif action.action_type == "compensate" or action.action_type == "restart":
                results[action.action_type] = True
            else:
                results[action.action_type] = False
                logger.warning(f"Unknown recovery action type: {action.action_type}")
        return results
