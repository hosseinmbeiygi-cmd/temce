#!/usr/bin/env python
"""Find duplicate symbols in instruments table using psycopg2."""
import re

import _db


def find_duplicates():
    conn = _db.psycopg2_connect()
    cur = conn.cursor()

    # Get all symbols
    cur.execute("SELECT id, symbol, name FROM instruments ORDER BY symbol")
    all_symbols = cur.fetchall()

    print(f"تعداد کل نمادها: {len(all_symbols)}\n")

    # Group by base symbol (remove numbers and suffixes)
    base_groups = {}

    for _id, symbol, name in all_symbols:
        # Remove trailing numbers and suffixes like ح, ج, الف
        base = symbol
        # Remove trailing numbers
        base = re.sub(r'\d+$', '', base)
        # Remove single Persian letter suffixes (ح, ج, الف, etc.)
        base = re.sub(r'[حجف]$', '', base)

        if base not in base_groups:
            base_groups[base] = []
        base_groups[base].append((_id, symbol, name))

    # Find groups with more than one symbol
    duplicates = {k: v for k, v in base_groups.items() if len(v) > 1}

    print(f"تعداد گروه‌های تکراری: {len(duplicates)}\n")
    print("=" * 80)

    for base, items in sorted(duplicates.items()):
        print(f"\nگروه: {base}")
        print("-" * 40)
        for _id, symbol, name in items:
            print(f"  {symbol:15} | {name}")

    # Also find symbols ending with numbers
    print("\n\n" + "=" * 80)
    print("نمادهای با شماره انتهایی:")
    print("=" * 80)

    numbered = [(_id, sym, name) for _id, sym, name in all_symbols if re.search(r'\d+$', sym)]
    for _id, symbol, name in numbered[:50]:  # Show first 50
        print(f"  {symbol:15} | {name}")

    # Find symbols with Persian letter suffixes
    print("\n\n" + "=" * 80)
    print("نمادهای با پسوند حروف فارسی (ح, ج, الف):")
    print("=" * 80)

    persian_suffix = [(_id, sym, name) for _id, sym, name in all_symbols if re.search(r'[حجف]$', sym)]
    for _id, symbol, name in persian_suffix[:50]:  # Show first 50
        print(f"  {symbol:15} | {name}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    find_duplicates()
