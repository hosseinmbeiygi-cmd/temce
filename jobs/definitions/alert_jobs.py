from __future__ import annotations

import json
from datetime import UTC, datetime

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)

# Number of recent daily closes fetched for RSI computation.
RSI_LOOKBACK = 30


class EvaluateAlertsJob(BaseJob):
    """Evaluate all enabled alerts against the latest market data.

    For each unique symbol with at least one enabled alert:
      * loads the latest snapshot (price_last, trade_volume) for the symbol,
      * loads the last N daily closes for RSI / SMA-cross computation,
      * calls AlertService.evaluate_and_trigger() only for the fields that
        symbol actually has alerts on.

    Alerts are matched by symbol (the frontend form stores symbol only), so a
    data point that evaluates to a triggered condition is persisted to
    alert_history and increments triggered_count.

    Symbols whose alerts cannot be evaluated (e.g. no live snapshot today, or
    not enough history for RSI/SMA) are counted in ``skipped`` so the operator
    can see why some alerts are not firing.
    """

    async def execute(self, context: JobContext) -> JobResult:
        from sqlalchemy import select, text

        from core.database import async_session_factory
        from jobs.market_hours import is_tehran_market_open
        from models.alert import AlertModel
        from services.alert_service import AlertService, _normalize_field

        # Gate on Tehran trading hours (audit F5, 2026-11-28): outside the session
        # the "today" snapshot is the closing state, so price/volume/RSI alerts
        # would fire hours after close against a market that is no longer trading.
        # Nothing is lost by waiting — the job runs every 2 minutes and the next
        # pass after the open evaluates on live data.
        if not is_tehran_market_open():
            # Audit F10: the skipped pass is observable, not silently absent.
            from core.metrics import inc_alert_job_evaluation

            inc_alert_job_evaluation(self._name, "skipped_market_closed")
            return JobResult.skipped_result(
                job_name=self._name,
                reason="market closed — evaluation runs only during Tehran trading hours",
            )

        if async_session_factory is None:
            return JobResult.failure("Database not available", job_name=self._name)

        try:
            from services.stock_assistant_service import TechnicalIndicators

            async with async_session_factory() as session:
                # ── 1. Load all enabled alerts once (no N+1 re-querying) ──
                alert_rows = (await session.execute(
                    select(AlertModel).where(
                        AlertModel.enabled,
                        AlertModel.symbol.is_not(None),
                        AlertModel.symbol != "",
                    )
                )).scalars().all()

                # group alerts by symbol → set of normalized condition fields
                symbols_needed: dict[str, set[str]] = {}
                for a in alert_rows:
                    symbol = (a.symbol or "").strip()
                    if not symbol:
                        continue
                    try:
                        cond = a.condition if isinstance(a.condition, dict) else (
                            json.loads(a.condition) if a.condition else {}
                        )
                        field = _normalize_field(str(cond.get("field", "price")))
                    except Exception:
                        field = "price"
                    symbols_needed.setdefault(symbol, set()).add(field)

                symbols = list(symbols_needed)
                if not symbols:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"evaluated": 0, "triggered": 0, "skipped": 0, "message": "No enabled alerts"},
                    )

                # ── 2. Latest snapshot per symbol (today's realtime data) ──
                # NOTE: fetched_at is a TIMESTAMPTZ column — the cutoff MUST be a
                # datetime/date object. asyncpg infers the parameter type from the
                # column and raises `DataError: expected a datetime.date or
                # datetime.datetime instance, got 'str'` when given a string.
                today = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
                snap_rows = await session.execute(
                    text(
                        """
                        SELECT DISTINCT ON (s.symbol)
                            s.symbol, s.price_last, s.trade_volume
                        FROM brsapi_symbol_snapshots s
                        WHERE s.fetched_at >= :today
                        ORDER BY s.symbol, s.fetched_at DESC
                        """
                    ),
                    {"today": today},
                )
                symbol_set = set(symbols)
                snapshots: dict[str, tuple[float | None, float | None]] = {}
                for row in snap_rows.fetchall():
                    if row.symbol in symbol_set:
                        snapshots[row.symbol] = (row.price_last, row.trade_volume)

                svc = AlertService(session)
                evaluated = 0
                triggered_total = 0
                skipped: dict[str, int] = {}

                for symbol in symbols:
                    fields = symbols_needed[symbol]
                    price = None
                    volume = None
                    if symbol in snapshots:
                        price, volume = snapshots[symbol]

                    # No live price today → cannot evaluate price-based alerts.
                    if price is None or price <= 0:
                        skipped[symbol] = 1
                        logger.info("Alert skip %s: no live snapshot today", symbol)
                        continue

                    evaluated += 1

                    if "price" in fields:
                        trig = await svc.evaluate_and_trigger("", symbol, "price", float(price))
                        triggered_total += len(trig)

                    if "volume" in fields and volume is not None and volume > 0:
                        trig = await svc.evaluate_and_trigger("", symbol, "volume", float(volume))
                        triggered_total += len(trig)

                    # RSI / SMA-cross alerts need daily close history.
                    needs_history = bool(fields & {"rsi", "sma_cross_above", "sma_cross_below"})
                    closes: list[float] = []
                    if needs_history:
                        closes_res = await session.execute(text(
                            """
                            SELECT price_close
                            FROM quotes
                            WHERE symbol = :sym AND price_close > 0
                            ORDER BY date DESC
                            LIMIT :limit
                            """
                        ), {"sym": symbol, "limit": RSI_LOOKBACK})
                        closes = [float(r[0]) for r in closes_res.fetchall()]

                    if "rsi" in fields:
                        if len(closes) >= 15:
                            closes_reversed = list(reversed(closes))
                            rsi_series = TechnicalIndicators.rsi(closes_reversed, 14)
                            if rsi_series:
                                trig = await svc.evaluate_and_trigger("", symbol, "rsi", float(rsi_series[-1]))
                                triggered_total += len(trig)
                            else:
                                skipped[symbol] = skipped.get(symbol, 0) + 1
                        else:
                            skipped[symbol] = skipped.get(symbol, 0) + 1
                            logger.info(
                                "Alert skip %s: only %d closes for RSI (need 15)",
                                symbol, len(closes),
                            )

                    if "sma_cross_above" in fields or "sma_cross_below" in fields:
                        if len(closes) >= 22:
                            chrono = list(reversed(closes))
                            price_now = chrono[-1]
                            price_prev = chrono[-2]
                            sma_now = sum(chrono[-20:]) / 20
                            sma_prev = sum(chrono[-21:-1]) / 20
                            crossed_above = 1.0 if (price_prev <= sma_prev and price_now > sma_now) else 0.0
                            crossed_below = 1.0 if (price_prev >= sma_prev and price_now < sma_now) else 0.0
                            if "sma_cross_above" in fields:
                                trig = await svc.evaluate_and_trigger("", symbol, "sma_cross_above", crossed_above)
                                triggered_total += len(trig)
                            if "sma_cross_below" in fields:
                                trig = await svc.evaluate_and_trigger("", symbol, "sma_cross_below", crossed_below)
                                triggered_total += len(trig)
                        else:
                            skipped[symbol] = skipped.get(symbol, 0) + 1
                            logger.info(
                                "Alert skip %s: only %d closes for SMA cross (need 22)",
                                symbol, len(closes),
                            )

                await session.commit()

            return JobResult.success_result(
                job_name=self._name,
                data={
                    "evaluated": evaluated,
                    "triggered": triggered_total,
                    "skipped": len(skipped),
                    "skipped_symbols": skipped,
                    "correlation_id": context.correlation_id,
                },
            )
        except Exception as e:
            logger.exception("EvaluateAlertsJob failed")
            return JobResult.failure(str(e), job_name=self._name)


