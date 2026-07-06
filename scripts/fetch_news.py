#!/usr/bin/env python
"""Fetch news from Iranian news agencies via RSS, with deduplication, filtering, and storage.

Usage:
    python scripts/fetch_news.py                          # Fetch from all sources
    python scripts/fetch_news.py --sources mehr,tasnim    # Specific sources
    python scripts/fetch_news.py --limit 30               # Per-source limit
    python scripts/fetch_news.py --days 3 --keywords بورس,سهام  # Filter by date & keywords
    python scripts/fetch_news.py --symbols فولاد,فملی     # Filter by stock symbols
    python scripts/fetch_news.py --no-save                # Fetch & display only, don't save
    python scripts/fetch_news.py --top 20                 # Show top N articles
    python scripts/fetch_news.py --no-dedup               # Skip deduplication
    python scripts/fetch_news.py --min-length 100         # Min content length filter
    python scripts/fetch_news.py --economy-only           # Economy keyword filter
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
from datetime import datetime, timedelta, timezone

from core.database import get_session, init_database
from core.logging import setup_logging
from services.news_ingestion import NewsIngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Iranian news from RSS feeds with deduplication and filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Source selection
    parser.add_argument(
        "--sources", "-s",
        type=str,
        default=None,
        help="Comma-separated source keys: mehr, tasnim, irna, isna, fars, donya-eqtesad (default: all)",
    )

    # Limits
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Max articles per RSS feed URL (default: 50)",
    )
    parser.add_argument(
        "--top", "-t",
        type=int,
        default=20,
        help="Number of top articles to display in summary (default: 20)",
    )

    # Date filters
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=None,
        help="Only show articles from the last N days",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default=None,
        help="Filter from date (ISO 8601, e.g. 2025-06-20)",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        help="Filter to date (ISO 8601)",
    )

    # Content filters
    parser.add_argument(
        "--keywords", "-k",
        type=str,
        default=None,
        help="Comma-separated keywords (article must match at least one)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated stock symbols (e.g. فولاد,فملی)",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=30,
        help="Minimum total text length for an article to pass (default: 30)",
    )
    parser.add_argument(
        "--economy-only",
        action="store_true",
        help="Apply economy relevance filter (uses built-in economy keyword list)",
    )

    # Behavior flags
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save articles to database (display only)",
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Skip deduplication",
    )
    parser.add_argument(
        "--no-sentiment",
        action="store_true",
        help="Skip sentiment analysis",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (stats only)",
    )

    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    setup_logging()

    # Parse sources
    sources = None
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    # Parse date filters
    from_date = None
    to_date = None

    if args.days:
        from_date = datetime.now(timezone.utc) - timedelta(days=args.days)
    if args.from_date:
        from_date = datetime.fromisoformat(args.from_date)
    if args.to_date:
        to_date = datetime.fromisoformat(args.to_date)

    # Parse keywords
    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    # ── Run ingestion WITHIN the session context so commit() fires ──
    await init_database()
    stats = {}
    async for session in get_session():
        service = NewsIngestionService(session=session)

        # If economy-only, apply built-in economy keywords
        if args.economy_only and not keywords:
            keywords = service.news_filter._default_economy_keywords

        # Run ingestion
        print(f"\n  [TIME]  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  [SOURCES]  Sources: {sources if sources else 'ALL'}")
        print(f"  [LIMIT]  Limit per feed: {args.limit}")
        if from_date:
            print(f"  [FROM]  From: {from_date.isoformat()}")
        if keywords:
            print(f"  [KEYWORDS]  Keywords: {', '.join(keywords[:10])}{'...' if len(keywords) > 10 else ''}")
        if symbols:
            print(f"  [SYMBOLS]  Symbols: {', '.join(symbols)}")

        stats = await service.ingest(
            sources=sources,
            limit_per_source=args.limit,
            from_date=from_date,
            to_date=to_date,
            keywords=keywords,
            symbols=symbols,
            min_content_length=args.min_length,
            save=not args.no_save,
            verbose=not args.quiet,
            skip_dedup=args.no_dedup,
            skip_sentiment=args.no_sentiment,
            top_n=args.top,
        )

    print(f"\n  [DONE]  Finished: {stats.get('finished_at', '?')} ")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
