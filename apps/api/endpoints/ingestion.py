"""Q2 P1 — Ingestion Service API boundary.

Standalone prefix so the future microservice can be extracted without
endpoint rewrites: the gateway will proxy /api/v1/ingestion/* to the new
service.

- GET  /ingestion/status
- POST /ingestion/brsapi/sync
- POST /ingestion/codal/sync
- GET  /ingestion/dead-letter/summary (+ Telegram alert if over threshold)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from core.config import settings
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.ingestion_service import get_ingestion_service

logger = get_logger(__name__)
router = APIRouter(tags=["Ingestion"])

_last_dl_alert: float = 0.0


@router.get("/status", summary="Ingestion service status")
async def ingestion_status() -> ApiResponse[dict[str, Any]]:
    svc = get_ingestion_service()
    data = await svc.status()
    return ApiResponse(success=True, data=data)


@router.post("/brsapi/sync", summary="Trigger BrsApi ingestion (budget-aware)")
async def trigger_brsapi_sync(symbols: list[str] | None = None) -> ApiResponse[dict[str, Any]]:
    svc = get_ingestion_service()
    result = await svc.ingest_brsapi(symbols=symbols)
    return ApiResponse(success=result.success, data=result.__dict__, error=None if result.success else {"message": result.error})


@router.post("/codal/sync", summary="Trigger CODAL ingestion")
async def trigger_codal_sync(days: int = 1) -> ApiResponse[dict[str, Any]]:
    svc = get_ingestion_service()
    result = await svc.ingest_codal(days=days)
    return ApiResponse(success=result.success, data=result.__dict__, error=None if result.success else {"message": result.error})


@router.get("/dead-letter/summary", summary="Dead-letter queue depth + alert")
async def dead_letter_summary() -> ApiResponse[dict[str, Any]]:
    """Return job:dead length and fire Telegram alert if over threshold (cooldown)."""
    global _last_dl_alert
    from core.cache import get_cache

    cache = get_cache()
    dl_len = 0
    try:
        client = cache.client
        if client is not None:
            dl_len = int(await client.llen(settings.job_queue_dead_letter) or 0)
    except Exception:
        pass

    alerted = False
    if dl_len >= settings.dl_alert_threshold and (time.time() - _last_dl_alert) > settings.dl_alert_cooldown_seconds:
        _last_dl_alert = time.time()
        try:
            from integrations.notifications.telegram_sender import TelegramSender

            sender = TelegramSender()
            await sender.send(f"⚠️ DL queue depth {dl_len} >= {settings.dl_alert_threshold} — check workers/logs")
            alerted = True
        except Exception:
            pass
        logger.warning("DL threshold exceeded: %d >= %d (alerted=%s)", dl_len, settings.dl_alert_threshold, alerted)

    return ApiResponse(
        success=True,
        data={"dead_letter_len": dl_len, "threshold": settings.dl_alert_threshold, "alerted": alerted},
    )
