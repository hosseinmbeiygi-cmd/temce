#!/usr/bin/env python
"""Ruff error categorization and remediation plan."""

import re
from collections import Counter

with open('ruff_output.txt', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Extract error codes - ruff output format is: "CODE Description" followed by "--> filepath:line:col"
# The code appears after the start of each error entry line
# Pattern: look for codes anywhere in the content
code_pattern = r'(SIM\d{3}|B\d{3}|E\d{3}|W\d{3}|F\d{3}|TID\d{2}|SC100|UP001|UP002)'
codes = re.findall(code_pattern, content)
code_counts = Counter(codes)

print('=== Ruff Error Categorization Report ===')
print(f'Total error code mentions: {len(codes)}')
print()

print('Error Code Categories (sorted by frequency):')
for code, count in sorted(code_counts.items(), key=lambda x: -x[1]):
    print(f'  {code}: {count}')

print()
print('Top categories needing attention:')
# Focus on the most frequent categories
top_codes = [code for code, _ in code_counts.most_common(10)]
for code in top_codes:
    print(f'  - {code}: {code_counts[code]} mentions')

# Provide remediation priority
print()
print('=== Remediation Priority ===')
print('1. F841 (unused variable) - Remove assignments to unused variables')
print('2. E701 (multiple statements on one line) - Split statements onto separate lines')
print('3. SIM105 (try-except-pass) - Use contextlib.suppress()')
print('4. B007 (unused loop variable) - Rename to _variable')
print('5. E722 (bare except) - Specify exception types')
print('6. E741 (ambiguous name) - Rename variable')
print('7. SIM103 (negated condition) - Inline the condition')
print('8. C414 (unnecessary list()) - Remove list() call')
