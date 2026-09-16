"""
Final batch: Run backtests + ML for all sectors, save to DB, generate report.
Fixed: proper error handling, longer timeouts, sequential execution.
"""
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

import asyncio
import contextlib
import json
import time

import requests
from sqlalchemy import text

from core.database import get_session, init_database
from core.time import now_utc

BASE_URL = "http://localhost:8000/api/v1"

SYMBOLS = [
    {"symbol": "فارس", "sector": "محصولات شیمیایی", "name": "پتروشیمی خلیج فارس"},
    {"symbol": "شبریز", "sector": "فراورده‌های نفتی", "name": "پالایش نفت تبریز"},
    {"symbol": "کگل", "sector": "استخراج کانه‌های فلزی", "name": "گل گهر"},
    {"symbol": "تیپیکو", "sector": "دارویی", "name": "سرمایه‌گذاری دارویی تامین"},
    {"symbol": "حکشتی", "sector": "حمل و نقل", "name": "کشتیرانی جمهوری اسلامی"},
    {"symbol": "شستا", "sector": "چند رشته‌ای", "name": "سرمایه‌گذاری تامین اجتماعی"},
    {"symbol": "وگردش", "sector": "بانک‌ها", "name": "بانک گردشگری"},
    {"symbol": "کالا", "sector": "واسطه‌گری مالی", "name": "بورس کالای ایران"},
    {"symbol": "اخابر", "sector": "مخابرات", "name": "مخابرات ایران"},
    {"symbol": "رمپنا", "sector": "خدمات فنی", "name": "گروه مپنا"},
    {"symbol": "فولاد", "sector": "فلزات اساسی", "name": "فولاد مبارکه"},
    {"symbol": "خودرو", "sector": "خودرو", "name": "ایران خودرو"},
    {"symbol": "فملی", "sector": "فلزات رنگین", "name": "ملی صنایع مس"},
    {"symbol": "شپنا", "sector": "پالایشگاه", "name": "پالایش نفت اصفهان"},
    {"symbol": "وبملت", "sector": "بانکی", "name": "بانک ملت"},
]

STRATEGIES = [
    "moving_average_cross", "momentum", "mean_reversion", "breakout",
    "rsi_reversion", "volatility_breakout", "half_trend",
    "squeeze_momentum", "support_resistance", "phase",
]

ML_MODELS = [
    "lightgbm", "xgboost", "catboost", "random_forest",
    "extra_trees", "hist_gradient_boosting", "bayesian_ridge", "huber_regressor",
]


def api_post(endpoint, payload, timeout=180):
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"success": False, "error": {"message": str(e)}}


def api_get(endpoint, timeout=60):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", timeout=timeout)
        return r.json()
    except Exception as e:
        return {"success": False, "error": {"message": str(e)}}


def run_backtest(symbol, strategy):
    payload = {
        "name": f"{strategy}_{symbol}",
        "symbols": [symbol],
        "strategy_type": strategy,
        "start_date": "1402-01-01",
        "end_date": "1405-01-01",
        "initial_capital": 1000000000,
        "commission_pct": 0.0035,
        "slippage_bps": 10.0,
    }
    d = api_post("/backtests/run", payload, timeout=120)
    if d.get("success") and d.get("data"):
        return {"success": True, **{k: v for k, v in d["data"].items() if k != "message"}}
    return {"success": False, "error": d.get("error", {}).get("message", "Unknown")}


def run_ml_train(symbol, model_type):
    payload = {
        "symbol": symbol,
        "model_type": model_type,
        "task_type": "regression",
        "feature_groups": ["price", "technical", "trades", "microstructure", "candlestick"],
        "train_ratio": 0.8,
    }
    d = api_post("/ml/train", payload, timeout=180)
    if d.get("success") and d.get("data"):
        msg = d["data"].get("message", "")
        r2 = mae = None
        with contextlib.suppress(Exception):
            if "R²=" in msg:
                r2 = float(msg.split("R²=")[1].split(",")[0])
            if "MAE=" in msg:
                mae = float(msg.split("MAE=")[1].split(")")[0])
        return {"success": True, "run_id": d["data"].get("run_id"), "r2": r2, "mae": mae, "message": msg}
    return {"success": False, "error": d.get("error", {}).get("message", "Unknown")}


def run_ml_inference(symbol, model_type):
    d = api_post("/ml/predict-real", {"symbol": symbol, "model_id": model_type}, timeout=60)
    if d.get("success") and d.get("data"):
        data = d["data"]
        return {
            "success": True,
            "prediction": data.get("prediction"),
            "predicted_change_pct": data.get("predicted_change_pct"),
            "confidence": data.get("confidence"),
            "last_price": data.get("last_price"),
        }
    return {"success": False, "error": d.get("error", {}).get("message", "Unknown")}


