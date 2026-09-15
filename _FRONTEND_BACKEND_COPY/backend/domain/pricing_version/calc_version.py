"""calc_version helper — فاز 1-3."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from typing import Any


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def calc_version(inputs: dict[str, Any], param_version: str = "v1") -> dict[str, str]:
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(canonical.encode()).hexdigest()[:12]
    return {
        "git_sha": git_sha(),
        "input_hash": h,
        "param_version": param_version,
        "timestamp": datetime.now(UTC).isoformat(),
    }
