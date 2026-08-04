import json

import requests

# Test with all feature groups
payload = {
    "symbol": "فولاد",
    "model_type": "lightgbm",
    "task_type": "regression",
    "feature_groups": ["price", "technical", "trades", "microstructure", "candlestick"],
    "train_ratio": 0.8
}
print("=== Training with all feature groups ===")
r = requests.post('http://localhost:8000/api/v1/ml/train', json=payload, timeout=120)
d = r.json()
print('Success:', d.get('success'))
if d.get('data'):
    print('Message:', d['data'].get('message'))
else:
    print('Error:', d.get('error'))

# Test inference
print("\n=== Testing inference ===")
payload2 = {
    "symbol": "فولاد",
    "model_id": d.get('data', {}).get('run_id', '')
}
r2 = requests.post('http://localhost:8000/api/v1/ml/predict-real', json=payload2, timeout=60)
d2 = r2.json()
print(json.dumps(d2, indent=2, ensure_ascii=False)[:1000])
