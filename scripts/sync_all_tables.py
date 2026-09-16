#!/usr/bin/env python
"""
BrsApi Complete Sync — تمام جداول را بروزرسانی می‌کند
====================================================

این اسکریپت تمام جدول‌های دیتابیس را از API برسapi (BrsApi.ir) همگام‌سازی می‌کند.

مراحل اجرا:
  1. همگام‌سازی دسته‌ای (بدون نیاز به نماد خاص):
     - TSETMC Symbols (AllSymbols.php)
     - TSETMC Index (TSE, Farabours, Selected)
     - TSETMC Options
     - IME Futures / Options / Certificates / Funds
     - Commodities (جهانی)
     - Cryptocurrency
     - Gold & Currency (Gold_Currency.php ترکیبی)
     - Codal announcements

  2. همگام‌سازی تک‌نمادها (برای ۲۰ نماد برتر بازار):
     - History Price (قیمت روزانه تاریخی) → brsapi_historical_daily
     - History Real/Legal (حقیقی/حقوقی)
     - Symbol Detail (جزئیات نماد)
     - Shareholder (ترکیب سهامداران)
     - Candlestick (شمعی)
     - Transaction (معاملات روز)
     - NAV (برای صندوق‌های ETF)

  3. Backfill تاریخچه قیمت برای نمادهای بدون داده
  4. گزارش نهایی

محدودیت نرخ API (AIO package): 500 درخواست در ۵ دقیقه

Usage:
    python scripts/sync_all_tables.py                    # همگام‌سازی کامل
    python scripts/sync_all_tables.py --batch-only       # فقط مرحله ۱
    python scripts/sync_all_tables.py --symbols-only     # فقط مرحله ۲
    python scripts/sync_all_tables.py --backfill         # فقط backfill

Author: Codebuff AI
"""
from __future__ import annotations

import asyncio
import io
import sys
import time
from pathlib import Path

# ── Auto PYTHONPATH ─────────────────────────────────────────────
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# ────────────────────────────────────────────────────────────────

# Fix Windows console encoding for Persian
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import contextlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService, SyncReport
from core.config import settings
from core.database import get_session

# ── تنظیمات ─────────────────────────────────────────────────────
REQUEST_DELAY = 2.5          # ثانیه بین درخواست‌های تکی (rate limit)
BATCH_DELAY = 2.0            # ثانیه بین دسته‌های مختلف
TOP_SYMBOLS_COUNT = 500      # تعداد نمادهای برتر برای همگام‌سازی
BACKFILL_SYMBOLS_LIMIT = 500  # تعداد نمادها برای backfill


# ── رنگ‌ها برای خروجی ───────────────────────────────────────────
class Style:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def ok(text: str) -> str:
    return f"{Style.GREEN}{Style.BOLD}{text}{Style.RESET}"

def fail(text: str) -> str:
    return f"{Style.RED}{Style.BOLD}{text}{Style.RESET}"

def warn(text: str) -> str:
    return f"{Style.YELLOW}{text}{Style.RESET}"

def header(text: str) -> str:
    return f"{Style.CYAN}{Style.BOLD}{text}{Style.RESET}"


# ── گزارش‌دهی ───────────────────────────────────────────────────
class SyncStats:
    def __init__(self):
        self.total_ok = 0
        self.total_fail = 0
        self.total_items = 0
        self.total_time_ms = 0.0
        self.reports: list[SyncReport] = []

    def add(self, report: SyncReport):
        self.reports.append(report)
        if report.success:
            self.total_ok += 1
            self.total_items += report.items_count
        else:
            self.total_fail += 1
        self.total_time_ms += report.duration_ms

    def print_header(self, title: str):
        print(f"\n{header('━' * 60)}")
        print(f"  {header(title)}")
        print(f"{header('━' * 60)}")

    def print_report(self, report: SyncReport):
        status = ok("OK") if report.success else (warn("SKIP") if report.skipped else fail("FAIL"))
        tag = f" {warn('(skipped)')}" if report.skipped else ""
        err = f" — {report.error}" if report.error else ""
        print(f"  [{status}] {report.endpoint:<45s} {report.items_count:>6} items  {report.duration_ms:>8.0f}ms{tag}{err}")

    def print_final(self, elapsed: float):
        print(f"\n{header('━' * 60)}")
        print(f"  {header('گزارش نهایی')}")
        print(f"{header('━' * 60)}")
        print(f"  ✅ موفق:     {self.total_ok}")
        print(f"  ❌ ناموفق:   {self.total_fail}")
        print(f"  📦 رکوردها:  {self.total_items:,}")
        print(f"  ⏱️  زمان:     {elapsed:.1f} ثانیه ({elapsed/60:.1f} دقیقه)")
        print(f"{header('━' * 60)}")


