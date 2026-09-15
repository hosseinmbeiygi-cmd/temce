"""Standalone Decision Engine microservice — FastAPI app.

Serves only the Decision Engine endpoints defined in apps.api.endpoints.decision_engine,
as a self-contained microservice per the 22-service architecture.

Endpoints:
  GET    /decision-engine/architecture
  GET    /decision-engine/features
  GET    /decision-engine/services
  GET    /decision-engine/database
  GET    /decision-engine/api
  GET    /decision-engine/overview
  POST   /decision-engine/seed
  GET    /decision-engine/decisions
  POST   /decision-engine/decisions
  GET    /decision-engine/decisions/buy-candidates
  GET    /decision-engine/decisions/watchlist
  GET    /decision-engine/decisions/rejected
  GET    /decision-engine/decisions/{symbol}
  GET    /decision-engine/decisions/{symbol}/history
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from apps.api.endpoints.decision_engine import router as decision_engine_router
from core.config import settings
from core.database import close_database, get_session, init_database
from core.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def _auto_seed_on_startup() -> dict:
    """Auto-seed architecture data from JSON into DB on first startup.

    Returns a dict with seed status for startup logging.
    """
    try:
        from sqlalchemy import func, select

        from apps.api.endpoints.decision_engine import _auto_seed
        from models.decision_engine import DecisionArchitecture, DecisionResult

        result: dict = {"arch_version": None, "arch_seeded": False, "decision_count": 0, "run_count": 0}

        async for session in get_session():
            # ── Check if architecture already seeded ──
            arch_result = await session.execute(select(DecisionArchitecture).limit(1))
            existing = arch_result.scalar_one_or_none()

            if existing is not None:
                result["arch_version"] = existing.version
                result["arch_seeded"] = False
                feat_count = len(existing.data.get("features", {}).get("features", [])) if existing.data else 0
                svc_count = len(existing.data.get("services", {}).get("services", [])) if existing.data else 0
                logger.info(
                    "Decision Engine — architecture already seeded: v%s (id=%s, %d features, %d services)",
                    existing.version,
                    existing.id,
                    feat_count,
                    svc_count,
                )
            else:
                # Perform the seed
                await _auto_seed(session)
                # Re-fetch to confirm
                arch_result = await session.execute(select(DecisionArchitecture).limit(1))
                seeded = arch_result.scalar_one_or_none()
                if seeded is not None:
                    result["arch_version"] = seeded.version
                    result["arch_seeded"] = True
                    feat_count = len(seeded.data.get("features", {}).get("features", [])) if seeded.data else 0
                    svc_count = len(seeded.data.get("services", {}).get("services", [])) if seeded.data else 0
                    logger.info(
                        "Decision Engine — architecture seeded: v%s (id=%s, %d features, %d services)",
                        seeded.version,
                        seeded.id,
                        feat_count,
                        svc_count,
                    )

            # ── Count existing decisions ──
            count_result = await session.execute(select(func.count(DecisionResult.id)))
            result["decision_count"] = count_result.scalar() or 0
            if result["decision_count"] > 0:
                logger.info("Decision Engine — existing decisions in DB: %d", result["decision_count"])

                # Count unique run IDs
                run_result = await session.execute(select(func.count(func.distinct(DecisionResult.run_id))))
                result["run_count"] = run_result.scalar() or 0
                logger.info("Decision Engine — unique runs: %d", result["run_count"])

            break

        return result

    except Exception as exc:
        logger.warning("Decision Engine — startup auto-seed skipped: %s", exc)
        return {"arch_version": None, "arch_seeded": False, "decision_count": 0, "run_count": 0}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler: init DB, auto-seed, close on shutdown."""
    _startup_time = time.time()

    setup_logging()

    # ── Startup Banner ──
    logger.info("═" * 55)
    logger.info("  🚀  Decision Engine  —  سامانه تصمیم‌یار بورس تهران")
    logger.info("  Version: %s  |  Log Level: %s", settings.api_version, settings.log_level)
    logger.info("═" * 55)

    # ── Database Initialization ──
    try:
        await init_database()
        logger.info("Decision Engine — database initialized (%.2fs)", time.time() - _startup_time)
    except Exception as exc:
        logger.warning("Decision Engine — database init skipped: %s", exc)

    # ── Auto-seed Architecture Data ──
    seed_info = await _auto_seed_on_startup()

    # ── Startup Complete ──
    elapsed = time.time() - _startup_time
    logger.info("Decision Engine — startup complete in %.2fs", elapsed)
    if seed_info.get("arch_version"):
        logger.info(
            "Decision Engine — architecture v%s | decisions: %d | runs: %d",
            seed_info["arch_version"],
            seed_info["decision_count"],
            seed_info["run_count"],
        )
    logger.info("Decision Engine — ready to accept requests")

    yield

    with suppress(Exception):
        await close_database()
    logger.info("Decision Engine — shut down (uptime: %.0fs)", time.time() - _startup_time)


def create_app() -> FastAPI:
    """Create and configure the Decision Engine microservice app."""
    app = FastAPI(
        title="Decision Engine — سامانه تصمیم‌یار بورس تهران",
        description=(
            "موتور تصمیم‌گیری مستقل: ترکیب BaseScore + MicroAdjustment + Penalty "
            "با Rulebook نسخه‌دار و تولید تصمیم ناضی (BUY / WATCHLIST / HOLD / REDUCE / REJECT / NEUTRAL)"
        ),
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Register Decision Engine routes
    app.include_router(
        decision_engine_router,
        prefix="/decision-engine",
        tags=["Decision Engine"],
    )

    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        return {"status": "ok", "service": "decision-engine"}

    return app


app = create_app()
