from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session, get_news_service
from core.logging import get_logger
from core.result import PaginatedResult
from domain.news.news_item import NewsItem
from schemas.api.news import NewsRequest, NewsResponse, SymbolMatchMeta
from schemas.common.responses import ApiResponse
from services.news_service import NewsService

logger = get_logger(__name__)

router = APIRouter()

# Standard categories — must match the ingestion-side classification in
# ``services/news_ingestion.py`` (``_CATEGORY_KEYWORDS``). ``companies`` is
# plural on purpose: the RSS classifier has always emitted ``companies`` and
# the frontend tab key is ``companies`` too. Accepting the legacy singular
# ``company`` and the spec's ``stock_market`` keeps old clients working while
# they migrate.
VALID_CATEGORIES = {"market", "companies", "company", "economic", "political", "international", "stock_market"}

# Canonical output category for each accepted alias (used to normalize before
# comparing against stored items, so both spellings return the same rows).
_CATEGORY_ALIASES = {"company": "companies", "stock_market": "market"}


def normalize_news_category(category: str) -> str:
    """Map a client-supplied category to the canonical stored value.

    The ingestion pipeline stores ``companies`` (plural) and ``market`` — the
    singular ``company`` and the news-module spec's ``stock_market`` are
    aliases. Unknown values pass through unchanged so callers can decide.
    """
    return _CATEGORY_ALIASES.get(category, category)


def parse_news_date_range(
    date_from: str | None, date_to: str | None
) -> tuple[datetime | None, datetime | None] | None:
    """Parse the ``?from``/``?to`` query params into aware UTC datetimes.

    Accepts ISO-8601 dates and datetimes: ``2026-09-16`` (whole-day window
    when used as ``?to``), ``2026-09-16T10:00``, ``...:00Z``, ``...+03:30``.
    Naive values are read as UTC. Returns ``None`` when both params are
    absent; raises ``ValueError`` with a client-friendly message on garbage
    input (the endpoint converts that into a 400-style error payload).
    Each bound may be given alone — the other stays unbounded.
    """
    # FastAPI's Query() default object leaks through when router functions
    # are called directly (unit tests invoke them as plain coroutines) —
    # treat any non-str value as absent, same as an omitted param.
    date_from = date_from if isinstance(date_from, str) and date_from else None
    date_to = date_to if isinstance(date_to, str) and date_to else None
    if not date_from and not date_to:
        return None

    def _parse(value: str, name: str) -> datetime:
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"Invalid {name} '{value}'. Use ISO-8601, e.g. 2026-09-16 or 2026-09-16T10:00:00Z"
            ) from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    from_dt = _parse(date_from, "from") if date_from else None
    to_dt = _parse(date_to, "to") if date_to else None
    # A bare date passed as ?to must include that entire day.
    if to_dt is not None and date_to is not None and len(date_to.strip()) <= 10:
        to_dt = to_dt.replace(hour=23, minute=59, second=59)
    return (from_dt, to_dt)

# Background refresh state
_refresh_status: dict[str, Any] = {"running": False, "last_run": None, "last_result": None}


def _item_to_response(item: NewsItem | dict[str, Any]) -> NewsResponse:
    """Convert a NewsItem domain object to a NewsResponse schema."""
    if isinstance(item, dict):
        trending = bool(item.get("trending", False))
        return NewsResponse(**item, trending=trending)
    pub_date = ""
    if item.publish_date:
        pub_date = item.publish_date.isoformat() if isinstance(item.publish_date, datetime) else str(item.publish_date)
    elif item.created_at:
        pub_date = item.created_at.isoformat() if isinstance(item.created_at, datetime) else str(item.created_at)
    # Mark as trending if sentiment is strong (positive or negative)
    trending = item.sentiment_label in ("positive", "negative") and abs(item.sentiment or 0) > 0.3
    return NewsResponse(
        id=item.id,
        title=item.title,
        summary=item.summary or "",
        source=item.source or "",
        url=item.url or "",
        category=item.category or "",
        symbols=item.symbols or [],
        published_at=pub_date,
        sentiment=item.sentiment_label or "neutral",
        sentiment_score=item.sentiment if isinstance(item.sentiment, (int, float)) else 0.0,
        created_at=item.created_at.isoformat() if isinstance(item.created_at, datetime) else str(item.created_at) if item.created_at else "",
        trending=trending,
    )


