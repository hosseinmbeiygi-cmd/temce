"""
BrsApi key-readiness monitor
============================

While the BrsApi key is blocked the platform runs in DB-only mode
(``BRSAPI_ENABLED=false``). This module powers a cheap hourly probe
(1 request) that watches for the moment the server-side usage counter
resets — i.e. when ``/Tsetmc/AllSymbols.php`` answers HTTP 200 instead of
HTTP 302 to a heavy file.

Key behaviours:

- ``probe_key()`` — one live request, never follows redirects, never retries.
- State is persisted to a small JSON file so the ``not-ready -> ready``
  transition is detected exactly once (no notification spam every hour).
- On the transition a notification is sent (Telegram if configured,
  otherwise a loud log line) so the operator can flip
  ``BRSAPI_ENABLED=true`` and run the backlog sync.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# State file lives next to the other brsapi runtime files (json/brsapi/).
_DEFAULT_STATE_FILE = Path(__file__).resolve().parent.parent / "json" / "brsapi" / "readiness_state.json"


@dataclass
class ReadinessState:
    """Persisted probe state (JSON file)."""

    ready: bool = False
    last_status: int = 0
    last_checked: str = ""
    last_detail: str = ""
    notified: bool = False  # True once we have notified about a reset


def _load_state(state_file: Path) -> ReadinessState:
    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
        return ReadinessState(
            ready=bool(raw.get("ready", False)),
            last_status=int(raw.get("last_status", 0)),
            last_checked=str(raw.get("last_checked", "")),
            last_detail=str(raw.get("last_detail", "")),
            notified=bool(raw.get("notified", False)),
        )
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return ReadinessState()


def _save_state(state: ReadinessState, state_file: Path) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_file)


async def probe_key() -> dict[str, Any]:
    """One live readiness request against the BrsApi AllSymbols endpoint.

    Returns ``{"ready": bool, "status_code": int, "detail": str}``.
    Deliberately bypasses the ``BRSAPI_ENABLED`` gate (the probe must work
    while DB-only mode is on) but honours the global rate limiter with
    fail-fast so it can never burn budget.
    """
    from brsapi.client import BrsApiClient

    client = BrsApiClient()
    await client.start()
    try:
        return await client.probe_ready()
    finally:
        await client.stop()


async def _notify_ready() -> None:
    """Best-effort notification that the key is usable again."""
    message = (
        "🎉 BrsApi key is READY again — the server-side usage counter has "
        "reset (AllSymbols returned HTTP 200). Set BRSAPI_ENABLED=true in "
        ".env and restart the server, then run "
        "`python scripts/run_backlog_sync.py` to catch up the backlog."
    )
    try:
        from integrations.notifications.telegram_sender import TelegramSender

        res = await TelegramSender().send(message)
        if res.success:
            logger.info("BrsApi readiness notification sent via Telegram")
            return
        logger.warning("Telegram not configured/sent (%s) — logging readiness instead", res.error)
    except Exception:  # noqa: BLE001
        logger.exception("Telegram notification failed — logging readiness instead")
    # Loud log fallback so the operator sees it even without Telegram.
    logger.info("[BRSAPI-READY] %s", message)


async def check_and_notify(state_file: Path | None = None) -> dict[str, Any]:
    """Run one probe, persist state, and notify on the reset transition.

    Args:
        state_file: Override the state file path (used by tests).

    Returns a serialisable summary dict for job results / logging.
    """
    fpath = state_file or _DEFAULT_STATE_FILE
    # First ever run (no state file, e.g. fresh deploy or a container that
    # lost the json/brsapi volume) must bootstrap SILENTLY: an already-healthy
    # key must not fire a spurious "key is READY again" notification.
    first_run = not fpath.exists()
    previous = _load_state(fpath)

    probe = await probe_key()
    ready = probe.get("ready", False)
    status = int(probe.get("status_code", 0))
    detail = str(probe.get("detail", ""))

    transitioned = ready and not previous.ready and not first_run
    if transitioned:
        await _notify_ready()

    state = ReadinessState(
        ready=ready,
        last_status=status,
        last_checked=datetime.now(UTC).isoformat(),
        last_detail=detail,
        notified=(transitioned or previous.notified) and not first_run,
    )
    _save_state(state, fpath)

    if ready:
        log_msg = f"BrsApi key READY (HTTP {status})" + (" — reset detected, notified!" if transitioned else "")
    else:
        log_msg = f"BrsApi key NOT ready (HTTP {status}): {detail}"
    logger.info("Readiness probe: %s", log_msg)

    return {
        "ready": ready,
        "status_code": status,
        "detail": detail,
        "transitioned": transitioned,
        "notified": transitioned,
        "checked_at": state.last_checked,
        "state_file": str(fpath),
    }