# ── مرحله ۱: همگام‌سازی دسته‌ای ────────────────────────────────
async def sync_batch_endpoints(service: BrsApiSyncService, session: AsyncSession, stats: SyncStats):
    """Sync all batch endpoints (no per-symbol params needed)."""
    stats.print_header("مرحله ۱ — همگام‌سازی دسته‌ای (Batch)")

    operations = [
        ("TSETMC Symbols (AllSymbols)", lambda: service.sync_all_symbols(session)),
        ("TSETMC Index - TSE", lambda: service.sync_index(session, "1")),
        ("TSETMC Index - Farabours", lambda: service.sync_index(session, "2")),
        ("TSETMC Index - Selected", lambda: service.sync_index(session, "3")),
        ("TSETMC Options (آپشن بورس)", lambda: service.sync_options(session)),
        ("IME Futures (آتی بورس کالا)", lambda: service.sync_ime_futures(session)),
        ("IME Options (اختیار بورس کالا)", lambda: service.sync_ime_options(session)),
        ("IME Certificates (گواهی سپرده)", lambda: service.sync_ime_certificates(session)),
        ("IME Funds (صندوق کالایی)", lambda: service.sync_ime_funds(session)),
        ("Commodities (کالاهای جهانی)", lambda: service.sync_commodities(session)),
        ("Cryptocurrency (ارز دیجیتال)", lambda: service.sync_crypto(session)),
        ("Gold/Currency (طلا و ارز)", lambda: service.sync_gold_currency(session)),
        ("Codal (اعلامیه‌ها)", lambda: service.sync_codal(session)),
    ]

    for name, op in operations:
        print(f"\n  🔄 {name}...")
        try:
            result = await op()
            if isinstance(result, list):
                for r in result:
                    stats.add(r)
                    stats.print_report(r)
            else:
                stats.add(result)
                stats.print_report(result)
        except Exception as e:
            err_report = SyncReport(endpoint=name, success=False, error=str(e))
            stats.add(err_report)
            stats.print_report(err_report)
        await asyncio.sleep(BATCH_DELAY)

    return stats


# ── مرحله ۲: همگام‌سازی تک‌نمادها ──────────────────────────────
async def get_top_symbols(session: AsyncSession, limit: int = TOP_SYMBOLS_COUNT) -> list[str]:
    """Get top symbols from the database.

    Tries brsapi_symbol_snapshots first, falls back to instruments table.
    """
    sources = [
        ("brsapi_symbol_snapshots", """
            SELECT DISTINCT symbol
            FROM brsapi_symbol_snapshots
            WHERE symbol IS NOT NULL AND symbol != ''
            ORDER BY symbol
            LIMIT :limit
        """),
        ("instruments", """
            SELECT symbol
            FROM instruments
            WHERE symbol IS NOT NULL AND symbol != ''
              AND (status IS NULL OR status = 'active')
            ORDER BY symbol
            LIMIT :limit
        """),
    ]
    for _table, query in sources:
        try:
            result = await session.execute(text(query), {"limit": limit})
            symbols = [row[0] for row in result.fetchall()]
            if symbols:
                return symbols
        except Exception:
            continue
    return []


