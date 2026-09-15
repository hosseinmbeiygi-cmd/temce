"""Shared core for replaying dead-letter job messages.

Single implementation used by BOTH entry points so the CLI and the admin
panel behave identically:

- ``scripts/replay_dead_letter.py``  — command-line tool
- ``POST /api/v1/jobs/queue/replay`` — admin API endpoint

The core is pure (Redis client + explicit options in, structured
:class:`ReplayResult` out) — no printing, no ``sys.exit``. Callers decide
how to render the result (CLI prints, API serialises to JSON).
"""

from __future__ import annotations

import contextlib
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.time.timezone import IRAN_TZ

# Upper bound on messages pulled in one read-only snapshot, so a runaway
# dead-letter queue cannot be loaded into memory wholesale.
MAX_SCAN = 5000


def current_token(token_from_settings: str | None = None) -> str:
    """Return the effective worker auth token.

    Matches ``JobQueuePublisher`` exactly: use the configured
    ``job_queue_token`` when set, otherwise generate a fresh random token
    per process (dev mode has no auth and any token passes).
    """
    return token_from_settings or secrets.token_urlsafe(16)


def _matches(payload: dict[str, Any], job_name: str | None, search: str | None) -> bool:
    """Apply the ``job_name`` / ``search`` filters to a decoded message."""
    if job_name and payload.get("job_name") != job_name:
        return False
    if search:
        hay = json.dumps(payload, ensure_ascii=False, default=str)
        if search not in hay:
            return False
    return True


@dataclass
class ReplayMessage:
    """Per-message outcome for the caller to render."""

    job_name: str
    job_id: str
    attempt: int
    error: str | None
    status: str  # replayed | failed | discarded | listed | skipped
    message: str | None = None


@dataclass
class ReplayResult:
    """Structured outcome of a replay/discard/list/dry-run operation."""

    mode: str  # replay | discard | list | dry-run
    total: int  # matching messages found in the dead queue
    replayed: int = 0
    failed: int = 0
    discarded: int = 0
    queue: str = ""
    dead_queue: str = ""
    queue_size: int = 0
    dead_size: int = 0
    messages: list[ReplayMessage] = field(default_factory=list)


