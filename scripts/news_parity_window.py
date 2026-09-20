#!/usr/bin/env python
"""Parity-window collector for the news read-path canary.

Drives real traffic against a running dev server while sampling
``GET /api/v1/news/read-path/status`` once a minute, appending one JSON
line per sample to the output file. Designed for the documented
one-hour window: plain HTTP only, proxy bypass, in-memory counter
fallback is fine (single-worker dev server).

Usage:
  python scripts/news_parity_window.py --port 3211 --minutes 60
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

QUERIES = ["خودرو", "بانک", "شپنا", "فولاد", "بورس", "دلار", "سکه", "گزارش", "تسهیلات", "انرژی"]
SYMBOLS = ["وبانك", "وبانک", "فولاد", "فملي", "فملی", "شپنا", "خودرو"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3211)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    out = Path(
        args.out
        or f"reports/parity_window_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fh = out.open("a", encoding="utf-8")

    def log_sample(sample: dict) -> None:
        fh.write(json.dumps(sample, ensure_ascii=False) + "\n")
        fh.flush()

    deadline = time.monotonic() + args.minutes * 60
    client = httpx.Client(base_url=base, timeout=15.0)

    next_status_at = 0.0  # sample immediately
    hits = 0
    errors = 0

    while time.monotonic() < deadline:
        # ── status sample once a minute ──
        if time.monotonic() >= next_status_at:
            try:
                r = client.get("/api/v1/news/read-path/status")
                try:
                    body = r.json()
                except Exception:
                    body = {"raw": r.text[:200]}
                log_sample(
                    {
                        "ts": now_iso(),
                        "kind": "status",
                        "http": r.status_code,
                        "body": body.get("data", body),
                    }
                )
            except Exception as e:
                errors += 1
                log_sample({"ts": now_iso(), "kind": "status_error", "error": str(e)[:200]})
            next_status_at = time.monotonic() + 60.0

        # ── traffic: three read routes, realistic mix ──
        try:
            pick = random.random()
            if pick < 0.5:
                url = f"/api/v1/news?page_size=30&page={random.randint(1, 5)}"
            elif pick < 0.7:
                q = random.choice(QUERIES)
                url = f"/api/v1/news/search?q={q}&page_size=30"
            else:
                sym = random.choice(SYMBOLS)
                url = f"/api/v1/news/symbol/{sym}?page_size=30"
            r = client.get(url)
            if r.status_code == 200:
                hits += 1
            else:
                errors += 1
        except Exception:
            errors += 1
            time.sleep(1.0)

        # ~2 req/s keeps the 1h window meaningful without stressing dev box
        time.sleep(0.5)

    fh.close()
    print(json.dumps({"out": str(out), "hits": hits, "errors": errors}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
