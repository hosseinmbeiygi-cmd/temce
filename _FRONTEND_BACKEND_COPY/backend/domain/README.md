# 🧠 لایه دامنه (Domain Layer)

لایه دامنه، قلب منطق کسب‌وکار سیستم بازار سرمایه ایران است. این لایه به سبک **Domain-Driven Design (DDD)** طراحی شده و شامل **Entity**، **Value Object**، **Domain Event**، **Business Rule** و **Specification** می‌شود. هیچ وابستگی به زیرساخت (دیتابیس، HTTP، فریم‌ورک) ندارد و کاملاً خالص (Pure) است.

---

## 🗂️ ساختار

```
domain/
├── common/          ← هسته مشترک: BaseEntity, ValueObject, Rules, Events, Specifications
├── instruments/     ← ابزارهای مالی (سهام، صندوق، اختیار، آتی)
├── market_data/     ← داده‌های بازار: قیمت، سفارش‌ها، معاملات
├── quotes/          ← قیمت لحظه‌ای و اسنپ‌شات‌ها
├── orderbook/       ← دفتر سفارش (5 سطح)
├── trades/          ← معاملات خرد
├── portfolios/      ← پرتفوی، موقعیت‌ها، عملکرد
├── watchlists/      ← لیست پیگیری
├── signals/         ← سیگنال‌ها: قدرت، اطمینان، دلایل
├── recommendations/ ← توصیه‌ها: تصمیم، توضیح، برچسب ریسک
├── alerts/          ← هشدارها: کانال، ماشه، قوانین
├── backtest/        ← بک‌تست: اجرا، متریک‌ها، معاملات
├── analytics/       ← تحلیل: فاکتور، امتیاز، رتبه‌بندی، سیگنال
├── indicators/      ← اندیکاتورها: تعریف، پارامتر، مقدار
├── screening/       ← غربالگری: فیلتر، پری‌ست، رتبه‌بندی
├── ml/              ← یادگیری ماشین: آموزش، پیش‌بینی، ویژگی
├── codal/           ← اطلاعیه‌ها و صورت‌های مالی
├── news/            ← اخبار: منبع، احساسات، نگاشت
├── macro/           ← شاخص‌های کلان: سری، رژیم‌ها
├── markets/         ← بازارها: طبقه‌بندی، جلسات
├── fx/              ← ارز: جفت‌ارز، تبدیل
├── metals/          ← فلزات: نقدی، آتی
├── commodities/     ← کالاها: قرارداد، طبقه‌بندی
├── energy/          ← انرژی: قرارداد، جلسه
├── bonds/           ← اوراق: مدت، منحنی بازده
├── funds/           ← صندوق‌ها: NAV، بازده، طبقه‌بندی
├── indices/         ← شاخص‌ها: ترکیب، عرض
├── options/         ← اختیار: قیمت‌گذاری، یونانی‌ها، واریانس
├── calendar/        ← تقویم معاملاتی
├── audit/           ← حسابرسی: بازیگر، اقدام، زمینه
└── __init__.py      ← خروجی‌های عمومی
```

هر زیردامنه الگوی ثابتی دارد:

| فایل | نقش |
|------|-----|
| `entities.py` | انتیتی‌های دامنه |
| `rules.py` | قواعد کسب‌وکار (`BusinessRule`) |
| `value_objects.py` | اشیای مقداری |
| `events.py` | رویدادهای دامنه |
| `__init__.py` | خروجی‌های عمومی |

---

## 🏛️ هسته مشترک (common/)

### `BaseEntity` — `domain/common/base_entity.py`

کلاس پایه همه انتیتی‌ها:

- `id: str` — شناسه یکتا
- `created_at` / `updated_at: datetime` — بر اساس ساعت **UTC** بدون timezone
- `mark_updated()` — به‌روزرسانی زمان
- برابری بر اساس `id` و `__hash__` بر پایه `id`
- `__repr__` خوانا برای دیباگ

```python
from domain import BaseEntity

class Instrument(BaseEntity):
    def __init__(self, id: str, symbol: str):
        super().__init__(id)
        self.symbol = symbol
```

### `AggregateRoot` — `domain/common/entities.py`

زیرکلاس `BaseEntity` با قابلیت ثبت رویداد دامنه:

```python
class Portfolio(AggregateRoot):
    def add_position(self, position):
        self.record_event(PositionAdded(portfolio_id=self.id, ...))
        ...
```

- `record_event(event)` — ثبت رویداد
- `clear_events()` — بازگرداندن و پاک کردن رویدادها (معمولاً پس از ذخیره‌سازی)

### `ValueObject` — `domain/common/value_object.py`

اشیای مقداری **immutable** (frozen dataclass):

```python
@dataclass(frozen=True)
class Price(ValueObject):
    amount: Decimal
    currency: str = "IRR"
```

- برابری ساختاری (بر اساس همه فیلدها)
- `__hash__` بر اساس همه فیلدها (امن برای استفاده در dict/set)
- `__post_init__` → `_validate()` برای اعتبارسنجی

### اشیای مقداری آماده — `domain/common/value_objects.py`

