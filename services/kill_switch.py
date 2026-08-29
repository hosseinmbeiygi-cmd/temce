"""System-wide Kill Switch (سند v5.0 §15.3 + §19.3 + §14.2 RBAC).

A singleton, process-wide kill switch that halts *all* new signal issuance
across markets when activated by the «مدیر» role. Existing positions are
not closed (سند §19.3: «فعال‌سازی بلافاصله صدور سیگنال جدید را متوقف می‌کند
اما موقعیت‌های باز موجود را نمیبندد»).

State is held in Redis (when available) so signal factory, jobs and HTTP
workers all observe the same flag. Falls back to in-process memory when
Redis is unreachable — still thread-safe via an asyncio Lock.

The kill switch also records activation/deactivation events in an
append-only history (90-day retention per سند §15.1) so post-incident
review (سند §19.3 step 3) can trace the timeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Redis keys — single source of truth across processes
_REDIS_KEY = "system:kill_switch:state"
_REDIS_HISTORY_PREFIX = "system:kill_switch:history:"

# In-process fallback when Redis is unreachable
_LOCAL_STATE: dict[str, Any] = {"killed": False, "by": "", "reason": "", "at": 0.0}
_LOCAL_LOCK = asyncio.Lock()


@dataclass
class KillState:
    killed: bool = False
    by: str = ""
    reason: str = ""
    at: float = 0.0


@dataclass
class KillSwitchEvent:
    event: str  # "activated" | "deactivated"
    actor: str
    reason: str
    timestamp: float = field(default_factory=time.time)


class TradingHaltedError(RuntimeError):
    """Domain error raised by the signal factory when the kill switch is
    engaged. Kept separate from HTTP so non-HTTP callers (jobs, batch
    workers) can catch a single domain error.
    """


class KillSwitch:
    """Singleton. The first instance is canonical; later ones share state
    via Redis (or the in-process fallback). Activate/deactivate are async
    so they can hit Redis; the sync ``is_killed()`` reads the in-process
    mirror for the hot path.
    """

    _instance: KillSwitch | None = None

    def __new__(cls) -> KillSwitch:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def reset_singleton() -> None:
        """Test helper — clear the singleton so a new one is created."""
        KillSwitch._instance = None

    # ── Async Redis-backed persistence (preferred) ─────────────────────

    async def _read_redis(self) -> KillState | None:
        try:
            from core.cache_manager import get_cache_manager

            cm = get_cache_manager()
            raw = await cm.get(_REDIS_KEY)
        except Exception as exc:
            logger.debug("KillSwitch Redis read failed: %s", exc)
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return KillState(
                killed=bool(data.get("killed")),
                by=data.get("by", ""),
                reason=data.get("reason", ""),
                at=float(data.get("at", 0.0)),
            )
        except (TypeError, ValueError):
            return None

    async def _write_redis(self, state: KillState) -> None:
        try:
            from core.cache_manager import get_cache_manager

            cm = get_cache_manager()
            await cm.set(
                _REDIS_KEY,
                json.dumps(
                    {
                        "killed": state.killed,
                        "by": state.by,
                        "reason": state.reason,
                        "at": state.at,
                    }
                ),
                ttl=None,
            )
        except Exception as exc:
            logger.debug("KillSwitch Redis write failed: %s", exc)

    async def _append_event(self, event: KillSwitchEvent) -> None:
        try:
            from core.cache_manager import get_cache_manager

            cm = get_cache_manager()
            await cm.set(
                f"{_REDIS_HISTORY_PREFIX}{event.timestamp}",
                json.dumps(
                    {
                        "event": event.event,
                        "actor": event.actor,
                        "reason": event.reason,
                        "timestamp": event.timestamp,
                    }
                ),
                ttl=90 * 24 * 3600,  # 90-day retention (سند §15.1)
            )
        except Exception:
            pass
        logger.warning("KillSwitch %s by %s: %s", event.event, event.actor, event.reason)

    # ── Public API ────────────────────────────────────────────────────

    def is_killed(self) -> bool:
        """Sync read of the in-process mirror. Hot path."""
        return _LOCAL_STATE["killed"]

    def status(self) -> KillState:
        return KillState(
            killed=_LOCAL_STATE["killed"],
            by=_LOCAL_STATE["by"],
            reason=_LOCAL_STATE["reason"],
            at=_LOCAL_STATE["at"],
        )

    async def refresh(self) -> KillState:
        """Read fresh state from Redis and update the in-process mirror.
        Call once on app startup so workers see the latest flag.
        """
        state = await self._read_redis()
        if state is not None:
            async with _LOCAL_LOCK:
                _LOCAL_STATE.update(
                    {
                        "killed": state.killed,
                        "by": state.by,
                        "reason": state.reason,
                        "at": state.at,
                    }
                )
        return self.status()

    async def kill(self, by: str, reason: str) -> KillState:
        """Activate the kill switch. سند §19.3: only role «مدیر» allowed —
        RBAC is enforced at the API boundary."""
        state = KillState(killed=True, by=by, reason=reason, at=time.time())
        await self._write_redis(state)
        async with _LOCAL_LOCK:
            _LOCAL_STATE.update({"killed": True, "by": by, "reason": reason, "at": state.at})
        await self._append_event(KillSwitchEvent(event="activated", actor=by, reason=reason))
        return state

    async def revive(self, by: str) -> KillState:
        """Deactivate. سند §19.3 step 3: requires joint approval of «تیم فنی»
        and «کارشناس کمّی». We log the actor and reason; the API layer is
        responsible for enforcing dual approval.
        """
        state = KillState(killed=False, by=by, reason="revived", at=time.time())
        await self._write_redis(state)
        async with _LOCAL_LOCK:
            _LOCAL_STATE.update({"killed": False, "by": by, "reason": "revived", "at": state.at})
        await self._append_event(KillSwitchEvent(event="deactivated", actor=by, reason="revived"))
        return state


# Module-level singleton — preserved across imports
kill_switch = KillSwitch()


def assert_not_killed() -> None:
    """Sync guard for the signal factory hot path. Raises
    ``TradingHaltedError`` if the kill switch is engaged.
    """
    if kill_switch.is_killed():
        raise TradingHaltedError(f"Trading is halted by {kill_switch.status().by}: {kill_switch.status().reason}")