async def _get_market_news(session: AsyncSession, limit: int = 50) -> list[NewsResponse]:
    """
    Fallback: generate market news items from brsapi_symbol_snapshots
    when the news_articles table is empty.
    """
    try:
        # Get latest snapshots - use subquery to avoid full table sort
        rows = await session.execute(
            text("""
                SELECT symbol, name, price_last, price_last_change_pct,
                       trade_volume, trade_value, time
                FROM brsapi_symbol_snapshots
                WHERE price_last > 0
                  AND price_last_change_pct IS NOT NULL
                ORDER BY ABS(price_last_change_pct) DESC
                LIMIT :lim
            """),
            {"lim": limit},
        )
        items: list[NewsResponse] = []
        for row in rows:
            symbol = row.symbol or ""
            change = row.price_last_change_pct or 0
            direction = "صعود" if change > 0 else "نزول"
            items.append(NewsResponse(
                id=f"market_{symbol}",
                title=f"{symbol}: {abs(change):.2f}% {direction}",
                summary=f"قیمت آخر {symbol} به {row.price_last:,.0f} ریال رسید. حجم معاملات: {row.trade_volume or 0:,.0f}",
                source="BrsApi",
                category="market",
                symbols=[symbol],
                published_at=row.time or "",
                sentiment="positive" if change > 0 else "negative",
                sentiment_score=change / 100 if change else 0,
            ))
        return items
    except Exception:
        logger.exception("_get_market_news: failed to fetch snapshots")
        return []


@router.get("")
async def list_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    category: str | None = Query(None, description="Filter by category (market, companies, economic, political, international)"),
    from_: str | None = Query(None, alias="from", description="ISO-8601 date or datetime (UTC), e.g. 2026-09-16T00:00:00Z"),
    to: str | None = Query(None, alias="to", description="ISO-8601 date or datetime (UTC); a bare date includes the whole day"),
    service: NewsService = Depends(get_news_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PaginatedResult[NewsResponse]]:
    try:
        date_range = parse_news_date_range(from_, to)
    except ValueError as exc:
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=False,
            data=None,
            error={"message": str(exc)},
        )
    date_from, date_to = date_range if date_range else (None, None)
    result = await service.list_all(page, page_size, date_from=date_from, date_to=date_to)
    if result.success and result.value and len(result.value.items) > 0:
        paginated = result.value
        items = [_item_to_response(item) for item in paginated.items]
        # Apply category filter if provided (keep DB total, page may have fewer)
        # Normalized first so the legacy ``company`` alias matches stored ``companies``.
        if category:
            canonical = normalize_news_category(category)
            items = [item for item in items if item.category == canonical]
        # Use the true DB total, not the current page size
        total = paginated.total
        total_pages = max(1, (total + page_size - 1) // page_size)
        if page > total_pages and total_pages > 0:
            items = []
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=True,
            data=PaginatedResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )
    # Fallback: return market news from symbol snapshots
    if page > 1:
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=True,
            data=PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1),
        )
    market_news = await _get_market_news(session, page_size)
    if category and category != "market":
        market_news = [n for n in market_news if n.category == category]
    return ApiResponse[PaginatedResult[NewsResponse]](
        success=True,
        data=PaginatedResult(
            items=market_news,
            total=len(market_news),
            page=page,
            page_size=page_size,
            total_pages=1,
        ),
    )


@router.post("")
async def create_news(
    body: NewsRequest,
    service: NewsService = Depends(get_news_service),
) -> ApiResponse[NewsResponse]:
    result = await service.create(**body.model_dump(exclude_none=True))
    data = _item_to_response(result.value) if result.value else None
    return ApiResponse[NewsResponse](
        success=result.success,
        data=data,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/search")
async def search_news(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
    service: NewsService = Depends(get_news_service),
) -> ApiResponse[PaginatedResult[NewsResponse]]:
    try:
        date_range = parse_news_date_range(from_, to)
    except ValueError as exc:
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=False,
            data=None,
            error={"message": str(exc)},
        )
    date_from, date_to = date_range if date_range else (None, None)
    result = await service.search(q, page, page_size, date_from=date_from, date_to=date_to)
    if result.success and result.value:
        paginated = result.value
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=True,
            data=PaginatedResult(
                items=[_item_to_response(item) for item in paginated.items],
                total=paginated.total,
                page=paginated.page,
                page_size=paginated.page_size,
                total_pages=paginated.total_pages,
            ),
        )
    return ApiResponse[PaginatedResult[NewsResponse]](
        success=True,
        data=PaginatedResult(items=[], total=0, page=page, page_size=50, total_pages=1),
    )


