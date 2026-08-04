# 🗂️ repositories/ — لایه دسترسی به داده

> پل بین مدل‌های ORM (`models/`) و آبجکت‌های دامنه (`domain/`). هر Repository با الگوی **دو-بک‌اند** (InMemory برای توسعه/تست + PostgreSQL برای تولید) کار می‌کند.

---

## 📑 فهرست مطالب

- [نقش و جایگاه](#نقش-و-جایگاه)
- [الگوی دو-بک‌اند](#الگوی-دو-بکاند)
- [کلاس‌های پایه](#کلاسهای-پایه)
- [فهرست Repository ها](#فهرست-repository-ها)
- [استفاده در Dependency Injection](#استفاده-در-dependency-injection)
- [import های Lazy](#import-های-lazy)
- [قوانین و Convention ها](#قوانین-و-convention-ها)
- [اشکالات رفع‌شده](#اشکالات-رفعشده)

---

## نقش و جایگاه

```
Endpoint / Service
      │  AsyncSession (از core.database.get_session)
      ▼
Repository  ──► DbRepository[Domain, Model]  ──► SQLAlchemy
      │
      └──► InMemoryRepository[Domain]  (بدون DB — dev/test/demo)
```

- **همه کوئری‌های SQL در این لایه** متمرکزند.
- خروجی متدها **`Result[T]`** است (Ok/Err) — نه exception.
- تبدیل ORM ↔ Domain با `_to_domain` / `_to_orm`.

---

## الگوی دو-بک‌اند

هر Repository وقتی `session` نداشته باشد از InMemory و وقتی `AsyncSession` بدهید از PostgreSQL استفاده می‌کند:

```python
class InstrumentRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Instrument] | None = None if session else InMemoryRepository[Instrument]()
        self._db: _InstrumentDbRepo | None = None if not session else _InstrumentDbRepo(session)

    async def get(self, id: str) -> Result[Instrument]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)
```

### مزیت‌ها

- تست‌های واحد بدون دیتابیس اجرا می‌شوند (InMemory).
- در production با همان کد، کوئری واقعی PostgreSQL اجرا می‌شود.
- دمو/توسعه محلی بدون Postgres کار می‌کند.

---

## کلاس‌های پایه

### `DbRepository[TDomain, TModel]` — `repositories/db_base.py`

CRUD جنریک + انتزاع `_to_domain` / `_to_orm`:

```python
class DbRepository(Generic[TDomain, TModel]):
    model_class: type[TModel]

    async def get(self, id: str) -> Result[TDomain]: ...
    async def save(self, entity: TDomain) -> Result[TDomain]: ...
    async def delete(self, id: str) -> Result[bool]: ...
    async def list(self, page=1, page_size=100) -> Result[PaginatedResult[TDomain]]: ...
```

- `save` از `session.add + flush` استفاده می‌کند (commit در سطح session dependency).
- `list` صفحه‌بندی می‌کند و `PaginatedResult` برمی‌گرداند.

### `BaseRepository` / `InMemoryRepository` — `repositories/base_repository.py`

- `BaseRepository[T]` — اینترفیس انتزاعی (`get/save/delete/list`).
- `InMemoryRepository[T]` — ذخیره در حافظه با `_shared_store` کلیدشده بر اساس نام کلاس (مشترک بین همه instance های یک کلاس).

---

## فهرست Repository ها

| Repository | موجودیت | جدول | کوئری‌های ویژه |
|-----------|---------|------|----------------|
| `InstrumentRepository` | `Instrument` | `instruments` | جستجوی Finglish، ISIN، بازار |
| `QuoteRepository` | `Quote` | `quotes` | آخرین قیمت، بازه، برترین‌ها |
| `SignalRepository` | `Signal` | `signals` | آخرین سیگنال، بر اساس نماد |
| `TradeRepository` | `Trade` | `trades` | بازه تاریخ، نماد |
| `AlertRepository` | `Alert` + `AlertHistory` | `alerts` / `alert_history` | تاریخچه هشدارها |
| `UserRepository` | `User` | `users` | نام کاربری / ایمیل |
| `MarketRepository` | `Market` | `markets` | نوع بازار، بورس |
| `FundRepository` | `Fund` | `funds` | نماد، ISIN، نوع صندوق، جستجو |
| `BacktestRepository` | `BacktestRun` | `backtest_runs` | نتایج بک‌تست |
| `MlRepository` | `MlModel` / `ModelVersion` / `TrainingRun` | `ml_*` | نسخه‌ها، اجراها |
| `NewsRepository` | `NewsItem` | `news_articles` | اخبار با فیلتر |
| `CodalRepository` | `Disclosure` | `codal_reports` | اطلاعیه‌های کدال |
| `MacroRepository` | `MacroEntity` | `macro_indicators` | شاخص‌های کلان |
| `IndicatorRepository` | — | `indicators` | اندیکاتورها |
| `RecommendationRepository` | — | `recommendations` | پیشنهادات |
| `OrderBookRepository` | `OrderBookSnapshot` | `orderbooks` | دفتر سفارشات |
| `PortfolioRepository` | `Portfolio` | `portfolios` | پرتفوی |
| `PredictionRepository` | — | — | پیش‌بینی‌ها |

---

## استفاده در Dependency Injection

در `apps/api/dependencies.py` — همه از طریق `get_db_session` ساخته می‌شوند:

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    from core.database import get_session
    async for session in get_session():
        yield session

def get_instrument_import_service(session: AsyncSession = Depends(get_db_session)):
    from repositories.instrument_repository import InstrumentRepository
    from services.instrument_import_service import InstrumentImportService
    return InstrumentImportService(repo=InstrumentRepository(session=session))
```

---

## import های Lazy

`repositories/__init__.py` با **PEP 562 `__getattr__`** کار می‌کند:

```python
from repositories import InstrumentRepository   # فقط همین ماژول load می‌شود
from repositories import *                       # __all__ = کلیدهای lazy
```

- `import repositories` → **~۸ms** (نه ۳+ ثانیه).
- هر نام فقط وقتی load می‌شود که واقعاً خواسته شود و سپس در `globals()` کش می‌شود.

> 🔧 **اصلاح اعمال‌شده:** قبلاً `__all__` به نام‌هایی اشاره می‌کرد که اصلاً import نشده بودند (`from repositories import User` → NameError) و import همه‌ی repository ها ~۳.۳ ثانیه طول می‌کشید. حالا lazy و درست است.

---

## قوانین و Convention ها

1. **خروجی `Result[T]`** — متدها با `Result.ok(...)` / `Result.fail(...)` برمی‌گردند؛ exception ها را به دامنه بیرون ندهید.
2. **`_to_domain` / `_to_orm`** — نگاشت صریح در کلاس خصوصی `_XxxDbRepo`.
3. **شمارش کارآمد** — تعداد رکوردها با `func.count()` خوانده می‌شود، نه با بارگذاری همه ردیف‌ها:

```python
count_stmt = select(sa_func.count()).select_from(QuoteModel).where(...)
total = (await self.session.execute(count_stmt)).scalar() or 0
```

> 🔧 **اصلاح اعمال‌شده:** `search`/`get_by_instrument`/`get_by_date_range` در Instrument/Signal/Trade/Fund قبلاً `len(rows.scalars().all())` می‌کردند (بارگذاری همه ردیف‌ها فقط برای شمارش!) — به `func.count()` بهینه شد.

4. **فیلتر امن** — رشته‌ها با `ilike` و پارامترهای binding؛ بدون الحاق مستقیم SQL.
5. **صفحه‌بندی یکسان** — `PaginatedResult(total_pages=max(1, ...))`.
6. **مقادیر NULL** — در `_to_orm` خالی‌ها به `None` تبدیل می‌شوند (نه `[]`/`{}`).

---

## اشکالات رفع‌شده

1. **`__all__` ناقص** — نام‌های `User`, `Trade`, `Market`, `MlModel`, `AlertHistory` و… import نشده بودند.
2. **import سنگین** — import همه repository ها در `__init__.py` (~۳.۳ ثانیه) → lazy `__getattr__` (~۸ms).
3. **شمارش ناکارآمد** — `len(...scalars().all())` → `func.count()` در Instrument/Signal/Trade/Fund.
4. **فیلتر prefix-match شکننده** — `get_versions_by_model` و `get_latest_version` در مسیر in-memory از `v.id.startswith(model_id)` استفاده می‌کردند (با id شروع می‌شد) → با `v.model_name == model_id` اصلاح شد تا با مسیر DB هماهنگ باشد.
