"""Gold summary service — builds the live /api/v1/gold/analytics/summary response.

Orchestration only: fetches from providers, computes derived values, returns
a dict shaped like GoldSummaryResponse. Pure function from inputs to output.

The injectable clock lets tests freeze time and verify idempotency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.gold.constants import AED_PEG, MESGHAL_GRAMS
from services.gold.physical_arbitrage import calculate_coin_bubbles

logger = get_logger(__name__)

# ── Shape helpers ──────────────────────────────────────────────────────

def _missing_fields(values: dict[str, Any]) -> list[str]:
    """Return keys whose value is None (field not supplied by provider)."""
    missing: list[str] = []
    for key in sorted(values.keys()):
        val = values[key]
        if val is None:
            missing.append(key)
    return missing


def _coin_bubble_from_price(
    ounce_usd: float | None, usd_irr: float | None, coin_prices: dict[str, float | None]
) -> dict[str, dict[str, Any]] | None:
    """Build coin bubbles only when all inputs are present."""
    if ounce_usd is None or usd_irr is None:
        return None
    valid_prices: dict[str, float] = {}
    for name, price in coin_prices.items():
        if price is not None:
            # Normalize key: e.g. "coin_emami" -> "emami"
            # We treat the key as-is for the bubble calculator, which handles aliases
            valid_prices[name] = price
    if not valid_prices:
        return None
    try:
        bubbles = calculate_coin_bubbles(ounce_usd, usd_irr, valid_prices)
        return bubbles
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        logger.warning("coin bubble calculation failed: %s", exc, exc_info=True)
        return None


# ── Internal providers (resilient wrappers) ────────────────────────────

async def _fetch_ounce_usd() -> float | None:
    """Resilient ounce USD provider. Returns None on failure."""
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from services.gold.live_service import GoldLiveService

        brsapi = BrsApiQueryService()
        live = GoldLiveService(brsapi)
        prices = await live.get_live_prices()
        ounce = prices.get("gold_oz_usd")
        if ounce is None or ounce <= 0:
            return None
        return float(ounce)
    except Exception as exc:
        logger.warning("ounce USD provider failed: %s", exc, exc_info=True)
        return None


async def _fetch_usd_irr() -> float | None:
    """Resilient USD/IRR provider."""
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from services.gold.live_service import GoldLiveService

        brsapi = BrsApiQueryService()
        live = GoldLiveService(brsapi)
        prices = await live.get_live_prices()
        usd = prices.get("usd_irr")
        if usd is None or usd <= 0:
            return None
        return float(usd)
    except Exception as exc:
        logger.warning("USD/IRR provider failed: %s", exc, exc_info=True)
        return None


async def _fetch_melted_irr() -> float | None:
    """Melted gold price per mesghal (ثم) in IRR."""
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from services.gold.live_service import GoldLiveService

        brsapi = BrsApiQueryService()
        live = GoldLiveService(brsapi)
        prices = await live.get_live_prices()
        # BrsApi does not directly provide melted price; compute from 18k gram price.
        gold_18k = prices.get("gold_18k_irr")
        if gold_18k is None or gold_18k <= 0:
            return None
        return gold_18k * MESGHAL_GRAMS
    except Exception as exc:
        logger.warning("melted gold provider failed: %s", exc, exc_info=True)
        return None


async def _fetch_coin_prices() -> dict[str, float | None]:
    """Per-coin market prices in IRR. Returns dict of coin -> price or None."""
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from services.gold.live_service import GoldLiveService

        brsapi = BrsApiQueryService()
        live = GoldLiveService(brsapi)
        prices = await live.get_live_prices()
        coin_bahar = prices.get("coin_bahar_irr")
        return {
            "emami": coin_bahar,  # coin_bahar_irr is the emami/full coin price
            "half": None,
            "quarter": None,
            "gerami": None,
        }
    except Exception as exc:
        logger.warning("coin price provider failed: %s", exc, exc_info=True)
        return { "emami": None, "half": None, "quarter": None, "gerami": None }


async def _fetch_aed_implied_usd(usd_irr: float | None) -> float | None:
    """AED/USD implied from AED/IRR via USD/IRR."""
    if usd_irr is None:
        return None
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from services.gold.live_service import GoldLiveService

        brsapi = BrsApiQueryService()
        live = GoldLiveService(brsapi)
        all_prices = await live.get_live_prices()
        aed_irr = all_prices.get("aed_irr")
        if aed_irr is None or aed_irr <= 0:
            return None
        return aed_irr / usd_irr
    except Exception as exc:
        logger.warning("AED implied USD provider failed: %s", exc, exc_info=True)
        return None


# ── Main build function ─────────────────────────────────────────────────

# async def build_gold_summary(
#     *, clock: Any = None, providers: Any = None
# ) -> dict[str, Any]:
#     """Build the gold summary response.

