"""Fix empty news categories using psycopg2."""
import _db

conn = _db.psycopg2_connect()
cur = conn.cursor()

cur.execute("SELECT id, title, summary, source FROM news_articles WHERE category IS NULL OR category = ''")
articles = cur.fetchall()
print(f"Found {len(articles)} articles to fix")

cats = {
    "market": ["بورس", "سهام", "شاخص", "معامله", "فرابورس", "طلا", "ارز", "دلار", "رمزارز", "کریپتو", "بازار سرمایه", "عرضه اولیه", "صندوق"],
    "companies": ["شرکت", "خودرو", "فولاد", "پتروشیمی", "بانک", "صنعت", "معدن", "تولید", "صادرات", "واردات", "سرمایه گذاری", "انرژی", "نفت", "گاز", "پالایش", "فناوری", "تکنولوژی", "استارتاپ"],
    "economic": ["اقتصاد", "تورم", "نرخ بهره", "نقدینگی", "بودجه", "مسکن", "کلان", "رشد اقتصادی"],
    "political": ["سیاست", "مجلس", "وزیر", "تحریم", "برجام", "دیپلماسی", "حکمرانی", "سیاسی", "قانون"],
    "international": ["بین الملل", "جهان", "آمریکا", "اروپا", "چین", "روسیه", "اوپک"],
}

fixed = 0
for art in articles:
    aid, title, summary, source = art
    combined = f"{title or ''} {summary or ''} {source or ''}".lower()
    best_cat, best_score = "", 0
    for cat, kws in cats.items():
        score = sum(1 for kw in kws if kw.lower() in combined)
        if score > best_score:
            best_score = score
            best_cat = cat
    if not best_cat and source:
        sl = source.lower()
        if any(x in sl for x in ["bourse", "gold", "crypto", "market"]):
            best_cat = "market"
        elif any(x in sl for x in ["industry", "energy", "auto", "companies", "tech", "mining", "prog_"]):
            best_cat = "companies"
        elif any(x in sl for x in ["macro", "housing", "econ"]):
            best_cat = "economic"
    if best_cat:
        cur.execute("UPDATE news_articles SET category = %s WHERE id = %s", (best_cat, aid))
        fixed += 1

conn.commit()
print(f"Fixed {fixed} articles")

cur.execute("SELECT category, COUNT(*) FROM news_articles GROUP BY category ORDER BY COUNT(*) DESC")
print("Updated categories:")
for row in cur.fetchall():
    print(f"  {repr(row[0]):>30} : {row[1]}")

cur.close()
conn.close()
