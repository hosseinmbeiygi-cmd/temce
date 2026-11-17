"""Data Admin — central admin console aggregation endpoint.

Provides aggregated overview health data and a static pipeline registry so
the /data frontend can render source→job→storage relationships.

Endpoints:
  GET /data-admin/overview      — health aggregate (jobs, queue, tables)
  GET /data-admin/sources       — pipeline registry with last-run enrichment
  GET /data-admin/table-freshness — per-table freshness from semantic timestamps
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


# ── Static pipeline registry ──────────────────────────────────────────────────
# Source → job → table mapping, derived from apps/scheduler/app.py.
# Update this list when new ingestion paths are added.

# ING-12: This registry covers only the APScheduler-based jobs stack
# (jobs/definitions/ → brsapi.client / providers/).  The ingestion/ package
# runs its own MarketScheduler independently and is NOT represented here.
PIPELINE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "tsetmc_instruments",
        "name": "ابزارهای بورس تهران",
        "name_en": "TSETMC Instruments",
        "source": "BrsApi / TSETMC",
        "connector": "brsapi.client",
        "job_name": "SyncInstrumentsJob",
        "schedule": "هر ۲۴ ساعت",
        "trigger": "interval(hours=24)",
        "tables": ["instruments"],
        "category": "tsetmc",
        "status": "active",
    },
    {
        "id": "tsetmc_quotes",
        "name": "قیمت‌های لحظه‌ای بورس",
        "name_en": "TSETMC Live Quotes",
        "source": "BrsApi / TSETMC",
        "connector": "brsapi.client",
        "job_name": "SyncQuotesJob",
        "schedule": "هر ۲ دقیقه",
        "trigger": "interval(minutes=2)",
        "tables": ["quotes"],
        "category": "tsetmc",
        "status": "active",
    },
    {
        "id": "tsetmc_snapshots",
        "name": "اسنپ‌شات بازار (TSETMC)",
        "name_en": "TSETMC Market Snapshots",
        "source": "BrsApi / TSETMC",
        "connector": "brsapi.client",
        "job_name": "SyncSnapshotsToQuotesJob",
        "schedule": "هر ۲ دقیقه",
        "trigger": "interval(minutes=2)",
        "tables": ["quotes"],
        "category": "tsetmc",
        "status": "active",
    },
    {
        "id": "tsetmc_backfill",
        "name": "بکفیل داده‌های تاریخی",
        "name_en": "Historical Data Backfill",
        "source": "BrsApi / TSETMC historical",
        "connector": "brsapi.client",
        "job_name": "BackfillHistoricalDataJob",
        "schedule": "ساعت ۰۲:۰۰",
        "trigger": "cron(hour=2)",
        "tables": ["quotes", "instruments"],
        "category": "tsetmc",
        "status": "active",
    },
    {
        "id": "codal_reports",
        "name": "گزارش‌های کدال",
        "name_en": "CODAL Disclosure Reports",
        "source": "BrsApi / CODAL",
        "connector": "brsapi.client",
        "job_name": "SyncCodalJob",
        "schedule": "هر ۶ ساعت",
        "trigger": "interval(hours=6)",
        "tables": ["codal_reports"],
        "category": "codal",
        "status": "active",
    },
    {
        "id": "codal_attachments",
        "name": "پیوست‌های کدال",
        "name_en": "CODAL Attachments Download",
        "source": "BrsApi / CODAL",
        "connector": "brsapi.client",
        "job_name": "CodalAttachmentDownloadJob",
        "schedule": "هر ۱۵ دقیقه",
        "trigger": "interval(minutes=15)",
        "tables": ["codal_reports"],
        "category": "codal",
        "status": "active",
    },
    {
        "id": "nav_funds",
        "name": "NAV صندوق‌های سرمایه‌گذاری",
        "name_en": "Investment Fund NAV",
        "source": "BrsApi",
        "connector": "brsapi.client",
        "job_name": "SyncNavAllJob",
        "schedule": "ساعت ۰۹:۰۰ و ۱۸:۰۰",
        "trigger": "cron(hour=9,18)",
        "tables": ["funds"],
        "category": "funds",
        "status": "active",
    },
    {
        "id": "funds_sync",
        "name": "همگام‌سازی صندوق‌ها",
        "name_en": "Funds Sync Job",
        "source": "BrsApi (internal sync)",
        "connector": "brsapi.client",
        "job_name": "FundsSyncJob",
        "schedule": "ساعت ۱۷:۳۰",
        "trigger": "cron(hour=17, minute=30)",
        "tables": ["funds"],
        "category": "funds",
        "status": "active",
    },
    {
        "id": "fund_discovery",
        "name": "کشف خودکار صندوق‌ها",
        "name_en": "Fund Auto-Discovery",
        "source": "BrsApi (zero-config discovery)",
        "connector": "brsapi.client",
        "job_name": "FundDiscoveryJob",
        "schedule": "ساعت ۰۸:۱۵، ۱۴:۱۵، ۲۰:۱۵",
        "trigger": "cron(hour=8,14,20, minute=15)",
        "tables": ["funds"],
        "category": "funds",
        "status": "active",
    },
    {
        "id": "news_ingestion",
        "name": "اخبار بازار",
        "name_en": "Market News Ingestion",
        "source": "منابع خبری متعدد",
        "connector": "news ingestion pipeline",
        "job_name": "NewsIngestionJob",
        "schedule": "هر ۱۰ دقیقه",
        "trigger": "interval(minutes=10)",
        "tables": ["news_articles"],
        "category": "news",
        "status": "active",
    },
    {
        "id": "news_sentiment",
        "name": "احساسات اخبار (NLP)",
        "name_en": "News Sentiment NLP",
        "source": "news_articles (internal derived)",
        "connector": "NLP sentiment pipeline",
        "job_name": "NewsSentimentJob",
        "schedule": "هر ۱۰ دقیقه",
        "trigger": "interval(minutes=10)",
        "tables": ["news_articles"],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "gold_macro_fred",
        "name": "ماکرو طلا — FRED",
        "name_en": "Gold Macro (FRED API)",
        "source": "FRED API (St. Louis Fed)",
        "connector": "FRED HTTP client",
        "job_name": "GoldMacroSyncJob",
        "schedule": "ساعت‌های ۰۶:۳۰، ۱۲:۳۰، ۱۸:۳۰، ۲۲:۳۰",
        "trigger": "cron(hour=6,12,18,22, minute=30)",
        "tables": ["macro_indicators"],
        "category": "gold_macro",
        "status": "active",
    },
    {
        "id": "gold_cftc",
        "name": "COT معاملات طلا — CFTC",
        "name_en": "Gold CFTC COT Report",
        "source": "CFTC (Commitment of Traders)",
        "connector": "CFTC HTTP client",
        "job_name": "GoldCftcCotSyncJob",
        "schedule": "ساعت‌های ۰۶:۴۵، ۱۲:۴۵، ۱۸:۴۵، ۲۲:۴۵",
        "trigger": "cron(hour=6,12,18,22, minute=45)",
        "tables": ["macro_indicators"],
        "category": "gold_macro",
        "status": "active",
    },
    {
        "id": "economic_calendar",
        "name": "تقویم اقتصادی",
        "name_en": "Economic Calendar Events",
        "source": "منابع تقویم اقتصادی",
        "connector": "economic calendar service",
        "job_name": "GoldEconomicCalendarSyncJob",
        "schedule": "ساعت ۰۵:۰۰ و ۱۷:۰۰",
        "trigger": "cron(hour=5,17)",
        "tables": [],
        "category": "macro",
        "status": "active",
    },
    {
        "id": "gold_tokenized",
        "name": "طلای توکنیزه (PAXG/XAUT)",
        "name_en": "Tokenized Gold Premium",
        "source": "BrsApi Crypto (internal derived)",
        "connector": "brsapi.client + DB",
        "job_name": "GoldTokenizedGoldSyncJob",
        "schedule": "ساعت‌های ۰۶:۵۰، ۱۲:۵۰، ۱۸:۵۰، ۲۲:۵۰",
        "trigger": "cron(hour=6,12,18,22, minute=50)",
        "tables": [],
        "category": "gold_macro",
        "status": "active",
    },
    {
        "id": "options_normalize",
        "name": "نرمال‌سازی اختیار معامله",
        "name_en": "Options Schema Normalization",
        "source": "BrsApi / Options raw data",
        "connector": "brsapi.client",
        "job_name": "OptionsNormalizeJob",
        "schedule": "ساعت ۱۹:۰۵",
        "trigger": "cron(hour=19, minute=5)",
        "tables": ["option_contracts", "option_snapshots"],
        "category": "options",
        "status": "active",
    },
    {
        "id": "gold_iv_snapshot",
        "name": "اسنپ‌شات IV اختیار طلا",
        "name_en": "Gold Option IV Snapshot",
        "source": "options data (internal derived)",
        "connector": "gold options service",
        "job_name": "GoldOptionIvSnapshotJob",
        "schedule": "ساعت ۱۸:۲۰",
        "trigger": "cron(hour=18, minute=20)",
        "tables": [],
        "category": "options",
        "status": "active",
    },
    {
        "id": "indicator_precompute",
        "name": "پیش‌محاسبه اندیکاتورها",
        "name_en": "Indicator Precompute",
        "source": "quotes + instruments (internal derived)",
        "connector": "IndicatorPrecompute engine",
        "job_name": "IndicatorPrecomputeJob",
        "schedule": "ساعت ۱۸:۳۰ و ۲۱:۳۰",
        "trigger": "cron(hour=18,21, minute=30)",
        "tables": ["indicators"],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "feature_store",
        "name": "Feature Store — یادگیری ماشین",
        "name_en": "ML Feature Store Build",
        "source": "instruments + quotes (internal derived)",
        "connector": "FeatureEngine",
        "job_name": "FeatureStoreBuildJob",
        "schedule": "ساعت ۲۳:۳۰",
        "trigger": "cron(hour=23, minute=30)",
        "tables": ["ml_engineered_features"],
        "category": "ml",
        "status": "active",
    },
    {
        "id": "screener_daily",
        "name": "اسکورهای روزانه اسکرینر",
        "name_en": "Screener Daily Scores",
        "source": "instruments + features (internal derived)",
        "connector": "Screener engine",
        "job_name": "ScreenerDailyScoresJob",
        "schedule": "ساعت ۲۳:۴۵",
        "trigger": "cron(hour=23, minute=45)",
        "tables": [],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "screener110",
        "name": "اسکرینر ۱۱۰ ستونی (CANSLIM)",
        "name_en": "110-Column Screener Run",
        "source": "instruments + market data (internal)",
        "connector": "Screener110 engine",
        "job_name": "Screener110RunCycleJob",
        "schedule": "هر ۲ دقیقه",
        "trigger": "interval(minutes=2)",
        "tables": [],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "monthly_sales_fill",
        "name": "فروش ماهانه کدال",
        "name_en": "Monthly CODAL Sales Fill",
        "source": "codal_reports (internal derived)",
        "connector": "CODAL pipeline",
        "job_name": "MonthlySalesFillJob",
        "schedule": "ساعت ۰۳:۳۰",
        "trigger": "cron(hour=3, minute=30)",
        "tables": ["codal_reports"],
        "category": "codal",
        "status": "active",
    },
    {
        "id": "nav_outbox_relay",
        "name": "انتشار Outbox دفتر NAV",
        "name_en": "Fund NAV Outbox Relay",
        "source": "fund_nav_outbox (internal at-least-once)",
        "connector": "outbox relay",
        "job_name": "FundNavOutboxRelayJob",
        "schedule": "هر ۵ دقیقه",
        "trigger": "interval(minutes=5)",
        "tables": ["funds"],
        "category": "funds",
        "status": "active",
    },
    {
        "id": "nav_reconciliation",
        "name": "تطبیق NAV صندوق‌ها",
        "name_en": "Fund NAV Reconciliation",
        "source": "funds (internal shadow run)",
        "connector": "reconciliation engine",
        "job_name": "FundNavReconciliationJob",
        "schedule": "ساعت ۱۸:۳۰",
        "trigger": "cron(hour=18, minute=30)",
        "tables": ["funds"],
        "category": "funds",
        "status": "active",
    },
    {
        "id": "brsapi_periodic",
        "name": "همگام‌سازی دوره‌ای BrsApi",
        "name_en": "BrsApi Periodic Sync Jobs",
        "source": "BrsApi (commodities, crypto, IME, global)",
        "connector": "brsapi.client + registry",
        "job_name": "BrsApi registry jobs",
        "schedule": "متغیر (تنظیم‌پذیر از رجیستری)",
        "trigger": "registry-managed",
        "tables": [],
        "category": "brsapi",
        "status": "active",
    },
    {
        "id": "brsapi_ready_check",
        "name": "بررسی آمادگی BrsApi",
        "name_en": "BrsApi Key Readiness Probe",
        "source": "BrsApi API probe",
        "connector": "brsapi.readiness",
        "job_name": "BrsApiReadyCheckJob",
        "schedule": "هر ۱ ساعت",
        "trigger": "interval(hours=1)",
        "tables": [],
        "category": "brsapi",
        "status": "active",
    },
    {
        "id": "evaluate_alerts",
        "name": "ارزیابی هشدارها",
        "name_en": "Evaluate Price/Volume Alerts",
        "source": "quotes + instruments (internal)",
        "connector": "alert engine",
        "job_name": "EvaluateAlertsJob",
        "schedule": "هر ۲ دقیقه",
        "trigger": "interval(minutes=2)",
        "tables": ["alerts", "alert_history"],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "monitoring_snapshot",
        "name": "اسنپ‌شات پایش داده",
        "name_en": "Data Monitoring Snapshot",
        "source": "جداول اصلی (internal freshness check)",
        "connector": "monitoring engine",
        "job_name": "MonitoringSnapshotJob",
        "schedule": "ساعت ۰۲:۳۰",
        "trigger": "cron(hour=2, minute=30)",
        "tables": ["provider_health"],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "db_retention",
        "name": "نگهداری جداول DB",
        "name_en": "Database Retention Cleanup",
        "source": "job_runs, audit_logs, provider_health (internal TTL)",
        "connector": "retention engine",
        "job_name": "DatabaseRetentionJob",
        "schedule": "ساعت ۰۳:۱۵",
        "trigger": "cron(hour=3, minute=15)",
        "tables": ["job_runs", "audit_logs", "provider_health"],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "paper_trading",
        "name": "معامله کاغذی",
        "name_en": "Paper Trading Settlement",
        "source": "signals (internal settlement)",
        "connector": "paper trading engine",
        "job_name": "PaperTradingJob",
        "schedule": "ساعت ۲۱:۰۰",
        "trigger": "cron(hour=21)",
        "tables": [],
        "category": "derived",
        "status": "active",
    },
    {
        "id": "ml_artifact_lifecycle",
        "name": "چرخه‌عمر مدل‌های ML",
        "name_en": "ML Artifact Lifecycle",
        "source": "ml_artifacts (internal pruning)",
        "connector": "artifact lifecycle engine",
        "job_name": "MlArtifactLifecycleJob",
        "schedule": "یکشنبه ۰۴:۰۰",
        "trigger": "cron(day_of_week=sun, hour=4)",
        "tables": ["ml_models", "ml_model_versions"],
        "category": "ml",
        "status": "active",
    },
]


# ── Freshness query registry ───────────────────────────────────────────────────
# Maps table_name → (column, description) for freshness probing.
# Only columns where the value represents actual source-data time, not write time.
_FRESHNESS_COLUMNS: dict[str, tuple[str, str]] = {
    "instruments": ("updated_at", "آخرین به‌روزرسانی ابزار"),
    "quotes": ("trade_date", "تاریخ آخرین معامله"),
    "codal_reports": ("published_at", "تاریخ آخرین گزارش کدال"),
    "news_articles": ("published_at", "تاریخ آخرین خبر"),
    "macro_indicators": ("date", "تاریخ آخرین داده ماکرو"),
    "indicators": ("updated_at", "آخرین به‌روزرسانی اندیکاتور"),
    "alert_history": ("triggered_at", "آخرین هشدار فعال‌شده"),
    "funds": ("updated_at", "آخرین به‌روزرسانی صندوق"),
    "provider_health": ("checked_at", "آخرین بررسی سلامت"),
}


async def _get_redis_queue_depths() -> dict[str, int]:
    """Return queue and dead-letter queue lengths; 0 on failure."""
    depths: dict[str, int] = {"queue": 0, "dead_letter": 0}
    with contextlib.suppress(Exception):
        from core.cache import get_cache
        cache = get_cache()
        client = cache.client
        if client is not None:
            q = await client.llen(settings.job_queue_name)
            dl = await client.llen(settings.job_queue_dead_letter)
            depths["queue"] = int(q or 0)
            depths["dead_letter"] = int(dl or 0)
    return depths


async def _get_job_stats_24h(session: AsyncSession) -> dict[str, int]:
    """Recent 24-hour job stats from job_runs (bounded query)."""
    stats = {"total": 0, "success": 0, "failed": 0, "running": 0}
    with contextlib.suppress(Exception):
        r = await session.execute(
            text("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) AS success,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed,
                    COUNT(CASE WHEN status = 'running' THEN 1 END) AS running
                FROM job_runs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
        )
        row = r.fetchone()
        if row:
            stats = {
                "total": int(row[0] or 0),
                "success": int(row[1] or 0),
                "failed": int(row[2] or 0),
                "running": int(row[3] or 0),
            }
    return stats


async def _get_recent_failures(session: AsyncSession, limit: int = 5) -> list[dict[str, Any]]:
    """Most recent failed jobs in the last 24h."""
    rows: list[dict[str, Any]] = []
    with contextlib.suppress(Exception):
        r = await session.execute(
            text("""
                SELECT job_type, error_message, completed_at, duration_seconds
                FROM job_runs
                WHERE status = 'failed'
                  AND created_at >= NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"lim": limit},
        )
        for row in r.fetchall():
            rows.append({
                "job_type": row[0] or "unknown",
                "error": (row[1] or "")[:200] if row[1] else None,
                "completed_at": row[2].isoformat() if row[2] else None,
                "duration_seconds": float(row[3] or 0),
            })
    return rows


