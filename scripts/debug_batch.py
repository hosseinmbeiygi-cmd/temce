"""
Debug: Check why backtests return 0% and ML inference fails
"""
import json

import requests

# 1. Check backtest data loading
print("=== 1. Backtest Data Stats ===")
r = requests.get('http://localhost:8000/api/v1/backtests/data/stats', timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:1000])

# 2. Check available symbols
print("\n=== 2. Available Symbols ===")
r = requests.get('http://localhost:8000/api/v1/backtests/data/symbols?limit=10', timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:1000])

# 3. Run a single backtest with debug
print("\n=== 3. Single Backtest Debug ===")
payload = {
    "name": "debug_test",
    "symbols": ["فولاد"],
    "strategy_type": "moving_average_cross",
    "start_date": "1402-01-01",
    "end_date": "1405-01-01",
    "initial_capital": 1000000000,
}
r = requests.post('http://localhost:8000/api/v1/backtests/run', json=payload, timeout=120)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False)[:1500])

# 4. Check ML data preview
print("\n=== 4. ML Data Preview ===")
r = requests.get('http://localhost:8000/api/v1/ml/data-preview/فولاد', timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:1000])

# 5. Check ML models available
print("\n=== 5. ML Models ===")
r = requests.get('http://localhost:8000/api/v1/ml/models', timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:1000])
