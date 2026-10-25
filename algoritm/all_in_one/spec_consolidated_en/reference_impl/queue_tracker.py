"""Observed-only queue tracker for one resting order (no invented decay parameters).

Conservative: queue ahead shrinks only through observed trades and observed cancellations ahead.
Without queue data on a locked side, entry is `unfillable`. Output is UNCALIBRATED until validated
against own order logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class QueueError(RuntimeError):
    pass


def locked_entry_status(side_is_locked: bool, has_queue_data: bool) -> str:
    if side_is_locked and not has_queue_data:
        return "unfillable"
    return "ok"


@dataclass
class QueueTracker:
    qty: int
    ahead: int
    submit_ts: float
    filled: int = 0
    calibrated: bool = False
    log: list = field(default_factory=list)

    def _check(self, ts: float) -> None:
        if ts < self.submit_ts:
            raise QueueError("event before submit")

    def on_cancel_ahead(self, ts: float, volume: int) -> None:
        self._check(ts)
        self.ahead = max(0, self.ahead - max(0, volume))

    def on_trade(self, ts: float, volume: int) -> int:
        """Trade volume executed at our price level; returns quantity filled to us by this event."""
        self._check(ts)
        v = max(0, volume)
        eaten = min(self.ahead, v)
        self.ahead -= eaten
        v -= eaten
        fill = min(self.qty - self.filled, v)
        self.filled += fill
        self.log.append((ts, volume, fill))
        return fill

    @property
    def status(self) -> str:
        if self.filled >= self.qty:
            return "FILLED"
        return "PARTIAL" if self.filled > 0 else "QUEUED"
