import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        import pathlib
        for f in [".env", ".env.production"]:
            p = pathlib.Path(f)
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip("\"'")
                        break
            if url:
                break
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    eng = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with eng.connect() as c:
        for t in ["signals", "paper_trades", "paper_equity_history",
                  "gold_holdings", "gold_trades", "alert_history"]:
            n = (await c.execute(text(f"SELECT count(*) FROM {t}"))).scalar()
            print(f"{t}: {n} rows")
        # exactness proof: 0.1+0.2 in NUMERIC vs float
        r = await c.execute(text(
            "SELECT (0.1::numeric(24,8)+0.2::numeric(24,8)) = 0.3::numeric(24,8)"))
        print("numeric_exact_0.1+0.2==0.3:", r.scalar())
        print("float_shows_error:", 0.1 + 0.2 != 0.3)
        # column types
        r = await c.execute(text(
            "SELECT relname||'.'||attname||'='||format_type(atttypid,atttypmod) "
            "FROM pg_attribute JOIN pg_class ON pg_class.oid=attrelid "
            "WHERE relname IN ('signals','paper_trades','paper_equity_history',"
            "'gold_holdings','gold_trades','alert_history',"
            "'gold_alert_rules','gold_alert_events','gold_dca_plans') "
            "AND format_type(atttypid,atttypmod)='numeric(24,8)'"))
        cols = r.fetchall()
        print("numeric_cols_converted:", len(cols))
    await eng.dispose()

asyncio.run(main())
