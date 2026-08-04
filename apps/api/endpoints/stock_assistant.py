"""Stock Assistant endpoint — conversational Q&A for the Smart Screener page.

POST /stock-assistant/query  — accepts a Persian text message, returns
structured response with analysis, recommendations, filters, etc.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.dependencies import get_brsapi_query_service
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


class AssistantRequest(BaseModel):
    message: str


class AssistantResponse(BaseModel):
    text: str
    type: str = "unknown"
    data: dict[str, Any] | None = None


@router.post(
    "/query",
    summary="Stock Assistant — Conversational Q&A",
    description="Ask questions about stocks in natural Persian. Supports analysis, comparison, filtering, market overview, portfolio management, alerts, and more.",
)
async def stock_assistant_query(
    body: AssistantRequest,
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[AssistantResponse]:
    try:
        from services.stock_assistant_service import StockAssistantService

        service = StockAssistantService(brsapi_service=brsapi)
        result = await service.process_message(body.message)

        return ApiResponse[AssistantResponse](
            success=True,
            data=AssistantResponse(
                text=result.get("text", ""),
                type=result.get("type", "unknown"),
                data=result.get("data"),
            ),
        )
    except ImportError as exc:
        logger.exception("Stock assistant import error — missing dependency?")
        return ApiResponse[AssistantResponse](
            success=False,
            data=AssistantResponse(
                text="⚠️ خطا در بارگذاری سرویس دستیار. لطفاً مطمئن شوید همه وابستگی‌ها نصب هستند: pip install -r requirements.txt",
                type="error",
            ),
            error={"message": f"Import error: {exc}"},
        )
    except Exception as exc:
        logger.exception("Stock assistant error")
        error_msg = str(exc)
        # Show a helpful message based on error type
        if "connection" in error_msg.lower() or "database" in error_msg.lower() or "psycopg" in error_msg.lower():
            user_text = "⚠️ خطا در اتصال به پایگاه داده. لطفاً مطمئن شوید PostgreSQL در حال اجراست (پورت ۵۴۳۲)."
        elif "timeout" in error_msg.lower():
            user_text = "⚠️ زمان درخواست به پایان رسید. لطفاً دوباره تلاش کنید."
        else:
            user_text = f"⚠️ خطایی رخ داد: {error_msg[:200]}. لطفاً دوباره تلاش کنید."
        return ApiResponse[AssistantResponse](
            success=False,
            data=AssistantResponse(
                text=user_text,
                type="error",
            ),
            error={"message": error_msg},
        )


@router.get(
    "/capabilities",
    summary="Get assistant capabilities",
    description="List all available features and commands.",
)
async def get_capabilities() -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "capabilities": [
                {
                    "name": "تحلیل نماد",
                    "description": "تحلیل کامل با ۱۰+ اندیکاتور تکنیکال",
                    "commands": ["تحلیل فولاد", "وضعیت خودرو", "پیشنهاد شپنا"],
                },
                {
                    "name": "الگوهای شمعی",
                    "description": "تشخیص خودکار الگوهای کندل‌استیک",
                    "commands": ["الگوهای فولاد", "کندل خودرو"],
                },
                {
                    "name": "مدیریت پرتفوی",
                    "description": "پیگیری سهام و محاسبه سود/زیان",
                    "commands": ["اضافه فولاد 100 50000", "خلاصه پرتفوی", "حذف فولاد"],
                },
                {
                    "name": "هشدارها",
                    "description": "ثبت هشدار قیمتی و اندیکاتوری",
                    "commands": ["هشدار فولاد rsi above 70", "لیست هشدارها"],
                },
                {
                    "name": "تحلیل چند بازه زمانی",
                    "description": "روزانه، هفتگی و ماهانه",
                    "commands": ["تحلیل چند بازه فولاد"],
                },
                {
                    "name": "حجم در قیمت",
                    "description": "سطوح حمایت/مقاومت بر اساس حجم",
                    "commands": ["حجم در قیمت فولاد"],
                },
                {
                    "name": "همبستگی",
                    "description": "محاسبه همبستگی بین سهام",
                    "commands": ["همبستگی فولاد خودرو"],
                },
                {
                    "name": "گزارش بازار",
                    "description": "گزارش جامع روزانه",
                    "commands": ["گزارش بازار"],
                },
                {
                    "name": "مقایسه",
                    "description": "مقایسه دو سهم",
                    "commands": ["مقایسه فولاد و خودرو"],
                },
                {
                    "name": "فیلتر",
                    "description": "فیلتر پیشرفته سهام",
                    "commands": ["فیلتر RSI<30 ROE>20 P/E<8"],
                },
            ],
        },
    )


@router.get(
    "/indicators",
    summary="List available technical indicators",
    description="Get list of all technical indicators available.",
)
async def get_indicators() -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "indicators": [
                {"name": "SMA", "description": "میانگین متحرک ساده"},
                {"name": "EMA", "description": "میانگین نمایی"},
                {"name": "RSI", "description": "شاخص قدرت نسبی"},
                {"name": "MACD", "description": "همگرایی/واگرایی میانگین متحرک"},
                {"name": "Bollinger Bands", "description": "نوارهای بولینگر"},
                {"name": "Stochastic", "description": "نوسان‌ساز استوکاستیک"},
                {"name": "ATR", "description": "میانگین دامنه واقعی"},
                {"name": "VWAP", "description": "میانگین حجمی وزنی قیمت"},
                {"name": "Ichimoku", "description": "ابر ایچیموکو"},
                {"name": "Fibonacci", "description": "سطوح فیبوناچی"},
                {"name": "MFI", "description": "شاخص جریان پول"},
            ],
        },
    )


@router.get(
    "/patterns",
    summary="List candlestick patterns",
    description="Get list of all detectable candlestick patterns.",
)
async def get_patterns() -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "patterns": [
                {"name": "دوجی", "type": "neutral", "description": "بی‌تصمیمی بازار"},
                {"name": "چکش", "type": "bullish", "description": "احتمال بازگشت صعودی"},
                {"name": "چکش وارونه", "type": "bearish", "description": "احتمال بازگشت نزولی"},
                {"name": "ستاره دنباله‌دار", "type": "bearish", "description": "فشار فروش در بالا"},
                {"name": "الگوی اینگالفینگ صعودی", "type": "bullish", "description": "شکست نزولی با قدرت"},
                {"name": "الگوی اینگالفینگ نزولی", "type": "bearish", "description": "شکست صعودی با قدرت"},
                {"name": "ستاره صبحگاهی", "type": "bullish", "description": "الگوی بازگشت صعودی قوی"},
                {"name": "ستاره شامگاهی", "type": "bearish", "description": "الگوی بازگشت نزولی قوی"},
                {"name": "سه سرباز سفید", "type": "bullish", "description": "روند صعودی قوی"},
                {"name": "سه کلاغ سیاه", "type": "bearish", "description": "روند نزولی قوی"},
                {"name": "الگوی هارامی صعودی", "type": "bullish", "description": "تضعیف روند نزولی"},
                {"name": "الگوی هارامی نزولی", "type": "bearish", "description": "تضعیف روند صعودی"},
            ],
        },
    )
