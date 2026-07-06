"""
Verify instrument relations across all BrsApi tables using JOINs.

This script:
1. Confirms FK constraints exist
2. Tests JOINs between instruments and each BrsApi table
3. Reports relation health (what fraction of records link successfully)
4. Finds orphaned records (symbols in BrsApi that don't exist in instruments)
"""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import os
import sys
from pathlib import Path

# Force UTF-8 for stdout to handle Persian characters
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
os.environ["PYTHONIOENCODING"] = "utf-8"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings


TABLES = [
    ("brsapi_symbol_snapshots",   "ins_id",   True,  "TSETMC symbol snapshots"),
    ("brsapi_symbol_details",     "ins_id",   True,  "TSETMC symbol details"),
    ("brsapi_historical_daily",   "symbol",   False, "Daily OHLCV history"),
    ("brsapi_historical_real_legal", "symbol", False, "Daily real/legal breakdown"),
    ("brsapi_intraday_trades",    "symbol",   False, "Intraday trade ticks"),
    ("brsapi_nav_records",        "symbol",   False, "ETF NAV records"),
    ("brsapi_shareholder_records","symbol",   False, "Shareholder composition"),
    ("brsapi_candlesticks",       "symbol",   False, "OHLCV candlesticks"),
    ("brsapi_option_snapshots",   "ins_id",   True,  "Option contracts snapshot"),
    ("brsapi_ime_funds",          "ins_id",   True,  "IME commodity funds"),
    ("brsapi_codal_announcements","symbol",   False, "Codal announcements"),
    ("brsapi_index_values",       None,       False, "Market index values"),
    ("brsapi_ime_futures",        None,       False, "IME futures contracts"),
    ("brsapi_ime_options",        None,       False, "IME option contracts"),
    ("brsapi_ime_certificates",   None,       False, "IME certificates"),
    ("brsapi_ime_physical_trades","symbol",   False, "IME physical trades"),
    ("brsapi_commodity_prices",   "symbol",   False, "Global commodity prices"),
    ("brsapi_gold_coin_prices",   "symbol",   False, "Gold & coin prices"),
    ("brsapi_gold_coin_history",  "symbol",   False, "Gold & coin history"),
    ("brsapi_currency_prices",    "symbol",   False, "Currency/forex prices"),
    ("brsapi_currency_24h",       "symbol",   False, "24h currency changes"),
    ("brsapi_gold_24h",           "symbol",   False, "24h gold changes"),
    ("brsapi_crypto_prices",      "symbol",   False, "Cryptocurrency prices"),
]

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
SKIP = "[SKIP]"


