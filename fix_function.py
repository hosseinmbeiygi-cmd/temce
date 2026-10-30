import sys

# Read the file
with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the _build_sectors function and fix it
output = []
in_function = False
function_start = -1
function_end = -1

for i, line in enumerate(lines):
    if '_build_sectors' in line and 'def _build_sectors' in line:
        in_function = True
        function_start = i
    if in_function:
        output.append(line)
        # Check if we've left the function (next function or end of relevant code)
        if i > function_start and line.strip().startswith('async def') and i > function_start + 10:
            in_function = False
            function_end = i
            break

if function_start >= 0:
    # Reconstruct the function with fixed avg_change calculation
    new_function = '''    def _build_sectors(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:\n        sectors: dict[str, dict[str, Any]] = {}\n        for s in snapshots:\n            sector = s.get("sector_name") or s.get("industry") or s.get("sector", "\u0633\u0627\u0631\u06cc")\n            if sector not in sectors:\n                sectors[sector] = {"name": sector, "count": 0, "total_value": 0, "avg_change": 0}\n            sectors[sector]["count"] += 1\n            sectors[sector]["total_value"] += s.get("trade_value", 0) or 0\n        result = list(sectors.values())\n        # Calculate actual avg_change from the data\n        if result:\n            # Group snapshots by sector and calculate average change\n            sector_changes: dict[str, list[float]] = {}\n            for s in snapshots:\n                sec = s.get("sector_name") or s.get("industry") or s.get("sector", "\u0633\u0627\u0631\u06cc")\n                change = s.get("price_last_change_pct") or 0\n                if sec not in sector_changes:\n                    sector_changes[sec] = []\n                sector_changes[sec].append(change)\n            for sec in result:\n                if sec["name"] in sector_changes and sector_changes[sec["name"]]:\n                    changes = sector_changes[sec["name"]]\n                    sec["avg_change"] = round(sum(changes) / len(changes), 2)\n                else:\n                    sec["avg_change"] = 0\n        return result\n'''
    
    # Replace the function
    new_lines = lines[:function_start] + [new_function] + lines[function_end:]
    
    with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Function fixed")
else:
    print("Function not found")
