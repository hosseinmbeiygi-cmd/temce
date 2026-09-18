"""Dead-source detection for the news ingestion pipeline.

``news_ingestion_sources`` is fed by the dual-write on every successful
fetch (``last_fetched_at`` upsert) and by the legacy backfill with
historical timestamps. This service turns that column into an actionable
health signal:

* **stale** — ``last_fetched_at`` older than ``news_source_stale_minutes``
  (default 120 = 12 missed 10-minute ingestion runs, per the news module
  spec). These sources stopped delivering within the last days.
* **never_fetched** — registered sources whose ``last_fetched_at`` is
  still NULL and whose registry row is older than
  ``news_source_never_fetches_hours``... (see settings docstring). They
  may simply have never been selected for ingestion yet, so they report
  separately instead of failing the check.
* **unregistered** — sources actively writing news but missing from the
  registry (a source renaming itself would land here), detected by
  diffing ``news_articles.source`` against ``source_name``.

Alerting follows the existing ops pattern (dead-letter alert in
``queue_consumer.py``): a Telegram message through ``TelegramSender``
with a Redis-key cooldown so a continuously stale source doesn't spam.

The job wrapper (``NewsSourceHealthJob``) runs right after each ingestion
run in the scheduler.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class NewsSourceHealthService:
    """Queries the source registry + news tables for freshness signals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _source_rows(self) -> list[dict[str, Any]]:
        # All elapsed-time math happens in SQL against the DB clock —
        # naive timestamps in this schema mix server-local and UTC writers,
        # so comparing stored values against Python's datetime.now() can be
        # off by the server timezone offset. Elapsed minutes/hours from
        # now() are clock-domain-consistent and safe to threshold-compare.
        rows = await self.session.execute(
            text(
                """
                SELECT source_name,
                       is_active,
                       last_fetched_at,
                       created_at,
                       CASE
                         WHEN last_fetched_at IS NULL THEN NULL
                         ELSE EXTRACT(EPOCH FROM (now() - last_fetched_at)) / 60.0
                       END AS minutes_since_fetch,
                       CASE
                         WHEN created_at IS NULL THEN NULL
                         ELSE EXTRACT(EPOCH FROM (now() - created_at)) / 3600.0
                       END AS hours_since_creation
                FROM news_ingestion_sources
                """
            )
        )
        return [dict(r._mapping) for r in rows.all()]

    async def _unregistered_sources(self) -> list[str]:
        """Sources writing news_articles but missing from the registry."""
        rows = await self.session.execute(
            text(
                """
                SELECT DISTINCT a.source
                FROM news_articles a
                WHERE a.source IS NOT NULL AND a.source <> ''
                  AND NOT EXISTS (
                      SELECT 1 FROM news_ingestion_sources s
                      WHERE s.source_name = a.source
                  )
                """
            )
        )
        return [r[0] for r in rows.all()]

    async def health_report(self) -> dict[str, Any]:
        """Full report: per-source freshness plus aggregated dead lists.

        Never raises — health checks must not take the ingestion pipeline
        down; errors come back as ``Result.fail``-style payload instead.
        """
        try:
            stale_minutes = settings.news_source_stale_minutes
            never_hours = settings.news_source_never_fetched_hours

            rows = await self._source_rows()
            sources: list[dict[str, Any]] = []
            stale: list[str] = []
            never_fetched: list[str] = []
            healthy = 0

            for r in rows:
                mins = r["minutes_since_fetch"]
                status = "healthy"
                if r["last_fetched_at"] is None:
                    hours = float(r["hours_since_creation"] or 0)
                    if hours > never_hours:
                        status = "never_fetched"
                        never_fetched.append(r["source_name"])
                elif mins is not None and float(mins) > stale_minutes:
                    status = "stale"
                    stale.append(r["source_name"])
                else:
                    healthy += 1
                sources.append(
                    {
                        "source_name": r["source_name"],
                        "is_active": r["is_active"],
                        "last_fetched_at": r["last_fetched_at"].isoformat() if r["last_fetched_at"] else None,
                        "minutes_since_fetch": round(mins, 1) if mins is not None else None,
                        "status": status,
                    }
                )

            unregistered = await self._unregistered_sources()
            active_count = sum(1 for s in sources if s["is_active"])
            return {
                "checked_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
                "thresholds": {
                    "stale_minutes": settings.news_source_stale_minutes,
                    "never_fetched_hours": settings.news_source_never_fetched_hours,
                },
                "summary": {
                    "total_registered": len(sources),
                    "active": active_count,
                    "healthy": healthy,
                    "stale_count": len(stale),
                    "never_fetched_count": len(never_fetched),
                    "unregistered_count": len(unregistered),
                    "all_ok": not stale and not never_fetched and not unregistered,
                },
                "stale_sources": stale,
                "never_fetched_sources": never_fetched,
                "unregistered_sources": unregistered,
                "sources": sources,
            }
        except Exception as exc:
            logger.exception("News source health check failed")
            return {
                "checked_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
                "error": str(exc),
                "summary": {"all_ok": False, "error": True},
            }

    @staticmethod
    def alert_message(report: dict[str, Any]) -> str | None:
        """Human-readable Telegram text for a report, or None if all-ok."""
        if report.get("error") or report.get("summary", {}).get("all_ok"):
            return None
        s = report.get("summary", {})
        lines = ["🟠 News source health alert"]
        if report.get("stale_sources"):
            shown = report["stale_sources"][:8]
            extra = len(report["stale_sources"]) - len(shown)
            suffix = f" (+{extra} more)" if extra > 0 else ""
            lines.append(
                f"• Stale (> {report['thresholds']['stale_minutes']}min, "
                f"{len(report['stale_sources'])} total): {', '.join(shown)}{suffix}"
            )
        if report.get("never_fetched_sources"):
            shown = report["never_fetched_sources"][:8]
            extra = len(report["never_fetched_sources"]) - len(shown)
            suffix = f" (+{extra} more)" if extra > 0 else ""
            lines.append(f"• Never fetched ({len(report['never_fetched_sources'])} total): {', '.join(shown)}{suffix}")
        if report.get("unregistered_sources"):
            shown = report["unregistered_sources"][:8]
            extra = len(report["unregistered_sources"]) - len(shown)
            suffix = f" (+{extra} more)" if extra > 0 else ""
            lines.append(f"• Unregistered ({len(report['unregistered_sources'])} total): {', '.join(shown)}{suffix}")
        lines.append(f"Summary: {s.get('healthy', 0)} healthy / {s.get('total_registered', 0)} registered")
        return "\n".join(lines)

    async def notify_if_degraded(self) -> dict[str, Any] | None:
        """Run the health check and fire a Telegram alert when degraded.

        Cooldown via a Redis key (same pattern as the dead-letter threshold
        alert) so a continuously stale source alerts at most once per
        ``news_source_alert_cooldown_seconds``. Returns the report when an
        alert was sent (or attempted), None when healthy/cooldown/skipped.
        """
        report = await self.health_report()
        if report.get("error") or report.get("summary", {}).get("all_ok"):
            return None
        message = self.alert_message(report)
        if not message:
            return None
        try:
            # Redis client comes from core.cache (same as the dead-letter
            # alert path in queue_consumer.py); it may be a sync-pool-backed
            # client, so use the async interface guardedly.
            from core.cache import get_cache

            client = getattr(get_cache(), "client", None)
            if client is not None:
                cooldown_key = "alert:news_source_health"
                if await client.get(cooldown_key):
                    return None  # within cooldown window
                await client.setex(
                    cooldown_key,
                    settings.news_source_alert_cooldown_seconds,
                    "1",
                )
            with suppress(Exception):
                from integrations.notifications.telegram_sender import TelegramSender

                sender = TelegramSender()
                await sender.send(message)
            logger.warning("News source health alert fired: %s", message)
            return report
        except Exception:
            logger.exception("News source health notification failed")
            return None
