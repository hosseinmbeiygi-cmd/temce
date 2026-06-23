from fastapi import APIRouter
from fastapi.responses import JSONResponse
from schemas.common.responses import ApiResponse
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("")
async def dashboard_overview():
    return {
        "metrics": {"total_instruments": 0, "active_signals": 0, "total_volume": 0.0},
        "market_breakdown": [],
        "top_gainers": [],
        "top_losers": [],
        "recent_announcements": [],
    }


@router.get("/health")
async def dashboard_health():
    return {"status": "ok"}
