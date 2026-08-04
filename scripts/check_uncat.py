import _db

conn = _db.psycopg2_connect()
cur = conn.cursor()
cur.execute("SELECT title, source FROM news_articles WHERE category IS NULL OR category = '' LIMIT 15")
for row in cur.fetchall():
    print(f"  source={repr(row[1]):>25} | {row[0][:70]}")
cur.close()
conn.close()
