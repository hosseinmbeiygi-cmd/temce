import json

import requests

# Test inference with correct model_id (model_type, not run_id)
payload = {"symbol": "فولاد", "model_id": "lightgbm"}
print("=== Testing inference with model_id=lightgbm ===")
r = requests.post("http://localhost:8000/api/v1/ml/predict-real", json=payload, timeout=60)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False)[:1500])

