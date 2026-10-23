import asyncio, io, json, sys, time
sys.path.insert(0, "C:/Users/Iran/Desktop/temce")
from datetime import date
import core.database as d
from services.backtest_service import BacktestService

SYMBOLS = ["\u0648\u067e\u062a\u0631\u0648", "\u0648\u0633\u0627\u062e\u062a", "\u062e\u0648\u062f\u0631\u0648", "\u0648\u0633\u067e\u0647", "\u062e\u0628\u0647\u0645\u0646"]
START = date(2024, 1, 1)
END = date(2024, 12, 29)
CAPITAL = 1_000_000_000

async def one(svc, sym):
    t0 = time.time()
    try:
        r = await svc.run_backtest(
            name=f"ml_signal-{sym}-step1",
            symbols=[sym],
            strategy_type="ml_signal",
            start_date=START, end_date=END, capital=CAPITAL,
        )
        el = round(time.time() - t0, 1)
        if r.success:
            full = await svc.get_result(r.value.id)
            m = full.value.get("metrics", {}) if (full.success and full.value) else {}
            return {"symbol": sym, "status": "ok", "elapsed_sec": el,
                    "run_id": r.value.id, "metrics": m}
        return {"symbol": sym, "status": "fail", "elapsed_sec": el, "error": str(r.error)}
    except Exception as e:
        return {"symbol": sym, "status": "error", "elapsed_sec": round(time.time()-t0,1),
                "error": f"{type(e).__name__}: {e}"}

async def main():
    await d.init_database()
    svc = BacktestService()
    out = {"period": f"{START} to {END}", "capital": CAPITAL,
           "strategy_type": "ml_signal", "results": []}
    for s in SYMBOLS:
        res = await one(svc, s)
        out["results"].append(res)
        print(json.dumps(res, ensure_ascii=False))
    with io.open("C:/Users/Iran/AppData/Local/Temp/opencode/step1_raw.json",
                 "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("SAVED step1_raw.json")

asyncio.run(main())
