"""Snapshot Service — ارکستراسیون کامل + self-check نرم.

build_snapshot() → دیکشنری ساختاریافته از همه asset + score.
اگر BrsApi قطع → fallback به TGJU (هم‌زمان).
Hard-stop با محاسبه تغییرات روزانه USD/TSE/DXY.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from . import bubbler, hard_stops, nav_checker, parity, pricer, scorer, signal_engine
from .constants import (
    COIN_SYMBOLS,
    DISPLAY_LABELS,
    FUND_SYMBOLS,
    GOLD_SYMBOLS,
    VALID_BUBBLE_PCT_RANGE,
    VALID_PARITY_GAP_RANGE,
    VALID_USD_RANGE,
    VALID_XAU_RANGE,
)
from .schemas import (
    AssetBlock,
    FundBlock,
    ReferenceBlock,
    ScoreBlock,
    ScoreComponents,
    SnapshotResponse,
)
from .secondary_source import fetch_prices as fetch_tgju_prices
from .secondary_source import is_available as tgju_available

logger = logging.getLogger(__name__)


def _display(symbol: str) -> str:
    return DISPLAY_LABELS.get(symbol, symbol)


async def _read_brsapi_prices() -> dict[str, float]:
    """خواندن قیمت‌ها از BrsApi QueryService. یک بار فراخوانی — کش در snapshot."""
    prices: dict[str, float] = {}
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from core.database import async_session_factory

        if async_session_factory is None:
            return prices
        async with async_session_factory() as session:
            svc = BrsApiQueryService(session=session)
            try:
                gold = await svc.get_gold_coin_prices()
                for row in gold:
                    sym = row.get("symbol")
                    p = row.get("price")
                    if sym and p and p > 0:
                        prices[sym] = float(p)
            except Exception as exc:
                logger.warning("BrsApi gold/coin fetch failed: %s", exc)
            try:
                fx = await svc.get_currency_prices()
                for row in fx:
                    sym = row.get("symbol")
                    p = row.get("price")
                    if sym and p and p > 0:
                        prices[sym] = float(p)
            except Exception as exc:
                logger.warning("BrsApi currency fetch failed: %s", exc)
            try:
                commodities = await svc.get_commodity_prices(category="precious_metal")
                for row in commodities:
                    sym = row.get("symbol")
                    p = row.get("price")
                    if sym and p and p > 0:
                        prices[sym] = float(p)
            except Exception as exc:
                logger.warning("BrsApi commodity fetch failed: %s", exc)
            # صندوق‌ها — اگر endpoint دارد
            try:
                if hasattr(svc, "get_fund_prices"):
                    f_rows = await svc.get_fund_prices()  # type: ignore
                    for row in f_rows or []:
                        sym = row.get("symbol")
                        p = row.get("price")
                        if sym and p and p > 0:
                            prices[sym] = float(p)
            except Exception as exc:
                logger.debug("BrsApi fund prices fetch failed: %s", exc)
    except Exception as exc:
        logger.error("BrsApi unavailable: %s", exc)
    return prices


async def _read_references(brsapi_prices: dict[str, float] | None = None) -> tuple[dict[str, float], str]:
    """xau_usd, usd_irt, aed_irt. Returns (prices, source)."""
    prices = brsapi_prices if brsapi_prices is not None else await _read_brsapi_prices()
    source = "brsapi"
    xau = prices.get("XAUUSD")
    usd = prices.get("USD")
    aed = prices.get("AED")

    if not all([xau, usd, aed]) and await tgju_available():
        logger.info("BrsApi incomplete, falling back to TGJU")
        tgju_prices = await fetch_tgju_prices()
        for tp in tgju_prices:
            if not xau and tp.symbol == "XAUUSD":
                xau = tp.price_irt
            elif not usd and tp.symbol == "USD":
                usd = tp.price_irt
            elif not aed and tp.symbol == "AED":
                aed = tp.price_irt
        if any([xau, usd, aed]):
            source = "tgju" if not all(prices.get(k) for k in ("XAUUSD", "USD", "AED")) else "mixed"

    if not all([xau, usd, aed]):
        raise RuntimeError("no price source available (BrsApi + TGJU both down)")

    return (
        {
            "xau_usd": float(xau),
            "usd_irt": float(usd),
            "aed_irt": float(aed),
        },
        source,
    )


async def _calc_daily_changes(session: AsyncSession, brsapi_prices: dict[str, float]) -> dict[str, float | None]:
    """محاسبه تغییرات روزانه برای hard-stop (USD، TSE، DXY)."""
    changes: dict[str, float | None] = {"usd": None, "tse": None, "dxy": None}
    # USD daily change از هیستوری GoldCoinHistory یا BrsApi
    with contextlib.suppress(Exception):
        closes = await signal_engine.fetch_closes(session, "USD", 2)
        if len(closes) >= 2 and closes[-2] > 0:
            changes["usd"] = (closes[-1] - closes[-2]) / closes[-2] * 100.0
        elif "USD" in brsapi_prices:
            # fallback: اگر هیستوری نیست، تغییرات را None بگذار
            pass
    # TSE: از برترین صندوق یا Index history اگر موجود باشد
    with contextlib.suppress(Exception):
        from brsapi.models.commodity import GoldCoinHistoryModel
        from sqlalchemy import desc, select

        # تلاش برای شاخص کل (نماد TSE کلی)
        for sym in ("TSE_INDEX", "INDEX", "TEDPIX"):
            try:
                stmt = (
                    select(GoldCoinHistoryModel.price_close)
                    .where(GoldCoinHistoryModel.symbol == sym)
                    .order_by(desc(GoldCoinHistoryModel.date))
                    .limit(2)
                )
                result = await session.execute(stmt)
                vals = [float(r[0]) for r in result.all() if r[0] and r[0] > 0]
                if len(vals) >= 2 and vals[0] > 0:
                    changes["tse"] = (vals[0] - vals[1]) / vals[1] * 100.0
                    break
            except Exception:
                continue
    # DXY: فعلاً از macro یا هیستوری ارز جهانی
    with contextlib.suppress(Exception):
        closes = await signal_engine.fetch_closes(session, "DXY", 2)
        if len(closes) >= 2 and closes[-2] > 0:
            changes["dxy"] = (closes[-1] - closes[-2]) / closes[-2] * 100.0
    return changes


def _soft_check(value: float, valid_range: tuple[float, float], name: str) -> bool:
    lo, hi = valid_range
    if not (lo <= value <= hi):
        logger.warning("%s out of range: %s not in [%s, %s]", name, value, lo, hi)
        return False
    return True


async def build_snapshot(session: AsyncSession) -> SnapshotResponse:
    """ساخت snapshot کامل — با یک بار خواندن BrsApi + hard-stop واقعی."""

    # 1) یک بار قیمت‌ها را بخوان
    brsapi_prices = await _read_brsapi_prices()

    refs, source = await _read_references(brsapi_prices)
    xau = refs["xau_usd"]
    usd = refs["usd_irt"]
    aed = refs["aed_irt"]

    # Self-check نرم (لاگ هشدار به‌جای assert crash)
    _soft_check(xau, VALID_XAU_RANGE, "XAU")
    _soft_check(usd, VALID_USD_RANGE, "USD")
    aed_parity = parity.aed_parity_usd(aed)
    aed_gap = parity.aed_gap_pct(usd, aed)
    _soft_check(aed_gap, VALID_PARITY_GAP_RANGE, "AED gap")

    ref_block = ReferenceBlock(
        xau_usd=xau,
        usd_irt=usd,
        aed_irt=aed,
        aed_parity_usd=aed_parity,
        aed_gap_pct=aed_gap,
        source=source,
    )

    # ── طلای وزنی ──
    gold: dict[str, AssetBlock] = {}
    for key, sym in GOLD_SYMBOLS.items():
        market = brsapi_prices.get(sym)
        if market is None or market <= 0:
            continue
        fair = pricer.fair_value(sym, xau, usd)
        bub = bubbler.calc_bubble(sym, market, fair, xau)
        if not _soft_check(bub.bubble_pct, VALID_BUBBLE_PCT_RANGE, f"{sym} bubble"):
            logger.warning("bubble outlier %s: %.2f%%", sym, bub.bubble_pct)
        gold[key] = AssetBlock(
            symbol=sym,
            display_name=_display(sym),
            asset_type="gold",
            market_price=market,
            fair_value=fair,
            bubble_abs=bub.bubble_abs,
            bubble_pct=bub.bubble_pct,
            implied_usd=bub.implied_usd,
        )

    # ── سکه ──
    coins: dict[str, AssetBlock] = {}
    for key, sym in COIN_SYMBOLS.items():
        market = brsapi_prices.get(sym)
        if market is None or market <= 0:
            continue
        fair = pricer.fair_value(sym, xau, usd)
        bub = bubbler.calc_bubble(sym, market, fair, xau)
        if not _soft_check(bub.bubble_pct, VALID_BUBBLE_PCT_RANGE, f"{sym} bubble"):
            logger.warning("bubble outlier %s: %.2f%%", sym, bub.bubble_pct)
        coins[key] = AssetBlock(
            symbol=sym,
            display_name=_display(sym),
            asset_type="coin",
            market_price=market,
            fair_value=fair,
            bubble_abs=bub.bubble_abs,
            bubble_pct=bub.bubble_pct,
            implied_usd=bub.implied_usd,
        )

    # ── صندوق‌ها — با override قیمت بازار واقعی ──
    fund_statuses = await nav_checker.get_all_funds_status(session, FUND_SYMBOLS, market_prices=brsapi_prices)
    funds: list[FundBlock] = []
    for f in fund_statuses:
        funds.append(
            FundBlock(
                symbol=f.symbol,
                fund_name=f.fund_name,
                nav_per_unit=f.nav_per_unit,
                market_price=f.market_price,
                bubble_pct=f.bubble_pct,
                bpr=f.bpr,
                real_buy_value=f.real_buy_value,
                real_sell_value=f.real_sell_value,
                net_inflow=f.net_inflow,
                nav_change_7d_pct=f.nav_7d_pct,
            )
        )

    # ── Technical (XAU) — همه اندیکاتورها ──
    indicators = await signal_engine.get_xau_indicators(session, days=40)
    xau_rsi = indicators.get("rsi")

    # ── Bubble + NAV for scoring ──
    coin_emami = coins.get("coin_emami")
    bubble_pct = coin_emami.bubble_pct if coin_emami else None

    nav_status = next((f for f in fund_statuses if "عیار" in f.symbol), None)
    nav_bubble_pct = nav_status.bubble_pct if nav_status else None
    nav_7d_pct = nav_status.nav_7d_pct if nav_status else None

    bpr = sum(f.bpr for f in fund_statuses) / len(fund_statuses) if fund_statuses else None
    net_inflow = sum(f.net_inflow for f in fund_statuses) if fund_statuses else None
    if bpr is not None and bpr == 0 and not fund_statuses:
        bpr = None

    # ── Hard stop — با داده واقعی روزانه ──
    daily = await _calc_daily_changes(session, brsapi_prices)
    hard = hard_stops.check_hard_stops(
        tse_daily_change_pct=daily.get("tse"),
        dxy_daily_change_pct=daily.get("dxy"),
        usd_irt_daily_change_pct=daily.get("usd"),
    )

    # ── Score ──
    score_result = scorer.compute_score(
        bubble_pct=bubble_pct,
        nav_bubble_pct=nav_bubble_pct,
        bpr=bpr,
        net_inflow=net_inflow,
        xau_rsi=xau_rsi,
        aed_gap_pct=aed_gap,
        nav_7d_pct=nav_7d_pct,
        hard_stop_active=hard.active,
        hard_stop_reason=hard.reason,
    )
    components_dict = score_result.components

    score_block = ScoreBlock(
        total=score_result.total,
        decision=score_result.decision,
        components=ScoreComponents(
            bubble=components_dict["bubble"].value,
            bubble_reason=components_dict["bubble"].reason,
            nav=components_dict["nav"].value,
            nav_reason=components_dict["nav"].reason,
            tsetmc=components_dict["tsetmc"].value,
            tsetmc_reason=components_dict["tsetmc"].reason,
            technical=components_dict["technical"].value,
            technical_reason=components_dict["technical"].reason,
            parity=components_dict["parity"].value,
            parity_reason=components_dict["parity"].reason,
            fund_flow=components_dict["fund_flow"].value,
            fund_flow_reason=components_dict["fund_flow"].reason,
        ),
        hard_stop_active=score_result.hard_stop_active,
        hard_stop_reason=score_result.hard_stop_reason,
    )

    # Self-check final — نرم
    if not (0 <= score_block.total <= 100):
        logger.warning("score out of range: %s", score_block.total)
    comp_sum = sum(
        [
            score_block.components.bubble,
            score_block.components.nav,
            score_block.components.tsetmc,
            score_block.components.technical,
            score_block.components.parity,
            score_block.components.fund_flow,
        ]
    )
    if comp_sum != score_block.total:
        logger.warning("components sum mismatch: %s vs %s", comp_sum, score_block.total)

    return SnapshotResponse(
        snapshot_at=datetime.now(UTC),
        references=ref_block,
        gold=gold,
        coins=coins,
        funds=funds,
        score=score_block,
        quality_flag="clean" if source == "brsapi" else "fallback",
    )


def snapshot_to_dict(snap: SnapshotResponse) -> dict[str, Any]:
    """تبدیل به dict برای Redis cache و JSON response."""
    return snap.model_dump(mode="json")
