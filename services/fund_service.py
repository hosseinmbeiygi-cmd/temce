"""🏦 Fund Service — سرویس مدیریت صندوق‌های سرمایه‌گذاری

Supports two modes:
  - InMemory (default) — for dev/test
  - PostgreSQL via AsyncSession — for production with real data persistence

Responsibilities:
  - CRUD operations for funds
  - Search / filter by symbol, ISIN, type
  - NAV history tracking (FundNAV repository)
  - Holding tracking (FundHolding repository)
  - Seed sample data on empty DB
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.funds.entities import Fund, FundHolding
from domain.funds.nav import FundNAV
from repositories.base_repository import InMemoryRepository
from repositories.fund_repository import FundRepository, new_fund_id

logger = get_logger(__name__)


class FundNavRepository(InMemoryRepository[FundNAV]):
    """NAV history repository — always in-memory for now.
    TODO: Add Db-backed NAV repository when needed.
    """

    async def get_by_fund(self, fund_id: str, start_date: str = "", end_date: str = "") -> Result[list[FundNAV]]:
        navs = [n for n in self._store.values() if n.fund_id == fund_id]
        if start_date:
            navs = [n for n in navs if n.nav_date and str(n.nav_date) >= start_date]
        if end_date:
            navs = [n for n in navs if n.nav_date and str(n.nav_date) <= end_date]
        navs.sort(key=lambda n: n.nav_date or date.min)
        return Result.ok(navs)


class FundHoldingRepository(InMemoryRepository[FundHolding]):
    """Holding repository — always in-memory for now.
    TODO: Add Db-backed holding repository when needed.
    """

    async def get_by_fund(self, fund_id: str) -> Result[list[FundHolding]]:
        holdings = [h for h in self._store.values() if h.fund_id == fund_id]
        return Result.ok(holdings)


class FundService:
    """🏦 سرویس صندوق‌ها — مدیریت، جستجو و تحلیل صندوق‌های سرمایه‌گذاری

    Args:
        session: AsyncSession (optional) — PostgreSQL connection for persistence
        fund_repo: FundRepository (optional) — custom repository
        nav_repo: FundNavRepository (optional) — NAV history repository
        holding_repo: FundHoldingRepository (optional) — holdings repository
    """

    def __init__(
        self,
        session: Any | None = None,
        fund_repo: FundRepository | None = None,
        nav_repo: FundNavRepository | None = None,
        holding_repo: FundHoldingRepository | None = None,
    ) -> None:
        self._session = session
        self.fund_repo = fund_repo or FundRepository(session=session)
        self.nav_repo = nav_repo or FundNavRepository()
        self.holding_repo = holding_repo or FundHoldingRepository()
        self._seed_done = False

    # ── CRUD ──────────────────────────────────────────────────────

    async def list_all(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        """List all funds with pagination."""
        return await self.fund_repo.list(page, page_size)

    async def get_by_id(self, fund_id: str) -> Result[Fund]:
        """Get a single fund by ID."""
        return await self.fund_repo.get(fund_id)

    async def get_by_symbol(self, symbol: str) -> Result[Fund]:
        """Get a fund by its trading symbol."""
        return await self.fund_repo.get_by_symbol(symbol)

    async def search(self, query: str, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Fund]]:
        """Search funds by name, symbol, or ISIN."""
        return await self.fund_repo.search(query, page, page_size)

    async def get_by_fund_type(self, fund_type: str, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Fund]]:
        """List funds filtered by type."""
        return await self.fund_repo.get_by_fund_type(fund_type, page, page_size)

    async def count_by_type(self) -> dict[str, int]:
        """Count funds grouped by type."""
        return await self.fund_repo.count_by_type()

    async def count(self) -> int:
        """Total number of funds."""
        return await self.fund_repo.count()

    # ── Create / Update ───────────────────────────────────────────

    async def create(self, name: str, symbol: str = "", **kwargs: Any) -> Result[Fund]:
        """Create a new fund and persist it."""
        fund = Fund(
            id=new_fund_id(),
            name=name,
            symbol=symbol,
            **kwargs,
        )
        result = await self.fund_repo.save(fund)
        if result.success:
            logger.info("Created fund %s (%s)", name, fund.id)
        return result

    async def update(self, fund_id: str, **kwargs: Any) -> Result[Fund]:
        """Update an existing fund's fields."""
        existing = await self.fund_repo.get(fund_id)
        if not existing.success:
            return Result.fail(existing.error or f"Fund {fund_id} not found")
        fund = existing.value
        for key, value in kwargs.items():
            if hasattr(fund, key):
                setattr(fund, key, value)
        fund.mark_updated()
        result = await self.fund_repo.save(fund)
        if result.success:
            logger.info("Updated fund %s (%s)", fund.name, fund_id)
        return result

    async def save_fund(self, fund: Fund) -> Result[Fund]:
        """Save an existing fund entity (upsert semantics)."""
        return await self.fund_repo.save(fund)

    # ── NAV ───────────────────────────────────────────────────────

    async def get_nav_history(
        self,
        fund_id: str,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
    ) -> Result[list[FundNAV]]:
        """Get NAV history for a fund."""
        sd = str(start_date) if start_date else ""
        ed = str(end_date) if end_date else ""
        return await self.nav_repo.get_by_fund(fund_id, sd, ed)

    async def save_nav(self, nav: FundNAV) -> Result[FundNAV]:
        """Save a NAV record."""
        return await self.nav_repo.save(nav)

    # ── Holdings ──────────────────────────────────────────────────

    async def get_holdings(self, fund_id: str) -> Result[list[FundHolding]]:
        """Get holdings for a fund."""
        return await self.holding_repo.get_by_fund(fund_id)

    async def save_holding(self, holding: FundHolding) -> Result[FundHolding]:
        """Save a holding record."""
        return await self.holding_repo.save(holding)

    # ── Update from BrsApi ────────────────────────────────────────

    async def update_from_brsapi(
        self,
        symbol: str,
        brsapi: Any,
    ) -> dict[str, Any]:
        """
        دریافت داده‌های لحظه‌ای یک صندوق از BrsApi و ذخیره در دیتابیس.

        Args:
            symbol: نماد صندوق (مثلاً "آگاس")
            brsapi: BrsApiQueryService instance

        Returns:
            dict با داده‌های به‌روزرسانی‌شده
        """
        enriched = await brsapi.get_enriched_symbol_detail(symbol)
        if not enriched:
            return {"symbol": symbol, "error": f"نماد {symbol} در BrsApi یافت نشد"}

        # ── Extract fields from enriched data ──
        price_last = float(enriched.get("price_last") or 0)
        price_yesterday = float(enriched.get("price_yesterday") or 0)
        price_close = float(enriched.get("price_close") or 0)
        price_max = float(enriched.get("price_max") or 0)
        price_min = float(enriched.get("price_min") or 0)
        trade_volume = int(enriched.get("trade_volume") or 0)
        trade_value = float(enriched.get("trade_value") or 0)
        trade_count = int(enriched.get("trade_count") or 0)
        buy_real = int(enriched.get("buy_real_volume") or 0)
        buy_legal = int(enriched.get("buy_legal_volume") or 0)
        sell_real = int(enriched.get("sell_real_volume") or 0)
        sell_legal = int(enriched.get("sell_legal_volume") or 0)
        shares_count = int(enriched.get("shares_count") or 0)
        market_value = float(enriched.get("market_value") or 0)
        isin = str(enriched.get("isin") or "")
        name = str(enriched.get("name") or symbol)

        # Compute NAV-related fields if possible
        nav = price_last if price_last > 0 else float(enriched.get("nav") or 0)
        nav_change = nav - price_yesterday if price_yesterday > 0 else 0
        nav_change_pct = round((nav_change / price_yesterday) * 100, 2) if price_yesterday > 0 else 0.0

        fund_type = self._infer_fund_type(enriched)

        # ── Try to find existing fund ──
        existing = await self.get_by_symbol(symbol)

        if existing.success:
            fund = existing.value
            # Update fields
            fund.nav = nav
            fund.total_units = shares_count
            extra = fund.extra or {}
            extra.update({
                "nav_change": nav_change,
                "nav_change_pct": nav_change_pct,
                "price_last": price_last,
                "price_close": price_close,
                "price_yesterday": price_yesterday,
                "price_max": price_max,
                "price_min": price_min,
                "trade_volume": trade_volume,
                "trade_value": trade_value,
                "trade_count": trade_count,
                "base_volume": int(shares_count * 0.01),
                "market_value": market_value,
                "buy_real_volume": buy_real,
                "buy_legal_volume": buy_legal,
                "sell_real_volume": sell_real,
                "sell_legal_volume": sell_legal,
                "time": datetime.now().strftime("%H:%M:%S"),
                "data_source": "brsapi",
                "snapshot_date": datetime.now().strftime("%Y-%m-%d"),
            })
            fund.extra = extra
            fund.mark_updated()
            result = await self.fund_repo.save(fund)
            if not result.success:
                return {"symbol": symbol, "error": result.error}
            logger.info("Updated fund %s from BrsApi", symbol)
        else:
            # Create new fund
            fund = Fund(
                id=new_fund_id(),
                name=name,
                symbol=symbol,
                isin=isin,
                fund_type=fund_type,
                nav=nav,
                total_units=shares_count,
                status="active",
                extra={
                    "nav_change": nav_change,
                    "nav_change_pct": nav_change_pct,
                    "price_last": price_last,
                    "price_close": price_close,
                    "price_yesterday": price_yesterday,
                    "price_max": price_max,
                    "price_min": price_min,
                    "trade_volume": trade_volume,
                    "trade_value": trade_value,
                    "trade_count": trade_count,
                    "base_volume": int(shares_count * 0.01),
                    "market_value": market_value,
                    "buy_real_volume": buy_real,
                    "buy_legal_volume": buy_legal,
                    "sell_real_volume": sell_real,
                    "sell_legal_volume": sell_legal,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "data_source": "brsapi",
                    "snapshot_date": datetime.now().strftime("%Y-%m-%d"),
                },
            )
            result = await self.fund_repo.save(fund)
            if not result.success:
                return {"symbol": symbol, "error": result.error}
            logger.info("Created fund %s from BrsApi", symbol)

        # Commit if we have a session
        if self._session:
            try:
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                logger.exception("Failed to commit fund update for %s", symbol)
                return {"symbol": symbol, "error": "خطا در ذخیره‌سازی"}

        return self._fund_to_dict(fund)

    def _infer_fund_type(self, enriched: dict[str, Any]) -> str:
        """Try to infer fund type from available data."""
        isin = (enriched.get("isin") or "").upper()
        name = (enriched.get("name") or "").lower()

        if "طلا" in name or "gold" in isin:
            return "بخشی"
        if "درآمد" in name or "ثابت" in name:
            return "درآمد ثابت"
        if "اهرمی" in name or "اهرم" in name:
            return "اهرمی"
        if "اختصاصی" in name:
            return "اختصاصی"
        if "سهام" in name or "شاخص" in name:
            return "سهامی"
        if "مختلط" in name:
            return "مختلط"
        return "سهامی"  # default

    @staticmethod
    def _fund_to_dict(fund: Fund) -> dict[str, Any]:
        """Convert a Fund entity to a plain dict for API responses."""
        extra = fund.extra or {}
        return {
            "symbol": fund.symbol,
            "name": fund.name,
            "isin": fund.isin or "",
            "fund_type": fund.fund_type or "",
            "nav": fund.nav,
            "nav_change": extra.get("nav_change", 0),
            "nav_change_pct": extra.get("nav_change_pct", 0),
            "price_last": extra.get("price_last", 0),
            "price_close": extra.get("price_close", 0),
            "price_yesterday": extra.get("price_yesterday", 0),
            "price_max": extra.get("price_max", 0),
            "price_min": extra.get("price_min", 0),
            "trade_volume": extra.get("trade_volume", 0),
            "trade_value": extra.get("trade_value", 0),
            "trade_count": extra.get("trade_count", 0),
            "shares_count": fund.total_units,
            "base_volume": extra.get("base_volume", 0),
            "market_value": extra.get("market_value", 0),
            "buy_real_volume": extra.get("buy_real_volume", 0),
            "buy_legal_volume": extra.get("buy_legal_volume", 0),
            "sell_real_volume": extra.get("sell_real_volume", 0),
            "sell_legal_volume": extra.get("sell_legal_volume", 0),
            "time": extra.get("time", ""),
            "data_source": extra.get("data_source", ""),
        }

    # ── Auto-seed ─────────────────────────────────────────────────

    async def ensure_seeded(self) -> int:
        """Seed sample funds if the database is empty.

        Call this during startup (lifespan) to ensure there's always
        data available for the frontend.

        Returns:
            Number of funds seeded, or 0 if already populated.
        """
        if self._seed_done:
            return 0

        count_result = await self.count()
        if count_result > 0:
            self._seed_done = True
            logger.info("Fund DB already populated (%d funds), skipping seed", count_result)
            return 0

        logger.info("Fund DB is empty — seeding %d sample funds...", len(_SAMPLE_FUNDS))

        seeded = 0
        for sym, name, ftype in _SAMPLE_FUNDS:
            fund = Fund(
                id=new_fund_id(),
                name=name,
                symbol=sym,
                isin=f"IR{sym}{seeded:04d}",
                fund_type=ftype,
                nav=float(seeded * 1000 + 500),
                total_units=seeded * 1_000_000 + 1_000_000,
                status="active",
            )
            result = await self.fund_repo.save(fund)
            if result.success:
                seeded += 1

        if self._session:
            try:
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                logger.exception("Failed to commit fund seed")

        logger.info("Seeded %d sample funds", seeded)
        self._seed_done = True
        return seeded


