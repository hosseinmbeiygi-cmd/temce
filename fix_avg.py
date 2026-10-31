
with open('/c/Users/Iran/Desktop/temce/services/market_service.py', encoding='utf-8') as f:
    content = f.read()

# Find and replace the _build_sectors function's avg_change calculation
old_block = """result = list(sectors.values())
        for sec in result:
            sec["avg_change"] = 0
        return result"""

new_block = """result = list(sectors.values())
        # Calculate actual avg_change from the data
        if result:
            # Group snapshots by sector and calculate average change
            sector_changes: dict[str, list[float]] = {}
            for s in snapshots:
                sec = s.get("sector_name") or s.get("industry") or s.get("sector", "ساری")
                change = s.get("price_last_change_pct") or 0
                if sec not in sector_changes:
                    sector_changes[sec] = []
                sector_changes[sec].append(change)
            for sec in result:
                if sec["name"] in sector_changes and sector_changes[sec["name"]]:
                    changes = sector_changes[sec["name"]]
                    sec["avg_change"] = round(sum(changes) / len(changes), 2)
                else:
                    sec["avg_change"] = 0
        return result"""

content = content.replace(old_block, new_block)

with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
