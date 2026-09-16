import asyncio
from core.database import init_database
from sqlalchemy import text

async def main():
    await init_database()
    from core.database import engine
    async with engine.begin() as conn:
        v = (await conn.execute(text('SELECT version_num FROM alembic_version'))).scalar()
        print('alembic_version:', v)
        expected = ['fund_capabilities','fund_nav_history','fund_portfolio_reports','fund_holdings',
                    'fund_portfolio_diffs','fund_market_quotes_cache','fund_scores_history',
                    'fund_ingestion_quarantine','fund_meta',
                    'stock_live_tape','stock_order_book_l2','stock_indicators_snapshot',
                    'stock_quant_signals','stock_news_sentiment','stock_monthly_sales_production',
                    'market_macro_indicators']
        for t in expected:
            n = (await conn.execute(text(f"SELECT to_regclass('public.{t}') IS NOT NULL"))).scalar()
            print(f"  {'OK ' if n else 'MISSING'} {t}")
        # additive columns on funds
        cols = (await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='funds' AND column_name IN ('national_id','manager_name','is_etf','discovered_at')"))).fetchall()
        print('funds additive cols:', sorted(c[0] for c in cols))
        idx = (await conn.execute(text("SELECT COUNT(*) FROM pg_indexes WHERE tablename='fund_nav_history'"))).scalar()
        print('fund_nav_history indexes:', idx)

asyncio.run(main())