def _decode(raw: str) -> dict[str, Any]:
    """Decode a raw JSON message, tolerating malformed entries."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"job_name": "<malformed>", "raw": raw[:80]}


def _new_replay_payload(payload: dict[str, Any], token: str) -> str:
    """Build the re-queued message: fresh retry budget + current token.

    - ``attempt`` resets to 1 so the consumer gets a full retry budget
      (otherwise an attempt=3 message would be dead-lettered again on the
      very next failure).
    - ``token`` is refreshed so a current worker can pass auth (especially
      relevant in dev where every process has its own random token).
    - ``error`` / ``dead_lettered_at`` are stripped — they belong to the
      failed run, not the new one.
    """
    replayed = dict(payload)
    replayed["attempt"] = 1
    replayed["token"] = token
    replayed.pop("error", None)
    replayed.pop("dead_lettered_at", None)
    now = datetime.now(UTC).isoformat()
    replayed["published_at"] = now
    replayed["replayed_at"] = now
    return json.dumps(replayed, ensure_ascii=False, default=str)


async def replay_dead_letter_messages(
    redis: Any,
    *,
    queue_name: str,
    dead_queue: str,
    token: str,
    job_name: str | None = None,
    search: str | None = None,
    limit: int = 0,
    mode: str = "replay",  # replay | discard | list | dry-run
) -> ReplayResult:
    """Run a dead-letter replay / discard / list / dry-run against Redis.

    Read-only modes (``list`` / ``dry-run``) snapshot the queue with a bounded
    ``LRANGE`` (at most :data:`MAX_SCAN` messages).

    Mutating modes (``replay`` / ``discard``) rotate the queue with atomic
    ``LPOP`` + ``RPUSH`` instead of ``LREM``: each message is popped once,
    non-matching ones are pushed back to the tail, and the loop is bounded by
    the queue length observed on entry so a rotated message is never visited
    twice. This is O(N) rather than ``LREM``'s O(N²), and two concurrent
    replayers can never process the same message.

    - ``replay``: push a *fresh* copy to ``queue_name`` (attempt=1, current
      token, no error). A failed ``LPUSH`` pushes the original back to the
      tail of ``dead_queue`` — no data loss.
    - ``discard``: drop the matching message (already popped).

    Returns a :class:`ReplayResult` with counts + per-message outcomes.
    """
    if mode in ("list", "dry-run"):
        return await _scan_read_only(
            redis,
            queue_name=queue_name,
            dead_queue=dead_queue,
            job_name=job_name,
            search=search,
            limit=limit,
            mode=mode,
        )

    result = ReplayResult(mode=mode, total=0, queue=queue_name, dead_queue=dead_queue)
    rotations = int(await redis.llen(dead_queue) or 0)

    for _ in range(rotations):
        if limit and limit > 0 and result.total >= limit:
            break
        raw = await redis.lpop(dead_queue)
        if raw is None:
            break

        payload = _decode(raw)
        if not _matches(payload, job_name, search):
            await redis.rpush(dead_queue, raw)  # tail — not revisited this pass
            continue

        result.total += 1
        if mode == "discard":
            result.discarded += 1
            result.messages.append(_outcome(payload, "discarded"))
            continue

        # ── Replay ───────────────────────────────────────────────────
        try:
            pushed = await redis.lpush(queue_name, _new_replay_payload(payload, token))
            if not pushed:
                raise RuntimeError("LPUSH returned 0")
            result.replayed += 1
            result.messages.append(_outcome(payload, "replayed", attempt=1, error=None))
        except Exception as exc:  # noqa: BLE001 — message must survive
            with contextlib.suppress(Exception):
                await redis.rpush(dead_queue, raw)
            result.failed += 1
            result.messages.append(_outcome(payload, "failed", message=str(exc)))

    result.queue_size = int(await redis.llen(queue_name) or 0)
    result.dead_size = int(await redis.llen(dead_queue) or 0)
    return result


def _outcome(
    payload: dict[str, Any],
    status: str,
    *,
    attempt: int | None = None,
    error: str | None = "",
    message: str | None = None,
) -> ReplayMessage:
    """Build a :class:`ReplayMessage` from a decoded payload."""
    return ReplayMessage(
        job_name=str(payload.get("job_name", "<malformed>")),
        job_id=str(payload.get("job_id", "")),
        attempt=attempt if attempt is not None else int(payload.get("attempt", 0) or 0),
        error=error if error != "" else str(payload.get("error") or ""),
        status=status,
        message=message,
    )


async def _scan_read_only(
    redis: Any,
    *,
    queue_name: str,
    dead_queue: str,
    job_name: str | None,
    search: str | None,
    limit: int,
    mode: str,
) -> ReplayResult:
    """Bounded read-only snapshot for ``list`` / ``dry-run`` modes."""
    raw_messages: list[str] = await redis.lrange(dead_queue, 0, MAX_SCAN - 1) or []
    matched = [p for p in (_decode(r) for r in raw_messages) if _matches(p, job_name, search)]
    if limit and limit > 0:
        matched = matched[:limit]

    result = ReplayResult(
        mode=mode,
        total=len(matched),
        queue=queue_name,
        dead_queue=dead_queue,
        messages=[_outcome(p, "listed") for p in matched],
    )
    result.queue_size = int(await redis.llen(queue_name) or 0)
    result.dead_size = int(await redis.llen(dead_queue) or 0)
    return result


# ──────────────────────────────────────────────
#  Dead-Letter Summary (troubleshooting report)
# ──────────────────────────────────────────────

# Supported time-window labels for filtering by ``dead_lettered_at``.
SUMMARY_WINDOWS = ("all", "today", "week", "24h")


def resolve_since(window: str, now: float | None = None) -> float | None:
    """Resolve a window label to a ``since`` epoch threshold (seconds).

    - ``all``  → ``None`` (no filter)
    - ``today`` → start of the current day in Tehran (Asia/Tehran)
    - ``week``  → ``now - 7 days``
    - ``24h``   → ``now - 24 hours``

    Unknown labels raise ``ValueError`` so callers can surface a clear
    validation message.
    """
    now = now if now is not None else time.time()
    if window in ("", "all"):
        return None
    if window == "today":
        tehran_now = datetime.fromtimestamp(now, tz=IRAN_TZ)
        start = tehran_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp()
    if window == "week":
        return now - 7 * 24 * 3600
    if window == "24h":
        return now - 24 * 3600
    raise ValueError(f"Unknown summary window: {window!r} — expected one of {SUMMARY_WINDOWS}")


# Common error signatures seen in dead-letter payloads, checked in order.
_ERROR_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("db_error", ("dberror", "sqlalchemy", "psycopg", "connection refused", "database")),
    ("parse_error", ("parseerror", "json decode", "unexpected token")),
    ("timeout", ("timeout", "timed out")),
    ("rate_limit", ("rate limit", "quota", "429", "402")),
    ("http_error", ("http ", "status code", "500", "502", "503", "504")),
    ("auth", ("token", "unauthorized", "forbidden", "401", "403")),
    ("lock_duplicate", ("lock not acquired", "duplicate")),
)


def classify_error(error: str | None) -> str:
    """Bucket a raw error string into a coarse category for aggregation.

    Categories (checked in order): ``db_error``, ``parse_error``,
    ``timeout``, ``rate_limit``, ``http_error``, ``auth``,
    ``lock_duplicate``, otherwise ``other``. Empty errors map to
    ``no_error``.
    """
    if not error:
        return "no_error"
    lower = error.lower()
    for category, markers in _ERROR_SIGNATURES:
        if any(marker in lower for marker in markers):
            return category
    return "other"


@dataclass
class DeadLetterSummary:
    """Aggregated view of the dead-letter queue for troubleshooting.

    Answers "what keeps failing?": which ``job_name``s dominate, which
    error categories recur, and whether the same logical message
    (``job_id``) appears multiple times (repeated failures).

    When ``since`` is set (from a ``window`` label), only messages whose
    ``dead_lettered_at >= since`` contribute to the totals and
    distributions — messages without a usable ``dead_lettered_at`` are
    excluded so a time-bounded report never hides stale failures as if
    they were recent.
    """

    total: int  # messages in scope (after window filter)
    queue: str = ""  # dead-letter queue name
    window: str = "all"  # applied window label (all | today | week | 24h)
    since: float | None = None  # epoch threshold used for the filter
    job_names: list[dict[str, Any]] = field(default_factory=list)  # [{name, count}] desc
    error_categories: list[dict[str, Any]] = field(default_factory=list)  # [{category, count}] desc
    top_errors: list[dict[str, Any]] = field(default_factory=list)  # [{error, count}] desc
    repeated: list[dict[str, Any]] = field(default_factory=list)  # [{job_name, job_id, count}] count>1
    repeated_messages: int = 0  # how many dead messages share a job_id
    malformed: int = 0  # undecodable payloads (always counted)


def _in_window(payload: dict[str, Any], since: float | None) -> bool:
    """True when the message passes the time window (no window → always)."""
    if since is None:
        return True
    raw = payload.get("dead_lettered_at")
    if raw is None:
        return False
    try:
        return float(raw) >= since
    except (TypeError, ValueError):
        return False


def _build_summary(
    raw_messages: list[str],
    dead_queue: str,
    *,
    since: float | None = None,
    window: str = "all",
) -> DeadLetterSummary:
    """Compute the aggregate summary from raw dead-letter payloads (pure).

    ``since`` filters by ``dead_lettered_at`` (epoch seconds) so the report
    can be limited to today / this week. Malformed payloads are still
    counted in ``malformed`` regardless of the window.
    """
    summary = DeadLetterSummary(total=0, queue=dead_queue, window=window, since=since)
    if not raw_messages:
        return summary

    job_counter: dict[str, int] = {}
    error_counter: dict[str, int] = {}
    raw_error_counter: dict[str, int] = {}
    job_id_counter: dict[tuple[str, str], int] = {}  # (job_name, job_id) → count

    for raw in raw_messages:
        payload = _decode(raw)
        if payload.get("job_name") == "<malformed>":
            summary.malformed += 1
            continue
        if not _in_window(payload, since):
            continue
        summary.total += 1

        job_name = str(payload.get("job_name", "<unknown>"))
        job_counter[job_name] = job_counter.get(job_name, 0) + 1

        error = str(payload.get("error") or "").strip()
        category = classify_error(error)
        error_counter[category] = error_counter.get(category, 0) + 1
        if error:
            raw_error_counter[error] = raw_error_counter.get(error, 0) + 1

        job_id = str(payload.get("job_id") or "")
        if job_id:
            key = (job_name, job_id)
            job_id_counter[key] = job_id_counter.get(key, 0) + 1

    summary.job_names = [
        {"name": name, "count": count} for name, count in sorted(job_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    summary.error_categories = [
        {"category": cat, "count": count}
        for cat, count in sorted(error_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    summary.top_errors = [
        {"error": err[:200], "count": count}
        for err, count in sorted(raw_error_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    ]

    repeats = [
        {"job_name": key[0], "job_id": key[1], "count": count} for key, count in job_id_counter.items() if count > 1
    ]
    summary.repeated = sorted(repeats, key=lambda r: (-r["count"], r["job_name"]))
    summary.repeated_messages = sum(r["count"] - 1 for r in summary.repeated)
    return summary


async def summarize_dead_letter(
    redis: Any,
    *,
    dead_queue: str,
    window: str = "all",
    since: float | None = None,
) -> DeadLetterSummary:
    """Read ``job:dead`` and return an aggregate troubleshooting report.

    Pure aggregation (no writes). Distribution of job_names, coarse error
    categories, top raw error strings, and repeated ``job_id``s so an
    operator can see which failures dominate without dumping every message.

    ``window`` (``all`` | ``today`` | ``week`` | ``24h``) or an explicit
    ``since`` epoch threshold restrict the report to messages
    dead-lettered within that window.
    """
    effective_since = since if since is not None else resolve_since(window)
    raw_messages: list[str] = await redis.lrange(dead_queue, 0, MAX_SCAN - 1) or []
    return _build_summary(
        raw_messages,
        dead_queue,
        since=effective_since,
        window=window,
    )
