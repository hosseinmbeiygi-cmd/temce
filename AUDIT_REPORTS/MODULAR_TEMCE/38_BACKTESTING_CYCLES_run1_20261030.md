# ۳۸ — AUD-ARCH-01: صفر شدن چرخه‌های `backtesting` — run1، ۳۰ اکتبر ۲۰۲۶

**AUD-ARCH-01:** **FIXED** — چرخه‌های وابستگی از ۱۵ خام/۹ کانونیک (پایان گزارش ۳۷)
به **۰ خام/۰ کانونیک** رسید. ۳۹۵ تست backtesting پاس شد.

---

## ۱) اسلایس‌ها

### ۱(الف) `TEHRAN_TZ` → `backtesting/constants.py`

`market/rule_engine.py` تنها برای یک ثابت، `engine.clock` را import می‌کرد.
ثابت به `constants.py` منتقل شد و `engine.clock` آن را re-export می‌کند.
نتیجه: **۷ خام / ۴ کانونیک**.

### ۱(ب) `EventType`/`MarketEvent` و `Clock` → ماژول‌های برگ

- `backtesting/event_types.py` (جدید): `EventType`, `MarketEvent`؛
  `engine.event_builder` آن‌ها را re-export می‌کند.
- `backtesting/clock.py` (جدید): `Clock`, `to_utc`؛ `engine.clock` re-export می‌کند.
- importهای `strategies/context.py`، `strategies/engine.py` و
  `microstructure/microstructure_engine.py` به ماژول‌های برگ تغییر کرد.
نتیجه: **۴ خام / ۲ کانونیک**.

### ۱(ج) `PositionManager` و `PortfolioManager` → لایه‌های برگ

- `backtesting/position_manager.py` (جدید، از `engine/position_manager.py`)؛
  `engine/position_manager.py` فقط re-export است.
- `backtesting/portfolio/manager.py` (جدید، از `engine/portfolio.py`)؛
  `engine/portfolio.py` فقط re-export است.
- `portfolio/__init__.py` دیگر از `engine` import نمی‌کند.
نتیجه: **۰ خام / ۰ کانونیک**.

> **ریسک سازگاری:** `__module__` این کلاس‌ها عوض شده است. همهٔ importهای قبلی از طریق
> `engine.portfolio` / `engine.position_manager` کار می‌کنند (smoke test: `True`)، اما
> pickle کردن نمونه‌های قدیمی به ماژول جدید resolve می‌شود.

---

## ۲) تست‌ها

| اجرا | نتیجه |
|---|---|
| `pytest tests/unit/backtesting` (اجرای اول) | ۳۸۶ passed / **۹ failed** — همه `AttributeError: 'Clock' object has no attribute 'reset'` |
| پس از بازگرداندن کامل متدهای `Clock` (`jump_to`, `on_tick`, `is_market_open`, `reset`) | — |
| دو فایل خطادار | **۲۸ passed** |
| `pytest tests/unit/backtesting` (نهایی) | **۳۹۵ passed / ۱ skipped**، exit 0 |

درس: انتقال کلاس باید با کل فایل اصلی diff شود، نه فقط بخش خوانده‌شده؛ متدهای
`Clock` در ادامهٔ فایل بودند و در انتقال اول جا افتادند.

---

## ۳) فایل‌ها

```
backtesting/constants.py                 + TEHRAN_TZ
backtesting/event_types.py               جدید
backtesting/clock.py                     جدید (کلاس کامل)
backtesting/position_manager.py          جدید (منتقل‌شده)
backtesting/portfolio/manager.py         جدید (منتقل‌شده)
backtesting/engine/clock.py              re-export
backtesting/engine/event_builder.py      استفاده از event_types
backtesting/engine/position_manager.py   re-export
backtesting/engine/portfolio.py          re-export
backtesting/portfolio/__init__.py        import محلی
backtesting/market/rule_engine.py        TEHRAN_TZ از constants
backtesting/strategies/context.py        importهای برگ
backtesting/strategies/engine.py         import برگ
backtesting/microstructure/microstructure_engine.py  import برگ
```

## ۴) وضعیت

| مورد | وضعیت |
|---|---|
| چرخه‌های وابستگی (۱۲ ماژول ریشه) | **PASS** — ۰ خام / ۰ کانونیک |
| تست backtesting | **PASS** — ۳۹۵/۳۹۶ (۱ skip) |
| رفتار runtime | **PASS** (re-exportها حفظ شدند) |
| گارد CI (`import-linter`) | **BLOCKED** — افزودن dependency نیاز به approval |
| commit | **BLOCKED** — درخت مشترک |
