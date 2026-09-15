import requests

r = requests.get("http://localhost:8000/api/v1/multi-market-signals?min_confidence=0.0&limit=10")
data = r.json()
print("Status:", r.status_code)
print("Success:", data["success"])
signals = data["data"]["signals"]
print("Signals count:", len(signals))
print("Summary:", data["data"]["summary"])
for s in signals[:5]:
    print(
        f"  {s.get('symbol', '?')} | {s.get('direction', '?')} | conf={s.get('confidence', 0):.2f} | score={s.get('boosted_score', 0):.2f}"
    )
