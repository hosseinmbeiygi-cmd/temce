#!/usr/bin/env python3
"""
🏦 Seed Fund Data from BrsApi
==============================

پر کردن دیتابیس با داده‌های واقعی صندوق‌ها از BrsApi.

این اسکریپت برای هر نماد صندوق:
  1. داده‌های غنی‌شده را از BrsApi دریافت می‌کند
  2. صندوق را در دیتابیس ایجاد یا به‌روزرسانی می‌کند
  3. پیشرفت و آمار را نمایش می‌دهد

مصرف:
    python scripts/seed_funds.py                        # همه صندوق‌ها
    python scripts/seed_funds.py --limit 5               # فقط ۵ صندوق
    python scripts/seed_funds.py --symbols آگاس,فولاد    # صندوق‌های مشخص
    python scripts/seed_funds.py --dry-run               # فقط پیش‌نمایش
    python scripts/seed_funds.py --db-url postgresql+asyncpg://user:pass@localhost:5432/db
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ── Console helpers (Windows-safe) ──


def _p(msg: str) -> None:
    """Print helper that avoids UnicodeEncodeError on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


# ── Known fund symbols ──

KNOWN_FUND_SYMBOLS: list[str] = [
    "آگاس", "آسامید", "آکاریز", "آکشاورز", "اسپید", "اشتیاق", "اطلس", "افتم",
    "اقبال", "الماس", "امید", "امین", "انرژی", "ایثار", "ایرانیان",
    "باپویا", "بدرخش", "باهنر", "باور", "برکت", "بسامان", "بهینه",
    "پارسیان", "پدیده", "پیشگامان", "پویا",
    "تابان", "تاپ", "تدبیر", "توسعه", "ثابت",
    "جامان", "جاوید", "حافظ", "خبرگان", "خرد",
    "دانش", "دلیران", "رادین", "رازی", "رفاه",
    "سپهر", "ستاره", "سدید", "سرآمد", "سرمد", "شفا", "صبا", "صنعت",
    "طلوع", "عقیق", "فردا", "فیروزه", "ققنوس",
    "کارآفرین", "کامران", "کیوان", "گنجینه",
    "مبین", "مثقال", "محصول", "مهر",
    "نادر", "ناهید", "نخل", "نیک", "وفاق", "همراه", "یسنا",
    "گهر", "زرفام", "نیرو", "دماوند", "البرز", "آذین", "بامداد", "بهار", "پارمیدا",
]


# ── Core logic ──


async def _ensure_db(db_url: str | None = None) -> None:
    """Initialize the database connection if not already initialized.

    Uses module-attribute access (``core.database.async_session_factory``)
    instead of ``from core.database import async_session_factory`` so the
    value is re-read *after* ``init_database()`` reassigns the module global —
    avoiding a stale ``None`` binding that would raise ``TypeError``.
    """
    import core.database as database

    if database.async_session_factory is None:
        if db_url:
            sync_url = db_url.replace("+asyncpg", "")
            os.environ["DATABASE_URL"] = sync_url
        await database.init_database()


