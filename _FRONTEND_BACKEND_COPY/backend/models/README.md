# 🗄️ models/ — لایه مدل‌های دیتابیس (SQLAlchemy ORM)

> تعریف ساختار جداول با **SQLAlchemy 2.0** (سبک `Mapped` / `mapped_column`). مهاجرت‌های واقعی دیتابیس در `migrations/` (Alembic) مدیریت می‌شوند.

---

## 📑 فهرست مطالب

- [نقش و جایگاه](#نقش-و-جایگاه)
- [ساختار پوشه‌ها](#ساختار-پوشهها)
- [کلاس پایه و Mixin ها](#کلاس-پایه-و-mixin-ها)
- [جداول اصلی](#جداول-اصلی)
- [JSON و داده‌های پیچیده](#json-و-دادههای-پیچیده)
- [قوانین و Convention ها](#قوانین-و-convention-ها)
- [ارتباط با لایه‌های دیگر](#ارتباط-با-لایههای-دیگر)
- [اشکالات رفع‌شده](#اشکالات-رفعشده)

---

## نقش و جایگاه

```
schemas/ (Pydantic)  ──▶  models/ (SQLAlchemy)  ◀──  repositories/
    ورودی/خروجی API            جداول دیتابیس           دسترسی به داده
```

- `models/` فقط **ساختار جدول** را تعریف می‌کند.
- **کوئری‌نویسی در repositories** است، نه در models.
- تبدیل مدل → آبجکت دامنه در repositories انجام می‌شود (لایه `domain/`).

---

## ساختار پوشه‌ها

```
models/
├── base.py              # Base + TimestampMixin (پایه همه مدل‌ها)
├── __init__.py          # ثبت/import همه مدل‌ها برای create_all و Alembic autogenerate
├── instrument.py        # نمادها و ابزارهای معاملاتی
├── quote.py             # قیمت‌ها (OHLCV + bid/ask)
├── trade.py             # معاملات
├── market.py            # بازارها
├── market_data.py       # symbols, daily_history, intraday_trades, shareholders,
│                        #   gold_currency, commodity_*, indices, options, etf_nav, ...
├── signal.py            # سیگنال‌ها
├── recommendation.py    # پیشنهادات خرید/فروش
├── alert.py             # هشدارها + تاریخچه هشدار
├── news.py              # اخبار
├── codal.py             # اطلاعیه‌های کدال
├── fund.py              # صندوق‌های سرمایه‌گذاری (NAV روزانه)
├── user.py              # کاربران
├── portfolio.py         # پرتفوی و موقعیت‌ها
├── orderbook.py         # دفتر سفارشات
├── ml.py                # مدل‌ها و اجراهای ML
├── backtest.py          # اجراهای بک‌تست
├── macro.py             # شاخص‌های کلان
├── indicator.py         # اندیکاتورها
├── screener.py          # پروفایل‌ها و نتایج غربالگری
├── saved_filter.py      # فیلترهای ذخیره‌شده
├── job_run.py           # اجرای شغل‌ها
├── queue_analysis.py    # تحلیل صف
├── decision_engine.py   # موتور تصمیم‌گیری
└── ...
```

---

## کلاس پایه و Mixin ها

### `models/base.py`

```python
class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),          # ← ساعت دیتابیس (DB clock)
        server_default=func.now(),   # ← در DDL هم اعمال می‌شود
    )
```

> 🔧 **اصلاح اعمال‌شده:** قبلاً `default` در پایتون `datetime.now(UTC)` بود ولی `server_default` از ساعت دیتابیس می‌آمد — دو مقدار متفاوت (ناسازگاری UTC/local). حالا **هر دو از ساعت دیتابیس** هستند و کاملاً هم‌سو.

### الگوی تعریف مدل

```python
from models.base import Base, TimestampMixin
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float

class MyModel(TimestampMixin, Base):
    __tablename__ = "my_table"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    price: Mapped[float | None] = mapped_column(Float)
```

---

## جداول اصلی

| مدل | جدول | توضیح |
|-----|------|-------|
| `InstrumentModel` | `instruments` | نمادها با ISIN، lot size، par value، sector |
| `QuoteModel` | `quotes` | قیمت روزانه + bid/ask + حجم و ارزش |
| `TradeModel` | `trades` | معاملات (قیمت، حجم، سمت) |
| `MarketModel` | `markets` | بازارها (ساعات معاملات، منطقه زمانی) |
| `SymbolModel` | `symbols` | کاتالوگ نماد (FK عددی برای TSETMC) |
| `DailyHistoryModel` | `daily_history` | تاریخچه روزانه (PK مرکب symbol_id + date) |
| `IntradayTradeModel` | `intraday_trades` | معاملات درون‌روز |
| `GoldCurrencyPriceModel` | `gold_currency_prices` | طلا و ارز |
| `CommodityTradeModel` | `commodity_trades` | معاملات کالا |
| `IndexModel` | `indices` | شاخص‌ها |
| `SignalModel` | `signals` | سیگنال‌ها با strength و direction |
| `AlertModel` / `AlertHistoryModel` | `alerts` / `alert_history` | هشدارها و تاریخچه |
| `NewsArticleModel` | `news_articles` | اخبار با sentiment |
| `FundModel` | `funds` | صندوق‌ها (NAV و معاملات روزانه) |
| `UserModel` | `users` | کاربران (roles, is_active, refresh_token) |
| `MlModelModel` / `MlModelVersionModel` | `ml_models` / `ml_model_versions` | مدل‌های ML |
| `BacktestRunModel` | `backtest_runs` | نتایج بک‌تست |
| `JobRunModel` | `job_runs` | اجرای شغل‌ها |

### ستون‌های پرکاربرد

- `id: String(50)` — شناسه متنی (تولید با `core.ids.new_id`).
- `symbol` — با `index=True` برای جستجوی سریع.
- `data_source` — منبع داده (`tsetmc`, `brsapi`, `system`).
- `created_at` — از `TimestampMixin`.
- `updated_at` — در مدل‌های نیازمند، جداگانه تعریف می‌شود.

---

## JSON و داده‌های پیچیده

### `UnicodeJSON` (در `models/instrument.py`)

نوع ستون JSON که متن فارسی را **بدون escape** ذخیره می‌کند (`ensure_ascii=False`):

```python
class UnicodeJSON(JSON):
    """JSON column that preserves non-ASCII text on write."""

    def bind_processor(self, dialect):
        ...
        return self._make_bind_processor(string_process, json_serializer)  # ensure_ascii=False
```

نمونه استفاده — `InstrumentModel.tags` و `InstrumentModel.metadata_`:

```python
tags: Mapped[list[str] | None] = mapped_column(UnicodeJSON, nullable=True)
metadata_: Mapped[dict[str, Any] | None] = mapped_column(UnicodeJSON, nullable=True)
```

### ستون‌های JSON به‌صورت رشته

برخی مدل‌ها (مثل `FundModel.extra`) داده JSON را به‌صورت **رشته در ستون TEXT** نگه می‌دارند و Repository سریال/دی‌سریال می‌کند:

```python
extra: Mapped[str | None] = mapped_column(Text, comment="داده‌های اضافی (JSON string)")
```

> 🔧 **اصلاح اعمال‌شده:** annotation قبلی `Mapped[dict]` بود درحالی‌که ستون `Text` است — SQLAlchemy هنگام bind یک dict به ستون Text خطا می‌داد. حالا annotation صادقانه (`str | None`) است.

---

## قوانین و Convention ها

1. **ارث‌بری**: `class XModel(TimestampMixin, Base)` — ترتیب مخلوط‌ها ثابت.
2. **نام جدول**: snake_case جمع (`instruments`, `signals`, `alert_history`).
3. **شناسه**: `String(50)` متنی؛ برای جدول‌های مبتنی بر TSETMC از `BigInteger` (مثل `SymbolModel`).
4. **تایپ کامل**: همه ستون‌ها با `Mapped[...]` تایپ می‌شوند (SQLAlchemy 2.0).
5. **ایندکس**: فیلدهای جستجو (`symbol`, `instrument_id`, `date`) ایندکس می‌شوند.
6. **سرور پیش‌فرض**: مقادیری مثل `server_default="active"`, `server_default="1.0"` — هماهنگ با مهاجرت‌ها.
7. **`models/__init__.py`**: همه مدل‌ها import می‌شوند تا `Base.metadata` کامل باشد (برای Alembic autogenerate و create_all).

---

## ارتباط با لایه‌های دیگر

- **Repository** با `DbRepository[Domain, Model]` نگاشت domain ↔ ORM را انجام می‌دهد (متدهای `_to_domain` / `_to_orm`).
- **مثال** — `repositories/instrument_repository.py`:

```python
class _InstrumentDbRepo(DbRepository[Instrument, InstrumentModel]):
    model_class = InstrumentModel

    def _to_domain(self, orm: InstrumentModel) -> Instrument:
        return Instrument(id=orm.id, symbol=orm.symbol, ...)
```

- **مهم**: مدل‌های ORM **هرگز** مستقیم به فرانت‌اند برگردانده نمی‌شوند؛ همیشه با schema (Pydantic) یا دیکشنری تبدیل می‌شوند.

---

## اشکالات رفع‌شده

1. **ناسازگاری `created_at`** — default پایتون (UTC) با server_default (ساعت DB) فرق داشت → هر دو به ساعت DB منتقل شد.
2. **annotation نادرست `FundModel.extra`** — `dict` روی ستون `Text` → اصلاح به `str | None` با توضیح.
3. **حروف چینی در docstring** — `ScreenerSnapshot` (خط ۱۱۳) کلمه چینی `包含` → «شامل».
4. **ترتیب mixin نامنظم** — سه مدل در `models/option.py` (`OptionContractModel`, `OptionSnapshotModel`, `OptionTradeModel`) از `(Base, TimestampMixin)` استفاده می‌کردند در حالی که Convention (`TimestampMixin, Base`) است → نرمال‌سازی شد.