async def _symbol_match_meta(session: AsyncSession | None, symbol: str, matched: list[str]) -> SymbolMatchMeta | None:
    """Meta for /news/symbol responses: which tag values matched and the
    persisted mappings behind them. Best-effort — meta is omitted on any
    failure (mapping table missing, pre-0059 DB, …)."""
    if session is None or not matched:
        return None
    try:
        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        maps = await NewsTagSymbolMapper(session).explain_symbol(symbol)
        return SymbolMatchMeta(symbol=symbol, matched=matched, maps=maps)
    except Exception:  # noqa: BLE001 — transparency only, never break the read
        logger.debug("symbol match meta unavailable", exc_info=True)
        return None


@router.get("/symbol/{symbol}")
async def news_by_symbol(
    symbol: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
    service: NewsService = Depends(get_news_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PaginatedResult[NewsResponse]]:
    try:
        date_range = parse_news_date_range(from_, to)
    except ValueError as exc:
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=False,
            data=None,
            error={"message": str(exc)},
        )
    date_from, date_to = date_range if date_range else (None, None)
    result = await service.get_by_symbol(symbol, page, page_size, date_from=date_from, date_to=date_to)
    if result.success and result.value:
        paginated = result.value
        matched = sorted({s for item in paginated.items for s in (item.symbols or [])})
        meta = await _symbol_match_meta(session, symbol, matched)
        return ApiResponse[PaginatedResult[NewsResponse]](
            success=True,
            data=PaginatedResult(
                items=[_item_to_response(item) for item in paginated.items],
                total=paginated.total,
                page=paginated.page,
                page_size=paginated.page_size,
                total_pages=paginated.total_pages,
            ),
            message=None if meta is None else meta.model_dump_json(),
        )
    return ApiResponse[PaginatedResult[NewsResponse]](
        success=True,
        data=PaginatedResult(items=[], total=0, page=page, page_size=50, total_pages=1),
    )


