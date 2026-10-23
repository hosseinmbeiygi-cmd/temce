"""Part D — re-derive the goal-doc numbers from the DB (SELECT only)."""
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
        for tbl in ("signal_accuracy", "paper_trades", "paper_equity_history", "ml_models",
                    "backtest_runs", "backtest_trades"):
            try:
                n = (await c.execute(text(f"SELECT count(*) FROM {tbl}"))).scalar()
                out[f"count_{tbl}"] = int(n or 0)
            except Exception as e:
                out[f"count_{tbl}"] = f"ERR {e}"

        # signal_accuracy columns
        try:
            cols = (await c.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='signal_accuracy' "
                "ORDER BY ordinal_position"))).fetchall()
            out["signal_accuracy_columns"] = [r[0] for r in cols]
        except Exception as e:
            out["signal_accuracy_columns"] = f"ERR {e}"

        # direction accuracy
        try:
            row = (await c.execute(text(
                "SELECT count(*), sum(case when direction_correct then 1 else 0 end), "
                "avg(actual_return_pct) FROM signal_accuracy"))).fetchone()
            out["signal_accuracy_stats"] = {
                "total": int(row[0] or 0),
                "correct": int(row[1] or 0) if row[1] is not None else None,
                "accuracy_pct": round(100.0 * (row[1] or 0) / row[0], 2) if row[0] else None,
                "avg_return_pct": round(float(row[2]), 3) if row[2] is not None else None,
            }
        except Exception as e:
            out["signal_accuracy_stats"] = f"ERR {e}"

        # paper trades
        try:
            row = (await c.execute(text("SELECT count(*) FROM paper_trades"))).scalar()
            out["paper_trades_total"] = int(row or 0)
        except Exception as e:
            out["paper_trades_total"] = f"ERR {e}"
    await eng.dispose()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open("audit_out/_tmp/partD_db.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())