class MonitorAlertInstrumentsJob(BaseJob):
    """Analyse every instrument that is active in Alerts and deliver pending notifications.

    * Monitors with a confirmed position are analysed first (risk before ideas).
    * Each monitor runs in its own transaction and is row-locked (SKIP LOCKED), so one
      failing or slow instrument never blocks the others and concurrent runs cannot
      analyse the same monitor twice.
    * Market-wide inputs (breadth/regime) are loaded once per pass and shared.
    * A time budget bounds the pass; anything not reached is reported as ``deferred``
      (degraded cadence is disclosed, never hidden) and picked up by the next run.
    * Reads stored data only — it never calls the data provider.
    """

    #: Seconds one pass may spend analysing before deferring the rest to the next run.
    TIME_BUDGET_SECONDS = 90.0

    async def execute(self, context: JobContext) -> JobResult:
        import time

        from core.database import async_session_factory
        from jobs.market_hours import is_tehran_market_open
        from services.alert_engine import data as engine_data
        from services.alert_engine import notifier
        from services.alert_engine.engine import AlertEngine
        from services.alert_engine.settings import FreshnessPolicy

        if async_session_factory is None:
            return JobResult.failure("Database not available", job_name=self._name)

        started = time.monotonic()
        stats = {"monitors": 0, "analyzed": 0, "unchanged": 0, "skipped_locked": 0, "errors": 0, "deferred": 0}
        try:
            async with async_session_factory() as session:
                ids = await AlertEngine(session).active_monitor_ids()
                market = None
                if ids:
                    market = await engine_data.load_market(session, FreshnessPolicy(), datetime.now(UTC), is_tehran_market_open())
                await session.rollback()
            stats["monitors"] = len(ids)

            for index, (monitor_id, _has_position) in enumerate(ids):
                if time.monotonic() - started > self.TIME_BUDGET_SECONDS:
                    stats["deferred"] = len(ids) - index
                    logger.warning("MonitorAlertInstrumentsJob: time budget hit, %d monitors deferred", stats["deferred"])
                    break
                try:
                    async with async_session_factory() as session:
                        result = await AlertEngine(session).analyze(monitor_id, market=market)
                        await session.commit()
                    if result is None:
                        stats["skipped_locked"] += 1
                    elif result.get("state") == "error":
                        stats["errors"] += 1
                    elif result.get("unchanged"):
                        stats["unchanged"] += 1
                    else:
                        stats["analyzed"] += 1
                except Exception:  # noqa: BLE001 — isolate one instrument's failure
                    stats["errors"] += 1
                    logger.exception("MonitorAlertInstrumentsJob: monitor %s failed", monitor_id)

            async with async_session_factory() as session:
                # 5 = validated maximum: each user's saved notifications.telegram_max_attempts
                # then decides whether their own rows are retried or left failed
                stats["telegram"] = await notifier.deliver_pending(session, now=datetime.now(UTC), max_attempts=5)
                await session.commit()
            stats["duration_seconds"] = round(time.monotonic() - started, 2)
            stats["correlation_id"] = context.correlation_id
            # Audit F10: the analysis pass outcome is observable in /metrics.
            from core.metrics import inc_alert_job_evaluation

            inc_alert_job_evaluation(self._name, "success")
            return JobResult.success_result(job_name=self._name, data=stats)
        except Exception as e:
            logger.exception("MonitorAlertInstrumentsJob failed")
            from core.metrics import inc_alert_job_evaluation

            inc_alert_job_evaluation(self._name, "failure")
            return JobResult.failure(str(e), job_name=self._name)
