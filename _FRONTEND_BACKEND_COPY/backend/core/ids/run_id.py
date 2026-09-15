from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def new_run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    uid = uuid4().hex[:12]
    return f"run_{ts}_{uid}"


def parse_run_id(run_id: str) -> dict[str, str] | None:
    parts = run_id.split("_")
    if len(parts) >= 3 and parts[0] == "run":
        return {
            "prefix": parts[0],
            "timestamp": parts[1],
            "uuid": parts[2],
        }
    return None


def is_valid_run_id(run_id: str) -> bool:
    return run_id.startswith("run_") and len(run_id) > 10
