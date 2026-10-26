"""Snapshot Service — ارکستراسیون کامل + self-check نرم.

build_snapshot() → دیکشنری ساختاریافته از همه asset + score.
اگر BrsApi قطع → fallback به TGJU (هم‌زمان).
Hard-stop با محاسبه تغییرات روزانه USD/TSE/DXY.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from . import bubbler, hard_stops, nav_checker, parity, pricer, scorer, signal_engine
from .constants import (
    COIN_SYMBOLS,
    DISPLAY_LABELS,
    FUND_SYMBOLS,
    GOLD_SYMBOLS,
    PRICE_LIVE_TTL_SECONDS,
    VALID_BUBBLE_PCT_RANGE,
    VALID_PARITY_GAP_RANGE,
    VALID_USD_RANGE,
    VALID_XAU_RANGE,
)
from .pricer import round_to_rial
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

_REFERENCE_SYMBOLS = ("XAUUSD", "USD", "AED")


class PriceBook(dict[str, float]):
    """dict قیمت‌ها + زمان منبع هر نماد.

    زیرکلاس dict است تا مصرف‌کننده‌های قبلی (antigravity API) و تست‌هایی که
    ``{}`` برمی‌گردانند بدون تغییر کار کنند.
    """

    def __init__(
        self,
        *args: Any,
        as_of_by_symbol: dict[str, datetime] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.as_of_by_symbol: dict[str, datetime] = as_of_by_symbol or {}

    @property
    def as_of(self) -> datetime | None:
        times = [t for t in self.as_of_by_symbol.values() if t is not None]
        return max(times) if times else None


def _as_utc(value: Any) -> datetime | None:
    """fetched_at ممکن است ISO با Z، datetime naive، یا None باشد."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _row_recency(row: dict[str, Any]) -> tuple[datetime, int, int]:
    """کلید انتخاب «آخرین ردیف» — timestamp منبع، سپس time_unix، سپس id."""
    stamp = _as_utc(row.get("fetched_at")) or _as_utc(row.get("created_at"))
    return (
        stamp or datetime.min.replace(tzinfo=UTC),
        int(row.get("time_unix") or 0),
        int(row.get("id") or 0),
    )