# ── Sample data (matching the endpoint's list) ──

_SAMPLE_FUNDS: list[tuple[str, str, str]] = [
    ("آگاس", "آتیه‌اندیشان اقتصاد پایدار", "اختصاصی"),
    ("آسامید", "آسمان توسعه ایرانیان", "اختصاصی"),
    ("آکاریز", "آگاه سرمایه ریز", "اهرمی"),
    ("آکشاورز", "آگاه کشاورز", "بخشی"),
    ("اسپید", "اسپیدار پارت", "اهرمی"),
    ("اشتیاق", "اشتیاق صبا", "درآمد ثابت"),
    ("اطلس", "اطلس سرمایه کیان", "اهرمی"),
    ("افتم", "افتخار همیشه سهام ایرانیان", "اهرمی"),
    ("اقبال", "اقبال یکم", "درآمد ثابت"),
    ("الماس", "الماس سرمد", "اختصاصی"),
    ("امید", "امید ایرانیان", "سهامی"),
    ("امین", "امین سرمایه پارس", "درآمد ثابت"),
    ("انرژی", "انرژی امید", "اختصاصی"),
    ("ایثار", "ایثار کارکنان بانک ملت", "اختصاصی"),
    ("ایرانیان", "صندوق سرمایه‌گذاری ایرانیان", "سهامی"),
    ("باپویا", "بانک پویا", "درآمد ثابت"),
    ("بدرخش", "بانک درخشش فردا", "اختصاصی"),
    ("باهنر", "بهمن اهتمام نوین رادین", "اختصاصی"),
    ("باور", "باور سرمایه", "اهرمی"),
    ("برکت", "برکت سهام", "سهامی"),
    ("بسامان", "بانک سامان", "درآمد ثابت"),
    ("بهینه", "بهینه پرداز", "اختصاصی"),
    ("پارسیان", "پارسیان سهام", "سهامی"),
    ("پدیده", "پدیده شفاف", "اهرمی"),
    ("پیشگامان", "پیشگامان سهام", "سهامی"),
    ("پویا", "پویا سرمایه", "اهرمی"),
    ("تابان", "تابان سهام", "بخشی"),
    ("تاپ", "تاپ سهام", "سهامی"),
    ("تدبیر", "تدبیرگران فردا", "اهرمی"),
    ("توسعه", "توسعه سهام", "سهامی"),
    ("ثابت", "ثابت سرمایه", "درآمد ثابت"),
    ("جامان", "جامان سهام", "سهامی"),
    ("جاوید", "جاوید سهم", "سهامی"),
    ("حافظ", "حافظ سهام", "سهامی"),
    ("خبرگان", "خبرگان سهام", "سهامی"),
    ("خرد", "خرد سهام", "سهامی"),
    ("دانش", "دانش بنیان", "اختصاصی"),
    ("دلیران", "دلیران سهام", "سهامی"),
    ("رادین", "رادین سهام", "سهامی"),
    ("رازی", "رازی سهام", "سهامی"),
    ("رفاه", "رفاه سهام", "اختصاصی"),
    ("سپهر", "سپهر سرمایه", "اهرمی"),
    ("ستاره", "ستاره سهام", "سهامی"),
    ("سدید", "سدید سهام", "سهامی"),
    ("سرآمد", "سرآمد سرمایه", "اهرمی"),
    ("سرمد", "سرمد سهام", "سهامی"),
    ("شفا", "شفا سهام", "بخشی"),
    ("صبا", "صبا سهام", "سهامی"),
    ("صنعت", "صنعت و معدن", "اختصاصی"),
    ("طلوع", "طلوع سهام", "سهامی"),
    ("عقیق", "عقیق سرمایه", "اهرمی"),
    ("فردا", "فردا سهام", "سهامی"),
    ("فیروزه", "فیروزه سهام", "اختصاصی"),
    ("ققنوس", "ققنوس سهام", "اهرمی"),
    ("کارآفرین", "کارآفرین سهام", "سهامی"),
    ("کامران", "کامران سهام", "سهامی"),
    ("کیوان", "کیوان سرمایه", "اهرمی"),
    ("گنجینه", "گنجینه سهام", "سهامی"),
    ("مبین", "مبین سرمایه", "اهرمی"),
    ("مثقال", "مثقال طلا", "بخشی"),
    ("محصول", "محصول کشاورزی", "بخشی"),
    ("مهر", "مهر سهام", "سهامی"),
    ("نادر", "نادر سهام", "سهامی"),
    ("ناهید", "ناهید سرمایه", "اهرمی"),
    ("نخل", "نخل طلا", "بخشی"),
    ("نیک", "نیک سهام", "سهامی"),
    ("وفاق", "وفاق سهام", "سهامی"),
    ("همراه", "همراه اول", "سهامی"),
    ("یسنا", "یسنا سهام", "سهامی"),
    ("گهر", "گهر انرژی", "سهامی"),
    ("زرفام", "زرین فام سرمایه", "اختصاصی"),
    ("نیرو", "نیرو سرمایه", "اهرمی"),
    ("دماوند", "دماوند سهام", "سهامی"),
    ("البرز", "البرز سهام", "سهامی"),
    ("آذین", "آذین سرمایه", "اهرمی"),
    ("بامداد", "بامداد سهام", "سهامی"),
    ("بهار", "بهار سهام", "سهامی"),
    ("پارمیدا", "پارمیدا سهام", "اختصاصی"),
]
