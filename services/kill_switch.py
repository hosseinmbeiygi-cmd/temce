"""Kill Switch — فاز 1-8."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class KillState:
    killed: bool = False
    by: str = ""
    reason: str = ""
    at: float = 0.0


class KillSwitch:
    def __init__(self) -> None:
        self._state = KillState()

    def is_killed(self) -> bool:
        return self._state.killed

    def kill(self, by: str, reason: str) -> None:
        # فقط مالک ریسک باید صدا بزند — چک RBAC در لایه API انجام می‌شود
        self._state = KillState(killed=True, by=by, reason=reason, at=time.time())

    def revive(self, by: str) -> None:
        # احیاء نیز فقط مالک ریسک
        self._state = KillState(killed=False, by=by, reason="revived", at=time.time())

    def status(self) -> KillState:
        return self._state


kill_switch = KillSwitch()
