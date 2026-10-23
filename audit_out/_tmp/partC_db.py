"""Part C — corporate actions, adjust factors, survivorship (read-only SELECTs)."""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


async def main():
    eng = create_async_engine(settings.database_url_async)
    out = {}
    async with eng.connect() as c:
        # symbol id for خودرو
        sid = (await c.execute(text("SELECT id FROM symbols WHERE symbol=:s LIMIT 1"), {"s": "خودرو"})).scalar()
        out["khodro_symbol_id"] = sid
        # corporate action events for خودرو
        rows = (await c.execute(text(
            "SELECT e.ex_date, e.action_type, e.ratio, e.dps, e.source, e.codal_ref "
            "FROM corporate_action_events e JOIN symbols s ON s.id=e.symbol_id "
            "WHERE s.symbol=:s ORDER BY e.ex_date"), {"s": "خودرو"})).fetchall()
        out["khodro_corporate_action_events"] = [
            {"ex_date": str(r[0]), "action_type": r[1], "ratio": str(r[2]), "dps": str(r[3]),
             "source": r[4], "codal_ref": r[5]} for r in rows]
        # adjust factors for خودرو in 2024
        if sid:
            af = (await c.execute(text(
                "SELECT trade_date, adj_factor FROM daily_adjust_factors "
                "WHERE symbol_id=:i AND trade_date BETWEEN '2023-12-01' AND '2025-01-31' "
                "ORDER BY trade_date"), {"i": sid})).fetchall()
            out["khodro_adjust_factors_2024ish"] = [{"d": str(a), "f": str(b)} for a, b in af]
        # count distinct action types and symbols affected
        tot = (await c.execute(text("SELECT count(*), count(DISTINCT symbol_id) FROM corporate_action_events"))).fetchone()
        out["corporate_action_events_total"] = {"rows": int(tot[0]), "symbols": int(tot[1])}
        at = (await c.execute(text("SELECT action_type, count(*) FROM corporate_action_events GROUP BY action_type ORDER BY 2 DESC"))).fetchall()
        out["action_type_counts"] = {r[0]: int(r[1]) for r in at}
        # survivorship: symbols in latest 90 days vs symbols table vs historical
        latest = (await c.execute(text(
            "SELECT count(DISTINCT symbol) FROM brsapi_historical_daily "
            "WHERE gregorian_date >= CURRENT_DATE - INTERVAL '90 days'"))).scalar()
        allsym = (await c.execute(text("SELECT count(DISTINCT symbol) FROM brsapi_historical_daily"))).scalar()
        symtab = (await c.execute(text("SELECT count(*) FROM symbols"))).scalar()
        out["survivorship"] = {"distinct_symbols_last_90d": int(latest or 0),
                               "distinct_symbols_all_time": int(allsym or 0),
                               "symbols_table_rows": int(symtab or 0)}
        # symbols present historically but NOT in last 90 days (proxy for delisted/renamed)
        gone = (await c.execute(text(
            "SELECT count(*) FROM (SELECT DISTINCT symbol FROM brsapi_historical_daily "
            "WHERE gregorian_date < CURRENT_DATE - INTERVAL '90 days') h "
            "WHERE h.symbol NOT IN (SELECT DISTINCT symbol FROM brsapi_historical_daily "
            "WHERE gregorian_date >= CURRENT_DATE - INTERVAL '90 days')"))).scalar()
        out["survivorship"]["symbols_only_before_90d"] = int(gone or 0)
        # 10 sample rows of brsapi_historical_daily around khodro 2024 (raw)
        srows = (await c.execute(text(
            "SELECT date, gregorian_date, price_first, price_max, price_min, price_close, trade_volume "
            "FROM brsapi_historical_daily WHERE symbol=:s AND gregorian_date BETWEEN '2024-06-01' AND '2024-06-20' "
            "ORDER BY gregorian_date LIMIT 10"), {"s": "خودرو"})).fetchall()
        out["khodro_raw_sample_jun2024"] = [
            {"date_jalali": r[0], "greg": str(r[1]), "open": r[2], "high": r[3], "low": r[4],
             "close": r[5], "vol": r[6]} for r in srows]
    await eng.dispose()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open("audit_out/_tmp/partC_db.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())