async def sync_per_symbol(
    service: BrsApiSyncService,
    session: AsyncSession,
    stats: SyncStats,
    symbols: list[str],
):
    """Sync per-symbol endpoints for a list of symbols."""
    if not symbols:
        print(f"\n  {warn('⚠️  هیچ نمادی برای همگام‌سازی یافت نشد')}")
        return stats

    stats.print_header(f"مرحله ۲ — همگام‌سازی {len(symbols)} نماد برتر")

    per_symbol_ops = [
        ("History Price (قیمت تاریخی)", lambda s: service.sync_history_price(session, s)),
        ("History Real/Legal (حقیقی/حقوقی)", lambda s: service.sync_history_real_legal(session, s)),
        ("Symbol Detail (جزئیات نماد)", lambda s: service.sync_symbol_detail(session, s)),
        ("Shareholder (سهامداران)", lambda s: service.sync_shareholders(session, s)),
        ("Candlestick (شمعی)", lambda s: service.sync_candlesticks(session, s)),
    ]

    for idx, symbol in enumerate(symbols, 1):
        print(f"\n  🔄 [{idx}/{len(symbols)}] {symbol}")
        for op_name, op_fn in per_symbol_ops:
            try:
                report = await op_fn(symbol)
                stats.add(report)
                if report.success and report.items_count > 0:
                    print(f"    {ok('✓')} {op_name}: {report.items_count} رکورد")
            except Exception as e:
                err_report = SyncReport(endpoint=f"{op_name}({symbol})", success=False, error=str(e))
                stats.add(err_report)
            await asyncio.sleep(REQUEST_DELAY)

        # Commit after each symbol
        try:
            await session.commit()
        except Exception:
            await session.rollback()

        if idx < len(symbols):
            await asyncio.sleep(BATCH_DELAY)

    return stats


# ── مرحله ۳: Backfill تاریخچه قیمت ─────────────────────────────
async def sync_backfill(service: BrsApiSyncService, session: AsyncSession, stats: SyncStats, max_symbols: int = BACKFILL_SYMBOLS_LIMIT):
    """Backfill historical data for symbols missing it."""
    stats.print_header("مرحله ۳ — Backfill تاریخچه قیمت (History)")

    print("\n  🔄 در حال بررسی نمادهای نیازمند backfill...")

    try:
        # Use the same query as history_backfill_service.execute_backfill
        # but with our own session (avoids async_session_factory=None issue)
        from services.history_backfill_service import MIN_BARS_FOR_SKIP, get_symbols_needing_backfill

        symbols = await get_symbols_needing_backfill(session, min_bars=MIN_BARS_FOR_SKIP)
        if not symbols:
            print(f"\n  {ok('✓')} همه نمادها به اندازه کافی داده تاریخی دارند.")
            stats.total_ok += 1
            return stats

        if max_symbols > 0:
            symbols = symbols[:max_symbols]

        print(f"  {len(symbols)} نماد نیاز به backfill دارند.")
        print(f"\n  🔄 شروع backfill برای {len(symbols)} نماد...")

        succeeded = 0
        failed = 0
        total_items = 0

        for idx, symbol in enumerate(symbols, 1):
            print(f"\n  🔄 [{idx}/{len(symbols)}] {symbol}...", end="", flush=True)
            try:
                report = await service.sync_history_price(session=session, symbol=symbol)
                if report.success:
                    succeeded += 1
                    total_items += report.items_count
                    print(f" {ok('✓')} {report.items_count} رکورد")
                else:
                    failed += 1
                    print(f" {fail('✗')} {report.error or 'خطا'}")
            except Exception as e:
                failed += 1
                print(f" {fail('✗')} {e}")

            # Commit progress
            try:
                await session.commit()
            except Exception:
                await session.rollback()

            if idx < len(symbols):
                await asyncio.sleep(2.0)

        print(f"\n  {ok('✓')} Backfill کامل شد:")
        print(f"     نمادهای پردازش‌شده: {len(symbols)}")
        print(f"     موفق: {succeeded}")
        print(f"     ناموفق: {failed}")
        print(f"     رکوردهای جدید: {total_items:,}")

        stats.total_items += total_items
        if succeeded > 0:
            stats.total_ok += 1
        if failed > 0:
            stats.total_fail += 1

    except Exception as e:
        print(f"\n  {fail(f'❌ Backfill failed: {e}')}")
        stats.total_fail += 1

    return stats


