from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

TABLES_QUERY = """
    SELECT relname AS table_name, n_live_tup AS row_estimate
    FROM pg_stat_user_tables
    ORDER BY n_live_tup DESC
"""

DAILY_RECORDS_QUERY = """
    SELECT
        (SELECT COUNT(*) FROM quotes WHERE created_at >= CURRENT_DATE) AS quotes_today,
        (SELECT COUNT(*) FROM trades WHERE created_at >= CURRENT_DATE) AS trades_today,
        (SELECT COUNT(*) FROM orderbooks WHERE created_at >= CURRENT_DATE) AS orderbooks_today,
        (SELECT COUNT(*) FROM news WHERE created_at >= CURRENT_DATE) AS news_today,
        (SELECT COUNT(*) FROM signals WHERE created_at >= CURRENT_DATE) AS signals_today,
        (SELECT COUNT(*) FROM recommendations WHERE created_at >= CURRENT_DATE) AS recommendations_today,
        (SELECT COUNT(*) FROM codal WHERE created_at >= CURRENT_DATE) AS codal_today,
        (SELECT COUNT(*) FROM job_runs WHERE created_at >= CURRENT_DATE) AS job_runs_today
"""

USER_STATS_QUERY = """
    SELECT
        COUNT(*) AS total_users,
        COUNT(*) FILTER (WHERE is_active = true) AS active_users,
        COUNT(*) FILTER (WHERE last_login >= NOW() - INTERVAL '7 days') AS weekly_active
    FROM users
"""

JOBS_STATS_QUERY = """
    SELECT
        COUNT(*) AS total_runs,
        COUNT(*) FILTER (WHERE status = 'completed') AS successful,
        COUNT(*) FILTER (WHERE status = 'failed') AS failed,
        COUNT(*) FILTER (WHERE status = 'running') AS running,
        AVG(duration_seconds) FILTER (WHERE status = 'completed') AS avg_duration
    FROM job_runs
    WHERE created_at >= NOW() - INTERVAL '7 days'
"""

RECENT_JOBS_QUERY = """
    SELECT id, job_type, status, started_at, completed_at, duration_seconds, error_message
    FROM job_runs
    ORDER BY created_at DESC
    LIMIT 20
"""