async def seed_funds(
    db_url: str | None = None,
    symbols: list[str] | None = None,
    dry_run: bool = False,
    delay: float = 1.5,
) -> dict[str, Any]:
    """
    Seed fund data from BrsApi into the database.

    Args:
        db_url: Async database URL (default: from settings).
        symbols: List of symbols to seed (default: all known).
        dry_run: If True, show what would be done without saving.
        delay: Seconds between API calls (rate-limit safety).

    Returns:
        Dict with summary stats.
    """
    from brsapi.services.query_service import BrsApiQueryService
    from core.logging import setup_logging
    from services.fund_service import FundService

    setup_logging()

    symbols_to_seed = symbols or KNOWN_FUND_SYMBOLS

    _p(f"\n{'='*60}")
    _p("  🏦 Seed Fund Data from BrsApi")
    _p(f"  📊 Symbols: {len(symbols_to_seed)}")
    _p(f"  🔍 Mode: {'DRY-RUN (no save)' if dry_run else 'LIVE'}")
    _p(f"{'='*60}")

    if dry_run:
        _p(f"\n🔍 Dry-run: بررسی داده‌های {len(symbols_to_seed)} صندوق:\n")
        # Initialize DB if needed
        await _ensure_db(db_url)
        import core.database as database

        async with database.async_session_factory() as session:
            brsapi = BrsApiQueryService(session=session)
            ok = fail = 0
            for i, sym in enumerate(symbols_to_seed, 1):
                try:
                    enriched = await brsapi.get_enriched_symbol_detail(sym)
                    if enriched:
                        name = enriched.get("name", sym)
                        price = int(enriched.get("price_last", 0) or 0)
                        vol = int(enriched.get("trade_volume", 0) or 0)
                        _p(f"  [{i:3d}/{len(symbols_to_seed)}] {sym:8s} | {str(name):20s} | price={price:>8,d} | vol={vol:>8,d}")
                        ok += 1
                    else:
                        _p(f"  [{i:3d}/{len(symbols_to_seed)}] {sym:8s} | {'— NO DATA —':^20s}")
                        fail += 1
                except Exception as e:
                    _p(f"  [{i:3d}/{len(symbols_to_seed)}] {sym:8s} | {'— ERROR:':^20s} {str(e)[:50]}")
                    fail += 1
                await asyncio.sleep(0.3)

        _p(f"\n✅ Dry-run complete: {ok} found, {fail} not found")
        return {"total": len(symbols_to_seed), "ok": ok, "fail": fail}

    # ── Initialize DB if needed ──
    await _ensure_db(db_url)

    # ── Live mode: fetch and save ──
    start_time = time.monotonic()
    results = {"ok": 0, "fail": 0, "skip": 0, "errors": []}

    import core.database as database

    async with database.async_session_factory() as session:
        fund_service = FundService(session=session)
        brsapi = BrsApiQueryService(session=session)

        for i, sym in enumerate(symbols_to_seed, 1):
            sym_start = time.monotonic()
            try:
                result = await fund_service.update_from_brsapi(
                    symbol=sym,
                    brsapi=brsapi,
                )
                elapsed = (time.monotonic() - sym_start) * 1000

                if "error" in result:
                    _p(f"  ⚠️  [{i:3d}/{len(symbols_to_seed)}] {sym:8s} | {result['error'][:60]:<60s} | {elapsed:6.0f}ms")
                    results["fail"] += 1
                    results["errors"].append({"symbol": sym, "error": result["error"]})
                else:
                    nav = int(result.get("nav", 0) or 0)
                    fund_type = result.get("fund_type", "") or ""
                    change = float(result.get("nav_change_pct", 0) or 0)
                    arrow = "▲" if change >= 0 else "▼"
                    _p(f"  ✅ [{i:3d}/{len(symbols_to_seed)}] {sym:8s} | {fund_type:10s} | NAV={nav:>8,d} | {arrow} {change:+.2f}% | {elapsed:6.0f}ms")
                    results["ok"] += 1

                # Rate-limit safety delay
                if i < len(symbols_to_seed):
                    await asyncio.sleep(delay)

            except Exception as e:
                elapsed = (time.monotonic() - sym_start) * 1000
                _p(f"  ❌ [{i:3d}/{len(symbols_to_seed)}] {sym:8s} | {'ERROR:':^10s} {str(e)[:60]:<50s} | {elapsed:6.0f}ms")
                results["fail"] += 1
                results["errors"].append({"symbol": sym, "error": str(e)[:200]})

        # Commit all changes
        await session.commit()

    elapsed_total = time.monotonic() - start_time
    results["total"] = len(symbols_to_seed)
    results["duration_s"] = round(elapsed_total, 1)

    _p(f"\n{'='*60}")
    _p("  🏦 Seed Complete!")
    _p(f"  ✅ Success: {results['ok']}")
    _p(f"  ⚠️  Failed:  {results['fail']}")
    _p(f"  ⏱️  Time:    {results['duration_s']}s")
    if results["errors"]:
        _p(f"\n  ⚠️  Errors ({len(results['errors'])}):")
        for err in results["errors"][:5]:
            _p(f"     {err['symbol']}: {err['error'][:80]}")
        if len(results["errors"]) > 5:
            _p(f"     ... and {len(results['errors']) - 5} more")
    _p(f"{'='*60}")

    return results


# ── CLI ──


def main() -> None:
    parser = argparse.ArgumentParser(
        description="🏦 Seed Fund Data from BrsApi — پر کردن دیتابیس با داده‌های واقعی صندوق‌ها",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Async database URL (default: from settings or DATABASE_URL_ASYNC env)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=f"Number of funds to seed (default: all {len(KNOWN_FUND_SYMBOLS)})",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of symbols (e.g. آگاس,فولاد)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between API calls for rate-limit safety (default: 1.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only fetch and display data without saving to database",
    )

    args = parser.parse_args()

    # Determine symbol list
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        _p(f"🔍 Using {len(symbols)} custom symbols: {', '.join(symbols[:10])}" +
           ("..." if len(symbols) > 10 else ""))
    elif args.limit:
        symbols = KNOWN_FUND_SYMBOLS[: args.limit]
        _p(f"🔍 Limiting to first {args.limit} symbols")

    # Run seed
    import asyncio
    result = asyncio.run(seed_funds(
        db_url=args.db_url,
        symbols=symbols,
        dry_run=args.dry_run,
        delay=args.delay,
    ))

    # Exit code based on results
    if result.get("fail", 0) > 0 and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    # ── Windows console fix ──
    if sys.platform == "win32":
        import contextlib
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")

    main()
