"""Screener110 API endpoints — populate profiles and run the 110-column model.

Endpoints:
  POST /screener110/populate       ← پر کردن screener_profiles از BrsApi
  POST /screener110/populate/{symbol}  ← پر کردن یک نماد خاص
  POST /screener110/run-cycle      ← اجرای چرخه کامل مدل ۱۱۰ ستونی
  GET  /screener110/status         ← وضعیت آخرین اجرا
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.error_handlers import safe_error_message
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

# ── Simple in-memory state for last run ──
_last_run: dict[str, Any] = {
    "last_populate": None,
    "last_cycle": None,
    "last_buy_signals": 0,
    "last_error": None,
}


@router.post(
    "/populate",
    summary="Populate screener profiles",
    description="Populate or update all screener_profiles from existing DB data (symbols, daily_history, etc.)",
)
async def populate_profiles(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """پر کردن یا بروزرسانی پروفایل همه نمادها از داده‌های موجود."""
    global _last_run
    try:
        from services.populate_profiles_service import PopulateProfilesService

        svc = PopulateProfilesService(session)
        summary = await svc.populate_all()

        _last_run["last_populate"] = datetime.now().isoformat()
        _last_run["last_error"] = None

        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "message": "Profiles populated successfully",
                "summary": summary,
            },
        )
    except Exception as exc:
        logger.exception("Populate profiles failed: %s", exc)
        _last_run["last_error"] = safe_error_message(exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"summary": {"total": 0, "created": 0, "updated": 0, "skipped": 0}},
            error={"message": safe_error_message(exc)},
        )


@router.post(
    "/populate/{symbol}",
    summary="Populate single screener profile",
    description="Populate or update screener_profiles for a single symbol",
)
async def populate_symbol(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """پر کردن پروفایل یک نماد خاص."""
    try:
        from services.populate_profiles_service import PopulateProfilesService

        svc = PopulateProfilesService(session)
        result = await svc.populate_symbol(symbol)

        if result.get("status") == "not_found":
            return ApiResponse[dict[str, Any]](
                success=False,
                data=result,
                error={"message": f"Symbol {symbol} not found"},
            )

        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Populate symbol %s failed: %s", symbol, exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"symbol": symbol, "status": "error"},
            error={"message": safe_error_message(exc)},
        )


@router.post(
    "/run-cycle",
    summary="Run 110-column model cycle",
    description="Execute a full cycle of the 110-column CANSLIM model for all active symbols",
)
async def run_cycle(
    total_capital: float = 1_000_000_000,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """اجرای چرخه کامل مدل ۱۱۰ ستونی."""
    global _last_run
    try:
        from services.screener110_service import Screener110Service

        svc = Screener110Service(session, total_capital=total_capital)
        buy_signals = await svc.run_full_cycle()

        _last_run["last_cycle"] = datetime.now().isoformat()
        _last_run["last_buy_signals"] = len(buy_signals)
        _last_run["last_error"] = None

        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "message": "Cycle completed",
                "buy_signals_count": len(buy_signals),
                "buy_signals": buy_signals[:20],  # return top 20
            },
        )
    except Exception as exc:
        logger.exception("Run cycle failed: %s", exc)
        _last_run["last_error"] = safe_error_message(exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"buy_signals_count": 0, "buy_signals": []},
            error={"message": safe_error_message(exc)},
        )


@router.get(
    "/status",
    summary="Screener110 status",
    description="Get the status of the last populate and run-cycle operations",
)
async def screener110_status() -> ApiResponse[dict[str, Any]]:
    """وضعیت آخرین اجراهای مدل ۱۱۰ ستونی."""
    return ApiResponse[dict[str, Any]](
        success=True,
        data=_last_run,
    )


@router.get("/monitor", summary="Screener110 monitoring", description="Get monitoring stats for screener110")
async def screener110_monitor(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[dict[str, Any]]:
    try:
        from sqlalchemy import text

        # --- 1. Profile stats ---
        p_sql = text(
            "SELECT COUNT(*) as total_profiles, COUNT(eps_current) FILTER (WHERE eps_current IS NOT NULL AND eps_current > 0) as with_eps, COUNT(net_operating_profit) FILTER (WHERE net_operating_profit IS NOT NULL AND net_operating_profit > 0) as with_profit, COUNT(gross_margin) FILTER (WHERE gross_margin IS NOT NULL AND gross_margin > 0) as with_margin, COUNT(accumulated_loss) FILTER (WHERE accumulated_loss IS NOT NULL AND accumulated_loss > 0) as with_loss, COUNT(registered_capital) FILTER (WHERE registered_capital IS NOT NULL AND registered_capital > 0) as with_capital, COALESCE(AVG(eps_current),0) as avg_eps, COALESCE(AVG(gross_margin),0) as avg_gross_margin FROM screener_profiles"
        )
        r1 = await session.execute(p_sql)
        ps = dict(r1.fetchone()._mapping)
        # --- 2. Signal stats ---
        s_sql = text(
            "SELECT COUNT(*) as total_signals, COUNT(*) FILTER (WHERE decision = :b) as buy_count, COUNT(*) FILTER (WHERE decision = :nb) as dont_buy_count, COUNT(*) FILTER (WHERE decision = :rk) as risk_reject_count, COUNT(*) FILTER (WHERE decision = :sr) as score_reject_count, COALESCE(AVG(final_score),0) as avg_final_score, COALESCE(MAX(final_score),0) as max_final_score, COUNT(*) FILTER (WHERE outcome_correct = TRUE) as correct_outcomes, COUNT(*) FILTER (WHERE outcome_correct IS NOT NULL) as tracked_outcomes FROM screener_signals"
        )
        r2 = await session.execute(s_sql, {"b": "خرید", "nb": "نخرید", "rk": "رد_ریسک", "sr": "رد_نمره"})
        ss = dict(r2.fetchone()._mapping)
        # --- 3. Score distribution ---
        d_sql = text(
            "SELECT CASE WHEN final_score >= 80 THEN '80-100' WHEN final_score >= 60 THEN '60-80' WHEN final_score >= 40 THEN '40-60' WHEN final_score >= 20 THEN '20-40' WHEN final_score >= 0 THEN '0-20' ELSE 'no_score' END as bucket, COUNT(*) as cnt FROM screener_signals GROUP BY bucket ORDER BY bucket DESC"
        )
        r3 = await session.execute(d_sql)
        distribution = [dict(r._mapping) for r in r3.fetchall()]
        # --- 4. Recent signals ---
        r4_sql = text(
            "SELECT symbol, final_score, decision, current_price, stop_loss_price, generated_at, score_fundamental, score_valuation, score_institutional, score_technical, score_macro FROM screener_signals ORDER BY generated_at DESC LIMIT 20"
        )
        r4 = await session.execute(r4_sql)
        recent_signals = [dict(r._mapping) for r in r4.fetchall()]
        # --- 5. Top industries ---
        r5_sql = text(
            "SELECT industry, COUNT(*) as cnt FROM screener_profiles WHERE industry IS NOT NULL AND industry != '' GROUP BY industry ORDER BY cnt DESC LIMIT 10"
        )
        r5 = await session.execute(r5_sql)
        top_industries = [dict(r._mapping) for r in r5.fetchall()]
        data = {
            "profiles": ps,
            "signals": ss,
            "score_distribution": distribution,
            "recent_signals": recent_signals,
            "top_industries": top_industries,
            "system": {
                "last_populate": _last_run.get("last_populate"),
                "last_cycle": _last_run.get("last_cycle"),
                "last_buy_signals": _last_run.get("last_buy_signals", 0),
                "last_error": _last_run.get("last_error"),
            },
        }
        return ApiResponse[dict[str, Any]](success=True, data=data)
    except Exception as exc:
        logger.exception("Monitor endpoint failed: %s", exc)
        return ApiResponse[dict[str, Any]](success=False, data={}, error={"message": safe_error_message(exc)})


# ═══════════════════════════════════════════════════════════════════════════
# AI Report endpoints — intelligent natural-language symbol & market reports
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/report/market",
    summary="AI market report",
    description="Generates an AI-style Persian report of the whole market from the latest run-cycle signals",
)
async def screener110_ai_market_report(
    limit: int = 25,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """گزارش کامل هوش مصنوعی از وضعیت بازار."""
    try:
        from services.screener_ai_report_service import ScreenerAIReportService

        svc = ScreenerAIReportService(session)
        report = await svc.generate_market_report(limit=limit)
        return ApiResponse[dict[str, Any]](success=True, data=report)
    except Exception as exc:
        logger.exception("AI market report failed: %s", exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={},
            error={"message": safe_error_message(exc)},
        )


@router.get(
    "/report/{symbol}",
    summary="AI report for a symbol",
    description=(
        "Generates a complete AI-style Persian analyst report for a symbol using "
        "the 110-column model + all available DB data (profile, signals history, "
        "daily history, institutional flow)."
    ),
)
async def screener110_ai_report(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """گزارش کامل هوش مصنوعی برای یک نماد."""
    try:
        from services.screener_ai_report_service import ScreenerAIReportService

        svc = ScreenerAIReportService(session)
        report = await svc.generate_symbol_report(symbol)

        if not report.get("model") and not report.get("profile") and not report.get("signal"):
            return ApiResponse[dict[str, Any]](
                success=False,
                data=report,
                error={"message": f"داده‌ای برای نماد {symbol} یافت نشد"},
            )

        return ApiResponse[dict[str, Any]](success=True, data=report)
    except Exception as exc:
        logger.exception("AI report failed for %s: %s", symbol, exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={},
            error={"message": safe_error_message(exc)},
        )


@router.get(
    "/top-buys",
    summary="Top buy signals from latest cycle",
    description="Returns the strongest buy signals from the most recent run-cycle, with a short AI explanation",
)
async def screener110_top_buys(
    limit: int = 10,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """برترین سیگنال‌های خرید از آخرین اجرای مدل."""
    try:
        from sqlalchemy import text

        r = await session.execute(
            text(
                """
                SELECT s1.symbol, s1.final_score, s1.adjusted_score, s1.live_pe,
                       s1.current_price, s1.stop_loss_price, s1.institutional_ratio,
                       s1.volume_spike, s1.risk_ok, s1.negative_filters_count,
                       s1.generated_at, s1.score_fundamental, s1.score_valuation,
                       s1.score_institutional, s1.score_technical
                FROM screener_signals s1
                JOIN (
                    SELECT symbol, MAX(generated_at) AS g
                    FROM screener_signals GROUP BY symbol
                ) s2 ON s1.symbol = s2.symbol AND s1.generated_at = s2.g
                WHERE s1.decision = 'خرید'
                ORDER BY s1.final_score DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
        buys = [dict(row._mapping) for row in r.fetchall()]
        return ApiResponse[dict[str, Any]](success=True, data={"count": len(buys), "items": buys})
    except Exception as exc:
        logger.exception("Top buys failed: %s", exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"count": 0, "items": []},
            error={"message": safe_error_message(exc)},
        )
