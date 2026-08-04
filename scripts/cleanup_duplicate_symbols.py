"""
پاکسازی نمادهای تکراری از brsapi_symbol_snapshots

این اسکریپت نمادهایی که پسوند عددی دارند (مثل آپ3، اتکام3) را حذف می‌کند
و فقط نمادهای منحصربفرد واقعی را نگه می‌دارد.

Usage:
    python scripts/cleanup_duplicate_symbols.py --dry-run
    python scripts/cleanup_duplicate_symbols.py --execute
    python scripts/cleanup_duplicate_symbols.py --export
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from core.database import get_session, init_database
from core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def clean_symbol_name(symbol: str) -> str:
    """حذف پسوند عددی از نام نماد.

    Examples:
        'آپ3' -> 'آپ'
        'اتکام3' -> 'اتکام'
        'فولاد' -> 'فولاد'
        'آ س پ' -> 'آ س پ'
    """
    return re.sub(r'[0-9]+$', '', symbol).strip()


def is_duplicate(symbol: str) -> bool:
    """بررسی آیا نماد پسوند عددی دارد."""
    return bool(re.search(r'[0-9]+$', symbol))


async def analyze_duplicates(session) -> dict:
    """تحلیل نمادهای تکراری."""
    # دریافت همه نمادها
    result = await session.execute(text("""
        SELECT DISTINCT symbol
        FROM brsapi_symbol_snapshots
        ORDER BY symbol
    """))
    all_symbols = [row[0] for row in result]

    # جداسازی نمادهای اصلی و تکراری
    unique_symbols = set()
    duplicates = []

    for sym in all_symbols:
        cleaned = clean_symbol_name(sym)
        if is_duplicate(sym):
            duplicates.append({
                'original': sym,
                'cleaned': cleaned,
            })
        else:
            unique_symbols.add(cleaned)

    # بررسی نمادهایی که هم نسخه اصلی و هم عددی دارند
    has_both = []
    for dup in duplicates:
        if dup['cleaned'] in unique_symbols:
            has_both.append(dup)

    return {
        'total_symbols': len(all_symbols),
        'unique_symbols': len(unique_symbols),
        'duplicates_count': len(duplicates),
        'duplicates': duplicates,
        'has_both_count': len(has_both),
        'has_both': has_both,
    }


async def cleanup_duplicates(session, dry_run: bool = True) -> int:
    """حذف نمادهای تکراری."""
    # پیدا کردن نمادهایی که پسوند عددی دارند
    result = await session.execute(text("""
        SELECT DISTINCT symbol
        FROM brsapi_symbol_snapshots
        WHERE symbol ~ '[0-9]+$'
        ORDER BY symbol
    """))
    duplicates = [row[0] for row in result]

    if not duplicates:
        logger.info("هیچ نماد تکراری یافت نشد")
        return 0

    logger.info("تعداد نمادهای تکراری: %d", len(duplicates))

    # حذف نمادهای تکراری
    deleted = 0
    for sym in duplicates:
        if dry_run:
            logger.info("[DRY RUN] حذف: %s -> %s", sym, clean_symbol_name(sym))
        else:
            await session.execute(text("""
                DELETE FROM brsapi_symbol_snapshots
                WHERE symbol = :symbol
            """), {'symbol': sym})
            logger.info("حذف شد: %s", sym)
        deleted += 1

    if not dry_run:
        await session.commit()
        logger.info("تعداد کل حذف شده: %d", deleted)

    return deleted


async def export_clean_symbols(session, output_file: str = "clean_symbols.csv") -> None:
    """خروجی نمادهای تمیز."""
    result = await session.execute(text("""
        SELECT DISTINCT symbol
        FROM brsapi_symbol_snapshots
        WHERE symbol !~ '[0-9]+$'
        ORDER BY symbol
    """))
    symbols = [row[0] for row in result]

    # نوشتن در فایل
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("symbol\n")
        for sym in symbols:
            f.write(f"{sym}\n")

    logger.info("فایل خروجی: %s (%d نماد)", output_file, len(symbols))


async def main():
    setup_logging()

    # بررسی آرگومان‌ها
    dry_run = '--execute' not in sys.argv
    export_mode = '--export' in sys.argv

    logger.info("=" * 60)
    logger.info("پاکسازی نمادهای تکراری")
    logger.info("حالت: %s", "DRY RUN" if dry_run else "EXECUTE")
    logger.info("=" * 60)

    await init_database()

    async for session in get_session():
        # تحلیل
        analysis = await analyze_duplicates(session)

        logger.info("-" * 60)
        logger.info("نتایج تحلیل:")
        logger.info("  کل نمادها: %d", analysis['total_symbols'])
        logger.info("  نمادهای منحصربفرد: %d", analysis['unique_symbols'])
        logger.info("  نمادهای تکراری: %d", analysis['duplicates_count'])
        logger.info("  نمادهایی که هم اصلی و هم عددی دارند: %d", analysis['has_both_count'])
        logger.info("-" * 60)

        if analysis['has_both']:
            logger.info("نمونه نمادهایی که هم اصلی و هم عددی دارند:")
            for item in analysis['has_both'][:20]:
                logger.info("  %s -> %s", item['original'], item['cleaned'])

        # خروجی
        if export_mode:
            await export_clean_symbols(session)

        # پاکسازی
        if not export_mode:
            deleted = await cleanup_duplicates(session, dry_run=dry_run)

            if dry_run and deleted > 0:
                logger.info("-" * 60)
                logger.info("برای اجرای واقعی، دستور زیر را اجرا کنید:")
                logger.info("  python scripts/cleanup_duplicate_symbols.py --execute")
                logger.info("-" * 60)

        break


if __name__ == "__main__":
    asyncio.run(main())
