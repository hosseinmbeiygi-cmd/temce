"""Phase 1 — bounded retry for snapshot_ready events.

When ``_snapshot_message()`` fails (e.g. transient Redis error), the hub must
retry up to 3 times with backoff before giving up — not on the first failure.

RED: hub retries 0 times (gives up after 1 attempt from pubsub handler).
GREEN: hub retries up to 2 more times (3 total), succeeds on 3rd if available.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_desk.ws_hub import GOLD_WS_CHANNEL, GoldWebSocketHub

AS_OF = "2026-10-25T08:00:00+00:00"


def _snapshot():
    return {
        "references": {"xau_usd": 2000.0, "usd_irt": 60_000.0, "aed_gap_pct": 1.2},
        "score": {"total": 42, "decision": "GREEN"},
        "coins": {},
        "funds": [],
        "snapshot_at": AS_OF,
    }


class RecordingWS:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


def _pubsub_message(payload: dict) -> dict:
    return {"type": "message", "channel": GOLD_WS_CHANNEL, "data": json.dumps(payload)}


@pytest.mark.asyncio
async def test_snapshot_ready_retries_on_transient_failure():
    """Fails 2× from pubsub, succeeds on 3rd: snapshot must be broadcast after retrying.

    Call sequence:
      call 1 — from register() initial push: succeeds
      call 2 — pubsub handler attempt 1: raises
      call 3 — pubsub handler attempt 2: raises
      call 4 — pubsub handler attempt 3: succeeds → broadcast
    """
    call_count = 0

    async def _provider():
        nonlocal call_count
        call_count += 1
        if call_count in (2, 3):   # first two pubsub attempts fail
            raise RuntimeError("transient Redis error")
        return _snapshot()

    sleep_calls: list[float] = []

    async def _fast_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    ws = RecordingWS()
    hub = GoldWebSocketHub(snapshot_provider=_provider, sleep=_fast_sleep)
    await hub.register(ws)   # call_count → 1 (succeeds, sends initial snapshot)

    # Clear messages so we only count the pubsub-triggered broadcast.
    ws.messages.clear()

    msg = _pubsub_message({"type": "snapshot_ready", "snapshot_at": AS_OF})
    await hub._handle_pubsub_message(msg)

    pubsub_calls = call_count - 1  # subtract the initial register() call
    assert pubsub_calls == 3, (
        f"Expected 3 provider calls from pubsub handler (2 fail + 1 success) "
        f"but got {pubsub_calls}. Hub must retry, not give up after 1 failure."
    )
    assert len(ws.messages) == 1, (
        f"Expected snapshot broadcast after retry; got {len(ws.messages)} messages."
    )
    assert len(sleep_calls) == 2, (
        f"Expected 2 backoff sleeps (between attempts 1→2 and 2→3), got {len(sleep_calls)}."
    )


@pytest.mark.asyncio
async def test_snapshot_ready_gives_up_after_3_failures():
    """After 3 consecutive pubsub failures, hub gives up: no broadcast, provider called exactly 3×.

    Call sequence:
      call 1 — from register(): succeeds (initial snapshot)
      call 2 — pubsub attempt 1: raises
      call 3 — pubsub attempt 2: raises
      call 4 — pubsub attempt 3: raises → give up, no broadcast
    """
    call_count = 0

    async def _provider():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _snapshot()          # register() initial push succeeds
        raise RuntimeError("persistent Redis error")   # all pubsub attempts fail

    async def _fast_sleep(_: float) -> None:
        pass

    ws = RecordingWS()
    hub = GoldWebSocketHub(snapshot_provider=_provider, sleep=_fast_sleep)
    await hub.register(ws)
    ws.messages.clear()

    msg = _pubsub_message({"type": "snapshot_ready", "snapshot_at": AS_OF})
    await hub._handle_pubsub_message(msg)

    pubsub_calls = call_count - 1
    assert pubsub_calls == 3, (
        f"Expected exactly 3 provider calls from pubsub handler before giving up, "
        f"got {pubsub_calls}."
    )
    assert len(ws.messages) == 0, "No broadcast expected after 3 consecutive failures."