| کلاس | توضیح |
|------|-------|
| `Money` | مبلغ با واحد پول؛ جمع/تفریق/ضرب با بررسی تطابق واحد |
| `Percentage` | درصد بین ۱۰۰- و ۱۰۰؛ متد `of(amount)` |
| `Range` | بازه `low..high`؛ `contains()` و `overlap()` |
| `ISIN` | شناسه بین‌المللی اوراق — اعتبارسنجی **12 کاراکتر + کد کشور + checksum لوهن** |

> ✅ **رفع‌شده در فاز ۲:** `ISIN` قبلاً فقط طول را بررسی می‌کرد. حالا:
> - حروف اول باید کد کشور ۲ حرفی باشد
> - فقط کاراکترهای `[A-Z0-9]` مجازند
> - **Check digit با الگوریتم Luhn (ISO 6166)** اعتبارسنجی می‌شود (حروف → عدد، سپس Luhn mod-10)
> - ورودی خودکار `strip` و `upper` می‌شود

### `BusinessRule` — `domain/common/rules.py`

الگوی قواعد کسب‌وکار با پیام خطای مشخص:

```python
class PositionLimitRule(BusinessRule):
    def __init__(self, current: float, limit: float):
        super().__init__("position_limit", f"Position {current} exceeds limit {limit}")
        self._current, self._limit = current, limit
    def is_satisfied(self) -> bool:
        return self._current <= self._limit
```

- `check()` → در صورت نقض `DomainRuleViolation` پرتاب می‌کند
- `PredicateRule` — قاعده از روی یک تابع `Callable[[], bool]`
- توابع کمکی: `validate_required`، `validate_positive`، `validate_non_negative`

### `DomainEvent` — `domain/common/events.py`

رویدادهای دامنه (dataclass):

- `event_id` (UUID)، `occurred_at` (UTC)، `name`، `data`، `aggregate_id`، `version`
- `event_type` → نام کلاس (مثلاً `EntityUpdated`)
- زیرکلاس‌ها: `EntityCreated`، `EntityUpdated`، `EntityDeleted`

### `Specification` — `domain/common/specifications.py`

الگوی Specification برای ترکیب شرط‌ها:

```python
spec = IsActive().and_(InSector("fidar")).or_(IsIndex())
if spec.is_satisfied_by(instrument): ...
```

- ترکیب‌ها: `and_`، `or_`، `not_`
- `AttributeSpecification` — بررسی ساده صفت
- فراخوانی‌پذیر: `spec(candidate)`

### `enum_types.py`

انواع شمارشی مشترک (StrEnum): `MarketType`، `AssetClass`، `InstrumentStatus`، `OrderSide`، `OrderType`، `TimeFrame`، `SignalType`، `RecommendationAction`، `ModelStage`، `DataSource`، `ProviderHealth`، `JobStatus`، `TimeSeriesGranularity`.

---

## 📦 زیردامنه‌های اصلی

### instruments/
انتیتی `Instrument` (ابزار مالی) + `InstrumentGroup`، بازار، بخش، قانون پذیرش، نام مستعار (alias). شامل `InstrumentGroup`، `listing_rules` (قوانین پذیرش/تعلیق)، `market.py`، `sector.py`، `services.py`.

### market_data/
- `quote.py` — قیمت لحظه‌ای (`Quote`)
- `trade.py` — معامله (`Trade`)
- `orderbook.py` — دفتر سفارش
- `corporate_action.py` — رویدادهای شرکتی
- `price_rules.py` — قوانین قیمت (دامنه نوسان)

### options/
قوی‌ترین زیردامنه مالی: `pricing.py`، `greeks.py`، `black_scholes`، `heston_model.py`، `tree_pricing.py`، `margin_engine.py`، `var_calculator.py`، `probability.py`، `volatility.py`، `higher_order_greeks.py`. تست‌ها: `tests/unit/domain/test_black_scholes_pricing.py`.

### signals/ و recommendations/
- `signals/confidence.py`، `strength.py`، `reasons.py` — ترکیب سیگنال
- `recommendations/decisions.py`، `explanations.py`، `risk_labels.py`

### backtest/
- `runs.py` — اجرای بک‌تست
- `trades.py` — معاملات شبیه‌سازی‌شده
- `metrics.py` — متریک‌های عملکرد

---

## 🧪 تست‌ها

`tests/unit/domain/` شامل تست‌های قواعد زیردامنه‌ها:

```
test_backtest_rules.py      test_black_scholes_pricing.py
test_instrument_rules.py    test_orderbook_rules.py
test_quote_rules.py         test_recommendation_rules.py
test_signal_rules.py
```

اجرا:

```bash
python -m pytest tests/unit/domain/ -q
```

---

## 🔒 اصول طراحی

1. **خالص بودن** — هیچ import از `repositories`، `services` یا `apps` در دامنه نیست
2. **Immutable بودن** — اشیای مقداری frozen هستند
3. **یکپارچگی** — قواعد کسب‌وکار در `rules.py`، نه پراکنده در سرویس‌ها
4. **رویدادمحوری** — تغییرات مهم از طریق `DomainEvent` اعلام می‌شوند
5. **انواع امن** — استفاده از `StrEnum` به‌جای رشته ساده
