from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from schemas.common.responses import ApiResponse

router = APIRouter()

RISK_METRICS: list[dict[str, Any]] = [
    {"label": "VaR (۹۵%)", "value": "-۲.۴%", "status": "safe", "description": "Value at Risk در سطح اطمینان ۹۵%"},
    {"label": "CVaR", "value": "-۴.۱%", "status": "warning", "description": "میانگین زیان در موارد فراتر از VaR"},
    {"label": "Sharpe Ratio", "value": "۱.۸۷", "status": "safe", "description": "نسبت بازده به ریسک"},
    {"label": "Beta", "value": "۱.۱۲", "status": "warning", "description": "حساسیت به بازار"},
    {"label": "Max Drawdown", "value": "-۱۵.۳%", "status": "danger", "description": "بیشترین کاهش از اوج"},
    {"label": "Volatility", "value": "۲۴.۶%", "status": "warning", "description": "انحراف معیار بازده‌ها"},
    {"label": "Exposure", "value": "۸۵%", "status": "safe", "description": "درصد سرمایه در معرض ریسک"},
    {"label": "Concentration", "value": "۳۲%", "status": "danger", "description": "درصد تمرکز در بزرگترین موقعیت"},
]


@router.get("/", summary="Risk metrics", description="Risk management indicators")
async def get_risk_metrics() -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse[list[dict[str, Any]]](success=True, data=RISK_METRICS)