async def main():
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print("=" * 70)
    print("  TEST: BrsApi ↔ instruments relations")
    print("=" * 70)
    print()

    engine = create_async_engine(db_url)
    passed = 0
    failed = 0
    skipped = 0

    async with engine.connect() as conn:
        # ── 1. FK constraint check ─────────────────
        print("📋 Step 1: Foreign Key Constraints")
        print("-" * 70)

        r = await conn.execute(text("""
            SELECT tc.table_name, tc.constraint_name,
                   kcu.column_name, ccu.table_name AS ref_table, ccu.column_name AS ref_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name LIKE 'brsapi_%'
            ORDER BY tc.table_name
        """))
        fks = r.fetchall()
        if fks:
            print(f"  Found {len(fks)} FK constraints:")
            for fk in fks:
                print(f"    {fk[0]}.{fk[2]} → {fk[3]}.{fk[4]}  [{fk[1]}]")
            passed += 1
        else:
            print(f"  {FAIL} No FK constraints found!")
            failed += 1
        print()

        # ── 2. Table existence & column check ──────
        print("📋 Step 2: Table structure")
        print("-" * 70)
        for table, join_col, has_ins_id, desc in TABLES:
            # Check table exists
            r = await conn.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"),
                {"t": table},
            )
            if not r.fetchone():
                print(f"  {SKIP} {table} — table does not exist")
                skipped += 1
                continue

            # Check required columns
            r = await conn.execute(
                text("""SELECT column_name FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=:t
                        AND column_name IN ('ins_id','instrument_id','symbol')
                        ORDER BY column_name"""),
                {"t": table},
            )
            cols = [row[0] for row in r.fetchall()]
            col_str = ", ".join(cols) if cols else "(none)"
            print(f"  {PASS} {table:35s} columns: {col_str}")

        print()

        # ── 3. JOIN test: instruments ↔ brsapi ─────
        print("📋 Step 3: JOIN health - instruments <-> brsapi tables")
        print("-" * 70)

        for table, join_col, has_ins_id, desc in TABLES:
            r = await conn.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"),
                {"t": table},
            )
            if not r.fetchone():
                skipped += 1
                continue

            # Check if table has symbol or ins_id
            has_symbol = await _has_column(conn, table, "symbol")
            has_insid = await _has_column(conn, table, "ins_id")
            has_instr_fk = await _has_column(conn, table, "instrument_id")

            if not has_symbol and not has_insid:
                print(f"  {SKIP} {table:35s} no linkable column (symbol/ins_id)")
                skipped += 1
                continue

            # Total rows
            r = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            total = r.scalar()

            # Test JOIN with instruments on symbol
            if has_symbol:
                r = await conn.execute(text(f"""
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE i.id IS NOT NULL) as linked,
                           COUNT(*) FILTER (WHERE i.id IS NULL) as orphaned
                    FROM {table} AS t
                    LEFT JOIN instruments AS i ON t.symbol = i.symbol
                """))
                total2, linked_sym, orphaned_sym = r.fetchone()
            else:
                total2, linked_sym, orphaned_sym = total, 0, total

            # Test JOIN with instruments on ins_id
            if has_insid:
                r = await conn.execute(text(f"""
                    SELECT COUNT(*) FILTER (WHERE i.id IS NOT NULL)
                    FROM {table} AS t
                    LEFT JOIN instruments AS i ON t.ins_id = i.id
                """))
                linked_ins = r.scalar()
            else:
                linked_ins = 0

            # Test via instrument_id directly
            if has_instr_fk:
                r = await conn.execute(text(f"""
                    SELECT COUNT(*) FILTER (WHERE instrument_id IS NOT NULL)
                    FROM {table}
                """))
                has_direct_fk = r.scalar()
            else:
                has_direct_fk = 0

            best_link = max(linked_sym, linked_ins, has_direct_fk)
            pct = (best_link / total * 100) if total > 0 else 100

            # Find orphaned symbols
            orphans = []
            if has_symbol and total > 0 and orphaned_sym > 0:
                r = await conn.execute(text(f"""
                    SELECT DISTINCT t.symbol
                    FROM {table} AS t
                    LEFT JOIN instruments AS i ON t.symbol = i.symbol
                    WHERE i.id IS NULL AND t.symbol IS NOT NULL AND t.symbol != ''
                    LIMIT 10
                """))
                orphans = [str(row[0]) for row in r.fetchall()]

            total_linked = max(linked_sym, linked_ins, has_direct_fk)
            total_orphaned = total - total_linked

            if pct >= 90:
                icon = PASS
            elif pct >= 50:
                icon = WARN
            else:
                icon = FAIL
                failed += 1

            print(f"  {icon} {table:35s} {total:>6} rows | "
                  f"linked: {total_linked:>6} ({pct:5.1f}%) | "
                  f"orphaned: {total_orphaned:>4}")

            if orphans and total_orphaned > 0:
                print(f"       orphaned symbols: {', '.join(orphans[:5])}"
                      f"{'...' if len(orphans) > 5 else ''}")

        print()

        # ── 4. Orphan analysis ─────────────────────
        print("📋 Step 4: Orphaned symbol analysis")
        print("-" * 70)
        r = await conn.execute(text("""
            SELECT COUNT(*) as cnt
            FROM (
                SELECT DISTINCT t.symbol
                FROM brsapi_historical_daily AS t
                LEFT JOIN instruments AS i ON t.symbol = i.symbol
                WHERE i.id IS NULL AND t.symbol IS NOT NULL AND t.symbol != ''
            ) AS orphans
        """))
        orphan_symbol_count = r.scalar()
        print(f"  Symbols in brsapi_historical_daily NOT in instruments: {orphan_symbol_count}")

        if orphan_symbol_count > 0:
            r = await conn.execute(text("""
                SELECT t.symbol, COUNT(*) as cnt
                FROM brsapi_historical_daily AS t
                LEFT JOIN instruments AS i ON t.symbol = i.symbol
                WHERE i.id IS NULL AND t.symbol IS NOT NULL AND t.symbol != ''
                GROUP BY t.symbol
                ORDER BY cnt DESC
                LIMIT 5
            """))
            top_orphans = r.fetchall()
            print("  Top orphaned symbols:")
            for row in top_orphans:
                print(f"    {row[0]}: {row[1]} records")
        print()

        # ── Summary ────────────────────────────────
        print("=" * 70)
        print(f"  RESULT: {PASS if failed == 0 else FAIL}")
        print(f"  Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
        print("=" * 70)

    await engine.dispose()
    return 0 if failed == 0 else 1


async def _has_column(conn, table: str, column: str) -> bool:
    r = await conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=:t AND column_name=:c"),
        {"t": table, "c": column},
    )
    return r.fetchone() is not None


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
