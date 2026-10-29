"""Part G — data inventory (read-only)."""
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
        # hypertables
        try:
            h = (await c.execute(text("SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY 1"))).fetchall()
            out["hypertables"] = [r[0] for r in h]
        except Exception as e:
            out["hypertables"] = f"N/A ({type(e).__name__})"
        # knowledge_time columns
        kt = (await c.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE column_name IN ('knowledge_time','known_at','valid_from','valid_to','effective_date','published_at') "
            "ORDER BY 1"))).fetchall()
        out["knowledge_time_like_columns"] = [f"{a}.{b}" for a, b in kt]
        # created_at/updated_at presence for key tables
        for t in ("brsapi_historical_daily", "brsapi_historical_real_legal", "corporate_action_events", "daily_adjust_factors"):
            cols = (await c.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name=:t"), {"t": t})).fetchall()
            names = [r[0] for r in cols]
            out[f"has_created_updated_{t}"] = {
                "created_at": "created_at" in names, "updated_at": "updated_at" in names,
            }
        # sample rows
        samples = {}
        for t, order in (("brsapi_historical_daily", "gregorian_date DESC"),
                         ("brsapi_historical_real_legal", "gregorian_date DESC"),
                         ("daily_adjust_factors", "trade_date DESC"),
                         ("corporate_action_events", "ex_date DESC")):
            try:
                rows = (await c.execute(text(f"SELECT * FROM {t} ORDER BY {order} LIMIT 5"))).fetchall()
                keys = [d[0] for d in (await c.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=:t ORDER BY ordinal_position"),
                    {"t": t})).fetchall()]
                samples[t] = [dict(zip(keys, [str(x) for x in r], strict=False)) for r in rows]
            except Exception as e:
                samples[t] = f"ERR {e}"
        out["samples"] = samples
        # row counts + ranges for key tables
        for t, dcol in (("brsapi_historical_daily", "gregorian_date"),
                        ("brsapi_historical_real_legal", "gregorian_date"),
                        ("daily_adjust_factors", "trade_date"),
                        ("brsapi_nav_records", None), ("brsapi_codal_announcements", None),
                        ("brsapi_symbol_details", None), ("brsapi_gold_coin_history", None),
                        ("brsapi_currency_history", None), ("brsapi_option_snapshots", None)):
            try:
                n = (await c.execute(text(f"SELECT count(*) FROM {t}"))).scalar()
                rng = None
                if dcol:
                    r = (await c.execute(text(f"SELECT min({dcol}), max({dcol}) FROM {t}"))).fetchone()
                    rng = [str(r[0]), str(r[1])]
                out[f"table_{t}"] = {"rows": int(n or 0), "range": rng}
            except Exception as e:
                out[f"table_{t}"] = f"ERR {type(e).__name__}"
    await eng.dispose()
    # Print with ASCII-safe encoding
    import sys
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=True, indent=2).encode('ascii', 'replace'))
    with open("audit_out/_tmp/partG.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())