#     Accepts injectable clock (datetime.now) and optionally custom providers
#     for testing. In production, uses real providers.
#     """
#     if clock is None:
#         clock = datetime.now(UTC)
#     if providers is None:
#         providers = {}
#
#     # Use provided providers or fetch live
#     ounce_usd = providers.get("ounce_usd") or await _fetch_ounce_usd()
#     usd_irr = providers.get("usd_irr") or await _fetch_usd_irr()
#     melted_irr = providers.get("melted_irr") or await _fetch_melted_irr()
#     coin_prices = providers.get("coin_prices") or await _fetch_coin_prices()
#     aed_implied = providers.get("aed_implied_usd") or await _fetch_aed_implied_usd(
#         usd_irr if "usd_irr" not in providers else providers["usd_irr"]
#     )
#
#     # Build derived values
#     result: dict[str, Any] = {
#         "timestamp": clock.isoformat(),
#         "ounce_usd": ounce_usd,
#         "usd_irr": usd_irr,
#         "melted_irr": melted_irr,
#         "aed_implied_usd": aed_implied,
#     }
#
#     # AED spread vs peg
#     if aed_implied is not None:
#         result["aed_spread_pct"] = (aed_implied - AED_PEG) / AED_PEG * 100.0
#     else:
#         result["aed_spread_pct"] = None
#
#     # Coin bubbles
#     coin_bubbles = _coin_bubble_from_price(ounce_usd, usd_irr, coin_prices or {})
#     result["coin_prices"] = coin_prices if coin_prices else None
#     result["coin_bubbles"] = coin_bubbles
#
#     # Missing fields
#     result["missing"] = _missing_fields(result)
#
#     return result



async def build_gold_summary(
    *, clock: Any = None, providers: Any = None
) -> dict[str, Any]:
    """Build the gold summary response.

    clock: callable returning datetime (frozen in tests).
    providers: optional dict of pre-computed values to bypass live providers.
    """
    if clock is None:
        clock = datetime.now(UTC)
    if providers is None:
        providers = {}

    # Fetch or use provided values
    if "ounce_usd" in providers:
        ounce_usd = providers["ounce_usd"]
    else:
        ounce_usd = await _fetch_ounce_usd()

    if "usd_irr" in providers:
        usd_irr = providers["usd_irr"]
    else:
        usd_irr = await _fetch_usd_irr()

    if "melted_irr" in providers:
        melted_irr = providers["melted_irr"]
    else:
        melted_irr = await _fetch_melted_irr()

    if "coin_prices" in providers:
        coin_prices = providers["coin_prices"]
    else:
        coin_prices = await _fetch_coin_prices()

    # AED implied
    if "aed_implied_usd" in providers:
        aed_implied = providers["aed_implied_usd"]
    else:
        aed_implied = await _fetch_aed_implied_usd(usd_irr)

    # Build result
    result: dict[str, Any] = {
        "timestamp": clock.isoformat(),
        "ounce_usd": ounce_usd,
        "usd_irr": usd_irr,
        "melted_irr": melted_irr,
        "aed_implied_usd": aed_implied,
    }

    # AED spread
    if aed_implied is not None:
        result["aed_spread_pct"] = (aed_implied - AED_PEG) / AED_PEG * 100.0
    else:
        result["aed_spread_pct"] = None

    # Coin bubbles
    coin_bubbles = _coin_bubble_from_price(ounce_usd, usd_irr, coin_prices or {})
    result["coin_prices"] = coin_prices if coin_prices else None
    result["coin_bubbles"] = coin_bubbles

    # Missing list
    result["missing"] = _missing_fields(result)

    return result
