#!/usr/bin/env python
"""
DEPRECATED — Use scripts/import_data.py instead.

This file has been replaced by scripts/import_data.py which supports
CSV, JSON, and Excel (.xlsx) formats with proper database persistence.

Usage:
    python scripts/import_data.py path/to/symbols.csv
    python scripts/import_data.py path/to/symbols.json
    python scripts/import_data.py path/to/symbols.xlsx
"""
import sys
print("DEPRECATED: Use 'python scripts/import_data.py <file>' instead (supports CSV, JSON, Excel)")
sys.exit(1)
