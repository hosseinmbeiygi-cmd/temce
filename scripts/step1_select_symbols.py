"""
Step 1: Get all sectors and select top symbol from each sector
"""
import contextlib
import json

import requests

# Get enriched heatmap data
r = requests.get('http://localhost:8000/api/v1/market/enriched-heatmap', timeout=30)
data = r.json()
print(f"Success: {data.get('success')}")
items = data.get('data', [])
print(f"Total items: {len(items)}")

if items:
    print(f"\nFirst item keys: {list(items[0].keys())}")
    print(f"First item: {json.dumps(items[0], ensure_ascii=False)[:500]}")

# Group by sector
sector_symbols = {}
for item in items:
    sector = item.get('sector', 'Unknown') or 'Unknown'
    trade_value = 0
    for key in ['trade_value', 'value', 'trade_amount']:
        if key in item:
            with contextlib.suppress(BaseException):
                trade_value = float(item[key] or 0)
            break

    symbol = item.get('symbol', '')
    name = item.get('name', '')
    if sector not in sector_symbols or trade_value > sector_symbols[sector]['trade_value']:
        sector_symbols[sector] = {
            'symbol': symbol,
            'name': name,
            'trade_value': trade_value,
            'sector': sector
        }

# Sort by trade value
sorted_sectors = sorted(sector_symbols.items(), key=lambda x: x[1]['trade_value'], reverse=True)

print("\n=== Top Symbol Per Sector ===")
selected = []
for sector, info in sorted_sectors[:15]:
    if info['symbol']:
        tv = info['trade_value']
        print(f"  {sector}: {info['symbol']} ({info['name']}) - TV: {tv:,.0f}")
        selected.append(info)

# Save
with open('C:/Users/Iran/Desktop/temce/scripts/selected_symbols.json', 'w', encoding='utf-8') as f:
    json.dump(selected, f, ensure_ascii=False, indent=2)

print(f"\nSelected {len(selected)} symbols")
