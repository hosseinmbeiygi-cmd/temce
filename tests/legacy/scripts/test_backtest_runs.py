import json

import requests

r = requests.get("http://localhost:8000/api/v1/backtests/runs?limit=5", timeout=30)
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False)[:1000])

