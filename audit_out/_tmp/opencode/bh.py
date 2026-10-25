import asyncio
import sys

sys.path.insert(0, "C:/Users/Iran/Desktop/temce")
from datetime import date

import core.database as d
from services.backtest_service import BacktestService


async def main():
    await d.init_database()
    bars = await BacktestService()._load_historical_data(
        "\u062e\u0648\u062f\u0631\u0648", date(2024, 1, 1), date(2024, 12, 29), source="auto")
    c = [b["close"] for b in bars]
    print("n:" + str(len(bars)))
    print("first:" + str(c[0]))
    print("last:" + str(c[-1]))
    print("bh_pct:" + str(round((c[-1] - c[0]) / c[0] * 100, 4)))

asyncio.run(main())
