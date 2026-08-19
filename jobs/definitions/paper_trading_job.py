"""Paper Trading Job — daily simulated-account maintenance.

Runs once per day (off-peak) and:

  1. Generates signals via the quant orchestrator (same pipeline the app uses).
  2. Snapshots every generated signal into ``paper_signal_snapshots`` (the
     daily journal — full signal details preserved).
  3. Auto-closes open paper trades that hit their target / stop-loss /
     max-holding window, recording P&L in ``paper_trades``.
  4. Writes today's equity row into ``paper_equity_history``.
"""

from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class PaperTradingJob(BaseJob):
    """Daily paper-trading maintenance: journal signals, settle trades, record equity."""

    async def execute(self, context: JobContext) -> JobResult:
        from core.database import async_session_factory

        from services.paper_trading_service import PaperTradingService
        from services.quant_signal_orchestrator import QuantSignalOrchestrator

        if async_session_factory is None:
            return JobResult.failure("Database not available", job_name=self._name)

        try:
            async with async_session_factory() as session:
                service = PaperTradingService(session=session)

                # 1. Generate signals (same pipeline as the API / hourly cron).
                orchestrator = QuantSignalOrchestrator(session=session)
                report = await orchestrator.generate(
                    market_filter="all",
                    timeframe_filter="all",
                    min_confidence=0.35,
                    limit=100,
                    use_ml=True,
                    use_voting=True,
                )
                signal_dicts = [s.to_dict() for s in report.signals]
                logger.info("PaperTradingJob: generated %d signals", len(signal_dicts))

                # 2. Persist the daily journal (full signal details).
                stored = await service.snapshot_signals(signal_dicts)
                if not stored.success:
                    logger.warning("PaperTradingJob: snapshot failed: %s", stored.error)

                # 3. Auto-close due trades.
                closed = await service.auto_close_due_trades()
                logger.info("PaperTradingJob: auto-closed %d trades", closed.value or 0)

                # 4. Record today's equity curve.
                await service._record_equity()

                dashboard = await service.get_dashboard()

            return JobResult.success_result(
                job_name=self._name,
                data={
                    "signals_generated": len(signal_dicts),
                    "snapshots_stored": stored.value if stored.success else 0,
                    "trades_auto_closed": closed.value or 0,
                    "dashboard": dashboard,
                },
            )
        except Exception as e:
            logger.exception("PaperTradingJob failed")
            return JobResult.failure(str(e), job_name=self._name)
