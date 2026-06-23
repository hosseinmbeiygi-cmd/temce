import sqlite3
try:
    conn = sqlite3.connect("data/market.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'") # Wait, I should use single quotes inside double quotes
except Exception as e:
    print(e)

