"""precompute/config.py — isolated config for the precompute scope.

Reads only process env (no cross-module import). Mirrors the keys the api
scope already relies on so both sides agree on the contract without sharing
code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PrecomputeConfig:
    redis_url: str = "redis://localhost:6379/0"
    # Hot-layer result TTL — same freshness window the api uses for STALE checks.
    result_ttl_seconds: int = 3600
    # Redis pub/sub channel precompute publishes contract events on. The api
    # ws_manager (api scope) subscribes to this; precompute never imports it.
    events_channel: str = "precompute:events"
    # Hot-layer per-symbol result key (read by api/routers/precompute_router).
    result_key_template: str = "precompute:result:{symbol}"
    # Priority queue names (consumed by a worker with -Q queue_group_a,b,c).
    queue_a: str = "queue_group_a"
    queue_b: str = "queue_group_b"
    queue_c: str = "queue_group_c"
    # How many symbols between progress broadcasts within a group.
    progress_every: int = 5


def load_config() -> PrecomputeConfig:
    return PrecomputeConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        result_ttl_seconds=int(os.getenv("PRECOMPUTE_RESULT_TTL", "3600")),
        events_channel=os.getenv("PRECOMPUTE_EVENTS_CHANNEL", "precompute:events"),
    )
