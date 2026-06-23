import sys
import os
# Add the project root to sys.path so we can import core if needed, but let's avoid core entirely
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import uuid

DB_PATH = "data/market.db"

def add_instrument():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get columns
    cursor.execute("PRAGMA table_info(instruments)")
    columns = [row[1] for row in cursor.fetchall()]
    print("📋 Columns:", columns)

    # Find the right column
    ins_code_col = None
    for col in columns:
        if col in ("ins_code", "instrument_code", "code", "isin"):
            ins_code_col = col
            break

    if not ins_code_col:
        print("❌ Could not find ins_code column. Please check the list above.")
        conn.close()
        return

    # Generate a simple unique ID without core.ids
    instrument_id = f"inst_{uuid.uuid4().hex[:12]}"

    query = f"""
        INSERT INTO instruments (id, symbol, name, {ins_code_col}, market_type)
        VALUES (?, ?, ?, ?, ?)
    """
    cursor.execute(query, (instrument_id, "فولاد", "فولاد مبارکه اصفهان", "IRO1FOLD0001", "bours"))
    conn.commit()
    conn.close()
    print(f"✅ Added 'فولاد' with {ins_code_col}='IRO1FOLD0001'")

if __name__ == "__main__":
    add_instrument()