"""End-to-end smoke test for all /funds/* endpoints.

Starts the API server, hits each endpoint, validates, kills the server.
"""

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

OUT = Path("data") / "top50_funds_intraday" / "smoke_test.json"


def _wait_port(host: str, port: int, timeout: float = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def _hit(url: str, timeout: float = 30):
    t0 = time.monotonic()
    try:
        with urlopen(url, timeout=timeout) as r:
            return r.status, time.monotonic() - t0, r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, time.monotonic() - t0, e.read().decode("utf-8", errors="replace")
    except URLError as e:
        return 0, time.monotonic() - t0, str(e)


def main() -> int:
    host, port = "127.0.0.1", 8765
    log_path = Path("logs") / "smoke_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["SERVER_PORT"] = str(port)
    env["SERVER_HOST"] = host
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = "."

    cmd = [
        sys.executable,
        "-u",
        "-m",
        "uvicorn",
        "apps.api.app:app",
        "--host",
        host,
        "--port",
        str(port),
        "--no-access-log",
    ]
    print(f"starting: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, env=env, stdout=log_fh, stderr=subprocess.STDOUT)
    try:
        if not _wait_port(host, port, timeout=60):
            print("server did not start; log:")
            print(log_path.read_text(encoding="utf-8")[-2000:])
            return 1

        base = f"http://{host}:{port}/api/v1"
        sym = quote("عیار")
        cases = [
            f"/funds/intraday?symbols={sym}&limit=3",
            f"/funds/intraday/candles?symbols={sym}&interval_minutes=5",
            "/funds/top?metric=market_value&top=3",
            "/funds/top?metric=intraday_volume&top=3",
            "/funds/top?metric=nav_change_pct&top=3",
        ]
        results = []
        all_ok = True
        for path in cases:
            status, elapsed, body = _hit(base + path, timeout=30)
            ok = 200 <= status < 300
            all_ok = all_ok and ok
            extra = ""
            with contextlib.suppress(Exception):
                parsed = json.loads(body)
                if isinstance(parsed, dict) and "symbols" in parsed:
                    extra = f"  symbols={len(parsed['symbols'])}"
                elif isinstance(parsed, dict) and "items" in parsed:
                    extra = f"  items={len(parsed['items'])}"
            print(f"  [{'OK' if ok else 'FAIL'}] {status}  {elapsed:6.2f}s  {path}{extra}")
            results.append({"path": path, "status": status, "elapsed_s": round(elapsed, 3), "ok": ok})

        OUT.write_text(json.dumps({"results": results, "all_ok": all_ok}, indent=2), encoding="utf-8")
        print(f"\nsummary: {OUT}  (all_ok={all_ok})")
        return 0 if all_ok else 1
    finally:
        log_fh.close()
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())

