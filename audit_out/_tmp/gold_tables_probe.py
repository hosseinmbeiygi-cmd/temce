"""Verify gold_* tables populated + freshness report."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from core import database  # noqa: E402

TABLES = [
    "gold_snapshots",
    "gold_score_history",
    "gold_fund_nav",
    "gold_portfolio_values",
    "gold_alert_rules",
    "gold_alert_events",
    "gold_holdings",
    "gold_trades",
    "gold_dca_plans",
]


async def main() -> None:
    await database.init_database()
    async with database.async_session_factory() as s:
        for t in TABLES:
            try:
                n = (await s.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                print(f"{t:28} rows={n}")
            except Exception as exc:  # noqa: BLE001
                print(f"{t:28} ERR {type(exc).__name__}")
                await s.rollback()

        from src.gold_desk.freshness import build_freshness_report

        rep = await build_freshness_report(s)
        print("\noverall:", rep["overall"], rep["counts"])
        for i in rep["sources"]:
            print(f"  {i['status']:8} {i['key']:42} rows={i['rows']} age_min={i['age_minutes']}")

        from src.gold_desk.portfolio_history import build_performance_report

        perf = await build_performance_report(s, days=90)
        d = perf.as_dict()
        print("\nperformance points:", d["points"], "twr:", d["twr_pct"])
        print("unavailable:", d["unavailable"])
        for k, v in d["benchmarks"].items():
            print("  bench", k, v)
        from datetime import date

        from src.gold_desk.portfolio_history import load_benchmark_series

        series = await load_benchmark_series(s, "gold", start=date(2026, 7, 1), end=date(2026, 10, 14))
        print("gold bench points:", len(series))
        series = await load_benchmark_series(s, "usd", start=date(2026, 7, 1), end=date(2026, 10, 14))
        print("usd bench points:", len(series))
        series = await load_benchmark_series(s, "tedpix", start=date(2026, 7, 1), end=date(2026, 10, 14))
        print("tedpix bench points:", len(series))


asyncio.run(main())
