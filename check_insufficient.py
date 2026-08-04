import json

with open('train_all_results.json', encoding='utf-8') as f:
    data = json.load(f)
print("=== Insufficient Data Symbols ===")
for item in data.get("insufficient_data", []):
    print(f"  {item['symbol']}: {item['rows']} rows")
print(f"\nTotal: {len(data.get('insufficient_data', []))} symbols")
