from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("orchestration.state_machine")

DEFAULT_STATES = [
    "PENDING",
    "RUNNING",
    "STEP_COMPLETED",
    "STEP_FAILED",
    "COMPENSATING",
    "COMPLETED",
    "FAILED",
    "PAUSED",
]

DEFAULT_TRANSITIONS: dict[str, dict[str, str]] = {
    "PENDING": {"start": "RUNNING", "cancel": "FAILED"},
    "RUNNING": {
        "step_completed": "STEP_COMPLETED",
        "step_failed": "STEP_FAILED",
        "pause": "PAUSED",
        "complete": "COMPLETED",
        "fail": "FAILED",
    },
    "STEP_COMPLETED": {
        "next_step": "RUNNING",
        "complete": "COMPLETED",
        "pause": "PAUSED",
    },
    "STEP_FAILED": {
        "compensate": "COMPENSATING",
        "retry": "RUNNING",
        "fail": "FAILED",
    },
    "COMPENSATING": {
        "compensation_done": "FAILED",
        "compensation_failed": "FAILED",
    },
    "PAUSED": {"resume": "RUNNING", "cancel": "FAILED"},
    "COMPLETED": {},
    "FAILED": {"retry": "PENDING"},
}


@dataclass
class Transition:
    from_state: str
    event: str
    to_state: str
    guard: Callable[[dict[str, Any]], bool] | None = None
    action: Callable[[dict[str, Any]], Any] | None = None


@dataclass
class StateRecord:
    workflow_id: str
    state: str
    history: list[tuple[str, str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowStateMachine:
    def __init__(
        self,
        states: list[str] | None = None,
        transitions: dict[str, dict[str, str]] | None = None,
        initial_state: str = "PENDING",
    ) -> None:
        self.states_list: list[str] = states or list(DEFAULT_STATES)
        self.initial_state = initial_state
        self.transitions_map: dict[str, dict[str, str]] = {}
        self._transitions_list: list[Transition] = []
        self._records: dict[str, StateRecord] = {}
        self._listeners: list[Callable[[str, str, str, str], Any]] = []
        if transitions is not None:
            self._build_from_transition_dict(transitions)
        else:
            self._build_from_transition_dict(DEFAULT_TRANSITIONS)

    def _build_from_transition_dict(self, td: dict[str, dict[str, str]]) -> None:
        for from_state, event_map in td.items():
            if from_state not in self.transitions_map:
                self.transitions_map[from_state] = {}
            for event, to_state in event_map.items():
                self.transitions_map[from_state][event] = to_state
                self._transitions_list.append(Transition(from_state=from_state, event=event, to_state=to_state))

    def add_transition(
        self,
        from_state: str,
        event: str,
        to_state: str,
        guard: Callable[[dict[str, Any]], bool] | None = None,
        action: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        if from_state not in self.transitions_map:
            self.transitions_map[from_state] = {}
        self.transitions_map[from_state][event] = to_state
        self._transitions_list.append(
            Transition(
                from_state=from_state,
                event=event,
                to_state=to_state,
                guard=guard,
                action=action,
            )
        )

    def get_state(self, workflow_id: str) -> str | None:
        record = self._records.get(workflow_id)
        return record.state if record else None

    def get_record(self, workflow_id: str) -> StateRecord | None:
        return self._records.get(workflow_id)

    def get_history(self, workflow_id: str) -> list[tuple[str, str, str]]:
        record = self._records.get(workflow_id)
        return list(record.history) if record else []

    def register(self, workflow_id: str, initial_state: str | None = None) -> StateRecord:
        state = initial_state or self.initial_state
        record = StateRecord(workflow_id=workflow_id, state=state)
        self._records[workflow_id] = record
        logger.info(f"Registered workflow {workflow_id} in state {state}")
        return record

    def transition(
        self,
        workflow_id: str,
        event: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        record = self._records.get(workflow_id)
        if record is None:
            raise KeyError(f"Workflow {workflow_id} not registered in state machine")
        current = record.state
        event_map = self.transitions_map.get(current, {})
        to_state = event_map.get(event)
        if to_state is None:
            available = list(event_map.keys())
            raise ValueError(f"No transition from state {current!r} on event {event!r}. Available events: {available}")
        t = self._find_transition(current, event)
        if t and t.guard:
            ctx = {"workflow_id": workflow_id, "metadata": metadata or {}}
            if not t.guard(ctx):
                raise ValueError(
                    f"Guard condition failed for transition {current!r} -> {to_state!r} on event {event!r}"
                )
        if t and t.action:
            ctx = {"workflow_id": workflow_id, "metadata": metadata or {}}
            t.action(ctx)
        record.history.append((current, event, to_state))
        record.state = to_state
        if metadata:
            record.metadata.update(metadata)
        logger.info(f"Workflow {workflow_id}: {current} --({event})--> {to_state}")
        for listener in self._listeners:
            with contextlib.suppress(Exception):
                listener(workflow_id, current, event, to_state)
        return to_state

    def _find_transition(self, from_state: str, event: str) -> Transition | None:
        for t in self._transitions_list:
            if t.from_state == from_state and t.event == event:
                return t
        return None

    def can_transition(self, workflow_id: str, event: str) -> bool:
        record = self._records.get(workflow_id)
        if record is None:
            return False
        event_map = self.transitions_map.get(record.state, {})
        return event in event_map

    def available_events(self, workflow_id: str) -> list[str]:
        record = self._records.get(workflow_id)
        if record is None:
            return []
        return list(self.transitions_map.get(record.state, {}).keys())

    def on_transition(self, listener: Callable[[str, str, str, str], Any]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, str, str, str], Any]) -> None:
        self._listeners = [fn for fn in self._listeners if fn is not listener]

    def reset(self, workflow_id: str, state: str | None = None) -> None:
        target = state or self.initial_state
        record = self._records.get(workflow_id)
        if record:
            record.state = target
            record.history.clear()
        else:
            self.register(workflow_id, target)

    def __repr__(self) -> str:
        return f"WorkflowStateMachine(states={self.states_list}, registered_workflows={len(self._records)})"
