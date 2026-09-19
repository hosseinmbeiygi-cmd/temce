"""🧮 Fund NAV shadow-run + reconciliation job.

اجرای روزانه «محاسبه NAV مستقل + تطبیق با مرجع» در حالت SHADOW برای همه
صندوق‌هایی که داده موقعیت یا NAV دارند. هیچ سفارشی ارسال نمی‌شود و خروجی
فقط برای پایش/گزارش است (فاز ۱۱ معماری — اجرای سایه).
"""

from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)

DEFAULT_FUND_LIMIT = 300


class FundNavReconciliationJob(BaseJob):
    """محاسبه NAV مستقل و تطبیق مرجع برای صندوق‌های دارای داده (SHADOW)."""

    async def execute(self, context: JobContext) -> JobResult:
        import time

        from sqlalchemy import text

        from core.database import get_session
        from services.fund_nav_engine import FundNavEngine
        from services.fund_nav_reconciliation import FundNavReconciliationService

        limit = int(getattr(context, "fund_limit", DEFAULT_FUND_LIMIT) or DEFAULT_FUND_LIMIT)
        t0 = time.time()
        calculated = 0
        reconciled = 0
        errors: list[str] = []

        session_obtained = False
        try:
            async for session in get_session():
                session_obtained = True
                rows = (
                    await session.execute(
                        text(
                            """
                            SELECT DISTINCT f.id
                            FROM funds f
                            WHERE EXISTS (
                                SELECT 1 FROM fund_holdings h WHERE h.fund_id = f.id
                            ) OR EXISTS (
                                SELECT 1 FROM fund_nav_history n WHERE n.fund_id = f.id
                            )
                            ORDER BY f.id
                            LIMIT :lim
                            """
                        ),
                        {"lim": limit},
                    )
                ).fetchall()

                engine = FundNavEngine(session)
                recon = FundNavReconciliationService(session)
                for (fid,) in rows:
                    try:
                        calc = await engine.calculate(str(fid), mode="SHADOW")
                        if calc.data.get("run_id") is not None:
                            calculated += 1
                        rec = await recon.reconcile(str(fid), mode="SHADOW")
                        if rec.data.get("recon_run_id") is not None:
                            reconciled += 1
                    except Exception as exc:  # noqa: BLE001 — خطای یک صندوق کل جاب را متوقف نمی‌کند
                        errors.append(f"{fid}: {exc}")
                        logger.warning("FundNavReconciliationJob fund=%s error=%s", fid, exc)

            if not session_obtained:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)

            data = {
                "funds": len(rows),
                "calculated": calculated,
                "reconciled": reconciled,
                "error_count": len(errors),
                "errors": errors[:20],
                "duration_ms": round((time.time() - t0) * 1000, 1),
            }
            logger.info("FundNavReconciliationJob: %s", data)
            return JobResult.success_result(job_name=self._name, data=data)
        except Exception as e:  # noqa: BLE001
            logger.exception("FundNavReconciliationJob failed")
            return JobResult.failure(str(e), job_name=self._name)


class FundNavOutboxRelayJob(BaseJob):
    """📤 انتشار رویدادهای Outbox دفتر (at-least-once).

    در این فاز، Sink پیش‌فرض «لاگ» است؛ اتصال به بروکر/Redis Streams فقط با
    جایگزینی ``_publish`` انجام می‌شود و بقیه منطق (attempts/backoff) ثابت است.
    """

    async def execute(self, context: JobContext) -> JobResult:
        import time

        from core.database import get_session
        from services.fund_ledger import FundLedgerService

        t0 = time.time()
        published = 0
        failed = 0
        session_obtained = False
        try:
            async for session in get_session():
                session_obtained = True
                ledger = FundLedgerService(session)
                pending = await ledger.pending_outbox(limit=200)
                for item in pending:
                    try:
                        await self._publish(item)
                        await ledger.mark_published(item["id"])
                        published += 1
                    except Exception as exc:  # noqa: BLE001
                        await ledger.mark_failed(item["id"], str(exc))
                        failed += 1
                        logger.warning("Outbox publish failed id=%s: %s", item["id"], exc)

            if not session_obtained:
                return JobResult.failure("Could not obtain DB session", job_name=self._name)

            data = {
                "pending": published + failed,
                "published": published,
                "failed": failed,
                "duration_ms": round((time.time() - t0) * 1000, 1),
            }
            logger.info("FundNavOutboxRelayJob: %s", data)
            return JobResult.success_result(job_name=self._name, data=data)
        except Exception as e:  # noqa: BLE001
            logger.exception("FundNavOutboxRelayJob failed")
            return JobResult.failure(str(e), job_name=self._name)

    async def _publish(self, item: dict) -> None:
        """Sink: Redis Streams در صورت دسترس بودن، وگرنه لاگ ساخت‌یافته.

        الگوی at-least-once: پیام تا ثبت ``mark_published`` در Outbox می‌ماند؛
        در صورت خطا، ``mark_failed`` تلاش را ثبت و دوباره صف می‌کند.
        """
        import json

        from core.config import settings

        redis = None
        try:
            import redis.asyncio as aioredis

            redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=1.5,
            )
            await redis.xadd(
                "fund_nav_events",
                {
                    "event_type": str(item.get("event_type")),
                    "fund_id": str(item.get("fund_id") or ""),
                    "payload": json.dumps(item.get("payload") or {}, ensure_ascii=False),
                },
                maxlen=10000,
            )
            return
        except Exception:  # noqa: BLE001 — نبود Redis = fallback لاگ
            logger.info(
                "outbox fallback-log event=%s fund=%s attempts=%s",
                item.get("event_type"),
                item.get("fund_id"),
                item.get("attempts"),
            )
        finally:
            if redis is not None:
                import contextlib

                with contextlib.suppress(Exception):
                    await redis.aclose()
