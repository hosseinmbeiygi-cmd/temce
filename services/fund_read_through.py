"""🏦 Fund Read-Through Service — هسته هماهنگ‌کننده (بخش ۴ معماری Enterprise).

الگوی «دیتابیس اول، سپس API» (Read-Through + Just-In-Time Ingestion):
  ۱. خواندن از جدول داخلی با بررسی Freshness TTL.
  ۲. Cache Miss / Stale → واکشی اتمیک از API تجاری از طریق Adapter.
  ۳. Upsert به دیتابیس و سپس تحویل به کاربر.
  ۴. Distributed Mutex (Redis SETNX با fallback به asyncio.Lock پروسه‌ای)
     برای مهار Thundering Herd — فقط یک درخواست به پرووایدر می‌رود.
  ۵. Stale-While-Revalidate برای Universe: پاسخ کهنه فوراً برمی‌گردد و
     به‌روزرسانی در پس‌زمینه انجام می‌شود.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from core.time import now_tehran, utc_now_naive
from services.fund_api_adapter import (
    FundApiAdapter,
)

logger = get_logger(__name__)

# ── Freshness TTL Policies (ثانیه) — قابل تنظیم با env ──────────────────────

TTL_MARKET_QUOTE = int(getattr(settings, "fund_ttl_market_quote", 45))       # ۳۰-۶۰ ثانیه در ساعات بازار
TTL_NAV_DAILY = 3600 * 4        # NAV روزانه؛ بعد از ۱۶:۰۰ هر روز به‌روزرسانی
TTL_PORTFOLIO_MONTHLY = 3600 * 24 * 30   # گزارش ماهانه کدال: ۳۰ روز
TTL_UNIVERSE = 3600 * 6         # کشف کل Universe: هر ۶ ساعت
TTL_LIVE_VALUATION = TTL_MARKET_QUOTE

# Mutex
MUTEX_TTL_SECONDS = 120
MUTEX_WAIT_SECONDS = 30


@dataclass
class StaleResult:
    """پاسخ حاوی فلگ تازگی برای UI (Live / Estimated / Stale)."""

    data: Any
    freshness: str = "live"        # live | estimated | stale
    fetched_from: str = "db"       # db | api | db+api
    age_seconds: float = 0.0


def _is_market_open() -> bool:
    """ساعات بازار تهران (۸:۴۵ تا ۱۲:۳۰) — ساده و بدون وابستگی خارجی."""
    import datetime as dt

    try:
        import pytz

        tehran = pytz.timezone("Asia/Tehran")
        now = datetime.now(tehran).time()
    except Exception:
        now = now_tehran().time()
    return dt.time(8, 45) <= now <= dt.time(12, 30)


# ── Distributed Mutex ────────────────────────────────────────────────────────


class DistributedMutex:
    """قفل توزیع‌شده Redis (SETNX + TTL) با fallback به asyncio.Lock.

    در استقرار تک‌پروسه‌ای همان asyncio.Lock کافی است؛ در چند-ورکر،
    Redis کلید ``fund:lock:<name>`` را قفل می‌کند تا فقط یک درخواست
    به API تجاری برود (مهار Thundering Herd).
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._redis: Any = None
        self._local = asyncio.Lock()
        self._token = uuid.uuid4().hex
        # جلوگیری از Hang: در نبود Redis، تلاش اتصال کش می‌شود (هر ۳۰s یک‌بار)
        self._redis_checked = False
        self._redis_retry_at = 0.0

    async def _get_redis(self) -> Any | None:
        if self._redis is not None:
            return self._redis
        now = time.time()
        if self._redis_checked and now < self._redis_retry_at:
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=1.0,
            )
            await self._redis.ping()
            self._redis_checked = False
            return self._redis
        except Exception:
            self._redis = None
            self._redis_checked = True
            self._redis_retry_at = now + 30.0
            return None

    async def acquire(self, name: str) -> bool:
        """Try-lock؛ True یعنی این caller برنده شد و باید منبع را بسازد."""
        redis = await self._get_redis()
        if redis is None:
            # Fallback پروسه‌ای: non-blocking
            return self._local.locked() is False and await self._local_acquire_fast()
        key = f"fund:lock:{name}"
        try:
            got = await redis.set(key, self._token, nx=True, ex=MUTEX_TTL_SECONDS)
            return bool(got)
        except Exception:
            logger.warning("DistributedMutex Redis failure — falling back to local lock")
            return self._local.locked() is False and await self._local_acquire_fast()

    async def _local_acquire_fast(self) -> bool:
        """Try-lock بدون انتظار روی asyncio.Lock (سازگار با Python 3.10+).

        بین ``locked()`` و ``acquire()`` هیچ await دیگری نیست؛ بنابراین این
        عملیات در حلقه رویداد اتمیک است.
        """
        if self._local.locked():
            return False
        await self._local.acquire()
        return True

    async def release(self, name: str) -> None:
        redis = await self._get_redis()
        if redis is None:
            if self._local.locked():
                with contextlib.suppress(RuntimeError):
                    self._local.release()
            return
        key = f"fund:lock:{name}"
        try:
            # آزادی امن: فقط اگر token مال ما باشد (اسکریپت Lua اتمیک)
            lua = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            await redis.eval(lua, 1, key, self._token)
        except Exception:
            logger.debug("Mutex release failed for %s", name)