async def save_to_db(all_results):
    """Save comprehensive results to database."""
    await init_database()
    async for session in get_session():
        # Create summary table if not exists
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS batch_analysis_summary (
                id SERIAL PRIMARY KEY,
                run_date TIMESTAMP DEFAULT NOW(),
                total_symbols INT,
                total_backtests INT,
                successful_backtests INT,
                total_ml_trains INT,
                successful_ml_trains INT,
                total_ml_predictions INT,
                successful_ml_predictions INT,
                full_results JSONB
            )
        """))

        s = all_results["summary"]
        await session.execute(text("""
            INSERT INTO batch_analysis_summary
            (total_symbols, total_backtests, successful_backtests, total_ml_trains,
             successful_ml_trains, total_ml_predictions, successful_ml_predictions, full_results)
            VALUES (:ts, :tb, :sb, :tm, :sm, :tp, :sp, :fr::jsonb)
        """), {
            "ts": len(all_results["symbols"]),
            "tb": s["total_backtests"],
            "sb": s["successful_backtests"],
            "tm": s["total_ml_trains"],
            "sm": s["successful_ml_trains"],
            "tp": s["total_ml_predictions"],
            "sp": s["successful_ml_predictions"],
            "fr": json.dumps(all_results, ensure_ascii=False),
        })
        await session.commit()
        print("Results saved to DB (batch_analysis_summary)")
        break


def main():
    print("=" * 80)
    print("COMPREHENSIVE BATCH: Backtest + ML for All Sectors")
    print(f"Started: {now_utc().isoformat()}")
    print(f"Symbols: {len(SYMBOLS)}, Strategies: {len(STRATEGIES)}, ML Models: {len(ML_MODELS)}")
    print("=" * 80)

    all_results = {
        "timestamp": now_utc().isoformat(),
        "symbols": [],
        "summary": {
            "total_backtests": 0, "successful_backtests": 0,
            "total_ml_trains": 0, "successful_ml_trains": 0,
            "total_ml_predictions": 0, "successful_ml_predictions": 0,
        },
    }

    for i, sym_info in enumerate(SYMBOLS):
        symbol = sym_info["symbol"]
        sector = sym_info["sector"]
        name = sym_info["name"]

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(SYMBOLS)}] {symbol} - {name} ({sector})")
        print(f"{'='*60}")

        sym_result = {"symbol": symbol, "sector": sector, "name": name, "backtests": [], "ml_models": []}

        # Backtests
        for strategy in STRATEGIES:
            print(f"  BT {strategy}...", end=" ", flush=True)
            result = run_backtest(symbol, strategy)
            all_results["summary"]["total_backtests"] += 1
            result["strategy"] = strategy
            sym_result["backtests"].append(result)
            if result["success"]:
                all_results["summary"]["successful_backtests"] += 1
                ret = result.get("total_return_pct") or result.get("return_pct") or 0
                shp = result.get("sharpe_ratio") or result.get("sharpe") or 0
                print(f"OK Ret={ret:.2f}% Shp={shp:.2f}")
            else:
                err = str(result.get("error", ""))[:40]
                print(f"FAIL {err}")
            time.sleep(1)

        # ML Training
        for model in ML_MODELS:
            print(f"  ML {model}...", end=" ", flush=True)
            result = run_ml_train(symbol, model)
            all_results["summary"]["total_ml_trains"] += 1
            result["model_type"] = model
            sym_result["ml_models"].append(result)
            if result["success"]:
                all_results["summary"]["successful_ml_trains"] += 1
                print(f"OK R²={result.get('r2')} MAE={result.get('mae')}")
            else:
                err = str(result.get("error", ""))[:40]
                print(f"FAIL {err}")
            time.sleep(1)

        # ML Inference (best model)
        best_model = "lightgbm"
        best_r2 = -999
        for m in sym_result["ml_models"]:
            if m.get("success") and m.get("r2") is not None and m["r2"] > best_r2:
                best_r2 = m["r2"]
                best_model = m["model_type"]

        pred = run_ml_inference(symbol, best_model)
        all_results["summary"]["total_ml_predictions"] += 1
        if pred["success"]:
            all_results["summary"]["successful_ml_predictions"] += 1
        sym_result["best_model"] = best_model
        sym_result["inference"] = pred
        all_results["symbols"].append(sym_result)

        print(f"  Best ML: {best_model} -> prediction={pred.get('prediction')}, change={pred.get('predicted_change_pct')}%")

    # Save to DB
    print("\nSaving to DB...")
    asyncio.run(save_to_db(all_results))

    # Generate report
    print("\n" + "=" * 80)
    print("FINAL REPORT")
    print("=" * 80)
    s = all_results["summary"]
    print(f"Total Backtests: {s['total_backtests']} ({s['successful_backtests']} OK)")
    print(f"Total ML Trains: {s['total_ml_trains']} ({s['successful_ml_trains']} OK)")
    print(f"Total Predictions: {s['total_ml_predictions']} ({s['successful_ml_predictions']} OK)")

    print("\n--- Best ML Model per Symbol ---")
    for sym in all_results["symbols"]:
        best_ml = max([m for m in sym["ml_models"] if m.get("success") and m.get("r2") is not None],
                       key=lambda x: x["r2"], default=None)
        r2v = best_ml["r2"] if best_ml else "N/A"
        mt = best_ml["model_type"] if best_ml else "N/A"
        pred = sym.get("inference", {})
        chg = pred.get("predicted_change_pct", "N/A") if pred.get("success") else "N/A"
        conf = pred.get("confidence", "N/A") if pred.get("success") else "N/A"
        print(f"  {sym['symbol']:8s} | {mt:25s} | R²={r2v} | Pred={chg}% Conf={conf}")

    # Save JSON
    with open("C:/Users/Iran/Desktop/temce/scripts/batch_final_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("\nJSON saved: scripts/batch_final_results.json")
    print(f"Completed: {now_utc().isoformat()}")


if __name__ == "__main__":
    main()
