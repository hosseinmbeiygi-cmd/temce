"""Unified Assistant endpoint — conversational AI for ALL app features.

POST /assistant/execute  — accepts Persian text, detects intent, routes to
the appropriate service, executes actions, returns structured results.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_backtest_service,
    get_brsapi_query_service,
    get_db_session,
    get_inference_service,
    get_market_service,
    get_watchlist_service,
)
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.backtest_service import BacktestService
from services.market_service import MarketService
from services.watchlist_service import WatchlistService

logger = get_logger(__name__)
router = APIRouter()


def _safe_error_message(exc: BaseException, default: str = "خطای داخلی سرویس") -> str:
    """Return a bounded error message without leaking credentials in responses."""
    message = str(exc).strip() or default
    lowered = message.lower()
    if any(secret in lowered for secret in ("password=", "token=", "api_key=", "authorization:")):
        return default
    return message[:500]


class AssistantExecuteRequest(BaseModel):
    message: str


class AssistantExecuteResponse(BaseModel):
    text: str
    type: str = "text"
    actions: list[dict[str, Any]] = []
    link: str | None = None
    link_label: str | None = None
    data: dict[str, Any] | None = None
    suggestions: list[str] = []


@router.post(
    "/execute",
    summary="Unified Assistant — Execute any command",
    description="Accepts natural Persian/English text and executes commands across all app features: analysis, watchlist, alerts, portfolio, backtest, ML, screener, market, news, macro, etc.",
)
async def assistant_execute(
    body: AssistantExecuteRequest,
    brsapi=Depends(get_brsapi_query_service),
    market_service: MarketService = Depends(get_market_service),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
    backtest_service: BacktestService = Depends(get_backtest_service),
    inference_service=Depends(get_inference_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[AssistantExecuteResponse]:
    try:
        from services.alert_service import AlertService
        from services.screener_service import ScreenerService
        from services.unified_assistant_service import UnifiedAssistantService

        # Validate critical dependencies before using
        if brsapi is None:
            raise RuntimeError("BrsApi query service not available — database may be down")

        screener_service = ScreenerService(session=session, history_limit=60) if session else None

        assistant = UnifiedAssistantService(
            brsapi_service=brsapi,
            market_service=market_service,
            watchlist_service=watchlist_service,
            alert_service=AlertService(session=session) if session else None,
            backtest_service=backtest_service,
            inference_service=inference_service,
            screener_service=screener_service,
            session=session,
        )

        result = await assistant.process(body.message)

        return ApiResponse[AssistantExecuteResponse](
            success=True,
            data=AssistantExecuteResponse(
                text=result.get("text", ""),
                type=result.get("type", "text"),
                actions=result.get("actions", []),
                link=result.get("link"),
                link_label=result.get("link_label"),
                data=result.get("data"),
                suggestions=result.get("suggestions", []),
            ),
        )
    except ImportError as exc:
        logger.exception("Assistant import error — missing dependency?")
        return ApiResponse[AssistantExecuteResponse](
            success=False,
            data=AssistantExecuteResponse(
                text="⚠️ خطا در بارگذاری سرویس. لطفاً pip install -r requirements.txt را اجرا کنید.",
                type="error",
            ),
            error={"message": f"Import error: {exc}"},
        )
    except RuntimeError as exc:
        logger.warning("Assistant runtime error: %s", exc)
        return ApiResponse[AssistantExecuteResponse](
            success=False,
            data=AssistantExecuteResponse(
                text=f"⚠️ {exc}",
                type="error",
            ),
            error={"message": _safe_error_message(exc)},
        )
    except Exception as exc:
        logger.exception("Assistant execute error")
        error_msg = _safe_error_message(exc)
        if "connection" in error_msg.lower() or "database" in error_msg.lower():
            user_text = "⚠️ خطا در اتصال به پایگاه داده. لطفاً مطمئن شوید PostgreSQL در حال اجراست."
        elif "timeout" in error_msg.lower():
            user_text = "⚠️ زمان درخواست به پایان رسید. لطفاً دوباره تلاش کنید."
        else:
            user_text = f"⚠️ خطایی رخ داد: {error_msg[:200]}. لطفاً دوباره تلاش کنید."
        return ApiResponse[AssistantExecuteResponse](
            success=False,
            data=AssistantExecuteResponse(
                text=user_text,
                type="error",
            ),
            error={"message": error_msg},
        )


@router.get(
    "/capabilities",
    summary="List all assistant capabilities",
    description="Get list of all supported features, commands, and navigation pages.",
)
async def assistant_capabilities() -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "features": [
                {
                    "name": "تحلیل نماد",
                    "intents": ["analyze_symbol"],
                    "examples": ["تحلیل فولاد", "فولاد چطوره؟", "وضعیت خودرو"],
                },
                {
                    "name": "مقایسه نمادها",
                    "intents": ["compare"],
                    "examples": ["مقایسه فولاد و خودرو", "فولاد با شپنا"],
                },
                {
                    "name": "خلاصه بازار",
                    "intents": ["market_overview", "gainers", "losers"],
                    "examples": ["بازار چطوره؟", "پرمتحرک‌ترین‌ها", "افزایشی‌ها"],
                },
                {
                    "name": "دیده‌بان",
                    "intents": ["add_watchlist", "remove_watchlist", "list_watchlist"],
                    "examples": ["اضافه فولاد به دیده‌بان", "دیده‌بان من", "حذف فولاد از دیده‌بان"],
                },
                {
                    "name": "هشدار",
                    "intents": ["add_alert", "list_alerts"],
                    "examples": ["هشدار فولاد rsi above 70", "لیست هشدارها"],
                },
                {
                    "name": "پرتفوی",
                    "intents": ["portfolio_add", "portfolio_remove", "portfolio_summary"],
                    "examples": ["خرید فولاد 100 50000", "پرتفوی من", "فروش فولاد"],
                },
                {
                    "name": "غربال‌گری",
                    "intents": ["screener"],
                    "examples": ["بهترین سهم‌ها", "سهام ارزنده", "فیلتر RSI<30"],
                },
                {
                    "name": "بک‌تست",
                    "intents": ["run_backtest", "list_backtests"],
                    "examples": ["بک‌تست فولاد", "لیست بک‌تست‌ها"],
                },
                {
                    "name": "پیش‌بینی AI",
                    "intents": ["ml_predict", "ml_train", "ml_list_models"],
                    "examples": ["پیش‌بینی فولاد", "آموزش مدل"],
                },
                {
                    "name": "اخبار و کدال",
                    "intents": ["news", "codal"],
                    "examples": ["اخبار بازار", "کدال فولاد"],
                },
                {
                    "name": "داده‌های کلان",
                    "intents": ["macro"],
                    "examples": ["طلا و ارز", "دلار", "نرخ بهره"],
                },
                {
                    "name": "نقشه بازار",
                    "intents": ["heatmap"],
                    "examples": ["نقشه بازار"],
                },
                {
                    "name": "ناوبری",
                    "intents": ["navigate"],
                    "examples": ["برو به غربالگر", "برو به دیده‌بان"],
                },
                {
                    "name": "راهنما",
                    "intents": ["help"],
                    "examples": ["help", "چیکار می‌تونی؟", "دستورات"],
                },
            ],
            "pages": {
                "داشبورد": "/",
                "بازار": "/markets",
                "غربالگر هوشمند": "/smart-screener",
                "غربالگر": "/screener",
                "دیده‌بان": "/watchlist",
                "هشدارها": "/alerts",
                "تحلیل": "/analysis",
                "بک‌تست": "/backtest",
                "یادگیری ماشین": "/ml",
                "اخبار": "/news",
                "کدال": "/codal",
                "داده‌های کلان": "/macro",
                "نقشه بازار": "/heatmap",
                "سیگنال‌ها": "/signals",
                "ریسک": "/risk",
                "پرتفوی": "/portfolios",
                "ناهنجاری‌ها": "/anomalies",
                "گزارش‌ها": "/reports",
                "صندوق‌ها": "/funds",
                "مدیریت": "/admin",
                "نمادها": "/instruments",
            },
        },
    )


@router.get(
    "/query-stats",
    summary="User query statistics",
    description="Get statistics about user queries including intent distribution and top queries.",
)
async def query_stats() -> ApiResponse[dict[str, Any]]:
    from services.query_logger import get_query_stats

    stats = get_query_stats()
    return ApiResponse[dict[str, Any]](success=True, data=stats)
