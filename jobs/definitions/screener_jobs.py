"""
Screener110 scheduled job — runs the 110-column model cycle.

Schedule:
    Screener110RunCycleJob:  every 2 minutes  — full run-cycle
"""

from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class Screener110RunCycleJob(BaseJob):
    """Run the full 110-column model cycle for all active symbols.

    Calls Screener110Service.run_full_cycle() which:
      1. Loads batch data via BatchLoader (symbols, daily, legal, profiles, snapshots)
      2. Computes scores for each symbol via VectorCalculator
      3. Saves results to screener_snapshots and screener_signals

    Returns buy-signal count as result data.
    """

    async def execute(self, context: JobContext) -> JobResult:
        from core.database import get_session

        total_capital = context.get_param("total_capital", 1_000_000_000)

        try:
            async for session in get_session():
                from services.screener110_service import Screener110Service

                svc = Screener110Service(session, total_capital=total_capital)
                buy_signals = await svc.run_full_cycle()

                # Extract stats
                decisions: dict[str, int] = {}
                for r in buy_signals:
                    decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1

                logger.info(
                    "Screener110 cycle complete: %d buy signals, decisions=%s",
                    len(buy_signals), decisions,
                )

                return JobResult.success_result(
                    job_name=self._name,
                    data={
                        "buy_signals_count": len(buy_signals),
                        "total_capital": total_capital,
                        "decisions": decisions,
                        "top_signals": [
                            {
                                "symbol": r["symbol"],
                                "final_score": r["final_score"],
                                "decision": r["decision"],
                                "current_price": r["current_price"],
                            }
                            for r in buy_signals[:20]
                        ],
                    },
                    message=f"Cycle complete: {len(buy_signals)} buy signals",
                )

            return JobResult.failure("Could not obtain DB session", job_name=self._name)

        except Exception as e:
            logger.exception("Screener110RunCycleJob failed: %s", e)
            return JobResult.failure(str(e), job_name=self._name)