# ── مرحله ۴: نمایش وضعیت جداول ─────────────────────────────────
async def print_table_stats(session: AsyncSession, stats: SyncStats):
    """Print row counts for all tables."""
    stats.print_header("وضعیت فعلی جداول")

    tables = [
        "brsapi_symbol_snapshots", "brsapi_symbol_details",
        "brsapi_index_values", "brsapi_nav_records",
        "brsapi_option_snapshots", "brsapi_intraday_trades",
        "brsapi_historical_daily", "brsapi_historical_real_legal",
        "brsapi_candlesticks", "brsapi_shareholder_records",
        "brsapi_ime_futures", "brsapi_ime_options",
        "brsapi_ime_certificates", "brsapi_ime_funds",
        "brsapi_ime_physical_trades",
        "brsapi_commodity_prices", "brsapi_crypto_prices",
        "brsapi_gold_coin_prices", "brsapi_currency_prices",
        "brsapi_codal_announcements",
        "quotes", "signals", "instruments",
    ]

    for tbl in tables:
        try:
            r = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            cnt = r.scalar() or 0
            icon = ok("✓") if cnt > 0 else warn("○")
            print(f"  {icon} {tbl:<35s} {cnt:>10,} rows")
        except Exception:
            print(f"  {warn('?')} {tbl:<35s} {fail('NOT FOUND')}")


# ── اجرای اصلی ─────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(
        description="BrsApi Complete Sync — تمام جداول را بروزرسانی می‌کند",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--batch-only", action="store_true", help="فقط همگام‌سازی دسته‌ای (مرحله ۱)")
    parser.add_argument("--symbols-only", action="store_true", help="فقط همگام‌سازی تک‌نمادها (مرحله ۲)")
    parser.add_argument("--backfill", action="store_true", help="فقط Backfill تاریخچه قیمت (مرحله ۳)")
    parser.add_argument("--stats", action="store_true", help="فقط نمایش وضعیت جداول")
    parser.add_argument("--top-symbols", type=int, default=TOP_SYMBOLS_COUNT, help="تعداد نمادهای برتر")
    parser.add_argument("--backfill-limit", type=int, default=BACKFILL_SYMBOLS_LIMIT, help="تعداد نمادها برای backfill")
    args = parser.parse_args()

    print(f"\n{header('╔' + '═' * 58 + '╗')}")
    print(f"{header('║')}  {Style.BOLD}BrsApi Complete Sync{Style.RESET}{header('║')}")
    print(f"{header('║')}  تمام جداول دیتابیس از BrsApi.ir بروزرسانی می‌شوند{header('║')}")
    print(f"{header('╚' + '═' * 58 + '╝')}")

    stats = SyncStats()
    start_time = time.monotonic()

    # ── Only stats ──
    if args.stats:
        async for session in get_session():
            await print_table_stats(session, stats)
            break
        return

    # ── Connect ──
    print(f"\n  {header('🔌')} اتصال به دیتابیس...")
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(
        db_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        print(f"  {header('🔌')} اتصال به BrsApi...")
        client = await get_client()
        service = BrsApiSyncService(client=client)

        async with async_session() as session:
            # ── Stats before ──
            print(f"\n  {warn('📊')} وضعیت قبل از همگام‌سازی:")
            await print_table_stats(session, stats)

            # ── Phase 1: Batch sync ──
            if not args.symbols_only and not args.backfill:
                await sync_batch_endpoints(service, session, stats)
                # Sync IME Physical (daily after market close)
                with contextlib.suppress(Exception):
                    print("\n  🔄 IME Physical (معاملات فیزیکی بورس کالا)...")
                    r = await service.sync_ime_physical(session)
                    stats.add(r)
                    stats.print_report(r)

            # ── Phase 2: Per-symbol sync ──
            if not args.batch_only and not args.backfill:
                symbols = await get_top_symbols(session, args.top_symbols)
                await sync_per_symbol(service, session, stats, symbols)

            # ── Phase 3: Backfill ──
            if not args.batch_only and not args.symbols_only:
                if args.backfill or (not args.batch_only and not args.symbols_only):
                    await sync_backfill(service, session, stats, args.backfill_limit)

            # ── Stats after ──
            print(f"\n  {warn('📊')} وضعیت بعد از همگام‌سازی:")
            await print_table_stats(session, stats)

        # ── Final report ──
        elapsed = time.monotonic() - start_time
        stats.print_final(elapsed)

        print(f"\n  {header('💡')} نکته: سرور API به طور خودکار هر چند دقیقه یکبار داده‌ها را بروز می‌کند.")
        print("  برای همگام‌سازی خودکار، فقط سرور را روشن بگذارید.")

    except KeyboardInterrupt:
        print(f"\n\n  {warn('⚠️')} همگام‌سازی توسط کاربر متوقف شد.")
    except Exception as e:
        print(f"\n  {fail(f'❌ خطا: {e}')}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
