import re
from collections import Counter

with open('ruff_output.txt', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Extract error codes (SIM105, B007, E701, etc.)
pattern = r'SIM\d{3}|B\d{3}|E\d{3}|W\d{3}|F\d{3}|TID\d{2}|SC100|UP0'
codes = re.findall(pattern, content)
code_counts = Counter(codes)

print('Error Code Categories:')
for code, count in sorted(code_counts.items(), key=lambda x: -x[1]):
    print(f'  {code}: {count}')
print(f'\nTotal errors: {sum(code_counts.values())}')
