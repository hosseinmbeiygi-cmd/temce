"""Concurrency proof: N parallel evaluate_and_trigger vs one alert with cooldown.

Uses synthetic alert (__QATEST__ symbol), counts history rows, cleans up.
Run: python qa/concurrency_proof.py [workers=30]
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SYM = "__QATEST_RACE__"

async def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    from core.database import init_database
    await init_database()
    from sqlalchemy import select, text

    from core.database import async_session_factory
    from core.ids import new_id
    from models.alert import AlertHistoryModel, AlertModel
    from services.alert_service import AlertService

    async with async_session_factory() as s:
        await s.execute(text(
            "DELETE FROM alert_history WHERE alert_id LIKE 'qalr%'"))
        await s.execute(text("DELETE FROM alerts WHERE id LIKE 'qalr%'"))
        await s.commit()
        aid = "qalr" + new_id("t")[:16]
        s.add(AlertModel(
            id=aid, instrument_id="", symbol=SYM, alert_type="price_above",
            condition=json.dumps({"field": "price", "operator": "gte",
                                  "threshold": 100, "cooldown_minutes": 60}),
            channels=json.dumps(["console"]), enabled=True,
            description="qa race probe"))
        await s.commit()

    async def fire(_):
        async with async_session_factory() as s:
            svc = AlertService(s)
            try:
                r = await svc.evaluate_and_trigger("", SYM, "price", 150.0)
                await s.commit()
                return len(r)
            except Exception:
                try:
                    await s.rollback()
                except Exception:
                    pass
                return -1

    res = await asyncio.gather(*[fire(i) for i in range(workers)])
    async with async_session_factory() as s:
        n = (await s.execute(
            select(text("count(*)")).select_from(AlertHistoryModel)
            .where(AlertHistoryModel.alert_id == aid))).scalar()
        trig = (await s.execute(
            select(AlertModel.triggered_count).where(AlertModel.id == aid)
            )).scalar()
        await s.execute(text("DELETE FROM alert_history WHERE alert_id=:a"), {"a": aid})
        await s.execute(text("DELETE FROM alerts WHERE id=:a"), {"a": aid})
        await s.commit()
    print(f"workers={workers} fired_sum={sum(max(0, x) for x in res)} "
          f"history_rows={n} triggered_count={trig}")
    print("RACE_OK_SINGLE" if n == 1 else "RACE_DOUBLE_FIRE")

asyncio.run(main())
