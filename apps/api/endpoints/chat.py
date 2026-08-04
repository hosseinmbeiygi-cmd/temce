"""Chat API endpoint — Uses the 20-level ChatEngine for intelligent responses.

Integrates with all services: stock assistant, screener, news, market,
watchlist, alerts, portfolio, and ML.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.dependencies import (
    get_brsapi_query_service,
    get_market_service,
    get_news_service,
    get_watchlist_service,
)
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.chat.chat_engine import ChatEngine

logger = get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"


class ChatResponse(BaseModel):
    text: str
    type: str = "text"
    suggestions: list[str] = []
    link: str | None = None
    link_label: str | None = None
    data: dict[str, Any] | None = None
    sentiment: dict[str, Any] | None = None


# ── ChatEngine singleton (lazy, per-request) ──────────────────────

_engine: ChatEngine | None = None


async def get_chat_engine(
    market_service=Depends(get_market_service),
    brsapi=Depends(get_brsapi_query_service),
    news_service=Depends(get_news_service),
    watchlist_service=Depends(get_watchlist_service),
) -> ChatEngine:
    """Create or reuse the ChatEngine with all dependencies injected."""
    global _engine
    if _engine is None:
        # Lazy-import the stock assistant
        try:
            from services.stock_assistant_service import StockAssistantService
            stock_assistant = StockAssistantService(brsapi_service=brsapi)
        except Exception as e:
            logger.warning("StockAssistantService unavailable: %s", e)
            stock_assistant = None

        # Lazy-import screener service (needed by UnifiedAssistantService)
        try:
            from services.screener_service import ScreenerService
            screener_service = ScreenerService()
        except Exception as e:
            logger.warning("ScreenerService unavailable: %s", e)
            screener_service = None

        # Lazy-import the unified assistant
        try:
            from services.unified_assistant_service import UnifiedAssistantService
            unified_assistant = UnifiedAssistantService(
                brsapi_service=brsapi,
                market_service=market_service,
                watchlist_service=watchlist_service,
                screener_service=screener_service,
            )
        except Exception as e:
            logger.warning("UnifiedAssistantService unavailable: %s", e)
            unified_assistant = None

        # Lazy-import smart money service
        try:
            from services.smart_money_service import SmartMoneyService
            smart_money_service = SmartMoneyService()
        except Exception as e:
            logger.warning("SmartMoneyService unavailable: %s", e)
            smart_money_service = None

        _engine = ChatEngine(
            stock_assistant=stock_assistant,
            unified_assistant=unified_assistant,
            screener_service=screener_service,
            smart_money_service=smart_money_service,
            market_service=market_service,
            news_service=news_service,
            watchlist_service=watchlist_service,
            brsapi_service=brsapi,
            brsapi_key=None,  # Will be read from env/config
        )
        logger.info("ChatEngine initialized with all services")

    return _engine


@router.post("", summary="AI Chatbot (20-Level Engine)",
             description="Intelligent conversational assistant for capital market analysis")
async def chat(
    body: ChatRequest,
    engine: ChatEngine = Depends(get_chat_engine),
) -> ApiResponse[ChatResponse]:
    """Process a chat message through the 20-level conversational engine."""
    try:
        msg = body.message.strip()
        if not msg:
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="سلام! 👋 چطور می‌توانم کمک کنم؟",
                    type="greeting",
                    suggestions=[
                        "تحلیل فولاد",
                        "بهترین سهم‌ها",
                        "خلاصه بازار",
                        "قیمت طلا",
                    ],
                ),
            )

        # Process through the 20-level engine
        result = await engine.process(
            user_id=body.user_id,
            message=msg,
        )

        # Map result to response
        response = ChatResponse(
            text=result.get("text", ""),
            type=result.get("type", "text"),
            suggestions=result.get("suggestions", []),
            data=result.get("data"),
            sentiment=result.get("sentiment"),
        )

        # Handle actions/links
        actions = result.get("actions", [])
        if actions:
            for action in actions:
                if action.get("type") in ("link", "navigate"):
                    response.link = action.get("url", action.get("link"))
                    response.link_label = action.get("label")
                    break

        # Handle navigation
        nav_link = result.get("link")
        if nav_link:
            response.link = nav_link
            response.link_label = result.get("link_label", "🔗 برو به صفحه")

        return ApiResponse[ChatResponse](success=True, data=response)

    except Exception as exc:
        logger.exception("Chat error: %s", exc)
        return ApiResponse[ChatResponse](
            success=False,
            data=ChatResponse(
                text="⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                type="error",
            ),
        )


@router.post("/feedback", summary="Submit feedback on chat response",
             description="Help the system learn from user feedback")
async def chat_feedback(
    query: str,
    response_text: str,
    rating: int = 3,
    feedback_text: str = "",
) -> ApiResponse[dict[str, Any]]:
    """Submit feedback for learning (Level 19)."""
    try:
        if _engine:
            _engine._learning.record_feedback(
                user_id="default",
                query=query,
                response=response_text,
                rating=max(1, min(5, rating)),
                feedback_text=feedback_text,
            )
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(text="✅ بازخورد شما ثبت شد. متشکرم! 🙏"),
            )
    except Exception as e:
        logger.warning("Feedback error: %s", e)

    return ApiResponse[ChatResponse](
        success=False,
        data=ChatResponse(text="⚠️ خطا در ثبت بازخورد."),
    )


@router.get("/stats", summary="Chat engine learning statistics",
            description="View learning statistics for the chat system")
async def chat_stats() -> ApiResponse[dict[str, Any]]:
    """Get learning stats from the engine."""
    if _engine:
        try:
            stats = _engine._learning.get_stats()
            return ApiResponse[dict[str, Any]](
                success=True,
                data=stats,
            )
        except Exception as e:
            logger.warning("Stats error: %s", e)

    return ApiResponse[dict[str, Any]](
        success=False,
        data={},
    )
