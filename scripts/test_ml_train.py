import json

import requests

payload = {
    "symbol": "فولاد",
    "model_type": "lightgbm",
    "task_type": "regression",
    "feature_groups": ["price", "technical"],
    "train_ratio": 0.8
}
r = requests.post('http://localhost:8000/api/v1/ml/train', json=payload, timeout=120)
print('Status:', r.status_code)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])
