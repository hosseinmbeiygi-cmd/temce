"""Archive multi-horizon gold and silver forecasts in one JSON file.

The archive only stores forecasts when a current price can be obtained from
the configured API. Missing markets are recorded as unavailable instead of
being filled with fabricated prices.

Usage:
    python scripts/archive_precious_metal_forecasts.py
    python scripts/archive_precious_metal_forecasts.py --api-base http://127.0.0.1:8000/api/v1

If the local API is unavailable, the script automatically downloads from
BrsApi.ir when ``BRSAPI_API_KEY`` is present in the environment or ``.env``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # optional dependency for standalone execution
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = REPO_ROOT / "data" / "archive" / "precious_metals_forecasts.json"
TIMEFRAMES = (1, 3, 7, 14, 30, 90)

if load_dotenv is not None:
    load_dotenv(REPO_ROOT / ".env")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _fetch_json(url: str, timeout: float = 8.0) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("data", payload)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    # Handle both flat lists and the nested Gold_Currency_Pro shape:
    # data.gold.{ounce,type,coin} -> lists of priced records.
    if any(key in payload for key in ("symbol", "code")) and any(key in payload for key in ("price", "value", "last_price")):
        return [payload]
    records: list[dict[str, Any]] = []
    for value in payload.values():
        if isinstance(value, (dict, list)):
            records.extend(_as_list(value))
    return records


def _symbol(item: dict[str, Any]) -> str:
    return str(item.get("symbol") or item.get("code") or item.get("name") or "").strip().upper()


def _price(item: dict[str, Any]) -> float | None:
    for key in ("price", "price_last", "last_price", "close", "value"):
        value = item.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def _collect_prices(api_base: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    prices: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    endpoints = (
        ("/brsapi/gold-coin", "gold-coin"),
        ("/brsapi/commodities?category=precious_metal", "commodities"),
    )
    for path, source in endpoints:
        try:
            items = _as_list(_fetch_json(f"{api_base.rstrip('/')}{path}"))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            errors.append(f"{source}: {exc}")
            continue
        for item in items:
            value = _price(item)
            if value is not None:
                prices[_symbol(item)] = {"price": value, "source": source, "raw": item}

    # Read the latest persisted rows directly when the local HTTP API is down.
    if not prices:
        try:
            db_prices = asyncio.run(_collect_prices_from_db())
            prices.update(db_prices)
        except Exception as exc:
            errors.append(f"database: {exc}")

    # Automatic direct-download fallback: do not require the local FastAPI
    # process to be running when a BrsApi key is configured.
    if not prices:
        api_key = os.environ.get("BRSAPI_API_KEY", "").strip()
        if api_key:
            direct_endpoints = (
                ("https://api.brsapi.ir/Market/Gold_Currency_Pro.php?key=" + urllib.parse.quote(api_key) + "&section=gold_coin", "brsapi-direct-gold"),
                ("https://api.brsapi.ir/Market/Commodity.php?key=" + urllib.parse.quote(api_key), "brsapi-direct-commodities"),
            )
            for url, source in direct_endpoints:
                try:
                    for item in _as_list(_fetch_json(url)):
                        value = _price(item)
                        symbol = _symbol(item)
                        if value is not None and symbol:
                            prices[symbol] = {"price": value, "source": source, "raw": item}
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    errors.append(f"{source}: {exc}")
        else:
            errors.append("brsapi-direct: BRSAPI_API_KEY is not configured")
    return prices, errors


async def _collect_prices_from_db() -> dict[str, dict[str, Any]]:
    """Load latest persisted prices from the existing BrsApi tables."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from brsapi.models.commodity import CommodityPriceModel, GoldCoinPriceModel, GoldCurrencyProPriceModel
    from scripts._db import database_url_async

    engine = create_async_engine(database_url_async(), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    prices: dict[str, dict[str, Any]] = {}
    try:
        async with session_factory() as session:
            for model, source in (
                (GoldCoinPriceModel, "db:brsapi_gold_coin_prices"),
                (GoldCurrencyProPriceModel, "db:brsapi_gold_currency_pro_prices"),
                (CommodityPriceModel, "db:brsapi_commodity_prices"),
            ):
                rows = (await session.execute(select(model).order_by(model.id.desc()).limit(500))).scalars().all()
                for row in rows:
                    item = {
                        "symbol": getattr(row, "symbol", ""),
                        "name": getattr(row, "name", ""),
                        "price": getattr(row, "price", None),
                        "fetched_at": getattr(row, "fetched_at", None),
                        "date": getattr(row, "date", None),
                        "time": getattr(row, "time", None),
                    }
                    value = _price(item)
                    symbol = _symbol(item)
                    if value is not None and symbol and symbol not in prices:
                        prices[symbol] = {"price": value, "source": source, "raw": item}
    finally:
        await engine.dispose()
    return prices


def _find_price(prices: dict[str, dict[str, Any]], symbols: tuple[str, ...]) -> dict[str, Any] | None:
    for symbol in symbols:
        if symbol in prices:
            return prices[symbol]
    return None


def _asset_specs() -> tuple[dict[str, Any], ...]:
    return (
        {"key": "gold_18k", "market": "gold", "display_name": "طلای ۱۸ عیار", "symbols": ("IR_GOLD_18K", "GOLD18", "GOLD_18")},
        {"key": "gold_24k", "market": "gold", "display_name": "طلای ۲۴ عیار", "symbols": ("IR_GOLD_24K", "GOLD24", "GOLD_24")},
        {"key": "gold_melted", "market": "gold", "display_name": "طلای آب‌شده نقدی", "symbols": ("IR_GOLD_MELTED", "GOLDMELTED", "MELTED_GOLD")},
        {"key": "coin_emami", "market": "gold", "display_name": "سکه امامی", "symbols": ("IR_COIN_EMAMI", "GOLD_IMAMI", "COIN_EMAMI")},
        {"key": "coin_bahar", "market": "gold", "display_name": "سکه بهار آزادی", "symbols": ("IR_COIN_BAHAR", "GOLD_BAHAR", "COIN_BAHAR")},
        {"key": "coin_half", "market": "gold", "display_name": "نیم‌سکه", "symbols": ("IR_COIN_HALF", "COIN_HALF", "HALF_COIN")},
        {"key": "coin_quarter", "market": "gold", "display_name": "ربع‌سکه", "symbols": ("IR_COIN_QUARTER", "COIN_QUARTER", "QUARTER_COIN")},
        {"key": "coin_1g", "market": "gold", "display_name": "سکه یک‌گرمی", "symbols": ("IR_COIN_1G", "COIN_1G", "GOLD_1G")},
        {"key": "xau_usd", "market": "gold", "display_name": "انس جهانی طلا", "symbols": ("XAUUSD", "XAU_USD")},
        {"key": "xag_usd", "market": "silver", "display_name": "انس جهانی نقره", "symbols": ("XAGUSD", "XAG_USD")},
    )


def _forecast_asset(spec: dict[str, Any], current: dict[str, Any] | None, generated_at: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "symbol": spec["key"],
        "market": spec["market"],
        "display_name": spec["display_name"],
        "generated_at": generated_at,
        "status": "unavailable",
        "source": None,
        "current_price": None,
        "timeframes": [],
    }
    if current is None:
        base["error"] = "No current price returned by configured API"
        return base

    from src.forecasting.service import forecast_from_history

    current_price = float(current["price"])
    base.update({"status": "generated", "source": current["source"], "current_price": current_price})
    timeframes: list[dict[str, Any]] = []
    for horizon in TIMEFRAMES:
        try:
            result = asyncio.run(forecast_from_history(spec["key"], horizon, current_price))
        except ValueError as exc:
            # No real history for this symbol/horizon — record honestly.
            timeframes.append({"horizon_days": horizon, "error": str(exc)})
            continue
        timeframes.append(
            {
                "horizon_days": horizon,
                "model": result["model"],
                "quality": result["quality"],
                "risk": result["risk"],
                "forecast": result["forecast"],
                "meta": result.get("meta"),
            }
        )
    base["timeframes"] = timeframes
    if not any("forecast" in timeframe for timeframe in timeframes):
        base["status"] = "unavailable"
        base["error"] = "No real daily history available for this symbol"
    return base


def _new_archive() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "archive_name": "precious_metals_forecasts",
        "description": "آرشیو پیش‌بینی چندافقی قیمت طلا و نقره",
        "timeframes_days": list(TIMEFRAMES),
        "assets": {
            "gold": [
                "gold_18k",
                "gold_24k",
                "gold_melted",
                "coin_emami",
                "coin_bahar",
                "coin_half",
                "coin_quarter",
                "coin_1g",
                "xau_usd",
            ],
            "silver": ["xag_usd"],
        },
        "snapshots": [],
    }