@router.get("/category/{category}")
async def news_by_category(
    category: str,
    page: int = Query(1, ge=1),
    from_: str | None = Query(None, alias="from", description="ISO-8601 date or datetime (UTC)"),
    to: str | None = Query(None, alias="to", description="ISO-8601 date or datetime (UTC); a bare date includes the whole day"),
    service: NewsService = Depends(get_news_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[NewsResponse]]:
    if category not in VALID_CATEGORIES:
        return ApiResponse[list[NewsResponse]](
            success=False,
            data=None,
            error={"message": f"Invalid category '{category}'. Valid: {', '.join(sorted(VALID_CATEGORIES))}"},
        )
    try:
        date_range = parse_news_date_range(from_, to)
    except ValueError as exc:
        return ApiResponse[list[NewsResponse]](
            success=False,
            data=None,
            error={"message": str(exc)},
        )
    date_from, date_to = date_range if date_range else (None, None)
    canonical = normalize_news_category(category)
    result = await service.list_all(page, 50, date_from=date_from, date_to=date_to)
    if result.success and result.value:
        paginated = result.value
        filtered = [i for i in paginated.items if (i.category if isinstance(i, NewsItem) else i.get("category", "")) == canonical]
        if filtered:
            return ApiResponse[list[NewsResponse]](
                success=True,
                data=[_item_to_response(item) for item in filtered],
            )
    if page > 1:
        return ApiResponse[list[NewsResponse]](
            success=True,
            data=[],
        )
    market_news = [n for n in await _get_market_news(session, 50) if n.category == canonical]
    if not market_news:
        market_news = [NewsResponse(
            id=f"category_{canonical}",
            title=f"آخرین اخبار {canonical}",
            summary=f"اخبار دسته {canonical}",
            source="سامانه",
            category=canonical,
            symbols=[],
            published_at="",
            sentiment="neutral",
            sentiment_score=0,
            created_at="",
        )]
    return ApiResponse[list[NewsResponse]](
        success=True,
        data=market_news,
    )


@router.get("/trending")
async def trending_news(
    limit: int = Query(10, ge=1, le=50),
    from_: str | None = Query(None, alias="from", description="ISO-8601 date or datetime (UTC)"),
    to: str | None = Query(None, alias="to", description="ISO-8601 date or datetime (UTC); a bare date includes the whole day"),
    service: NewsService = Depends(get_news_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[NewsResponse]]:
    try:
        date_range = parse_news_date_range(from_, to)
    except ValueError as exc:
        return ApiResponse[list[NewsResponse]](
            success=False,
            data=None,
            error={"message": str(exc)},
        )
    date_from, date_to = date_range if date_range else (None, None)
    result = await service.list_all(1, limit, date_from=date_from, date_to=date_to)
    if result.success and result.value:
        items = result.value.items
        if items:
            return ApiResponse[list[NewsResponse]](
                success=True,
                data=[_item_to_response(item) for item in items[:limit]],
            )
    # Fallback to market news from symbol snapshots
    market_news = await _get_market_news(session, limit)
    if market_news:
        return ApiResponse[list[NewsResponse]](success=True, data=market_news[:limit])
    # No trending data available — return empty list instead of placeholders
    logger.info("No trending news available from DB or market snapshots")
    return ApiResponse[list[NewsResponse]](success=True, data=[])


@router.post("/refresh")
async def refresh_news() -> ApiResponse[dict[str, Any]]:
    """Trigger background news ingestion from RSS feeds."""
    if _refresh_status["running"]:
        return ApiResponse[dict[str, Any]](
            success=True,
            data={"status": "already_running", "last_result": _refresh_status["last_result"]},
        )

    async def _run_refresh() -> None:
        _refresh_status["running"] = True
        try:
            from core.database import get_session
            from services.news_ingestion import NewsIngestionService

            # The request-scoped session is closed as soon as the response is
            # returned. The background job owns a fresh session instead of
            # retaining a dependency-managed session after request teardown.
            stats = None
            async for owned_session in get_session():
                service = NewsIngestionService(session=owned_session)
                stats = await service.ingest(
                    sources=None,
                    limit_per_source=30,
                    save=True,
                    verbose=False,
                    skip_sentiment=False,
                )
                break
            if stats is None:
                raise RuntimeError("Could not obtain a database session")
            _refresh_status["last_result"] = {
                "fetched": stats.get("fetched", 0),
                "saved": stats.get("saved", 0),
                "duplicates": stats.get("duplicates_removed", 0),
                "filtered": stats.get("filtered_out", 0),
            }
            _refresh_status["last_run"] = datetime.now(UTC).isoformat()
        except Exception as e:
            logger.exception("News refresh failed")
            _refresh_status["last_result"] = {"error": str(e)}
        finally:
            _refresh_status["running"] = False

    # Register with the API lifecycle manager when available so shutdown
    # cancels this task before the database is closed. Keep a small fallback
    # for direct/unit invocation outside the FastAPI app.
    try:
        from apps.api.app import _track_background_task

        _track_background_task(_run_refresh(), "news-manual-refresh")
    except Exception:
        asyncio.create_task(_run_refresh(), name="news-manual-refresh")
    return ApiResponse[dict[str, Any]](
        success=True,
        data={"status": "started", "last_result": _refresh_status["last_result"]},
    )


@router.get("/refresh/status")
async def refresh_status() -> ApiResponse[dict[str, Any]]:
    """Check background news refresh status."""
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "running": _refresh_status["running"],
            "last_run": _refresh_status["last_run"],
            "last_result": _refresh_status["last_result"],
        },
    )


@router.get("/sources/health")
async def news_sources_health(
    notify: bool = Query(False, description="Also fire the Telegram alert (cooldown-gated)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Freshness report for the news ingestion source registry.

    Reports stale sources (no successful fetch within
    ``NEWS_SOURCE_STALE_MINUTES``), never-fetched registrations, and
    sources writing news without a registry row. ``?notify=true`` also
    fires the Telegram alert (subject to its cooldown) — the scheduled
    path uses the job instead; the response adds ``alert_fired`` when the
    message actually went out.
    """
    from services.news_source_health import NewsSourceHealthService

    service = NewsSourceHealthService(session)
    if notify:
        # Cooldown-gated like the scheduled job; alert_fired tells the
        # caller whether a notification actually went out this request.
        report = await service.notify_if_degraded()
        if report is None:
            report = await service.health_report()
            report["alert_fired"] = False
        else:
            report["alert_fired"] = True
        return ApiResponse[dict[str, Any]](success=not report.get("error"), data=report)
    report = await service.health_report()
    return ApiResponse[dict[str, Any]](success=not report.get("error"), data=report)
