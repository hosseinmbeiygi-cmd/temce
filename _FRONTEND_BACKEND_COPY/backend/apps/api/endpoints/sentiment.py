from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

# Lazy singleton — avoids import-time side effects
_service = None


def _get_service():
    global _service
    if _service is None:
        from services.persian_sentiment_service import PersianSentimentService

        _service = PersianSentimentService()
    return _service


@router.post("/analyze", summary="Analyze Persian sentiment", description="Analyze sentiment of a single Persian text")
async def analyze_sentiment(
    body: dict[str, Any] = Body(..., examples=[{"text": "بازار امروز بسیار مثبت بود و رشد خوبی داشت"}]),
) -> ApiResponse[dict[str, Any]]:
    try:
        text = body.get("text", "")
        if not text:
            return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": "text is required"})
        service = _get_service()
        result = service.analyze(text)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Sentiment analysis failed")
        return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": str(exc)})


@router.post("/batch", summary="Batch analyze sentiment", description="Analyze sentiment for multiple Persian texts")
async def batch_analyze_sentiment(
    body: dict[str, Any] = Body(..., examples=[{"texts": ["بازار مثبت", "سقوط شدید قیمت‌ها"]}]),
) -> ApiResponse[dict[str, Any]]:
    try:
        texts = body.get("texts", [])
        if not texts:
            return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": "texts array is required"})
        service = _get_service()
        results = service.analyze_batch(texts)
        summary = {
            "total": len(results),
            "positive": sum(1 for r in results if r["label"] == "positive"),
            "negative": sum(1 for r in results if r["label"] == "negative"),
            "neutral": sum(1 for r in results if r["label"] == "neutral"),
            "avg_score": round(sum(r["score"] for r in results) / max(len(results), 1), 4),
        }
        return ApiResponse[dict[str, Any]](success=True, data={"results": results, "summary": summary})
    except Exception as exc:
        logger.exception("Batch sentiment analysis failed")
        return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": str(exc)})


@router.post(
    "/train", summary="Train sentiment model", description="Train the Persian sentiment ML model with labelled data"
)
async def train_sentiment_model(
    body: dict[str, Any] = Body(
        ..., examples=[{"texts": ["بازار خوب", "سقوط شدید"], "labels": ["positive", "negative"]}]
    ),
) -> ApiResponse[dict[str, Any]]:
    try:
        texts = body.get("texts", [])
        labels = body.get("labels", [])
        if not texts or not labels or len(texts) != len(labels):
            return ApiResponse[dict[str, Any]](
                success=False, data=None, error={"message": "texts and labels arrays must be non-empty and same length"}
            )
        service = _get_service()
        result = service.train(texts, labels)
        return ApiResponse[dict[str, Any]](
            success=result.get("success", False),
            data=result,
            error={"message": result.get("error")} if not result.get("success") else None,
        )
    except Exception as exc:
        logger.exception("Sentiment model training failed")
        return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": str(exc)})


@router.get(
    "/stats", summary="Sentiment service stats", description="Get statistics about the sentiment analysis service"
)
async def sentiment_stats() -> ApiResponse[dict[str, Any]]:
    try:
        service = _get_service()
        stats = service.get_stats()
        return ApiResponse[dict[str, Any]](success=True, data=stats)
    except Exception as exc:
        logger.exception("Sentiment stats failed")
        return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": str(exc)})
