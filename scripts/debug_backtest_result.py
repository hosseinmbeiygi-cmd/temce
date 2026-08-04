"""
Debug: Check backtest result details
"""
import json

import requests

# Get the backtest result
r = requests.get('http://localhost:8000/api/v1/backtests/runs/bt_03681fb6bd8f4eb696fedcca/result', timeout=30)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])

# Also check the run details
r2 = requests.get('http://localhost:8000/api/v1/backtests/runs/bt_03681fb6bd8f4eb696fedcca', timeout=30)
d2 = r2.json()
print("\n=== Run Details ===")
print(json.dumps(d2, indent=2, ensure_ascii=False)[:1000])
