"""Fix remaining uncategorized news articles."""
import _db

conn = _db.psycopg2_connect()
cur = conn.cursor()

cur.execute("SELECT id, title, summary, source FROM news_articles WHERE category IS NULL OR category = ''")
articles = cur.fetchall()
print(f"Found {len(articles)} remaining uncategorized articles")

# For articles with no source and political/general news content
political_keywords = ["مردم", "تجمع", "رهبر", "انقلاب", "حماسه", "عاشورا", "بیعت", "عزاداری", " تشییع ", "سخنرانی", "دولت", "مجلس", "وزیر", "قانون", "سیاست", "انتخابات"]
economic_keywords = ["قیمت", "نرخ", "ارز", "دلار", "طلا", "بورس", "سهام", "تورم", "اقتصاد", "بازار", "معامله", "صادرات", "واردات", "تولید", "شرکت", "بانک", "سود", "زیان"]

fixed = 0
for art in articles:
    aid, title, summary, source = art
    text = f"{title or ''} {summary or ''}".lower()

    # Check political first
    pol_score = sum(1 for kw in political_keywords if kw in text)
    eco_score = sum(1 for kw in economic_keywords if kw in text)

    if pol_score > eco_score and pol_score >= 2:
        cur.execute("UPDATE news_articles SET category = %s WHERE id = %s", ("political", aid))
        fixed += 1
    elif eco_score > 0:
        cur.execute("UPDATE news_articles SET category = %s WHERE id = %s", ("economic", aid))
        fixed += 1
    else:
        # Default to market for economy-related feed, political for others
        cur.execute("UPDATE news_articles SET category = %s WHERE id = %s", ("political", aid))
        fixed += 1

conn.commit()
print(f"Fixed {fixed} articles")

cur.execute("SELECT category, COUNT(*) FROM news_articles GROUP BY category ORDER BY COUNT(*) DESC")
print("\nFinal categories:")
for row in cur.fetchall():
    print(f"  {repr(row[0]):>20} : {row[1]}")

cur.close()
conn.close()
