"""
Comprehensive Batch: Run ALL backtest strategies + ALL ML models on selected symbols
Saves results to database and generates a report.
"""
import contextlib
import json
import time

import requests

from core.time import now_utc

BASE_URL = "http://localhost:8000/api/v1"

# Selected symbols - one per major sector (cleaned, no numeric suffixes)
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

# All available backtest strategies
STRATEGIES = [
    "moving_average_cross",
    "momentum",
    "mean_reversion",
    "breakout",
    "rsi_reversion",
    "volatility_breakout",
    "half_trend",
    "squeeze_momentum",
    "support_resistance",
    "phase",
]

# All available ML models
ML_MODELS = [
    "lightgbm",
    "xgboost",
    "catboost",
    "random_forest",
    "extra_trees",
    "hist_gradient_boosting",
    "bayesian_ridge",
    "huber_regressor",
]


def run_backtest(symbol, strategy):
    """Run a single backtest."""
    payload = {
        "name": f"{strategy}_{symbol}",
        "symbols": [symbol],
        "strategy_type": strategy,
        "strategy_params": {},
        "start_date": "1402-01-01",
        "end_date": "1405-01-01",
        "initial_capital": 1000000000,
        "commission_pct": 0.0035,
        "slippage_bps": 10.0,
    }
    try:
        r = requests.post(f"{BASE_URL}/backtests/run", json=payload, timeout=120)
        d = r.json()
        if d.get("success") and d.get("data"):
            return {
                "success": True,
                "run_id": d["data"].get("id"),
                "status": d["data"].get("status"),
                "return_pct": d["data"].get("total_return_pct"),
                "sharpe": d["data"].get("sharpe_ratio"),
                "max_drawdown": d["data"].get("max_drawdown_pct"),
                "win_rate": d["data"].get("win_rate"),
                "trades": d["data"].get("total_trades"),
            }
        return {"success": False, "error": d.get("error", {}).get("message", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_ml_train(symbol, model_type):
    """Train an ML model."""
    payload = {
        "symbol": symbol,
        "model_type": model_type,
        "task_type": "regression",
        "feature_groups": ["price", "technical", "trades", "microstructure", "candlestick"],
        "train_ratio": 0.8,
    }
    try:
        r = requests.post(f"{BASE_URL}/ml/train", json=payload, timeout=180)
        d = r.json()
        if d.get("success") and d.get("data"):
            msg = d["data"].get("message", "")
            # Parse R2 and MAE from message
            r2 = None
            mae = None
            if "R²=" in msg:
                with contextlib.suppress(BaseException):
                    r2 = float(msg.split("R²=")[1].split(",")[0])
            if "MAE=" in msg:
                with contextlib.suppress(BaseException):
                    mae = float(msg.split("MAE=")[1].split(")")[0])
            return {
                "success": True,
                "run_id": d["data"].get("run_id"),
                "r2": r2,
                "mae": mae,
                "message": msg,
            }
        return {"success": False, "error": d.get("error", {}).get("message", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_ml_inference(symbol, model_type):
    """Run ML inference."""
    payload = {"symbol": symbol, "model_id": model_type}
    try:
        r = requests.post(f"{BASE_URL}/ml/predict-real", json=payload, timeout=60)
        d = r.json()
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
    except Exception as e:
        return {"success": False, "error": str(e)}


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
            "total_backtests": 0,
            "successful_backtests": 0,
            "total_ml_trains": 0,
            "successful_ml_trains": 0,
            "total_ml_predictions": 0,
            "successful_ml_predictions": 0,
        },
    }

    for i, sym_info in enumerate(SYMBOLS):
        symbol = sym_info["symbol"]
        sector = sym_info["sector"]
        name = sym_info["name"]

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(SYMBOLS)}] {symbol} - {name} ({sector})")
        print(f"{'='*60}")

        sym_result = {
            "symbol": symbol,
            "sector": sector,
            "name": name,
            "backtests": [],
            "ml_models": [],
        }

        # ── Backtests ──
        print(f"\n  --- Backtests ({len(STRATEGIES)} strategies) ---")
        for strategy in STRATEGIES:
            print(f"  Running {strategy}...", end=" ", flush=True)
            result = run_backtest(symbol, strategy)
            all_results["summary"]["total_backtests"] += 1
            if result["success"]:
                all_results["summary"]["successful_backtests"] += 1
                ret = result.get('return_pct') or 0
                shp = result.get('sharpe') or 0
                print(f"OK - Return: {ret:.2f}%, Sharpe: {shp:.2f}")
            else:
                print(f"FAIL - {result.get('error', 'Unknown')[:50]}")
            result["strategy"] = strategy
            sym_result["backtests"].append(result)
            time.sleep(0.5)  # Rate limit

        # ── ML Training ──
        print(f"\n  --- ML Training ({len(ML_MODELS)} models) ---")
        for model in ML_MODELS:
            print(f"  Training {model}...", end=" ", flush=True)
            result = run_ml_train(symbol, model)
            all_results["summary"]["total_ml_trains"] += 1
            if result["success"]:
                all_results["summary"]["successful_ml_trains"] += 1
                r2 = result.get("r2", "N/A")
                mae = result.get("mae", "N/A")
                print(f"OK - R²={r2}, MAE={mae}")
            else:
                print(f"FAIL - {result.get('error', 'Unknown')[:50]}")
            result["model_type"] = model
            sym_result["ml_models"].append(result)
            time.sleep(0.5)

        # ── ML Inference (best model) ──
        print("\n  --- ML Inference ---")
        best_model = "lightgbm"  # Default
        best_r2 = -999
        for m in sym_result["ml_models"]:
            if m.get("success") and m.get("r2") is not None:
                if m["r2"] > best_r2:
                    best_r2 = m["r2"]
                    best_model = m["model_type"]

        print(f"  Best model: {best_model} (R²={best_r2})")
        pred = run_ml_inference(symbol, best_model)
        all_results["summary"]["total_ml_predictions"] += 1
        if pred["success"]:
            all_results["summary"]["successful_ml_predictions"] += 1
            print(f"  Prediction: {pred.get('prediction', 'N/A')} ({pred.get('predicted_change_pct', 0):.2f}%) Confidence: {pred.get('confidence', 0):.1%}")
        else:
            print(f"  Inference failed: {pred.get('error', 'Unknown')[:50]}")
        sym_result["best_model"] = best_model
        sym_result["inference"] = pred

        all_results["symbols"].append(sym_result)

    # ── Save results to JSON ──
    output_path = "C:/Users/Iran/Desktop/temce/scripts/batch_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {output_path}")

    # ── Generate summary report ──
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    s = all_results["summary"]
    print(f"Total Backtests: {s['total_backtests']} ({s['successful_backtests']} succeeded)")
    print(f"Total ML Trains: {s['total_ml_trains']} ({s['successful_ml_trains']} succeeded)")
    print(f"Total ML Predictions: {s['total_ml_predictions']} ({s['successful_ml_predictions']} succeeded)")
    print()

    # Best backtest per symbol
    print("Best Backtest per Symbol:")
    for sym in all_results["symbols"]:
        best_bt = max(
            [b for b in sym["backtests"] if b.get("success")],
            key=lambda x: x.get("return_pct", -999),
            default=None,
        )
        if best_bt:
            ret = best_bt.get('return_pct') or 0
            shp = best_bt.get('sharpe') or 0
            print(f"  {sym['symbol']:8s} | {best_bt['strategy']:25s} | Return: {ret:8.2f}% | Sharpe: {shp:6.2f}")
        else:
            print(f"  {sym['symbol']:8s} | No successful backtest")

    # Best ML per symbol
    print("\nBest ML Model per Symbol:")
    for sym in all_results["symbols"]:
        best_ml = max(
            [m for m in sym["ml_models"] if m.get("success") and m.get("r2") is not None],
            key=lambda x: x.get("r2", -999),
            default=None,
        )
        if best_ml:
            r2_val = best_ml.get('r2') or 0
            mae_val = best_ml.get('mae') or 0
            print(f"  {sym['symbol']:8s} | {best_ml['model_type']:25s} | R²: {r2_val:8.4f} | MAE: {mae_val:.6f}")
        else:
            print(f"  {sym['symbol']:8s} | No successful ML model")

    # Predictions summary
    print("\nML Predictions:")
    for sym in all_results["symbols"]:
        if sym.get("inference", {}).get("success"):
            pred = sym["inference"]
            direction = "📈" if pred.get("predicted_change_pct", 0) > 0 else "📉"
            print(f"  {sym['symbol']:8s} | {direction} {pred.get('predicted_change_pct', 0):+.2f}% | Confidence: {pred.get('confidence', 0):.1%} | Best: {sym.get('best_model', 'N/A')}")

    print(f"\nCompleted: {now_utc().isoformat()}")


if __name__ == "__main__":
    main()