# Singleton mutex برای همه سرویس‌ها
_shared_mutex = DistributedMutex()


class FundReadThroughService:
    """سرویس هماهنگ‌کننده صندوق‌ها — DB-first با JIT ingestion و Mutex."""

    def __init__(
        self,
        session: AsyncSession,
        adapter: FundApiAdapter | None = None,
    ) -> None:
        self.session = session
        # Session جاری به adapter تزریق می‌شود تا منابع DB-محور (مثل
        # کشف صندوق‌های TSE از snapshot ها) بدون session دوم کار کنند.
        self.adapter = adapter or FundApiAdapter(db_session=session)
        if self.adapter.db_session is None:
            self.adapter.db_session = session
        self._mutex = _shared_mutex
        from services.fund_circuit_breaker import get_fund_breaker

        self._breaker = get_fund_breaker()

    # ════════════════════════════════════════════════════════════════
    # ۱) Universe — کشف خودکار Zero-Config
    # ════════════════════════════════════════════════════════════════

    async def get_fund_universe(self) -> StaleResult:
        """کل صندوق‌های بازار؛ در صورت خالی بودن دیتابیس، Lazy Discovery.

        Stale-While-Revalidate: اگر داده کهنه است، همان کهنه برگردد و
        rebuild در پس‌زمینه با session مستقل انجام شود.
        """
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT meta_value, updated_at FROM fund_meta
                    WHERE meta_key = 'universe_snapshot'
                    """
                )
            )
        ).first()

        now = time.time()
        if row is not None:
            age = now - row[1].timestamp() if isinstance(row[1], datetime) else 1e18
            try:
                payload = json.loads(row[0] or "[]")
            except (TypeError, json.JSONDecodeError):
                payload = None
            if payload is not None:
                if age < TTL_UNIVERSE:
                    return StaleResult(payload, "live", "db", age)
                # Stale → بازگرداندن کهنه + Revalidate در پس‌زمینه
                asyncio.create_task(self._rebuild_universe_background())
                return StaleResult(payload, "stale", "db", age)

        # Cold start → با mutex بساز
        async with self._guarded("universe"):
            built = await self._build_and_store_universe()
        return StaleResult(built, "live", "db+api", 0.0)

    @contextlib.asynccontextmanager
    async def _guarded(self, name: str):
        """Context manager برای mutex — اگر قفل نگیرد، صبر کوتاه سپس ادامه.

        Async-context-manager واقعی؛ آزادسازی قفل حتی در صورت خطا تضمین می‌شود.
        """
        got = await self._mutex.acquire(name)
        if got:
            handle: Any = _MutexHandle(self._mutex, name)
        else:
            handle = _MutexHandle(self._mutex, name, owned=False)
            # منتظر می‌مانیم (تا MUTEX_WAIT) تا سازندهٔ برنده تمام کند؛ سپس از DB می‌خوانیم
            deadline = time.monotonic() + MUTEX_WAIT_SECONDS
            while time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                row = (
                    await self.session.execute(
                        text("SELECT meta_value FROM fund_meta WHERE meta_key = :k"),
                        {"k": name if name != "universe" else "universe_snapshot"},
                    )
                ).first()
                if row is not None:
                    handle = _NoopHandle()
                    break
        async with handle:
            yield

    async def _rebuild_universe_background(self) -> None:
        try:
            from core.database import async_session_factory

            if async_session_factory is None:
                return
            async with async_session_factory() as session:
                svc = FundReadThroughService(session, self.adapter)
                async with svc._guarded("universe"):
                    await svc._build_and_store_universe()
        except Exception:
            logger.exception("Background universe rebuild failed")

    async def _build_and_store_universe(self) -> list[dict[str, Any]]:
        """Delegate به موتور Discovery (هویت کانونی + Alias + Capability + ممیزی)."""
        from services.fund_discovery import FundDiscoveryService

        svc = FundDiscoveryService(self.session, self.adapter)
        return await svc.discover(store_snapshot=True)

    # ════════════════════════════════════════════════════════════════
    # ۲) NAV History — پر کردن تاریخچه غایب از API
    # ════════════════════════════════════════════════════════════════

    async def get_fund_nav_history(
        self,
        fund_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> StaleResult:
        start_date = start_date or (date.today() - timedelta(days=365))
        end_date = end_date or date.today()

        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT nav_date, nav_issue, nav_redemption, nav_statistical,
                           total_asset_value, units_outstanding, data_source
                    FROM fund_nav_history
                    WHERE fund_id = :fid AND nav_date BETWEEN :d1 AND :d2
                    ORDER BY nav_date ASC
                    """
                ),
                {"fid": fund_id, "d1": start_date, "d2": end_date},
            )
        ).fetchall()

        points = [
            {
                "date": str(r[0]),
                "nav_issue": r[1],
                "nav_redemption": r[2],
                "nav_statistical": r[3],
                "total_asset_value": r[4],
                "units_outstanding": r[5],
            }
            for r in rows
        ]

        # امروز در DB هست؟ (NAV بعد از ۱۶:۰۰ منتشر می‌شود)
        has_today = any(p["date"] == str(date.today()) for p in points)
        fresh_enough = has_today or (_hours_since_last(points) < (TTL_NAV_DAILY / 3600.0))

        if points and fresh_enough:
            return StaleResult(points, "live", "db", 0.0)

        # Gap filling از API (یک call برای آخرین NAV)
        symbol = fund_id.split(":", 1)[-1]
        if not await self._breaker.allow(fund_id):
            logger.info("Fund circuit open — NAV gap-fill skipped for %s", fund_id)
            return StaleResult(points, "stale", "db", 0.0)
        async with self._guarded(f"nav:{fund_id}"):
            try:
                nav = await self.adapter.fetch_nav(symbol)
            except Exception:
                await self._breaker.record_failure(fund_id, "nav fetch exception")
                raise
            if nav is not None and nav.get("nav_date") is not None:
                await self._upsert_nav(fund_id, nav)
                await self._breaker.record_success(fund_id)
                point = {
                    "date": str(nav["nav_date"]),
                    "nav_issue": nav.get("nav_issue"),
                    "nav_redemption": nav.get("nav_redemption"),
                    "nav_statistical": None,
                    "total_asset_value": None,
                    "units_outstanding": None,
                }
                if point["date"] not in {p["date"] for p in points}:
                    points.append(point)
                    points.sort(key=lambda p: p["date"])
            else:
                await self._breaker.record_failure(fund_id, "nav fetch empty")
        freshness = "live" if has_today else ("estimated" if points else "stale")
        return StaleResult(points, freshness, "db+api" if points else "db", 0.0)

    async def _upsert_nav(self, fund_id: str, nav: dict[str, Any]) -> None:
        nav_date = nav.get("nav_date")
        if isinstance(nav_date, datetime):
            nav_date = nav_date.date()
        if not isinstance(nav_date, date):
            return
        await self.session.execute(
            text(
                """
                INSERT INTO fund_nav_history
                    (fund_id, isin, nav_date, nav_date_greg, nav_issue,
                     nav_redemption, data_source, updated_at)
                VALUES (:fid, :isin, :nd, :nd, :ni, :nr, 'brsapi_nav', now())
                ON CONFLICT (fund_id, nav_date) DO UPDATE SET
                    nav_issue = EXCLUDED.nav_issue,
                    nav_redemption = EXCLUDED.nav_redemption,
                    updated_at = now()
                WHERE fund_nav_history.nav_issue IS DISTINCT FROM EXCLUDED.nav_issue
                   OR fund_nav_history.nav_redemption IS DISTINCT FROM EXCLUDED.nav_redemption
                """
            ),
            {
                "fid": fund_id,
                "isin": None,
                "nd": nav_date,
                "ni": nav.get("nav_issue"),
                "nr": nav.get("nav_redemption"),
            },
        )
        await self.session.commit()

    # ════════════════════════════════════════════════════════════════
    # ۳) Holdings — ریز دارایی با دریافت خودکار
    # ════════════════════════════════════════════════════════════════

    async def get_fund_holdings(self, fund_id: str, period_date: date | None = None) -> StaleResult:
        period_date = period_date or await self._latest_period(fund_id)
        if period_date is None:
            return StaleResult([], "stale", "db", 0.0)

        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT holding_type, instrument_symbol, instrument_name,
                           instrument_isin, quantity, book_value, market_value, weight_pct
                    FROM fund_holdings
                    WHERE fund_id = :fid AND period_end_date = :pd
                    ORDER BY weight_pct DESC NULLS LAST
                    """
                ),
                {"fid": fund_id, "pd": period_date},
            )
        ).fetchall()

        holdings = [
            {
                "holding_type": r[0],
                "instrument_symbol": r[1],
                "instrument_name": r[2],
                "instrument_isin": r[3],
                "quantity": r[4],
                "book_value": r[5],
                "market_value": r[6],
                "weight_pct": r[7],
            }
            for r in rows
        ]
        if holdings:
            return StaleResult(holdings, "live", "db", 0.0)

        # JIT: از کدال بیاور
        symbol = fund_id.split(":", 1)[-1]
        isin = await self._fund_isin(fund_id)
        if not await self._breaker.allow(fund_id):
            logger.info("Fund circuit open — holdings JIT skipped for %s", fund_id)
            return StaleResult([], "stale", "db", 0.0)
        async with self._guarded(f"holdings:{fund_id}:{period_date}"):
            try:
                fetched = await self.adapter.fetch_portfolio_report(isin or symbol, period_date)
            except Exception:
                await self._breaker.record_failure(fund_id, "holdings fetch exception")
                raise
            if fetched:
                await self._upsert_holdings(fund_id, period_date, fetched)
                await self._breaker.record_success(fund_id)
            else:
                await self._breaker.record_failure(fund_id, "holdings fetch empty")
        return StaleResult(fetched or [], "live" if fetched else "stale", "db+api" if fetched else "api", 0.0)

    async def _latest_period(self, fund_id: str) -> date | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT MAX(period_end_date) FROM fund_portfolio_reports
                    WHERE fund_id = :fid
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        return row[0] if row and row[0] else None

    async def _fund_isin(self, fund_id: str) -> str | None:
        row = (
            await self.session.execute(
                text("SELECT isin FROM funds WHERE id = :fid"), {"fid": fund_id}
            )
        ).first()
        return (row[0] or None) if row else None

    async def _upsert_holdings(self, fund_id: str, period: date, holdings: list[dict[str, Any]]) -> None:
        for h in holdings:
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_holdings
                        (fund_id, period_end_date, holding_type, instrument_symbol,
                         instrument_name, instrument_isin, quantity, book_value,
                         market_value, weight_pct, data_source, updated_at)
                    VALUES (:fid, :pd, :ht, :sym, :nm, :isin, :q, :bv, :mv, :w,
                            'brsapi_codal', now())
                    ON CONFLICT (fund_id, period_end_date, holding_type, instrument_symbol)
                    DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        book_value = EXCLUDED.book_value,
                        market_value = EXCLUDED.market_value,
                        weight_pct = EXCLUDED.weight_pct,
                        updated_at = now()
                    WHERE fund_holdings.quantity IS DISTINCT FROM EXCLUDED.quantity
                       OR fund_holdings.market_value IS DISTINCT FROM EXCLUDED.market_value
                       OR fund_holdings.weight_pct IS DISTINCT FROM EXCLUDED.weight_pct
                    """
                ),
                {
                    "fid": fund_id,
                    "pd": period,
                    "ht": h.get("holding_type") or "other",
                    "sym": h.get("instrument_symbol") or "",
                    "nm": h.get("instrument_name"),
                    "isin": h.get("instrument_isin"),
                    "q": h.get("quantity"),
                    "bv": h.get("book_value"),
                    "mv": h.get("market_value"),
                    "w": h.get("weight_pct"),
                },
            )
        # سربرگ گزارش
        await self.session.execute(
            text(
                """
                INSERT INTO fund_portfolio_reports
                    (fund_id, period_end_date, data_source, updated_at)
                VALUES (:fid, :pd, 'brsapi_codal', now())
                ON CONFLICT (fund_id, period_end_date) DO NOTHING
                """
            ),
            {"fid": fund_id, "pd": period},
        )
        await self.session.commit()

    # ════════════════════════════════════════════════════════════════
    # ۴) Live Valuation — NAV تخمینی با ترکیب ماه قبل × قیمت لایو
    # ════════════════════════════════════════════════════════════════

    async def get_live_valuation(self, fund_id: str) -> StaleResult:
        """Estimated NAV = Σ(تعداد سهام × قیمت لایو) + نقد + درآمد ثابت − بدهی / کل واحد.

        Coverage Ratio: اگر قیمت روز برای بخشی از سهام در دسترس نباشد،
        درصد پوشش محاسبه و به UI برمی‌گردد («NAV تخمینی با پوشش X٪»).
        """
        symbol = fund_id.split(":", 1)[-1]

        # ۱) قیمت لایو صندوق (کش TTL دار)
        quote = await self._cached_quote(fund_id, symbol)

        # ۲) آخرین holdings موجود
        holdings_res = await self.get_fund_holdings(fund_id)
        holdings = holdings_res.data if isinstance(holdings_res.data, list) else []

        # ۳) قیمت‌های لایو سهامِ داخل پرتفوی (batch از snapshots — بدون API اضافه)
        live_prices = await self._live_prices_for_symbols(
            [h.get("instrument_symbol") for h in holdings if h.get("instrument_symbol")]
        )

        total_value = 0.0
        covered_value = 0.0
        equity_value = 0.0
        cash_like = 0.0
        for h in holdings:
            mv = float(h.get("market_value") or 0)
            htype = h.get("holding_type") or "other"
            if htype == "equity":
                sym = h.get("instrument_symbol")
                qty = float(h.get("quantity") or 0)
                price = live_prices.get(sym or "")
                if price and qty:
                    v = qty * price
                    equity_value += v
                    covered_value += v
                else:
                    # توقف نماد / نبود قیمت → ارزش گزارش‌شده ماه قبل
                    equity_value += mv
                    total_value += mv
                    continue
                total_value += v
            else:
                cash_like += mv
                total_value += mv

        equity_reported = sum(
            float(h.get("market_value") or 0)
            for h in holdings
            if (h.get("holding_type") or "") == "equity"
        )
        coverage = (covered_value / equity_reported * 100.0) if equity_reported > 0 else 100.0

        units = await self._units_outstanding(fund_id)
        nav_estimated = (total_value / units) if units and units > 0 else None

        freshness = "live" if coverage >= 99.0 else ("estimated" if coverage >= 50 else "stale")
        return StaleResult(
            {
                "fund_id": fund_id,
                "nav_estimated": nav_estimated,
                "nav_official": quote.get("nav_official") if quote else None,
                "coverage_pct": round(coverage, 1),
                "equity_value": equity_value,
                "cash_and_fixed_income": cash_like,
                "total_value": total_value,
                "units_outstanding": units,
                "quote": quote,
                "holdings_age": holdings_res.freshness,
            },
            freshness,
            "db+api",
            0.0,
        )

    async def _cached_quote(self, fund_id: str, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT last_price, close_price, yesterday_price, bid_price, ask_price,
                           trade_volume, trade_value, market_value, price_change_pct,
                           quoted_at, fetched_at
                    FROM fund_market_quotes_cache WHERE fund_id = :fid
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        now = utc_now_naive()
        if row is not None and row[9] is not None:
            age = (now - row[9]).total_seconds() if isinstance(row[9], datetime) else 1e18
            ttl = TTL_MARKET_QUOTE if _is_market_open() else 3600
            if age < ttl:
                return self._quote_dict(row)
        # Stale/Miss → JIT fetch (فقط در ساعات بازار یا اگر کش خالی)
        if not await self._breaker.allow(fund_id):
            logger.info("Fund circuit open — quote JIT skipped for %s", fund_id)
            return self._quote_dict(row) if row is not None else None
        async with self._guarded(f"quote:{fund_id}"):
            try:
                fetched = await self.adapter.fetch_market_quote(symbol)
            except Exception:
                await self._breaker.record_failure(fund_id, "quote fetch exception")
                raise
            if fetched:
                await self._breaker.record_success(fund_id)
                await self.session.execute(
                    text(
                        """
                        INSERT INTO fund_market_quotes_cache
                            (fund_id, symbol, last_price, close_price, yesterday_price,
                             bid_price, ask_price, trade_volume, trade_value,
                             market_value, price_change_pct, quoted_at, fetched_at)
                        VALUES (:fid, :sym, :lp, :cp, :yp, :bp, :ap, :tv, :tval, :mv,
                                :pcp, :qa, now())
                        ON CONFLICT (fund_id) DO UPDATE SET
                            last_price = EXCLUDED.last_price,
                            close_price = EXCLUDED.close_price,
                            yesterday_price = EXCLUDED.yesterday_price,
                            bid_price = EXCLUDED.bid_price,
                            ask_price = EXCLUDED.ask_price,
                            trade_volume = EXCLUDED.trade_volume,
                            trade_value = EXCLUDED.trade_value,
                            market_value = EXCLUDED.market_value,
                            price_change_pct = EXCLUDED.price_change_pct,
                            quoted_at = EXCLUDED.quoted_at,
                            fetched_at = now()
                        WHERE fund_market_quotes_cache.quoted_at IS DISTINCT FROM EXCLUDED.quoted_at
                           OR fund_market_quotes_cache.last_price IS DISTINCT FROM EXCLUDED.last_price
                        """
                    ),
                    {
                        "fid": fund_id,
                        "sym": symbol,
                        "lp": fetched.get("last_price"),
                        "cp": fetched.get("close_price"),
                        "yp": fetched.get("yesterday_price"),
                        "bp": fetched.get("bid_price"),
                        "ap": fetched.get("ask_price"),
                        "tv": fetched.get("trade_volume"),
                        "tval": fetched.get("trade_value"),
                        "mv": fetched.get("market_value"),
                        "pcp": fetched.get("price_change_pct"),
                        "qa": fetched.get("quoted_at") or now,
                    },
                )
                await self.session.commit()
                return fetched
            await self._breaker.record_failure(fund_id, "quote fetch empty")
        return self._quote_dict(row) if row is not None else None

    @staticmethod
    def _quote_dict(row: Any) -> dict[str, Any]:
        return {
            "last_price": row[0],
            "close_price": row[1],
            "yesterday_price": row[2],
            "bid_price": row[3],
            "ask_price": row[4],
            "trade_volume": row[5],
            "trade_value": row[6],
            "market_value": row[7],
            "price_change_pct": row[8],
            "quoted_at": str(row[9]) if row[9] else None,
        }

    async def _live_prices_for_symbols(self, symbols: list[str]) -> dict[str, float]:
        """آخرین قیمت هر نماد از snapshots داخلی — بدون call اضافه به API."""
        if not symbols:
            return {}
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT DISTINCT ON (symbol) symbol, price_last
                    FROM brsapi_symbol_snapshots
                    WHERE symbol = ANY(:syms) AND price_last > 0
                    ORDER BY symbol, id DESC
                    """
                ),
                {"syms": symbols},
            )
        ).fetchall()
        return {r[0]: float(r[1]) for r in rows if r[1]}

    async def _units_outstanding(self, fund_id: str) -> int | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT units_outstanding FROM fund_nav_history
                    WHERE fund_id = :fid AND units_outstanding IS NOT NULL
                    ORDER BY nav_date DESC LIMIT 1
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        if row and row[0]:
            return int(row[0])
        # fallback: funds.shares_count
        row2 = (
            await self.session.execute(
                text("SELECT shares_count FROM funds WHERE id = :fid"), {"fid": fund_id}
            )
        ).first()
        return int(row2[0]) if row2 and row2[0] else None


# ── Mutex handle helpers ─────────────────────────────────────────────────────


class _MutexHandle:
    def __init__(self, mutex: DistributedMutex, name: str, owned: bool = True) -> None:
        self._mutex = mutex
        self._name = name
        self._owned = owned

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> None:
        if self._owned:
            await self._mutex.release(self._name)


class _NoopHandle:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _hours_since_last(points: list[dict[str, Any]]) -> float:
    if not points:
        return 1e18
    last = points[-1].get("date")
    try:
        d = datetime.strptime(str(last), "%Y-%m-%d")
        return (utc_now_naive() - d).total_seconds() / 3600.0
    except ValueError:
        return 1e18
