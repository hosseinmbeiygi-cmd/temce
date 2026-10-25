import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TABLES = ["signals", "paper_trades", "paper_equity_history",
          "gold_alert_rules", "gold_alert_events",
          "gold_portfolio_positions", "gold_portfolio_trades"]

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
        for t in TABLES:
            try:
                r = await c.execute(text(f"SELECT count(*) FROM {t}"))
                print(f"{t}: {r.scalar()} rows")
            except Exception as e:
                print(f"{t}: MISSING ({str(e)[:80]})")
    await eng.dispose()

asyncio.run(main())