@router.get("")
async def dashboard_overview(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    try:
        # ── Table row estimates ──
        table_rows: list[dict[str, Any]] = []
        try:
            result = await session.execute(text(TABLES_QUERY))
            for row in result.fetchall():
                table_rows.append({"table": row[0], "rows": row[1] or 0})
        except Exception:
            logger.warning("Could not fetch pg_stat_user_tables – using fallback counts")

        # Fallback: count rows directly
        if not table_rows:
            table_rows = []
            for tbl in [
                "instruments", "quotes", "trades", "orderbooks", "signals",
                "recommendations", "news", "codal", "macro", "indicators",
                "portfolios", "alerts", "job_runs", "users", "brsapi_symbol_details",
                "brsapi_option_snapshots", "brsapi_nav_records",
                "brsapi_historical_daily", "brsapi_historical_real_legal",
            ]:
                try:
                    r = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                    table_rows.append({"table": tbl, "rows": r.scalar() or 0})
                except Exception:
                    pass  # table may not exist

        total_db_records = sum(r["rows"] for r in table_rows)

        # ── User stats ──
        users_data: dict[str, Any] = {"total_users": 0, "active_users": 0, "weekly_active": 0}
        try:
            r = await session.execute(text(USER_STATS_QUERY))
            row = r.one_or_none()
            if row:
                users_data = {
                    "total_users": row[0] or 0,
                    "active_users": row[1] or 0,
                    "weekly_active": row[2] or 0,
                }
        except Exception:
            logger.warning("Could not fetch user stats")

        # ── Daily records ──
        daily: dict[str, int] = {}
        try:
            r = await session.execute(text(DAILY_RECORDS_QUERY))
            row = r.one_or_none()
            if row:
                daily = {
                    "quotes_today": row[0] or 0,
                    "trades_today": row[1] or 0,
                    "orderbooks_today": row[2] or 0,
                    "news_today": row[3] or 0,
                    "signals_today": row[4] or 0,
                    "recommendations_today": row[5] or 0,
                    "codal_today": row[6] or 0,
                    "job_runs_today": row[7] or 0,
                }
        except Exception:
            logger.warning("Could not fetch daily records")

        # ── Job stats ──
        job_stats: dict[str, Any] = {"total_runs": 0, "successful": 0, "failed": 0, "running": 0, "avg_duration": 0}
        try:
            r = await session.execute(text(JOBS_STATS_QUERY))
            row = r.one_or_none()
            if row:
                job_stats = {
                    "total_runs": row[0] or 0,
                    "successful": row[1] or 0,
                    "failed": row[2] or 0,
                    "running": row[3] or 0,
                    "avg_duration": round(row[4], 2) if row[4] else 0,
                }
        except Exception:
            logger.warning("Could not fetch job stats")

        # ── Recent jobs ──
        recent_jobs: list[dict[str, Any]] = []
        try:
            r = await session.execute(text(RECENT_JOBS_QUERY))
            for row in r.fetchall():
                recent_jobs.append({
                    "id": row[0] or "",
                    "job_type": row[1] or "",
                    "status": row[2] or "unknown",
                    "started_at": row[3].isoformat() if row[3] else None,
                    "completed_at": row[4].isoformat() if row[4] else None,
                    "duration_seconds": row[5] or 0,
                    "error_message": row[6][:200] if row[6] else None,
                })
        except Exception:
            logger.warning("Could not fetch recent jobs")

        # ── Key counts ──
        instruments_count = next((r["rows"] for r in table_rows if r["table"] == "instruments"), 0)
        quotes_count = next((r["rows"] for r in table_rows if r["table"] == "quotes"), 0)
        trades_count = next((r["rows"] for r in table_rows if r["table"] == "trades"), 0)
        signals_count = next((r["rows"] for r in table_rows if r["table"] == "signals"), 0)
        news_count = next((r["rows"] for r in table_rows if r["table"] == "news"), 0)

        # ── ML Models (from in-memory global registry) ──
        ml_models: list[dict[str, Any]] = []
        try:
            from ml.global_registry import get_registry
            registry = get_registry()
            ml_models = registry.list_models()
        except Exception:
            logger.warning("Could not fetch ML models for dashboard")

        # ── Backtesting Strategies (from strategy registry) ──
        strategies: list[dict[str, Any]] = []
        try:
            from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
            sreg = get_strategy_registry()
            if not sreg.list_names():
                register_all_strategies()
            strategies = sreg.list_strategies()
        except Exception:
            logger.warning("Could not fetch backtesting strategies for dashboard")

        # Determine overall status
        failed_jobs = job_stats.get("failed", 0)
        overall_status = "healthy"
        if failed_jobs > 10:
            overall_status = "degraded"
        elif failed_jobs > 0:
            overall_status = "warning"

        return {
            "metrics": {
                "total_instruments": instruments_count,
                "active_signals": signals_count,
                "total_volume": quotes_count,
                "total_db_records": total_db_records,
                "total_users": users_data["total_users"],
                "active_users": users_data["active_users"],
                "weekly_active_users": users_data["weekly_active"],
                "total_trades": trades_count,
                "total_news": news_count,
                "today_records": sum(daily.values()),
            },
            "user_stats": users_data,
            "daily_records": daily,
            "job_stats": job_stats,
            "recent_jobs": recent_jobs,
            "table_rows": table_rows,
            "ml_models": ml_models,
            "strategies": strategies,
            "system_status": overall_status,
        }
    except Exception as exc:
        logger.exception("Dashboard error")
        return {
            "metrics": {
                "total_instruments": 0,
                "active_signals": 0,
                "total_volume": 0,
                "total_db_records": 0,
                "total_users": 0,
                "active_users": 0,
                "weekly_active_users": 0,
                "total_trades": 0,
                "total_news": 0,
                "today_records": 0,
            },
            "user_stats": {"total_users": 0, "active_users": 0, "weekly_active": 0},
            "daily_records": {},
            "job_stats": {"total_runs": 0, "successful": 0, "failed": 0, "running": 0, "avg_duration": 0},
            "recent_jobs": [],
            "table_rows": [],
            "ml_models": [],
            "strategies": [],
            "system_status": "error",
            "error": str(exc),
        }
