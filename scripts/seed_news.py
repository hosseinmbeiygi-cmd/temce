#!/usr/bin/env python
"""Seed the news_articles table from real Iranian RSS feeds + BrsApi fallback.

Run once to populate the database with market & economic news for the frontend.

Usage:
    python scripts/seed_news.py                          # Fetch all, save all
    python scripts/seed_news.py --dry-run                 # Show what would be saved
    python scripts/seed_news.py --sources mehr,tasnim     # Specific sources
    python scripts/seed_news.py --force                   # Re-fetch even if DB has news
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from core.logging import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed news_articles table from Iranian RSS feeds + BrsApi fallback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--sources", type=str, default=None,
                        help="Comma-separated source keys: mehr, tasnim, irna, isna, fars, donya-eqtesad (default: all)")
    parser.add_argument("--limit", type=int, default=30,
                        help="Max articles per feed URL (default: 30)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and display only — do NOT save")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch even if news_articles already has data")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Minimal output")
    return parser.parse_args()


async def _count_news(session) -> int:
    """Return how many news articles are already in the database."""
    from sqlalchemy import select, func
    from models.news import NewsArticleModel
    result = await session.execute(select(func.count(NewsArticleModel.id)))
    return result.scalar() or 0


async def _seed_from_rss(args, session) -> dict:
    """Fetch news from RSS feeds and save to database."""
    from services.news_ingestion import NewsIngestionService
    from services.news_service import NewsService
    from repositories.news_repository import NewsRepository

    repo = NewsRepository(session=session)
    news_service = NewsService(repo=repo)
    ingestion = NewsIngestionService(news_service=news_service, session=session)

    sources = None
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    if not args.quiet:
        print(f"\n  📡  Fetching from RSS feeds (sources: {sources or 'ALL'})...")

    stats = await ingestion.ingest(
        sources=sources,
        limit_per_source=args.limit,
        min_content_length=30,
        save=not args.dry_run,
        verbose=not args.quiet,
        skip_dedup=False,
        skip_sentiment=False,
        top_n=10,
    )

    return stats


async def _seed_from_brsapi(args, session) -> int:
    """Fallback: generate market-news items from brsapi_symbol_snapshots data.

    Only runs when RSS feeds return 0 articles OR when --force is passed.
    Creates brief news items from top gainers/losers and market summary data.
    """
    from core.ids import new_id
    from domain.news.news_item import NewsItem
    from services.news_service import NewsService
    from repositories.news_repository import NewsRepository
    from sqlalchemy import text

    repo = NewsRepository(session=session)
    news_service = NewsService(repo=repo)

    if not args.quiet:
        print(f"\n  📊  Generating market news from BrsApi data...")

    # Fetch top movers from symbol_snapshots
    result = await session.execute(text("""
        SELECT symbol, name, price_last, price_last_change_pct,
               trade_volume, trade_value, market
        FROM brsapi_symbol_snapshots
        WHERE price_last_change_pct IS NOT NULL
        ORDER BY ABS(price_last_change_pct) DESC
        LIMIT 30
    """))
    rows = result.fetchall()

    if not rows:
        if not args.quiet:
            print("  ⚠️  No market data available for news generation")
        return 0

    saved = 0
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    generated: list[dict] = []

    # Group by market for category assignment
    for row in rows:
        symbol = row.symbol or ""
        name = row.name or symbol
        change = row.price_last_change_pct or 0
        volume = row.trade_volume or 0
        value = row.trade_value or 0
        market = row.market or ""

        if abs(change) >= 2:
            direction = "صعود" if change > 0 else "نزول"
            title = f"{direction} {abs(change):.1f}% قیمت {name} در بازار {market}"
            summary = (
                f"نماد {symbol} ({name}) در معاملات امروز با {direction} "
                f"{abs(change):.1f} درصدی به قیمت {row.price_last or 0:,} ریال رسید. "
                f"حجم معاملات: {volume:,} سهم به ارزش {value:,.0f} ریال."
            )
            generated.append({
                "title": title,
                "summary": summary,
                "content": summary,
                "symbols": [symbol],
                "category": "market",
                "source": "brsapi",
                "sentiment_score": change / 100.0,
                "sentiment_label": "positive" if change > 0 else "negative",
                "publish_date": now,
            })

    # Add some general market summary items
    total_stocks = len(rows)
    gainers = sum(1 for r in rows if (r.price_last_change_pct or 0) > 0)
    losers = sum(1 for r in rows if (r.price_last_change_pct or 0) < 0)

    if total_stocks > 0:
        generated.append({
            "title": f"خلاصه بازار {today_str} — {gainers} نماد مثبت، {losers} نماد منفی",
            "summary": f"در پایان معاملات امروز، از {total_stocks} نماد مورد بررسی، "
                       f"{gainers} نماد مثبت و {losers} نماد منفی بودند.",
            "content": "",
            "symbols": [],
            "category": "market",
            "source": "brsapi",
            "sentiment_score": (gainers - losers) / max(total_stocks, 1),
            "sentiment_label": "positive" if gainers > losers else "negative",
            "publish_date": now,
        })

    # Save generated items
    for item_data in generated:
        if args.dry_run:
            continue
        try:
            item = NewsItem(
                id=new_id("news"),
                title=item_data["title"],
                content=item_data["content"],
                summary=item_data["summary"],
                source=item_data["source"],
                url="",
                publish_date=item_data["publish_date"],
                category=item_data["category"],
                sentiment=item_data["sentiment_score"],
                sentiment_label=item_data["sentiment_label"],
                symbols=item_data["symbols"],
                data_source="market_data",
            )
            await news_service.save(item)
            saved += 1
        except Exception as e:
            if not args.quiet:
                print(f"  ⚠️  Error saving market news item: {e}")

    if not args.quiet:
        print(f"  ✅ Generated {len(generated)} market news items ({saved} saved)")
        for g in generated[:5]:
            print(f"     • {g['title'][:80]}")

    return saved


async def main() -> int:
    args = parse_args()
    setup_logging()

    # ── Initialize database ────────────────────────────────────────
    if not args.quiet:
        print("=" * 65)
        print("  🌱  NEWS SEEDER")
        print("=" * 65)

    from core.database import init_database, get_session

    await init_database()
    async for session in get_session():
        # ── Check existing data ────────────────────────────────────
        existing = await _count_news(session)
        if not args.quiet:
            print(f"\n  📊  Existing news articles in DB: {existing}")

        if existing > 50 and not args.force and not args.dry_run:
            if not args.quiet:
                print(f"  ✅  Database already has {existing} news articles — nothing to do.")
                print(f"  💡  Use --force to re-fetch anyway, or --dry-run to preview.")
            return 0

        # ── Step 1: Try RSS feeds ──────────────────────────────────
        rss_stats = await _seed_from_rss(args, session)

        # ── Step 2: Fallback to BrsApi market data if RSS failed ───
        rss_saved = rss_stats.get("saved", 0)
        if rss_saved == 0:
            if not args.quiet:
                print(f"\n  ⚠️  RSS feeds returned 0 articles — falling back to market data...")
            brsapi_saved = await _seed_from_brsapi(args, session)
        else:
            brsapi_saved = 0

        # ── Summary ────────────────────────────────────────────────
        if not args.quiet:
            print("\n" + "=" * 65)
            print("  📋  SEED SUMMARY")
            print("=" * 65)
            print(f"  RSS saved:             {rss_saved:>6,d}")
            print(f"  BrsApi market saved:   {brsapi_saved:>6,d}")
            print(f"  Dry run:               {'YES' if args.dry_run else 'NO'}")
            print(f"  Previous count:        {existing:>6,d}")
            after = existing
            if not args.dry_run and (rss_saved or brsapi_saved):
                after = await _count_news(session)
            print(f"  Total in DB after:     {after:>6,d}")
            print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