async def _get_last_job_runs(session: AsyncSession) -> dict[str, dict[str, Any]]:
    """Latest run per job_type for all job types seen in the last 7 days."""
    result: dict[str, dict[str, Any]] = {}
    with contextlib.suppress(Exception):
        r = await session.execute(
            text("""
                SELECT DISTINCT ON (job_type)
                    job_type, status, completed_at, duration_seconds, error_message
                FROM job_runs
                WHERE created_at >= NOW() - INTERVAL '7 days'
                ORDER BY job_type, created_at DESC
            """)
        )
        for row in r.fetchall():
            result[row[0]] = {
                "status": row[1] or "unknown",
                "completed_at": row[2].isoformat() if row[2] else None,
                "duration_seconds": float(row[3] or 0),
                "error": (row[4] or "")[:200] if row[4] else None,
            }
    return result


async def _get_table_row_estimates(session: AsyncSession) -> dict[str, int]:
    """Fast row estimates from pg_class statistics."""
    estimates: dict[str, int] = {}
    with contextlib.suppress(Exception):
        r = await session.execute(
            text("""
                SELECT relname, GREATEST(reltuples, 0)::bigint
                FROM pg_class
                JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
                WHERE nspname = 'public' AND relkind = 'r'
            """)
        )
        for row in r.fetchall():
            estimates[row[0]] = int(row[1])
    return estimates


