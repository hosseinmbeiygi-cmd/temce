"""
Check BrsApi key readiness (manual CLI)
========================================

Sends ONE live request to BrsApi and reports whether the server-side usage
counter has reset (HTTP 200) or the key is still over quota (HTTP 302 to a
heavy file). Also persists the probe state and notifies on the reset
transition, exactly like the hourly BrsApiReadyCheckJob.

Usage:
    python scripts/check_brsapi_ready.py          # probe + persist + notify
    python scripts/check_brsapi_ready.py --once   # probe only, no state write
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _p(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:  # Windows console safety
        print(msg.encode("ascii", errors="replace").decode("ascii"))


async def _run(once: bool) -> int:
    from brsapi.readiness import probe_key

    if once:
        probe = await probe_key()
        ready = probe.get("ready", False)
        status = probe.get("status_code", 0)
        detail = probe.get("detail", "")
        _p(f"ready={ready} status={status} detail={detail}")
        return 0 if ready else 1

    from brsapi.readiness import check_and_notify

    summary = await check_and_notify()
    _p(f"ready={summary['ready']} status={summary['status_code']} "
       f"transitioned={summary['transitioned']} notified={summary['notified']}")
    _p(f"detail={summary['detail']}")
    return 0 if summary["ready"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BrsApi key readiness")
    parser.add_argument("--once", action="store_true",
                        help="Probe only — do not persist state / notify")
    args = parser.parse_args()
    return asyncio.run(_run(args.once))


if __name__ == "__main__":
    raise SystemExit(main())
