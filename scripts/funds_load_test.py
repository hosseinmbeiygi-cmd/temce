# -*- coding: utf-8 -*-
"""Fund Module Load & Scalability Harness — N = 500..2000 funds (A8.6).

دو حالت اجرا:
  --mode sim : بدون DB — ظرفیت محاسباتی (هویت، قابلیت، پوشش) + سرکوب
               Thundering Herd با Mutex + آمار تأخیر P50/P95.
  --mode db  : با DB واقعی — Idempotent Discovery روی N صندوق موجود
               (بدون مصرف API؛ FakeAdapter از خود جدول funds می‌خواند) و
               اندازه‌گیری نرخ نوشتن/پایداری.

نمونه:
  python -X utf8 scripts/funds_load_test.py --mode sim --n 500,1000,2000 --concurrency 50
  python -X utf8 scripts/funds_load_test.py --mode db  --n 500

خروجی: جدول خلاصه + فایل JSON در ``reports/funds_load_test_<ts>.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from core.time import now_utc
from services.fund_circuit_breaker import BreakerState, decide_state  # noqa: E402
from services.fund_discovery import (  # noqa: E402
    coverage_score,
    coverage_status,
    detect_capabilities,
)
from services.fund_identity import (  # noqa: E402
    decide_identity,
    derive_fund_id,
    identity_fingerprint,
)
from services.fund_read_through import DistributedMutex  # noqa: E402


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((pct / 100.0) * (len(values) - 1)))))
    return values[k]


def synth_universe(n: int) -> list[dict]:
    rng = random.Random(1404)
    types = ["سهامی", "کالایی", "درآمد ثابت", "اهرمی", "بخشی", "مختلط"]
    out = []
    for i in range(n):
        sym = f"صندوق{i:04d}"
        out.append(
            {
                "symbol": sym,
                "name": f"صندوق آزمون بار شماره {i}",
                "isin": f"IRLOAD{i:05d}",
                "market": "tse" if i % 5 else "ime",
                "sector": "صندوق سرمایه گذاری قابل معامله",
                "fund_type_hint": types[i % len(types)],
            }
        )
    return out


async def bench_thundering_herd(concurrency: int, rounds: int = 20) -> dict:
    """C درخواست هم‌زمان برای یک کلید ناموجود → فقط ۱ بار Adapter صدا زده شود."""
    mutex = DistributedMutex()
    # اجبار به fallback حافظه‌ای (بدون Redis) برای تست قطعی
    mutex._redis = None
    mutex._redis_checked = True
    mutex._redis_retry_at = time.time() + 3600

    calls = {"adapter": 0}
    cache: dict[str, dict] = {}

    async def adapter_fetch(key: str) -> dict:
        calls["adapter"] += 1
        await asyncio.sleep(0.002)  # تأخیر شبیه‌سازی‌شده Provider
        return {"key": key, "value": 1}

    async def request(key: str):
        if key in cache:
            return cache[key]
        got = await mutex.acquire(f"load:{key}")
        if got:
            try:
                data = await adapter_fetch(key)
                cache[key] = data
                return data
            finally:
                await mutex.release(f"load:{key}")
        # بازنده‌ها: منتظر DB می‌مانند (اینجا cache)
        for _ in range(200):
            if key in cache:
                return cache[key]
            await asyncio.sleep(0.001)
        return None

    latencies: list[float] = []
    for r in range(rounds):
        key = f"miss-{r}"
        t0 = time.perf_counter()
        await asyncio.gather(*[request(key) for _ in range(concurrency)])
        latencies.append((time.perf_counter() - t0) * 1000)

    return {
        "adapter_calls": calls["adapter"],
        "expected_calls": rounds,
        "suppression_ok": calls["adapter"] == rounds,
        "round_latency_p50_ms": round(percentile(latencies, 50), 2),
        "round_latency_p95_ms": round(percentile(latencies, 95), 2),
    }


def run_sim(n_values: list[int], concurrency: int) -> list[dict]:
    results = []
    for n in n_values:
        universe = synth_universe(n)
        t0 = time.perf_counter()

        # ۱) هویت + Fingerprint
        matches_pool = {}
        for i, rec in enumerate(universe):
            fp = identity_fingerprint(rec["isin"], None, rec["symbol"])
            fid = derive_fund_id(symbol=rec["symbol"], market=rec["market"])
            matches_pool[fp] = fid
        identity_ops = 0
        for rec in universe:
            d = decide_identity(
                symbol=rec["symbol"],
                isin=rec["isin"],
                national_id=None,
                matches={},
            )
            assert d.action == "new"
            identity_ops += 1

        # ۲) قابلیت‌ها
        nav_symbols = {r["symbol"] for r in universe[: n // 2]}
        quote_symbols = {r["symbol"] for r in universe[: int(n * 0.8)]}
        codal_symbols = {r["symbol"] for r in universe[: n // 3]}
        caps_ops = 0
        for rec in universe:
            detect_capabilities(
                fund_id=derive_fund_id(symbol=rec["symbol"], market=rec["market"]),
                symbol=rec["symbol"],
                market=rec["market"],
                nav_symbols=nav_symbols,
                nav_funds=set(),
                quote_symbols=quote_symbols,
                quote_funds=set(),
                codal_symbols=codal_symbols,
                portfolio_funds=set(),
                holding_funds=set(),
            )
            caps_ops += 1

        # ۳) Coverage
        scores = [
            coverage_score(i % 100, i % 2 == 0, (i % 180) / 2.0, i % 3)
            for i in range(n)
        ]
        statuses = [
            coverage_status(i % 100, i % 2 == 0, (i % 180) / 2.0)
            for i in range(n)
        ]

        # ۴) Circuit Breaker (شبیه‌سازی ۱۰٪ خطا)
        states = {}
        for i in range(n):
            fid = f"tse:صندوق{i:04d}"
            st = BreakerState()
            for _ in range(random.Random(i).randint(0, 7)):
                st = decide_state(st, success=False, now=1000.0)
            states[fid] = st.open_until

        elapsed = time.perf_counter() - t0
        results.append(
            {
                "n_funds": n,
                "identity_ops": identity_ops,
                "capability_ops": caps_ops,
                "coverage_ops": len(scores) + len(statuses),
                "breaker_states": len(states),
                "total_ops": identity_ops + caps_ops + len(scores) + len(statuses) + len(states),
                "elapsed_ms": round(elapsed * 1000, 1),
                "ops_per_sec": round((identity_ops + caps_ops + len(scores)) / max(elapsed, 1e-9), 0),
                "status_distribution": {s: statuses.count(s) for s in set(statuses)},
            }
        )
    herd = asyncio.run(bench_thundering_herd(concurrency))
    for r in results:
        r["thundering_herd"] = herd
    return results


async def run_db(n: int) -> dict:
    """Discovery واقعی روی N صندوق موجود — Idempotent، بدون مصرف API."""
    from core.database import close_database, get_session, init_database
    from services.fund_discovery import FundDiscoveryService

    class ExistingFundsAdapter:
        def __init__(self, rows: list[dict]):
            self.rows = rows

        async def fetch_universe(self):
            return self.rows

    await init_database()
    try:
        async for session in get_session():
            from sqlalchemy import text

            rows = (
                await session.execute(
                    text(
                        "SELECT id, symbol, name, isin, fund_type, is_etf "
                        "FROM funds WHERE symbol IS NOT NULL ORDER BY id LIMIT :lim"
                    ),
                    {"lim": n},
                )
            ).fetchall()
            universe = [
                {
                    "fund_id": r[0],
                    "symbol": r[1],
                    "name": r[2],
                    "isin": r[3],
                    "market": "ime" if str(r[0]).startswith("ime:") else "tse",
                    "sector": "صندوق",
                    "fund_type_hint": r[4] or "سهامی",
                }
                for r in rows
            ]
            if not universe:
                return {"error": "جدول funds خالی است — ابتدا Discovery واقعی را اجرا کنید.", "n": 0}

            svc = FundDiscoveryService(session, ExistingFundsAdapter(universe))
            t0 = time.perf_counter()
            await svc.discover(store_snapshot=False)
            elapsed = time.perf_counter() - t0
            stats = svc.last_stats.to_dict() if svc.last_stats else {}
            n_done = len(universe)
            return {
                "n_funds": n_done,
                "elapsed_sec": round(elapsed, 2),
                "funds_per_sec": round(n_done / max(elapsed, 1e-9), 1),
                "ms_per_fund": round(elapsed * 1000 / max(n_done, 1), 1),
                "stats": stats,
            }
    finally:
        await close_database()


def main() -> None:
    ap = argparse.ArgumentParser(description="Fund module load test")
    ap.add_argument("--mode", choices=["sim", "db"], default="sim")
    ap.add_argument("--n", type=str, default="500,1000,2000")
    ap.add_argument("--concurrency", type=int, default=50)
    args = ap.parse_args()

    n_values = [int(x) for x in args.n.split(",") if x.strip()]
    started = now_utc()
    print(f"# Fund Load Test — mode={args.mode} n={n_values} concurrency={args.concurrency}")
    if args.mode == "sim":
        results = run_sim(n_values, args.concurrency)
        print(f"{'N':>6} | {'ops':>10} | {'ops/sec':>10} | {'elapsed_ms':>10}")
        print("-" * 50)
        for r in results:
            print(f"{r['n_funds']:>6} | {r['total_ops']:>10} | {r['ops_per_sec']:>10.0f} | {r['elapsed_ms']:>10.1f}")
        herd = results[0]["thundering_herd"] if results else {}
        print("\nThundering-herd suppression:", herd)
    else:
        out = asyncio.run(run_db(max(n_values)))
        results = [out]
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))

    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    payload = {
        "started_at": started.isoformat(),
        "mode": args.mode,
        "concurrency": args.concurrency,
        "results": results,
    }
    fp = out_dir / f"funds_load_test_{started.strftime('%Y%m%d_%H%M%S')}.json"
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nJSON report: {fp}")


if __name__ == "__main__":
    main()
