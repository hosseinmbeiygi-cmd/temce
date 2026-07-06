import asyncio
import sys

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

dash = "-"


async def analyze():
    from core.database import init_database, close_database, get_session
    from sqlalchemy import text

    await init_database()
    async for session in get_session():

        # ── 1) TOP 20 SYMBOLS BY QUOTES VOLUME ──
        print("=" * 65)
        print("1. TOP 20 SYMBOLS BY QUOTES VOLUME")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT i.symbol, COUNT(*) AS cnt, "
                "MIN(q.date) AS fd, MAX(q.date) AS ld, "
                "COUNT(DISTINCT q.date) AS days "
                "FROM quotes q "
                "JOIN instruments i ON q.instrument_id = i.id "
                "GROUP BY i.symbol "
                "HAVING COUNT(*) > 100 "
                "ORDER BY cnt DESC LIMIT 20"
            )
        )
        hdr = f"  {'Symbol':<12} {'Records':<12} {'Days':<8} {'DateRange':<28}"
        print(hdr)
        print("  " + dash * 60)
        for row in r.fetchall():
            sym = str(row[0])
            cnt = row[1]
            fd = str(row[2] or "N/A")
            ld = str(row[3] or "N/A")
            days = row[4]
            print(f"  {sym:<12} {cnt:<12,} {days:<8,} {fd} to {ld}")

        # ── 2) MOST TRADING DAYS + PRICE RANGES ──
        print()
        print("=" * 65)
        print("2. TOP SYMBOLS - MOST TRADING DAYS + PRICE RANGES")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT i.symbol, COUNT(DISTINCT q.date) AS days, "
                "ROUND(AVG(q.price_close)::numeric, 0) AS avgp, "
                "MAX(q.price_close) AS maxp, "
                "MIN(q.price_close) AS minp "
                "FROM quotes q "
                "JOIN instruments i ON q.instrument_id = i.id "
                "GROUP BY i.symbol "
                "ORDER BY days DESC LIMIT 15"
            )
        )
        print(
            f"  {'Symbol':<12} {'TradingDays':<12} {'AvgClose':<12} {'MaxPrice':<12} {'MinPrice':<12}"
        )
        print("  " + dash * 60)
        for row in r.fetchall():
            sym = str(row[0])
            days = row[1]
            avgp = str(row[2] or "N/A")
            maxp = str(row[3] or "N/A")
            minp = str(row[4] or "N/A")
            print(f"  {sym:<12} {days:<12,} {avgp:<12} {maxp:<12} {minp:<12}")

        # ── 3) CODAL - MONTHLY REPORT PATTERNS ──
        print()
        print("=" * 65)
        print("3. CODAL - MONTHLY REPORT PATTERNS (LAST 24 MONTHS)")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT EXTRACT(year FROM publish_date) AS yr, "
                "EXTRACT(month FROM publish_date) AS mon, "
                "COUNT(*) AS cnt "
                "FROM codal_reports "
                "GROUP BY yr, mon "
                "ORDER BY yr DESC, mon DESC "
                "LIMIT 24"
            )
        )
        print(f"  {'Year':<8} {'Month':<8} {'Reports':<10}")
        print("  " + dash * 28)
        for row in r.fetchall():
            yr = int(row[0])
            mon = int(row[1])
            cnt = row[2]
            print(f"  {yr:<8} {mon:<8} {cnt:<10,}")

        # ── 4) CODAL REPORT TYPE PATTERNS ──
        print()
        print("=" * 65)
        print("4. CODAL - REPORT TYPE PATTERNS (ALL)")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT report_type, COUNT(*) AS cnt "
                "FROM codal_reports "
                "GROUP BY report_type "
                "ORDER BY cnt DESC"
            )
        )
        print(f"  {'ReportType':<15} {'Count':<10} {'Pct':<8}")
        print("  " + dash * 35)
        total = r.fetchall()
        grand = sum(row[1] for row in total)
        for row in total:
            rt = str(row[0]) if row[0] else "(empty)"
            cnt = row[1]
            pct = round(cnt / grand * 100, 1)
            print(f"  {rt:<15} {cnt:<10,} {pct:<8}%")

        # ── 5) INTRADAY TRADE VOLUME ──
        print()
        print("=" * 65)
        print("5. INTRADAY TRADES - TOP SYMBOLS BY DAILY AVG")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT symbol, COUNT(*) AS total, "
                "COUNT(DISTINCT trade_date) AS days, "
                "ROUND(COUNT(*) / NULLIF(COUNT(DISTINCT trade_date), 0), 0) AS avg_per_day "
                "FROM brsapi_intraday_trades "
                "GROUP BY symbol "
                "ORDER BY total DESC"
            )
        )
        print(f"  {'Symbol':<12} {'Total':<12} {'Days':<8} {'Avg/Day':<12}")
        print("  " + dash * 45)
        for row in r.fetchall():
            sym = str(row[0])
            tot = row[1]
            days = row[2]
            avg = row[3]
            print(f"  {sym:<12} {tot:<12,} {days:<8,} {avg:<12,.0f}")

        # ── 6) CODAL SYMBOL PATTERNS ──
        print()
        print("=" * 65)
        print("6. CODAL - TOP SYMBOLS BY REPORT COUNT")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT symbol, COUNT(*) AS cnt, "
                "COUNT(DISTINCT report_type) AS types, "
                "MIN(publish_date) AS first, "
                "MAX(publish_date) AS last "
                "FROM codal_reports "
                "GROUP BY symbol "
                "ORDER BY cnt DESC "
                "LIMIT 20"
            )
        )
        print(
            f"  {'Symbol':<12} {'Reports':<10} {'Types':<8} {'DateRange':<28}"
        )
        print("  " + dash * 60)
        for row in r.fetchall():
            sym = str(row[0])
            cnt = row[1]
            types = row[2]
            first = str(row[3] or "N/A")
            last = str(row[4] or "N/A")
            print(f"  {sym:<12} {cnt:<10,} {types:<8} {first} to {last}")

        # ── 7) REAL LEGAL - BUY/SELL PATTERNS ──
        print()
        print("=" * 65)
        print("7. REAL LEGAL - AVERAGE BUY/SELL BY SYMBOL")
        print("=" * 65)
        r = await session.execute(
            text(
                "SELECT symbol, COUNT(*) AS days, "
                "ROUND(AVG(buy_legal_volume)::numeric, 0) AS avg_buy_legal, "
                "ROUND(AVG(buy_real_volume)::numeric, 0) AS avg_buy_real, "
                "ROUND(AVG(sell_legal_volume)::numeric, 0) AS avg_sell_legal, "
                "ROUND(AVG(sell_real_volume)::numeric, 0) AS avg_sell_real "
                "FROM brsapi_historical_real_legal "
                "GROUP BY symbol "
                "ORDER BY days DESC"
            )
        )
        print(
            f"  {'Symbol':<10} {'Days':<6} {'AvgBuyLegal':<14} {'AvgBuyReal':<14} {'AvgSellLegal':<14} {'AvgSellReal':<14}"
        )
        print("  " + dash * 65)
        for row in r.fetchall():
            sym = str(row[0])
            days = row[1]
            abl = str(row[2] or "0")
            abr = str(row[3] or "0")
            asl = str(row[4] or "0")
            asr = str(row[5] or "0")
            print(f"  {sym:<10} {days:<6,} {abl:<14} {abr:<14} {asl:<14} {asr:<14}")

        await close_database()
        print("\nDone.")


asyncio.run(analyze())
