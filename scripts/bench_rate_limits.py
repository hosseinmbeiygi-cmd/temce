"""Live benchmark for the BrsApi rate-limit status endpoint.

Usage:
    python scripts/bench_rate_limits.py [BASE_URL]

Connects to ``<BASE_URL>/api/v1/rate-limits`` (default ``http://localhost:8000``)
and prints the current daily / 5-min / per-category usage, plus a single
GET latency reading. Useful for the admin dashboard or for confirming
the safety-margin behaviour against a running stack.

Output is plain JSON followed by a one-line human summary. Exit code is
0 on a 200 response, 1 otherwise. The script never writes anything to
the API — read-only.
"""

from __future__ import annotations

import json
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_BASE = "http://localhost:8000"


def fetch_status(base: str) -> dict:
    """GET /api/v1/rate-limits and return the JSON payload."""
    url = f"{base.rstrip('/')}/api/v1/rate-limits"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=5) as resp:  # noqa: S310 — operator-controlled URL
        body = resp.read().decode("utf-8")
    return json.loads(body)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    try:
        t0 = time.perf_counter()
        payload = fetch_status(base)
        latency_ms = (time.perf_counter() - t0) * 1000
    except (URLError, TimeoutError, ConnectionError) as exc:
        print(f"ERROR: cannot reach {base}: {exc}", file=sys.stderr)
        return 1

    # The endpoint wraps the BrsApi status in an ApiResponse envelope.
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    g = data.get("global", {})

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(
        f"\nlatency={latency_ms:.1f}ms  "
        f"daily={g.get('daily_count', 0)}/{g.get('daily_limit', 0)} "
        f"({g.get('daily_used_pct', 0):.1f}%)  "
        f"5min={g.get('5min_count', 0)}/{g.get('5min_limit', 0)} "
        f"({g.get('5min_used_pct', 0):.1f}%)  "
        f"tehran_time={g.get('tehran_time', 'n/a')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
