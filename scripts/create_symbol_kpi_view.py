"""
Create symbol_kpi_view materialized view.
Uses a two-step approach to avoid timing out on the 7.3M quotes table:
1. Pre-compute quotes aggregation into a temp table
2. Create the materialized view using the pre-computed data
"""
import asyncio
import sys

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


async def create_view():
    from core.database import init_database, close_database, get_session
    from sqlalchemy import text

    await init_database()
    async for session in get_session():
        # Drop old objects if they exist
        await session.execute(text("DROP MATERIALIZED VIEW IF EXISTS symbol_kpi_view CASCADE"))
        await session.execute(text("DROP TABLE IF EXISTS _quotes_agg_temp"))
        await session.commit()
        print("Dropped old objects")

        # === STEP 1: Pre-compute quotes aggregation ===
        print("\nStep 1: Pre-computing quotes aggregation (7.3M records)...")
        await session.execute(text("""
            CREATE TABLE _quotes_agg_temp AS
            SELECT
                instrument_id AS q_instrument_id,
                COUNT(*) AS q_total_records,
                MIN(date) AS q_first_date,
                MAX(date) AS q_last_date,
                COUNT(DISTINCT date) AS q_trading_days,
                ROUND(AVG(price_close)::numeric, 0) AS q_avg_close,
                MAX(price_close) AS q_max_close,
                MIN(price_close) AS q_min_close,
                CASE
                    WHEN AVG(price_close) IS NOT NULL AND AVG(price_close) > 0
                    THEN ROUND(((MAX(price_close) - MIN(price_close)) / NULLIF(AVG(price_close), 0) * 100)::numeric, 2)
                    ELSE NULL
                END AS q_close_volatility_pct,
                SUM(volume) AS q_total_volume,
                ROUND(AVG(volume)::numeric, 0) AS q_avg_volume
            FROM quotes
            GROUP BY instrument_id
        """))
        cnt = await session.execute(text("SELECT COUNT(*) FROM _quotes_agg_temp"))
        print(f"  Pre-computed {cnt.scalar():,} instrument aggregations")

        # Create index on temp table for faster join
        await session.execute(text("CREATE INDEX ON _quotes_agg_temp (q_instrument_id)"))

        # Also get latest quote per instrument
        await session.execute(text("""
            CREATE TABLE _latest_quote_temp AS
            SELECT DISTINCT ON (instrument_id)
                instrument_id AS lq_instrument_id,
                price_close AS lq_latest_close,
                volume AS lq_latest_volume,
                date AS lq_latest_date
            FROM quotes
            ORDER BY instrument_id, date DESC
        """))
        lq_cnt = await session.execute(text("SELECT COUNT(*) FROM _latest_quote_temp"))
        print(f"  Pre-computed {lq_cnt.scalar():,} latest quotes")
        await session.execute(text("CREATE INDEX ON _latest_quote_temp (lq_instrument_id)"))
        await session.commit()
        print("Step 1 complete!\n")

        # === STEP 2: Create the materialized view ===
        print("Step 2: Creating symbol_kpi_view...")
        await session.execute(text("""
            CREATE MATERIALIZED VIEW symbol_kpi_view AS
            SELECT
                -- Basic info
                i.symbol,
                i.name,
                i.market_type,
                i.sector_code,

                -- === Quotes KPIs (from pre-computed tables) ===
                COALESCE(qa.q_total_records, 0) AS quote_records,
                qa.q_first_date AS first_trade_date,
                qa.q_last_date AS last_trade_date,
                COALESCE(qa.q_trading_days, 0) AS trading_days,
                qa.q_avg_close,
                qa.q_max_close,
                qa.q_min_close,
                qa.q_close_volatility_pct,
                COALESCE(qa.q_total_volume, 0) AS total_volume,
                qa.q_avg_volume,

                -- Latest quote
                lq.lq_latest_close AS latest_close,
                lq.lq_latest_volume AS latest_volume,
                lq.lq_latest_date AS latest_date,

                -- Price change (latest vs avg)
                CASE
                    WHEN qa.q_avg_close IS NOT NULL AND qa.q_avg_close > 0 AND lq.lq_latest_close IS NOT NULL
                    THEN ROUND(((lq.lq_latest_close - qa.q_avg_close)::numeric / NULLIF(qa.q_avg_close, 0)) * 100, 2)
                    ELSE NULL
                END AS pct_change_vs_avg,

                -- === Codal KPIs ===
                COALESCE(cs.report_count, 0) AS codal_reports,
                COALESCE(cs.report_types, 0) AS codal_report_types,
                cs.first_report_date,
                cs.last_report_date,

                -- === Real/Legal KPIs ===
                COALESCE(rls.record_days, 0) AS real_legal_days,
                rls.avg_buy_legal_volume,
                rls.avg_buy_real_volume,
                rls.avg_sell_legal_volume,
                rls.avg_sell_real_volume,
                rls.avg_buy_legal_count,
                rls.avg_buy_real_count,
                rls.avg_sell_legal_count,
                rls.avg_sell_real_count,

                -- Net legal flow
                CASE
                    WHEN rls.avg_buy_legal_volume IS NOT NULL AND rls.avg_sell_legal_volume IS NOT NULL
                    THEN (rls.avg_buy_legal_volume - rls.avg_sell_legal_volume)
                    ELSE NULL
                END AS net_legal_flow_avg,

                -- === Intraday Trades KPIs ===
                COALESCE(tds.trade_count, 0) AS intraday_trades,
                COALESCE(tds.trade_days, 0) AS intraday_trade_days,
                tds.avg_trades_per_day,

                -- === Composite Score ===
                COALESCE(qa.q_trading_days, 0)
                + COALESCE(cs.report_count, 0) * 10
                + COALESCE(rls.record_days, 0)
                + COALESCE(tds.trade_count, 0) / 1000
                AS data_richness_score

            FROM instruments i

            -- Pre-computed quotes aggregation
            LEFT JOIN _quotes_agg_temp qa ON qa.q_instrument_id = i.id
            LEFT JOIN _latest_quote_temp lq ON lq.lq_instrument_id = i.id

            -- Codal stats (fast - only 11k rows)
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS report_count,
                    COUNT(DISTINCT report_type) AS report_types,
                    MIN(publish_date) AS first_report_date,
                    MAX(publish_date) AS last_report_date
                FROM codal_reports c
                WHERE c.symbol = i.symbol
            ) cs ON true

            -- Real/Legal stats (fast - only 12k rows)
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS record_days,
                    ROUND(AVG(buy_legal_volume)::numeric, 0) AS avg_buy_legal_volume,
                    ROUND(AVG(buy_real_volume)::numeric, 0) AS avg_buy_real_volume,
                    ROUND(AVG(sell_legal_volume)::numeric, 0) AS avg_sell_legal_volume,
                    ROUND(AVG(sell_real_volume)::numeric, 0) AS avg_sell_real_volume,
                    ROUND(AVG(buy_legal_count)::numeric, 0) AS avg_buy_legal_count,
                    ROUND(AVG(buy_real_count)::numeric, 0) AS avg_buy_real_count,
                    ROUND(AVG(sell_legal_count)::numeric, 0) AS avg_sell_legal_count,
                    ROUND(AVG(sell_real_count)::numeric, 0) AS avg_sell_real_count
                FROM brsapi_historical_real_legal rl
                WHERE rl.symbol = i.symbol
            ) rls ON true

            -- Intraday trades stats (moderate - 1.5M rows, but grouped by symbol)
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS trade_count,
                    COUNT(DISTINCT trade_date) AS trade_days,
                    ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT trade_date), 0), 0) AS avg_trades_per_day
                FROM brsapi_intraday_trades td
                WHERE td.symbol = i.symbol
            ) tds ON true

            WHERE i.symbol IS NOT NULL
            ORDER BY i.symbol
        """))
        print("  Materialized view created!")

        # Create indexes
        await session.execute(text("CREATE UNIQUE INDEX ON symbol_kpi_view (symbol)"))
        print("  Index 1 (symbol) created")
        await session.execute(text("CREATE INDEX ON symbol_kpi_view (data_richness_score DESC)"))
        print("  Index 2 (richness) created")
        await session.execute(text("CREATE INDEX ON symbol_kpi_view (trading_days DESC)"))
        print("  Index 3 (trading_days) created")

        # Clean up temp tables
        await session.execute(text("DROP TABLE IF EXISTS _quotes_agg_temp"))
        await session.execute(text("DROP TABLE IF EXISTS _latest_quote_temp"))
        print("  Temp tables cleaned up")

        await session.commit()

        # Verify
        r = await session.execute(text("SELECT COUNT(*) FROM symbol_kpi_view"))
        cnt = r.scalar()
        print(f"\nTotal symbols in view: {cnt}")

        # Show top 5 by richness
        r = await session.execute(text("""
            SELECT symbol, data_richness_score, quote_records, trading_days, codal_reports
            FROM symbol_kpi_view
            ORDER BY data_richness_score DESC
            LIMIT 5
        """))
        print("\nTop 5 symbols by data richness:")
        for row in r.fetchall():
            print(f"  {row[0]:12} score={row[1]:>8,}  quotes={row[2]:>8,}  days={row[3]:>5,}  codal={row[4]:>4,}")

        await close_database()
        print("\nDone!")


asyncio.run(create_view())
