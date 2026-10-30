#!/usr/bin/env python3
import re

with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the sector line - look for the pattern sector = s.get("sector_name") or s.get("industry",
old_pattern = r'sector = s\.get\("sector_name"\) or s\.get\("industry"\)'
new_line = 'sector = s.get("sector_name") or s.get("industry") or s.get("sector", "ساری")'

# Try to find and replace
content = re.sub(
    r'sector = s\.get\("sector_name"\) or s\.get\("industry"\)[^}]*',
    new_line,
    content
)

with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")