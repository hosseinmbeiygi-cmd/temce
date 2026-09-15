from __future__ import annotations

import contextlib
import logging

from api.routes import router as forecast_router
from api.routers.precompute_router import router as precompute_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from services.query_service import init_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="BrsApi Gold & FX Forecasting Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

app.include_router(forecast_router)
app.include_router(precompute_router)
with contextlib.suppress(Exception):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