def _latest_rows(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """یک ردیف به‌ازای هر نماد: جدیدترین، نه «آخری که در حلقه آمد».

    ``BrsApiQueryService`` همهٔ fetchها را برمی‌گرداند؛ overwrite ساده در حلقه
    می‌توانست قیمت قدیمی‌تر را جای جدیدتر بگذارد و timestamp را دور بریزد.
    """
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = row.get("symbol")
        price = row.get("price")
        if not symbol or price is None:
            continue
        try:
            if float(price) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        current = latest.get(symbol)
        if current is None or _row_recency(row) >= _row_recency(current):
            latest[symbol] = row
    return latest


def _merge_rows(book: PriceBook, rows: Iterable[dict[str, Any]]) -> None:
    for symbol, row in _latest_rows(rows).items():
        book[symbol] = float(row["price"])
        stamp = _as_utc(row.get("fetched_at")) or _as_utc(row.get("created_at"))
        if stamp is not None:
            book.as_of_by_symbol[symbol] = stamp


def _quality_for(source: str, as_of: datetime | None, now: datetime) -> str:
    """LIVE فقط با منبع brsapi و timestamp اثبات‌شدهٔ درون TTL.

    - TGJU: به‌دلیل تأخیر ذاتی و نبود timestamp منبع، همیشه DELAYED.
    - timestamp غایب یا آینده (clock skew): DELAYED، نه LIVE.
    """
    if source != "brsapi" or as_of is None:
        return "DELAYED"
    age = (now - as_of).total_seconds()
    if age < 0:
        return "DELAYED"
    return "LIVE" if age <= PRICE_LIVE_TTL_SECONDS else "DELAYED"


def _age_seconds(as_of: datetime | None, now: datetime) -> float | None:
    if as_of is None:
        return None
    return max(0.0, (now - as_of).total_seconds())


def _display(symbol: str) -> str:
    return DISPLAY_LABELS.get(symbol, symbol)


async def _read_brsapi_prices() -> PriceBook:
    """خواندن قیمت‌ها از BrsApi QueryService. یک بار فراخوانی — کش در snapshot.

    خروجی ``PriceBook`` است: قیمت + زمان fetched_at هر نماد. برای هر نماد فقط
    جدیدترین ردیف انتخاب می‌شود (خدمت همهٔ fetchها را برمی‌گرداند).
    """
    book = PriceBook()
    try:
        from brsapi.services.query_service import BrsApiQueryService
        from core.database import async_session_factory

        if async_session_factory is None:
            return book
        async with async_session_factory() as session:
            svc = BrsApiQueryService(session=session)
            try:
                _merge_rows(book, await svc.get_gold_coin_prices())
            except Exception as exc:
                logger.warning("BrsApi gold/coin fetch failed: %s", exc)
            try:
                _merge_rows(book, await svc.get_currency_prices())
            except Exception as exc:
                logger.warning("BrsApi currency fetch failed: %s", exc)
            try:
                _merge_rows(book, await svc.get_commodity_prices(category="precious_metal"))
            except Exception as exc:
                logger.warning("BrsApi commodity fetch failed: %s", exc)
            # صندوق‌ها — BrsApi هیچ get_fund_prices ندارد (۷D-4): اسنپشات
            # نماد‌به‌نمادِ همان سرویس، آخرین قیمت معامله‌شدهٔ صندوق را می‌دهد.
            for fund_symbol in FUND_SYMBOLS:
                if fund_symbol in book:
                    continue
                try:
                    snap = await svc.get_symbol_snapshot(fund_symbol)
                except Exception as exc:
                    logger.debug("BrsApi fund snapshot failed for %s: %s", fund_symbol, exc)
                    continue
                row = snap or {}
                price = row.get("price_last") or row.get("price_close")
                if price and float(price) > 0:
                    _merge_rows(
                        book,
                        [
                            {
                                "symbol": fund_symbol,
                                "price": price,
                                "fetched_at": row.get("fetched_at"),
                                "created_at": row.get("created_at"),
                                "time_unix": row.get("time_unix"),
                                "id": row.get("id"),
                            }
                        ],
                    )
    except Exception as exc:
        logger.error("BrsApi unavailable: %s", exc)
    return book


def _complete(book: dict[str, float]) -> bool:
    return all(book.get(symbol) and book[symbol] > 0 for symbol in _REFERENCE_SYMBOLS)


def _reference_as_of(book: PriceBook) -> datetime | None:
    """محافظه‌کارانه‌ترین زمان: قدیمی‌ترین timestamp مراجعِ نمایش‌داده‌شده.

    DXY هم اگر در snapshot هست یک قیمتِ نمایشی است، پس تازگی آن هم باید در
    محاسبه بیاید؛ در غیر این صورت یک DXY کهنه با برچسب LIVE نمایش داده می‌شد.
    اگر حتی یکی از مراجعِ موجود timestamp نداشته باشد، تازگی کل مجموعه
    اثبات‌پذیر نیست.
    """
    symbols = list(_REFERENCE_SYMBOLS)
    if book.get("DXY") is not None:
        symbols.append("DXY")
    stamps = [getattr(book, "as_of_by_symbol", {}).get(symbol) for symbol in symbols]
    if any(stamp is None for stamp in stamps):
        return None
    return min(stamps)  # type: ignore[type-var]


async def _read_references(
    brsapi_prices: dict[str, float] | None = None,
) -> tuple[dict[str, float], str, datetime | None, PriceBook]:
    """xau_usd, usd_irt, aed_irt از **یک منبع کامل** + همان book برای assetها.

    Returns (prices, source, as_of, book). قرارداد فاز ۰: ``source="mixed"``
    ممنوع است. اگر BrsApi هر سه مرجع را ندارد، مجموعهٔ کامل TGJU امتحان
    می‌شود؛ حتی قیمت طلا/سکه هم از همان منبع انتخاب می‌شود تا asset و مرجع
    دومنبعی نشوند.
    """
    prices = brsapi_prices if brsapi_prices is not None else await _read_brsapi_prices()

    if _complete(prices):
        book = prices if isinstance(prices, PriceBook) else PriceBook(prices)
        return (
            {
                "xau_usd": float(book["XAUUSD"]),
                "usd_irt": float(book["USD"]),
                "aed_irt": float(book["AED"]),
            },
            "brsapi",
            _reference_as_of(book),
            book,
        )

    if await tgju_available():
        logger.info("BrsApi incomplete; using the complete TGJU fallback set")
        tgju_prices = await fetch_tgju_prices()
        book = PriceBook(
            {p.symbol: float(p.price_irt) for p in tgju_prices},
            as_of_by_symbol={p.symbol: p.fetched_at for p in tgju_prices},
        )
        if _complete(book):
            selected = [book.as_of_by_symbol[symbol] for symbol in _REFERENCE_SYMBOLS]
            return (
                {
                    "xau_usd": float(book["XAUUSD"]),
                    "usd_irt": float(book["USD"]),
                    "aed_irt": float(book["AED"]),
                },
                "tgju",
                min(selected),
                book,
            )

    raise RuntimeError("no complete price source available (BrsApi + TGJU both incomplete)")


async def _calc_daily_changes(session: AsyncSession, brsapi_prices: dict[str, float]) -> dict[str, float | None]:
    """محاسبه تغییرات روزانه برای hard-stop (USD، TSE، DXY).

    هر منبع جداگانه خطا/نبودِ داده را لاگ می‌کند؛ پیش‌تر کل محاسبه در
    ``contextlib.suppress`` بود و نبود داده به سکوت تبدیل می‌شد (GS-07).
    """
    changes: dict[str, float | None] = {"usd": None, "tse": None, "dxy": None}

    # USD: تاریخچه در brsapi_gold_currency_pro_daily_history است.
    try:
        closes = await signal_engine.fetch_closes(session, "USD", 2)
        if len(closes) >= 2 and closes[-2] > 0:
            changes["usd"] = (closes[-1] - closes[-2]) / closes[-2] * 100.0
        else:
            logger.warning("USD daily history unavailable (%d rows)", len(closes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("USD daily change failed: %s", exc)

    # TSE: تغییر درصدی روز جاری شاخص کل در brsapi_index_values نگه‌داری می‌شود.
    try:
        from sqlalchemy import desc, select

        from brsapi.models.tsetmc import IndexValueModel

        stmt = (
            select(IndexValueModel.index_change_pct)
            .where(IndexValueModel.name.ilike("%شاخص کل%"))
            .order_by(desc(IndexValueModel.id))
            .limit(1)
        )
        pct = (await session.execute(stmt)).scalar()
        if pct is not None:
            changes["tse"] = float(pct)
        else:
            logger.warning("TSE index change_pct unavailable (no matching index row)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("TSE daily change failed: %s", exc)

    # DXY: منبع تاریخچه‌ای در DB موجود نیست → None (و در hard-stop به‌عنوان
    # «ارزیابی‌نشده» علامت می‌خورد).
    try:
        closes = await signal_engine.fetch_closes(session, "DXY", 2)
        if len(closes) >= 2 and closes[-2] > 0:
            changes["dxy"] = (closes[-1] - closes[-2]) / closes[-2] * 100.0
    except Exception as exc:  # noqa: BLE001
        logger.debug("DXY daily change unavailable: %s", exc)

    if all(v is None for v in changes.values()):
        logger.warning("hard-stop inputs missing: USD/DXY/TSE all None")
    return changes


def _soft_check(value: float | None, valid_range: tuple[float, float], name: str) -> bool:
    if value is None:
        return False  # check impossible; no warning needed
    lo, hi = valid_range
    if not (lo <= value <= hi):
        logger.warning("%s out of range: %s not in [%s, %s]", name, value, lo, hi)
        return False
    return True


def _build_asset_block(
    *,
    symbol: str,
    asset_type: str,
    market: float,
    xau: float,
    usd: float,
    source: str,
    book: PriceBook,
    ref_as_of: datetime | None,
    now: datetime,
) -> AssetBlock:
    """یک asset با ارزش ذاتی، حباب و **متادیتای همان ردیف قیمت**.

    ارزش‌ها به تومان‌اند (واحد خودِ BrsApi در raw_json) و در دقت ریال
    (۰.۱ تومان) با ROUND_HALF_UP گرد می‌شوند.
    """
    fair = pricer.fair_value(symbol, xau, usd)
    bub = bubbler.calc_bubble(symbol, market, fair, xau)
    asset_stamp = book.as_of_by_symbol.get(symbol)
    as_of = asset_stamp or ref_as_of
    # تازگیِ خودِ ردیف قیمت ملاک است؛ timestamp مرجع جای آن را نمی‌گیرد.
    quality = _quality_for(source, asset_stamp, now)
    return AssetBlock(
        symbol=symbol,
        display_name=_display(symbol),
        asset_type=asset_type,
        value=round_to_rial(fair, "toman"),
        unit="toman",
        asOf=as_of or now,
        source=source,
        quality=quality,
        market_price=round_to_rial(market, "toman"),
        fair_value=round_to_rial(fair, "toman"),
        bubble_abs=round_to_rial(bub.bubble_abs, "toman") if bub.bubble_abs is not None else None,
        bubble_pct=bub.bubble_pct,
        implied_usd=round(bub.implied_usd, 2) if bub.implied_usd is not None else None,
        quality_flag="clean",
    )


async def build_snapshot(session: AsyncSession) -> SnapshotResponse:
    """ساخت snapshot کامل — با یک بار خواندن BrsApi + hard-stop واقعی."""

    now = datetime.now(UTC)

    # 1) یک بار قیمت‌ها را بخوان؛ مرجع و asset از یک منبع کامل می‌آیند.
    brsapi_prices = await _read_brsapi_prices()

    refs, source, ref_as_of, book = await _read_references(brsapi_prices)
    if not isinstance(book, PriceBook):
        book = PriceBook(book)
    xau = refs["xau_usd"]
    usd = refs["usd_irt"]
    aed = refs["aed_irt"]

    # Self-check نرم (لاگ هشدار به‌جای assert crash)
    _soft_check(xau, VALID_XAU_RANGE, "XAU")
    _soft_check(usd, VALID_USD_RANGE, "USD")
    aed_parity = parity.aed_parity_usd(aed)
    aed_gap = parity.aed_gap_pct(usd, aed)
    _soft_check(aed_gap, VALID_PARITY_GAP_RANGE, "AED gap")

    dxy_raw = book.get("DXY")
    dxy_index = float(dxy_raw) if dxy_raw is not None and dxy_raw > 0 else None
    ref_block = ReferenceBlock(
        xau_usd=xau,
        usd_irt=usd,
        aed_irt=aed,
        aed_parity_usd=aed_parity,
        aed_gap_pct=aed_gap,
        source=source,
        age_seconds=_age_seconds(ref_as_of, now),
        asOf=ref_as_of,
        quality=_quality_for(source, ref_as_of, now),
        unit="toman",
        dxy_index=dxy_index,
    )

    # ── طلای وزنی ──
    gold: dict[str, AssetBlock] = {}
    for key, sym in GOLD_SYMBOLS.items():
        market = book.get(sym)
        if market is None or market <= 0:
            continue
        block = _build_asset_block(
            symbol=sym,
            asset_type="gold",
            market=market,
            xau=xau,
            usd=usd,
            source=source,
            book=book,
            ref_as_of=ref_as_of,
            now=now,
        )
        if not _soft_check(block.bubble_pct, VALID_BUBBLE_PCT_RANGE, f"{sym} bubble"):
            logger.warning("bubble outlier %s: %.2f%%", sym, block.bubble_pct)
        gold[key] = block

    # ── سکه ──
    coins: dict[str, AssetBlock] = {}
    for key, sym in COIN_SYMBOLS.items():
        market = book.get(sym)
        if market is None or market <= 0:
            continue
        block = _build_asset_block(
            symbol=sym,
            asset_type="coin",
            market=market,
            xau=xau,
            usd=usd,
            source=source,
            book=book,
            ref_as_of=ref_as_of,
            now=now,
        )
        if not _soft_check(block.bubble_pct, VALID_BUBBLE_PCT_RANGE, f"{sym} bubble"):
            logger.warning("bubble outlier %s: %.2f%%", sym, block.bubble_pct)
        coins[key] = block

    # ── صندوق‌ها — با override قیمت بازار واقعی ──
    fund_statuses = await nav_checker.get_all_funds_status(session, FUND_SYMBOLS, market_prices=book)
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

    # BPR تجمعی = مجموع خرید/مجموع فروش (برآورد وزنی به حجم)، نه میانگین سادهٔ
    # نسبت‌ها که صندوق بی‌داده آن را با صفر پایین می‌کشید (GS-15).
    total_buy = sum(f.real_buy_value for f in fund_statuses)
    total_sell = sum(f.real_sell_value for f in fund_statuses)
    bpr = (total_buy / total_sell) if (fund_statuses and total_sell > 0) else None
    net_inflow = sum(f.net_inflow for f in fund_statuses) if fund_statuses else None

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
        # موتور (scorer.ScoreResult) این سه فیلد را همیشه دارد؛ fallback پنهان
        # فقط یک پوشش دروغین بود و خطای قرارداد را به دادهٔ جعلی تبدیل می‌کرد.
        raw_total=score_result.raw_total,
        available_weight=score_result.available_weight,
        data_coverage_pct=score_result.data_coverage_pct,
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
    # فقط وقتی همهٔ اجزا داده دارند، جمع اجزا باید با امتیاز نهایی یکی باشد؛ در
    # حالت پوشش ناقص، total روی وزن موجود مقیاس می‌شود (GS-02).
    if score_result.data_coverage_pct >= 100.0 and comp_sum != score_block.total:
        logger.warning("components sum mismatch: %s vs %s", comp_sum, score_block.total)

    return SnapshotResponse(
        snapshot_at=now,
        references=ref_block,
        gold=gold,
        coins=coins,
        funds=funds,
        score=score_block,
        # legacy snapshot-level flag؛ UI نباید آن را به‌جای quality نمایش دهد.
        quality_flag="clean" if source == "brsapi" else "fallback",
    )


def snapshot_to_dict(snap: SnapshotResponse) -> dict[str, Any]:
    """تبدیل به dict برای Redis cache و JSON response."""
    return snap.model_dump(mode="json")
