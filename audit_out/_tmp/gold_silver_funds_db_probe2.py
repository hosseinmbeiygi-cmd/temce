"""DB probe 2 (فقط SELECT) — عیارهای تاریخ، صندوق‌های طلا، جداول GoldDesk/صندوق."""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402
from core import database  # noqa: E402
from core.time import utc_now_naive  # noqa: E402

GOLD_FUNDS = ["عیار", "طلا", "کهربا", "زر", "زرفام", "گوهر", "تابش", "نفیس", "آلتون", "ناب"]


async def main() -> None:
    await database.init_database()
    factory = database.async_session_factory
    if factory is None:
        print("no db factory")
        return
    async with factory() as s:
        print("=" * 70)
        print("A) backtest.py cutoff (Gregorian string) در برابر date ژلالی ستون")
        print("=" * 70)
        cutoff = (utc_now_naive() - timedelta(days=90 + 60)).strftime("%Y-%m-%d")
        q = text(
            "SELECT COUNT(*) FROM brsapi_gold_coin_history "
            "WHERE symbol = 'IR_COIN_EMAMI' AND date >= :c"
        )
        n = (await s.execute(q, {"c": cutoff})).scalar()
        total = (
            await s.execute(
                text("SELECT COUNT(*) FROM brsapi_gold_coin_history WHERE symbol='IR_COIN_EMAMI'")
            )
        ).scalar()
        print(f"  cutoff code-generated = {cutoff!r} (میلادی)")
        print(f"  rows matching date >= cutoff : {n}")
        print(f"  rows total (IR_COIN_EMAMI)   : {total}")
        n2 = (await s.execute(q, {"c": "1405-01-01"})).scalar()
        print(f"  rows matching date >= '1405-01-01' (ژلالی): {n2}")

        print("=" * 70)
        print("B) فهرست صندوق‌های طلا در brsapi_historical_real_legal (منبع BPR/Inflow امتیاز)")
        print("=" * 70)
        rows = (
            await s.execute(
                text(
                    """
                    SELECT symbol, COUNT(*), MIN(date), MAX(date)
                    FROM brsapi_historical_real_legal
                    WHERE symbol = ANY(:syms) GROUP BY symbol ORDER BY symbol
                    """
                ),
                {"syms": GOLD_FUNDS},
            )
        ).all()
        if not rows:
            print("  هیچ ردیفی برای نمادهای صندوق طلا یافت نشد")
        for r in rows:
            print("  ", tuple(r))

        print("=" * 70)
        print("C) جدیدترین تاریخ در brsapi_historical_real_legal و نمادهای صندوق")
        print("=" * 70)
        rows = (
            await s.execute(
                text(
                    """
                    SELECT symbol, date FROM brsapi_historical_real_legal
                    ORDER BY date DESC LIMIT 8
                    """
                )
            )
        ).all()
        for r in rows:
            print("  ", tuple(r))
        rows = (
            await s.execute(
                text(
                    """
                    SELECT symbol, date FROM brsapi_historical_real_legal
                    WHERE symbol LIKE '%عیار%' ORDER BY date DESC LIMIT 5
                    """
                )
            )
        ).all()
        print("  --- black «عیار»:")
        for r in rows:
            print("  ", tuple(r))

        print("=" * 70)
        print("D) جداول GoldDesk / صندوق — شمارش ردیف")
        print("=" * 70)
        for t in (
            "gold_snapshots",
            "gold_fund_nav",
            "gold_score_history",
            "gold_holdings",
            "gold_trades",
            "gold_alert_rules",
            "gold_alert_events",
            "gold_dca_plans",
            "fund_holdings",
            "fund_portfolio_reports",
            "fund_nav_runs",
            "fund_position_valuations",
            "fund_nav_results",
            "fund_nav_reconciliation_runs",
            "funds",
            "fund_universe",
            "brsapi_symbol_snapshots",
        ):
            try:
                c = (await s.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                print(f"   {t:<34} {c}")
            except Exception as exc:
                print(f"   {t:<34} ERROR {type(exc).__name__}: {str(exc)[:90]}")

        print("=" * 70)
        print("E) نماد XAUUSD در جداول دیگر (منبع RSI/technical)")
        print("=" * 70)
        for t in ("brsapi_gold_coin_history", "brsapi_symbol_snapshots"):
            try:
                c = (await s.execute(text(f"SELECT COUNT(*) FROM {t} WHERE symbol='XAUUSD'"))).scalar()
                print(f"   {t:<34} XAUUSD rows = {c}")
            except Exception as exc:
                print(f"   {t:<34} ERROR {type(exc).__name__}: {str(exc)[:90]}")


asyncio.run(main())
