# scripts/check_table.py
import sqlite3

conn = sqlite3.connect("data/market.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(quotes)")
columns = cursor.fetchall()
print("📋 ستون‌های جدول quotes:")
for col in columns:
    print(f"   {col[1]} ({col[2]})")
conn.close()