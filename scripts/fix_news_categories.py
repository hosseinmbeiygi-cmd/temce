"""Check and fix news categories in the database."""
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import text

import core.database as _db

# Category mapping: Persian/raw RSS categories -> standard categories
_CATEGORY_KEYWORDS = {
    "market": [
        "بورس", "سهام", "شاخص", "معامله", "فرابورس", "سازمان بورس",
        "طلا", "ارز", "دلار", "رمزارز", "کریپتو", "بازار سرمایه",
        "عرضه اولیه", "سبد", "صندوق",
    ],
    "companies": [
        "شرکت", "خودرو", "فولاد", "پتروشیمی", "بانک",
        "صنعت", "معدن", "تولید", "صادرات", "واردات", "سرمایه‌گذاری",
        "انرژی", "نفت", "گاز", "پالایش", "فناوری", "تکنولوژی",
        "استارتاپ", "خودرویی", "دارویی", "غذایی", "سیمان",
    ],
    "economic": [
        "اقتصاد", "تورم", "نرخ بهره", "نقدینگی", "بودجه",
        "مسکن", "کلان", "رشد اقتصادی",
    ],
    "political": [
        "سیاست", "مجلس", "وزیر", "تحریم", "برجام",
        "دیپلماسی", "حکمرانی", "سیاسی", "قانون",
    ],
    "international": [
        "بین‌الملل", "جهان", "آمریکا", "اروپا", "چین", "روسیه",
        "اوپک", "بین‌المللی",
    ],
}


def classify(title: str, summary: str, source: str) -> str:
    combined = f"{title} {summary} {source}".lower()
    best_cat, best_score = "", 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in combined)
        if score > best_score:
            best_score = score
            best_cat = cat
    if not best_cat:
        sl = source.lower()
        if any(x in sl for x in ["bourse", "gold", "crypto", "market"]):
            best_cat = "market"
        elif any(x in sl for x in ["industry", "energy", "auto", "companies", "tech", "mining", "prog_"]):
            best_cat = "companies"
        elif any(x in sl for x in ["macro", "housing", "econ"]):
            best_cat = "economic"
    return best_cat


async def check():
    await _db.init_database()
    async with _db.async_session_factory() as session:
        result = await session.execute(
            text("SELECT category, COUNT(*) as cnt FROM news_articles GROUP BY category ORDER BY cnt DESC")
        )
        rows = result.fetchall()
        print("=== Current categories ===")
        for row in rows:
            print(f"  {repr(row[0]):>30} : {row[1]}")

        # Count empty categories
        empty = next((r[1] for r in rows if not r[0]), 0)
        print(f"\n  Articles with empty category: {empty}")

        if empty > 0:
            print("\n=== Fixing empty categories ===")
            result2 = await session.execute(
                text("SELECT id, title, summary, source FROM news_articles WHERE category = '' OR category IS NULL")
            )
            articles = result2.fetchall()
            fixed = 0
            for art in articles:
                cat = classify(art[1] or "", art[2] or "", art[3] or "")
                if cat:
                    await session.execute(
                        text("UPDATE news_articles SET category = :cat WHERE id = :id"),
                        {"cat": cat, "id": art[0]}
                    )
                    fixed += 1
            await session.commit()
            print(f"  Fixed {fixed} articles")

            # Show new distribution
            result3 = await session.execute(
                text("SELECT category, COUNT(*) as cnt FROM news_articles GROUP BY category ORDER BY cnt DESC")
            )
            print("\n=== Updated categories ===")
            for row in result3.fetchall():
                print(f"  {repr(row[0]):>30} : {row[1]}")


asyncio.run(check())
