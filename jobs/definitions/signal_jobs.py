from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.signal_service import SignalService

logger = get_logger(__name__)


class SignalGenerationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        instrument_ids = context.get_param("instrument_ids", [])
        service = SignalService()
        count = 0
        for inst_id in instrument_ids:
            result = await service.generate(inst_id)
            if result.success:
                count += len(result.value) if isinstance(result.value, list) else 1
        return JobResult.success_result(job_name=self.name, data={"generated": count})


class SignalEvaluationJob(BaseJob):
    """Nightly TP/SL evaluation for signals whose evaluation window has closed.

    Audit F17 (2026-11-28): this job existed as a stub that only counted signal ids —
    the real ``jobs.signal_eval_daily.run_daily`` path (sync session) had no production
    caller, so signal-linked alert subscribers were never evaluated or recorded. This
    implementation is async-native and reuses the pure ``evaluate()`` contract:

    * pending signals with ``eval_due_at <= now`` are evaluated against daily bars
      from ``quotes`` (high/low/close per session — one row per symbol per day);
    * the result fields are written back on the signal (``status`` flips off
      ``pending``, so a rerun never re-evaluates or re-notifies);
    * each failing signal is isolated in its own SAVEPOINT — one bad row never
      aborts the pass;
    * signal-linked enabled alerts get an ``alert_history`` row with
      ``delivered=False`` — this path has no channel transport (audit F2); the row
      is the in-platform record only.

    Limitation carried over from ``run_daily``: ``halted_days`` is not derived, so a
    limit-locked session is evaluated as a normal bar.
    """

    async def execute(self, context: JobContext) -> JobResult:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from core.database import async_session_factory
        from core.ids import new_id
        from jobs.signal_eval_daily import evaluate
        from models.alert import AlertHistoryModel, AlertModel
        from models.signal import SignalModel
        from services.alert_service import quarantine_reason

        if async_session_factory is None:
            return JobResult.failure("Database not available", job_name=self._name)

        now = datetime.now(UTC)
        evaluated: list[dict] = []
        notified = 0
        errors = 0
        try:
            async with async_session_factory() as session:
                pending = (await session.execute(
                    select(SignalModel).where(
                        SignalModel.status == "pending", SignalModel.eval_due_at <= now)
                )).scalars().all()
                for row in pending:
                    try:
                        async with session.begin_nested():
                            bars = await self._load_bars(session, row.symbol, row.generated_at, row.eval_due_at)
                            result = evaluate({
                                "entry": row.entry, "take_profit": row.take_profit,
                                "stop_loss": row.stop_loss, "direction": row.direction,
                                "market": row.market,
                            }, bars)
                            for field, value in result.items():
                                if hasattr(row, field):
                                    setattr(row, field, value)
                            alerts = (await session.execute(
                                select(AlertModel).where(
                                    AlertModel.signal_id == row.id, AlertModel.enabled.is_(True))
                            )).scalars().all()
                            for alert in alerts:
                                reason = quarantine_reason(alert)
                                if reason:
                                    logger.warning("Signal alert %s quarantined (%s); outcome not recorded",
                                                   alert.id, reason)
                                    continue
                                session.add(AlertHistoryModel(
                                    id=new_id("alh"), alert_id=alert.id,
                                    trigger_value=result["actual_outcome_price"],
                                    message=(f"Signal {row.symbol} [{row.id[:8]}]: "
                                             f"{result['status']} @ {result['actual_outcome_price']}"),
                                    delivered=False))
                                alert.triggered_count = (alert.triggered_count or 0) + 1
                                notified += 1
                        evaluated.append({"signal_id": row.id, "symbol": row.symbol,
                                          "status": result["status"]})
                    except Exception:  # noqa: BLE001 — one bad signal never aborts the pass
                        errors += 1
                        logger.exception("SignalEvaluationJob: signal %s failed", row.id)
                await session.commit()
            return JobResult.success_result(job_name=self._name, data={
                "evaluated": len(evaluated), "notified": notified, "errors": errors,
                "signals": evaluated,
            })
        except Exception as e:
            logger.exception("SignalEvaluationJob failed")
            return JobResult.failure(str(e), job_name=self._name)

    @staticmethod
    async def _load_bars(session, symbol, start, end) -> list[dict]:
        """Daily high/low/close bars between the signal's generation and due dates.

        ``quotes.date`` is a Gregorian ISO string written by SyncSnapshotsToQuotesJob
        (one row per symbol per day). Missing sessions are simply absent — evaluate()
        treats the gap as no bar for that day.
        """
        from sqlalchemy import text

        start_day = start.date().isoformat() if hasattr(start, "date") else str(start)[:10]
        end_day = end.date().isoformat() if hasattr(end, "date") else str(end)[:10]
        rows = (await session.execute(text(
            "SELECT price_max, price_min, price_close FROM quotes "
            "WHERE symbol = :sym AND date >= :start AND date <= :end AND price_close > 0 "
            "ORDER BY date ASC"
        ), {"sym": symbol, "start": start_day, "end": end_day})).fetchall()
        bars: list[dict] = []
        for price_max, price_min, price_close in rows:
            close = float(price_close)
            bars.append({
                "high": float(price_max) if price_max else close,
                "low": float(price_min) if price_min else close,
                "close": close,
            })
        return bars
