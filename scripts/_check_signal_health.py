"""Check signal pipeline health: counts, accuracy, coverage."""
import asyncio
import sys

sys.path.insert(0, ".")
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from core.config import settings  # noqa: E402


async def main():
    eng = create_async_engine(settings.database_url_async)
    async with eng.connect() as c:
        async def q(label, sql, params=None):
            try:
                r = await c.execute(text(sql), params or {})
                rows = r.fetchall()
                print(f"--- {label} ---")
                for row in rows[:12]:
                    print("  ", tuple(row))
                return rows
            except Exception as e:
                print(f"--- {label} --- ERR: {str(e)[:140]}")
                await c.rollback()
                return []

        # signal_accuracy table
        await q("signal_accuracy total", "SELECT COUNT(*) FROM signal_accuracy")
        await q(
            "signal_accuracy evaluated",
            "SELECT COUNT(*) FILTER (WHERE outcome_set_at IS NOT NULL), "
            "COUNT(*) FILTER (WHERE direction_correct IS NOT NULL) FROM signal_accuracy",
        )
        await q(
            "signal_accuracy by direction",
            "SELECT direction, COUNT(*) FROM signal_accuracy GROUP BY direction ORDER BY 2 DESC",
        )
        await q(
            "signal_accuracy by market",
            "SELECT market, COUNT(*) FROM signal_accuracy GROUP BY market ORDER BY 2 DESC",
        )
        await q(
            "signal_accuracy date range",
            "SELECT MIN(generated_at), MAX(generated_at) FROM signal_accuracy",
        )
        await q(
            "accuracy overall (evaluated only)",
            "SELECT COUNT(*), SUM(direction_correct::int), "
            "ROUND(100.0 * SUM(direction_correct::int) / NULLIF(COUNT(*),0), 2) "
            "FROM signal_accuracy WHERE direction_correct IS NOT NULL",
        )
        await q(
            "signals in last 7 days",
            "SELECT COUNT(*) FROM signal_accuracy WHERE generated_at >= NOW() - INTERVAL '7 days'",
        )
        await q(
            "signal_accuracy table cols",
            "SELECT column_name FROM information_schema.columns WHERE table_name='signal_accuracy' ORDER BY ordinal_position",
        )

        # signals table (if any)
        await q("signals table", "SELECT COUNT(*) FROM signals")

        # paper_signal_snapshots
        try:
            await q("paper snapshots", "SELECT COUNT(*) FROM paper_signal_snapshots")
        except Exception:
            pass

        # signal_accuracy distinct symbols
        await q(
            "distinct symbols",
            "SELECT COUNT(DISTINCT symbol) FROM signal_accuracy",
        )

    await eng.dispose()


asyncio.run(main())
