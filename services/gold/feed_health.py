"""Persisted health for the resilient gold spot feed.

``check_gold_feed_health`` performs one live failover check and records every
provider attempt (ok, error, timeout, stale) before returning. If all providers
fail, the attempts are still committed and the original
``GoldFeedUnavailableError`` is re-raised with the check id attached.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.gold_feed_health import GoldFeedHealthAttemptModel
from providers.gold_spot import build_default_gold_spot_providers
from services.gold.macro_indicators import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_STALENESS_SECONDS,
    GoldFeedUnavailableError,
    fetch_resilient_gold_spot,
)

logger = get_logger(__name__)

PRIMARY_GOLD_FEED_PROVIDER = "brsapi"
DEFAULT_FEED_HEALTH_LIMIT = 20


def _normalize_attempts(
    attempts: list[dict[str, Any]], successful_price: float | None
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for attempt in attempts:
        item = dict(attempt)
        if item.get("status") == "ok" and successful_price is not None:
            item["price"] = successful_price
        normalized.append(item)
    return normalized


def _attempt_payload(item: dict[str, Any], checked_at: datetime) -> dict[str, Any]:
    return {
        "provider": item.get("provider"),
        "status": item.get("status"),
        "ok": item.get("status") == "ok",
        "latency_ms": item.get("latency_ms"),
        "age_seconds": item.get("age_seconds"),
        "error": item.get("error"),
        "price": item.get("price"),
        "checked_at": checked_at.isoformat(),
    }


def summarize_primary_status(
    attempts: list[dict[str, Any]],
    checked_at: datetime | None = None,
    primary_name: str = PRIMARY_GOLD_FEED_PROVIDER,
) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(UTC)
    for item in attempts:
        if item.get("provider") == primary_name:
            payload = _attempt_payload(item, checked_at)
            payload["provider"] = primary_name
            return payload
    return {
        "provider": primary_name,
        "status": "not_attempted",
        "ok": False,
        "latency_ms": None,
        "age_seconds": None,
        "error": None,
        "price": None,
        "checked_at": checked_at.isoformat(),
    }


def _row_payload(row: GoldFeedHealthAttemptModel) -> dict[str, Any]:
    checked_at = row.checked_at.isoformat() if row.checked_at else None
    return {
        "check_id": row.check_id,
        "provider": row.provider,
        "status": row.status,
        "ok": bool(row.ok),
        "latency_ms": row.latency_ms,
        "age_seconds": row.age_seconds,
        "error": row.error,
        "price": row.price,
        "checked_at": checked_at,
    }


async def check_gold_feed_health(
    session: AsyncSession,
    providers: Sequence[Any] | None = None,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_staleness_seconds: float = MAX_STALENESS_SECONDS,
    now: float | None = None,
) -> dict[str, Any]:
    """Run one failover check, persist every attempt, and return the result."""
    active_providers = list(providers) if providers is not None else build_default_gold_spot_providers()
    check_id = uuid.uuid4().hex
    checked_at = datetime.now(UTC)

    result: dict[str, Any] | None = None
    error: GoldFeedUnavailableError | None = None
    try:
        result = await asyncio.to_thread(
            fetch_resilient_gold_spot,
            active_providers,
            timeout_seconds=timeout_seconds,
            max_staleness_seconds=max_staleness_seconds,
            now=now,
        )
        attempts = result["attempts"]
        successful_price = float(result["price"])
    except GoldFeedUnavailableError as exc:
        error = exc
        attempts = exc.attempts
        successful_price = None

    normalized = _normalize_attempts(attempts, successful_price)
    rows = [
        GoldFeedHealthAttemptModel(
            check_id=check_id,
            provider=str(item.get("provider") or "unknown"),
            status=str(item.get("status") or "error"),
            ok=item.get("status") == "ok",
            latency_ms=item.get("latency_ms"),
            age_seconds=item.get("age_seconds"),
            error=item.get("error"),
            price=item.get("price"),
            checked_at=checked_at,
        )
        for item in normalized
    ]
    session.add_all(rows)
    await session.commit()

    payload: dict[str, Any] = {
        "check_id": check_id,
        "checked_at": checked_at.isoformat(),
        "ok": error is None,
        "primary": summarize_primary_status(normalized, checked_at),
        "attempts": [_attempt_payload(item, checked_at) for item in normalized],
    }

    if error is not None:
        error.check_id = check_id  # type: ignore[attr-defined]
        error.checked_at = checked_at  # type: ignore[attr-defined]
        error.primary = summarize_primary_status(normalized, checked_at)  # type: ignore[attr-defined]
        error.attempts = normalized
        raise error

    assert result is not None
    payload.update(
        {
            "provider": result["provider"],
            "price": result["price"],
            "timestamp": result["timestamp"],
            "age_seconds": result["age_seconds"],
            "fallback_used": result["fallback_used"],
            "sources_tried": result["sources_tried"],
        }
    )
    return payload


async def load_recent_feed_health_attempts(
    session: AsyncSession,
    limit: int = DEFAULT_FEED_HEALTH_LIMIT,
) -> list[dict[str, Any]]:
    """Return the most recent persisted attempts, newest first."""
    statement = (
        select(GoldFeedHealthAttemptModel)
        .order_by(
            desc(GoldFeedHealthAttemptModel.checked_at),
            desc(GoldFeedHealthAttemptModel.id),
        )
        .limit(limit)
    )
    result = await session.execute(statement)
    return [_row_payload(row) for row in result.scalars().all()]
