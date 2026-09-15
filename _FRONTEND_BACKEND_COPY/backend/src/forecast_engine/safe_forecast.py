from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SafeResult:
    symbol: str
    ok: bool
    data: dict | None = None
    error_code: str | None = None
    error_message: str | None = None


async def safe_forecast_one(symbol: str, forecast_fn: Callable[[str], Awaitable[dict]]) -> SafeResult:
    try:
        data = await forecast_fn(symbol)
        return SafeResult(symbol=symbol, ok=True, data=data)
    except ValueError as exc:
        logger.info("forecast validation failed for %s: %s", symbol, exc)
        return SafeResult(symbol=symbol, ok=False, error_code="invalid_input", error_message=str(exc))
    except LookupError as exc:
        logger.info("no data for %s: %s", symbol, exc)
        return SafeResult(symbol=symbol, ok=False, error_code="no_data", error_message=str(exc))
    except Exception as exc:
        logger.exception("unexpected error forecasting %s", symbol)
        return SafeResult(symbol=symbol, ok=False, error_code="internal_error", error_message=str(exc))


async def safe_forecast_many(
    symbols: list[str], forecast_fn: Callable[[str], Awaitable[dict]]
) -> dict[str, SafeResult]:
    import asyncio

    results = await asyncio.gather(*[safe_forecast_one(s, forecast_fn) for s in symbols])
    return {r.symbol: r for r in results}


def to_api_response(results: dict[str, SafeResult]) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            sym: (r.data if r.ok else {"status": r.error_code, "message": r.error_message})
            for sym, r in results.items()
        },
        "meta": {
            "total": len(results),
            "succeeded": sum(1 for r in results.values() if r.ok),
            "failed": sum(1 for r in results.values() if not r.ok),
        },
    }
