#!/usr/bin/env python
"""
Build Screener Daily Scores — اسنپ‌شات روزانه امتیازهای مدل ۱۱۰ ستونه
=====================================================================

برای همه نمادهای فعال، امتیازهای مدل ۱۱۰ ستونه (Screener110Service /
VectorCalculator) را محاسبه و در جدول ``screener_daily_scores`` ذخیره می‌کند
به‌همراه:
  * رتبه در بازار (rank_in_market)
  * رتبه در صنعت (rank_in_industry) — اگر صنعت نماد موجود باشد
  * درصدک (percentile_score)

این اسکریپت با یک session می‌رود (مانند Screener110RunCycleJob) و فقط
محاسبه را انجام می‌دهد — خروجی جداگانه از screener_signals است.

Usage:
    python scripts/build_screener_scores.py            # همه نمادها
    python scripts/build_screener_scores.py --date 1404-05-24
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from core.database import get_session, init_database  # noqa: E402
from core.logging import get_logger  # noqa: E402
from services.screener110_service import BatchLoader, VectorCalculator  # noqa: E402

logger = get_logger(__name__)

CHUNK_SIZE = 100


# ═══════════════════════════════════════════════════════════════════════════
#  BUILDER
# ═══════════════════════════════════════════════════════════════════════════

async def build_daily_scores(session: Any, trade_date: date) -> dict[str, Any]:
    """Load → calculate → rank → save. Returns stats."""
    started_at = time.monotonic()
    loader = BatchLoader(session)
    calc = VectorCalculator()

    data = await loader.load_all()
    symbols = data["symbols"]
    daily_map = data["daily"]
    legal_map = data["legal"]
    profile_map = data["profiles"]
    snapshot_map = data["snapshots"]

    results: list[dict[str, Any]] = []
    for sym_data in symbols:
        sym = sym_data.get("symbol", "")
        if not sym:
            continue
        eps = float(sym_data.get("eps", 0) or 0)
        shares = float(sym_data.get("shares_count", 0) or 0)
        profile = profile_map.get(sym)
        if profile and profile.get("eps_current"):
            eps = float(profile["eps_current"])

        result = calc.calculate(
            symbol=sym,
            eps=eps,
            shares=shares,
            daily_rows=daily_map.get(sym, []),
            legal_rows=legal_map.get(sym, []),
            profile=profile,
            last_snapshot=snapshot_map.get(sym),
        )
        result["industry"] = (sym_data.get("industry") or "").strip()
        results.append(result)

    # ── Ranking ──────────────────────────────────────────────────────────
    # رتبه در بازار بر اساس final_score
    ranked = sorted(results, key=lambda r: r.get("final_score", 0), reverse=True)
    total = len(ranked)
    for idx, r in enumerate(ranked, start=1):
        r["rank_in_market"] = idx
        r["percentile_score"] = round((total - idx) / max(total - 1, 1) * 100, 1) if total > 1 else 100.0

    # رتبه در صنعت — گروه‌بندی بر اساس industry
    by_industry: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        ind = r.get("industry") or "سایر"
        by_industry.setdefault(ind, []).append(r)
    for _ind, group in by_industry.items():
        group.sort(key=lambda r: r.get("final_score", 0), reverse=True)
        for idx, r in enumerate(group, start=1):
            r["rank_in_industry"] = idx

    # ── Map to table columns ─────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    for r in results:
        rows.append({
            "symbol": r["symbol"],
            "trade_date": trade_date,
            "score_total": r.get("final_score"),
            "score_momentum": r.get("score_technical"),
            "score_value": r.get("score_valuation"),
            "score_growth": r.get("score_fundamental"),
            "score_quality": r.get("score_institutional"),
            "score_liquidity": r.get("score_liquidity"),
            "score_sentiment": r.get("score_gov_support"),
            "rank_in_market": r.get("rank_in_market"),
            "rank_in_industry": r.get("rank_in_industry"),
            "percentile_score": r.get("percentile_score"),
            "raw_scores": r,
            "calculated_at": datetime.now(UTC),
        })

    # ── Upsert (chunked) ─────────────────────────────────────────────────
    # NOTE: never call ``.values(rows)`` AND pass a params list to
    # ``execute()`` — the two bindings collide and PostgreSQL ends up
    # rendering a giant statement that hangs (regression: full-market run
    # blocked for minutes). Build the bare insert once and feed the row
    # chunks as executemany params.
    if rows:
        from sqlalchemy import MetaData, Table
        table = await session.run_sync(
            lambda sync_s: Table("screener_daily_scores", MetaData(),
                                 autoload_with=sync_s.bind, keep_existing=True)
        )
        stmt = pg_insert(table)
        stmt = stmt.on_conflict_do_update(
            constraint="screener_daily_scores_pkey",
            set_={
                col: getattr(stmt.excluded, col)
                for col in rows[0] if col not in ("symbol", "trade_date")
            },
        )
        for i in range(0, len(rows), CHUNK_SIZE):
            await session.execute(stmt, rows[i:i + CHUNK_SIZE])
        await session.commit()

    duration_ms = (time.monotonic() - started_at) * 1000
    stats = {
        "symbols": len(results),
        "rows": len(rows),
        "duration_ms": round(duration_ms, 1),
        "trade_date": str(trade_date),
    }
    logger.info("Screener daily scores: %s", stats)

    # لاگ در brsapi_sync_log
    try:
        await session.execute(
            text("""
                INSERT INTO brsapi_sync_log
                    (endpoint, category, status, items_count, duration_ms,
                     params_snapshot, started_at, completed_at, gregorian_date)
                VALUES
                    (:endpoint, :category, 'OK', :items_count, :duration_ms,
                     :params_snapshot, :started_at, :completed_at, CURRENT_DATE)
            """),
            {
                "endpoint": "screener_daily_scores",
                "category": "screener",
                "items_count": len(rows),
                "duration_ms": duration_ms,
                "params_snapshot": f"trade_date={trade_date}",
                "started_at": datetime.fromtimestamp(started_at),
                "completed_at": datetime.now(),
            },
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write sync log for screener_daily_scores")

    return stats


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

async def main() -> None:
    parser = argparse.ArgumentParser(description="Build screener_daily_scores snapshot")
    parser.add_argument("--date", type=str, default=None,
                        help="Trade date (YYYY-MM-DD). Default: today")
    args = parser.parse_args()

    await init_database()

    trade_date = date.fromisoformat(args.date) if args.date else date.today()

    async for session in get_session():
        stats = await build_daily_scores(session, trade_date)
        print(f"Screener daily scores: {stats['symbols']} symbols, "
              f"{stats['rows']} rows in {stats['duration_ms']}ms")
        return


if __name__ == "__main__":
    asyncio.run(main())