def build_snapshot(api_base: str) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    prices, errors = _collect_prices(api_base)
    assets = {
        spec["key"]: _forecast_asset(spec, _find_price(prices, spec["symbols"]), generated_at)
        for spec in _asset_specs()
    }
    return {
        "snapshot_id": generated_at.replace(":", "").replace("+00:00", "Z"),
        "generated_at": generated_at,
        "api_base": api_base,
        "source_errors": errors,
        "assets": assets,
    }


def write_snapshot(api_base: str, path: Path = ARCHIVE_PATH, replace: bool = False) -> dict[str, Any]:
    archive = _new_archive()
    if path.exists() and not replace:
        with contextlib.suppress(OSError, json.JSONDecodeError):
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                archive.update(existing)
    snapshot = build_snapshot(api_base)
    # A transport/API outage must not become a misleading historical snapshot.
    # Keep the in-memory result for diagnostics, but do not mutate the archive.
    if not any(asset.get("status") == "generated" for asset in snapshot["assets"].values()):
        snapshot["archived"] = False
        return snapshot
    snapshots = archive.setdefault("snapshots", [])
    snapshots.append(snapshot)
    snapshot["archived"] = True
    archive["latest_snapshot_id"] = snapshot["snapshot_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--archive", type=Path, default=ARCHIVE_PATH)
    parser.add_argument("--replace", action="store_true", help="Replace existing snapshots")
    args = parser.parse_args()
    snapshot = write_snapshot(args.api_base, args.archive, args.replace)
    statuses = {key: value["status"] for key, value in snapshot["assets"].items()}
    print(
        json.dumps(
            {"archive": str(args.archive), "snapshot_id": snapshot["snapshot_id"], "archived": snapshot.get("archived", False), "assets": statuses},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
