#!/usr/bin/env python
"""Remove duplicate symbols with numbers at the end from instruments table.

This script:
1. Finds symbols with numbers at the end (e.g., آباد3, آباد2)
2. Checks if the base symbol (without number) exists
3. If both exist, removes the numbered duplicate
4. Reports what was removed
"""
import re

import _db
from psycopg2.extras import DictCursor


def find_duplicates_to_remove():
    """Find symbols with numbers that have a base symbol duplicate."""
    conn = _db.psycopg2_connect(cursor_factory=DictCursor)
    cur = conn.cursor(cursor_factory=DictCursor)

    # Get all symbols
    cur.execute("SELECT id, symbol, name FROM instruments ORDER BY symbol")
    all_symbols = cur.fetchall()

    # Group by base symbol
    base_groups = {}
    for row in all_symbols:
        symbol = row['symbol']
        # Remove trailing numbers
        base = re.sub(r'\d+$', '', symbol)

        if base not in base_groups:
            base_groups[base] = []
        base_groups[base].append(row)

    # Find duplicates to remove
    to_remove = []
    for base, items in base_groups.items():
        if len(items) > 1:
            # Check if we have both base and numbered versions
            symbols = [item['symbol'] for item in items]
            has_base = base in symbols
            has_numbered = any(re.search(r'\d+$', s) for s in symbols)

            if has_base and has_numbered:
                # Remove the numbered versions, keep the base
                for item in items:
                    if re.search(r'\d+$', item['symbol']):
                        to_remove.append(item)

    return to_remove


def remove_duplicates(dry_run=True):
    """Remove duplicate symbols. Set dry_run=False to actually delete."""
    to_remove = find_duplicates_to_remove()

    print(f"تعداد نمادهای تکراری برای حذف: {len(to_remove)}\n")

    if not to_remove:
        print("هیچ نماد تکراری یافت نشد.")
        return

    print("=" * 80)
    print("نمادهایی که حذف خواهند شد:")
    print("=" * 80)

    for item in to_remove:
        print(f"  {item['symbol']:15} | {item['name']}")

    print("\n" + "=" * 80)

    if dry_run:
        print("\n⚠️  این حالت آزمایشی است. هیچ داده‌ای حذف نشد.")
        print("برای حذف واقعی، dry_run=False را تنظیم کنید.")
        return

    # Actually remove
    conn = _db.psycopg2_connect()
    cur = conn.cursor()

    removed_count = 0
    for item in to_remove:
        try:
            cur.execute("DELETE FROM instruments WHERE id = %s", (item['id'],))
            removed_count += 1
            print(f"✓ حذف شد: {item['symbol']}")
        except Exception as e:
            print(f"✗ خطا در حذف {item['symbol']}: {e}")
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ تعداد {removed_count} نماد تکراری حذف شد.")


if __name__ == "__main__":
    # First run in dry mode to see what will be removed
    print("مرحله 1: بررسی نمادهای تکراری (حالت آزمایشی)\n")
    remove_duplicates(dry_run=True)
