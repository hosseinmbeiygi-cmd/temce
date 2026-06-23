import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from httpx import AsyncClient, ASGITransport
from apps.api.app import app

async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/v1/backtests/run", json={
            "name": "T", "symbols": ["فولاد"],
            "strategy_type": "moving_average_cross",
            "strategy_params": {"fast_period": 5, "slow_period": 20},
            "start_date": "2025-03-01", "end_date": "2025-06-01",
            "initial_capital": 1000000000,
        })
        j = r.json()
        print("RUN success:", j.get("success"), "id:", j.get("data", {}).get("id"))
        rid = j.get("data", {}).get("id")
        if rid:
            r2 = await c.get(f"/api/v1/backtests/runs/{rid}/result")
            j2 = r2.json()
            print("Result response status:", r2.status_code)
            print("Result success:", j2.get("success"))
            print("Raw result keys:", list(j2.keys()))
            d = j2.get("data")
            if d is None:
                print("Result data is None!")
                print("Full response:", j2)
            else:
                print("return:", d.get("total_return_pct"), "%")
                print("trades:", d.get("total_trades"))
                print("sharpe:", d.get("sharpe_ratio"))

        r3 = await c.post("/api/v1/ml/predict/linear_regression", json={"price_close": 38500, "volume": 1000000})
        j3 = r3.json()
        print("ML predict success:", j3.get("success"))
        if j3.get("data"):
            print("prediction:", j3["data"].get("prediction"), "confidence:", j3["data"].get("confidence"))

asyncio.run(test())