async def _get_table_freshness(session: AsyncSession) -> dict[str, str | None]:
    """Sample latest timestamps from key tables (one row per table)."""
    freshness: dict[str, str | None] = {}
    for table, (col, _desc) in _FRESHNESS_COLUMNS.items():
        with contextlib.suppress(Exception):
            r = await session.execute(
                text(f'SELECT MAX("{col}") FROM "{table}"')  # noqa: S608
            )
            val = r.scalar()
            freshness[table] = val.isoformat() if val is not None else None
    return freshness


def _staleness_seconds(ts_iso: str | None) -> float | None:
    """Return age of a timestamp in seconds; None when unavailable."""
    if not ts_iso:
        return None
    try:
        ts = datetime.fromisoformat(ts_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(UTC) - ts).total_seconds())
    except Exception:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/overview",
    summary="Data admin overview — aggregated health",
    description=(
        "Single-call aggregation of job stats (24h), Redis queue depths, "
        "table inventory summary, and recent failures. Admin only."
    ),
)
async def data_overview(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """Fast health aggregate for the /data admin console Overview tab."""
    job_stats, queue_depths, row_estimates, recent_failures = (
        await _get_job_stats_24h(session),
        await _get_redis_queue_depths(),
        await _get_table_row_estimates(session),
        await _get_recent_failures(session),
    )

    total_tables = len(row_estimates)
    total_rows_estimate = sum(row_estimates.values())

    # Queue health
    dl_depth = queue_depths["dead_letter"]
    dl_status = "ok" if dl_depth == 0 else ("warning" if dl_depth < settings.dl_alert_threshold else "critical")

    # Overall system status
    failure_rate = (
        job_stats["failed"] / max(job_stats["total"], 1)
    )
    overall_status: str
    if dl_status == "critical" or failure_rate > 0.3:
        overall_status = "critical"
    elif dl_status == "warning" or failure_rate > 0.1 or job_stats["failed"] > 0:
        overall_status = "warning"
    else:
        overall_status = "ok"

    return ApiResponse(
        success=True,
        data={
            "timestamp": datetime.now(UTC).isoformat(),
            "overall_status": overall_status,
            "jobs_24h": job_stats,
            "queue": {
                **queue_depths,
                "dl_status": dl_status,
                "dl_threshold": settings.dl_alert_threshold,
                "enabled": settings.job_queue_enabled,
            },
            "storage": {
                "total_tables": total_tables,
                "total_rows_estimate": total_rows_estimate,
                "row_estimates": row_estimates,
            },
            "recent_failures": recent_failures,
            "failure_rate_24h": round(failure_rate, 3),
            # ING-12: two ingestion stacks exist; this registry covers only APScheduler jobs.
            "ingestion_stack_note": "registry covers apscheduler+brsapi stack only; ingestion/ standalone stack is not reflected here",
        },
    )


@router.get(
    "/sources",
    summary="Pipeline registry with last-run enrichment",
    description=(
        "Static source→job→table pipeline map, enriched with the latest "
        "run metadata from job_runs. Admin only."
    ),
)
async def data_sources(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """Return the full pipeline registry enriched with DB-side run history."""
    last_runs = await _get_last_job_runs(session)

    enriched: list[dict[str, Any]] = []
    for src in PIPELINE_REGISTRY:
        entry = dict(src)
        job_name = src["job_name"]
        last = last_runs.get(job_name)
        if last:
            entry["last_run"] = last
            st = last["status"]
            # Treat "registry-managed" jobs specially
            if job_name == "BrsApi registry jobs":
                entry["pipeline_status"] = "unknown"
            elif st == "success":
                entry["pipeline_status"] = "ok"
            elif st == "running":
                entry["pipeline_status"] = "running"
            else:
                entry["pipeline_status"] = "failing"
        else:
            entry["last_run"] = None
            entry["pipeline_status"] = "unknown"
        enriched.append(entry)

    categories = sorted({s["category"] for s in PIPELINE_REGISTRY})
    return ApiResponse(
        success=True,
        data={
            "sources": enriched,
            "total": len(enriched),
            "categories": categories,
        },
    )


@router.get(
    "/table-freshness",
    summary="Table freshness from semantic timestamps",
    description=(
        "Per-table freshness using source-data timestamps (not write timestamps). "
        "Bounded single-row aggregates only. Admin only."
    ),
)
async def table_freshness(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """Sample MAX of semantic timestamp columns for each monitored table."""
    freshness_ts = await _get_table_freshness(session)

    result: list[dict[str, Any]] = []
    for table, (col, description) in _FRESHNESS_COLUMNS.items():
        ts = freshness_ts.get(table)
        stale_seconds = _staleness_seconds(ts)
        result.append({
            "table": table,
            "freshness_column": col,
            "description": description,
            "latest_ts": ts,
            "staleness_seconds": stale_seconds,
            "staleness_label": _staleness_label(stale_seconds),
        })

    return ApiResponse(success=True, data={"tables": result})


def _staleness_label(seconds: float | None) -> str:
    if seconds is None:
        return "نامشخص"
    if seconds < 300:
        return "تازه"
    if seconds < 3600:
        return f"{int(seconds / 60)} دقیقه پیش"
    if seconds < 86400:
        return f"{int(seconds / 3600)} ساعت پیش"
    return f"{int(seconds / 86400)} روز پیش"
