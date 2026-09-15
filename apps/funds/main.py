"""ورودی مستقل صندوق‌یار — اجرا:

    uvicorn apps.funds.main:app --reload

مسیرها (پیش‌فرض بدون /sandooghyar):
    GET  /funds
    GET  /funds/{symbol}
    GET  /funds/compare?symbols=A,B
    POST /funds/screener
    GET  /funds/bubble/live
    GET  /funds/health/sources
    GET  /funds/backtest/report
    GET  /funds/alerts | POST /funds/alerts
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as funds_api_router
from .constants import DISCLAIMER_API

app = FastAPI(
    title="Sandooghyar — پایش هوشمند صندوق‌های سرمایه‌گذاری ایران",
    version="0.1.0",
    description=(
        "سامانه تحلیل ۵۶ شاخصی صندوق‌ها در ۵ لایه، امتیازدهی وزن‌دار ۰-۱۰۰، پایش حباب هم‌گروه و اسکرینر. " + DISCLAIMER_API
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(funds_api_router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "sandooghyar",
        "version": "0.1.0",
        "docs": "/docs",
        "disclaimer": DISCLAIMER_API,
    }
