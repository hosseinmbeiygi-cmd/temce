"""Redis-backed state documents shared by every API worker.

``uvicorn --workers N`` forks N independent processes: every module-level
dict has its own copy per worker. State that operators expect to see once
(cron status, alert cooldowns, enable/disable toggles) therefore has to live
in Redis, with each process keeping the *same* dict object as a local mirror
so request handlers and background tasks stay synchronous.

Writes go through :func:`state_transaction`, which takes a distributed lock,
reloads both documents, lets the caller mutate the mirrors and persists them
before releasing the lock. That turns a read-modify-write cycle such as
``run_count += 1`` or ``enabled = not enabled`` into a compare-free critical
section: two workers can never overwrite each other's update.

Without Redis the transaction degrades to a process-local one (the mirrors
are still updated, they are simply not shared) and every degradation is
logged at warning level.
"""

from __future__ import annotations

import contextlib
import copy
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Iterable, Mapping
from typing import Any

from core.cache import CacheService, get_cache
from core.logging import get_logger

logger = get_logger(__name__)

#: Minimum gap between repeated "Redis unavailable" warnings for one document,
#: so a down Redis does not flood the log on every cron tick.
_WARN_THROTTLE_S = 60.0


class RedisStateDocument:
    """One JSON document in Redis with an in-process dict mirror.

    ``mirror`` is the module-level dict that the rest of the application
    reads directly; keeping the same object means callers never need to
    await a load before reading a field. ``defaults`` is the canonical
    schema: keys absent from the persisted payload keep their default, and
    keys unknown to the schema are ignored (forward compatibility after a
    downgrade).

    ``history_key`` names a bounded list field (converted to a ``deque`` in
    the mirror); only the newest ``history_limit`` entries are retained.
    """

    def __init__(
        self,
        mirror: dict[str, Any],
        *,
        key: str,
        defaults: Mapping[str, Any],
        history_key: str | None = None,
        history_limit: int = 100,
        cache: CacheService | None = None,
    ) -> None:
        self._mirror = mirror
        self._key = key
        self._defaults = dict(defaults)
        self._history_key = history_key
        self._history_limit = history_limit
        self._cache = cache
        self._warned_at = 0.0

    @property
    def key(self) -> str:
        return self._key

    def _cache_service(self) -> CacheService:
        return self._cache if self._cache is not None else get_cache()

    def _warn(self, message: str, *args: Any) -> None:
        now = time.monotonic()
        if now - self._warned_at < _WARN_THROTTLE_S:
            logger.debug(message, *args)
            return
        self._warned_at = now
        logger.warning(message, *args)

    # ── mirror helpers ────────────────────────────────────────────────

    def defaults(self) -> dict[str, Any]:
        """Fresh copy of the schema, including an empty history deque."""
        state: dict[str, Any] = {name: copy.deepcopy(value) for name, value in self._defaults.items()}
        if self._history_key is not None:
            state[self._history_key] = deque(maxlen=self._history_limit)
        return state

    def reset(self) -> None:
        """Restore the mirror to its defaults (tests and first boot)."""
        self._apply(self.defaults())

    def snapshot(self) -> dict[str, Any]:
        """JSON-safe copy of the mirror; deques are serialised as lists."""
        return {
            name: (list(value) if isinstance(value, deque) else copy.deepcopy(value))
            for name, value in self._mirror.items()
        }

    def _apply(self, state: Mapping[str, Any]) -> None:
        for name, value in state.items():
            existing = self._mirror.get(name)
            if name == self._history_key and isinstance(existing, deque) and isinstance(value, deque):
                # Mutate in place: other coroutines may hold the deque.
                existing.clear()
                existing.extend(value)
                continue
            self._mirror[name] = value

    # ── Redis I/O ─────────────────────────────────────────────────────

    async def load(self) -> bool:
        """Overlay the persisted document onto the mirror.

        Returns True when the shared store was consulted (the key may still
        be missing on first boot), False when Redis is unavailable and the
        mirror keeps this worker's own state.
        """
        cache = self._cache_service()
        try:
            raw = await cache.get(self._key)
        except Exception:
            logger.warning("Shared state %s could not be read", self._key, exc_info=True)
            return False
        if raw is None:
            if not cache.is_connected:
                self._warn("Shared state %s unavailable (Redis down) — worker-local state only", self._key)
                return False
            return True
        if not isinstance(raw, Mapping):
            logger.warning("Shared state %s has an unexpected payload type %s — ignored", self._key, type(raw).__name__)
            return False

        state: dict[str, Any] = {
            name: copy.deepcopy(raw.get(name, default)) for name, default in self._defaults.items()
        }
        if self._history_key is not None:
            entries = raw.get(self._history_key)
            if not isinstance(entries, (list, tuple)):
                entries = []
            state[self._history_key] = deque(list(entries)[-self._history_limit :], maxlen=self._history_limit)
        self._apply(state)
        return True

    async def save(self) -> bool:
        """Persist the mirror. Returns True only when Redis accepted it."""
        cache = self._cache_service()
        try:
            saved = await cache.set_persistent(self._key, self.snapshot())
        except Exception:
            logger.warning("Shared state %s could not be written", self._key, exc_info=True)
            return False
        if not saved:
            self._warn(
                "Shared state %s not persisted (Redis unavailable) — changes stay in this worker", self._key
            )
        return bool(saved)


_state_locker: Any = None


def _get_locker(default_ttl: float) -> Any:
    """Process-wide lock instance.

    One shared instance matters for the in-memory fallback: its dict is the
    lock table, so separate instances would not see each other's locks.
    """
    global _state_locker
    if _state_locker is None:
        from jobs.locking import JobLocking

        _state_locker = JobLocking(default_ttl=default_ttl)
    return _state_locker


@contextlib.asynccontextmanager
async def state_transaction(
    documents: Iterable[RedisStateDocument],
    *,
    lock_key: str,
    wait_seconds: float = 5.0,
    lock_ttl: float = 30.0,
) -> AsyncIterator[None]:
    """Run a load → mutate → save cycle under a distributed lock.

    Every worker applies its mutation to the freshly loaded state, so
    concurrent writers (cron tick, admin toggle, manual run) compose instead
    of overwriting each other. Do not await slow work (HTTP, model training)
    inside the block: the lock guards the state update, not the job.
    """
    docs = tuple(documents)
    locker = _get_locker(lock_ttl)
    owner = f"state:{uuid.uuid4().hex}"
    acquired = await locker.acquire(lock_key, owner, lock_ttl, wait=wait_seconds)
    if not acquired:
        logger.error(
            "Shared state lock %s not acquired within %.1fs — committing unguarded", lock_key, wait_seconds
        )
    try:
        for doc in docs:
            await doc.load()
        yield
        for doc in docs:
            await doc.save()
    finally:
        if acquired:
            with contextlib.suppress(Exception):
                await locker.release(lock_key, owner)


def reset_state_locker() -> None:
    """Drop the shared lock instance (tests only)."""
    global _state_locker
    _state_locker = None
