from __future__ import annotations

import asyncio
import contextlib
import json

from core.redis_client import health_check
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from services.forecasting_service import forecast_any_symbol
from services.query_service import SessionLocal, get_latest_market_prices, record_forecast
from services.safe_forecast import safe_forecast_many, to_api_response
from services.symbol_registry import SYMBOL_REGISTRY, all_intraday_eligible_symbols
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ForecastingError, NoDataError, StaleDataError

router = APIRouter(prefix="/api", tags=["forecast"])


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


@router.get("/health")
async def health():
    redis_ok = await health_check()
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}


@router.get("/symbols")
async def list_symbols():
    return {
        key: {"canonical_id": meta.canonical_id, "asset_type": meta.asset_type.value, "display_name": meta.display_name}
        for key, meta in SYMBOL_REGISTRY.items()
    }


@router.get("/forecast/{symbol}")
async def get_single_forecast(symbol: str, current_market_price: float, session: AsyncSession = Depends(get_session)):
    from fastapi import HTTPException

    try:
        result = await forecast_any_symbol(symbol, current_market_price)
        await record_forecast(session, result)
        return result
    except StaleDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except NoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForecastingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/forecast")
async def get_bulk_forecast(session: AsyncSession = Depends(get_session)):
    symbols = all_intraday_eligible_symbols()
    latest_prices = await get_latest_market_prices(session, symbols)

    async def _forecast_fn(sym: str) -> dict:
        market_price = latest_prices.get(sym)
        if market_price is None:
            raise LookupError(f"قیمت بازار برای {sym} در دیتابیس موجود نیست.")
        return await forecast_any_symbol(sym, market_price)

    results = await safe_forecast_many(symbols, _forecast_fn)
    return to_api_response(results)


@router.websocket("/ws/forecast")
async def websocket_forecast(websocket: WebSocket):
    """Push forecast stream — replaces 15s Poll with server push.

    On connect: sends bulk forecast immediately, then every `interval` seconds.
    Client may send JSON {"symbols": ["GOLD_18K", ...], "interval": 15} to filter.
    """
    await websocket.accept()
    interval = 15
    requested_symbols: list[str] | None = None
    try:
        while True:
            # Build forecast with a short-lived DB session
            try:
                async with SessionLocal() as session:
                    symbols = requested_symbols or all_intraday_eligible_symbols()
                    latest_prices = await get_latest_market_prices(session, symbols)

                    async def _forecast_fn(sym: str, _prices=latest_prices) -> dict:  # noqa: B023
                        mp = _prices.get(sym)
                        if mp is None:
                            raise LookupError(f"قیمت بازار برای {sym} موجود نیست.")
                        return await forecast_any_symbol(sym, mp)

                    results = await safe_forecast_many(symbols, _forecast_fn)
                    payload = to_api_response(results)
                    for r in payload.get("data", {}).get("results", []):
                        if r.get("status") == "ok":
                            with contextlib.suppress(Exception):
                                await record_forecast(session, r["data"])
                    await session.commit()
            except Exception as exc:
                payload = {"status": "error", "detail": str(exc)}  # type: ignore

            try:
                await websocket.send_json(payload)
            except WebSocketDisconnect:
                break
            except Exception:
                break  # noqa: SIM105

            # Sleep `interval` but wake early if client sends a filter message
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=interval)  # noqa: UP041
                try:
                    msg = json.loads(raw)
                    if isinstance(msg.get("symbols"), list):
                        requested_symbols = [str(s) for s in msg["symbols"] if s]
                    if isinstance(msg.get("interval"), int) and 5 <= msg["interval"] <= 60:
                        interval = int(msg["interval"])
                except Exception:
                    pass  # noqa: SIM105
                # Immediately loop to send filtered data without waiting full interval
                continue
            except TimeoutError:  # noqa: UP041
                continue
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass  # noqa: SIM105
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
