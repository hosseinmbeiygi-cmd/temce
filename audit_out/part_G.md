# بخش G — داده

> [خوانده‌شده+اجراشده] با SELECT فقط (`audit_out/_tmp/partG_db.py` → `audit_out/_tmp/partG.json`). DB زنده: `localhost:5432/my_first_db`.

---

## G1) فهرست جدول‌های داده بک‌تست/ML (از DB واقعی، نه حدس)

| جدول | وجود دارد؟ | ستون‌های کلیدی | knowledge_time؟ | گذشته بازنویسی می‌شود؟ | تعداد ردیف / بازه |
|---|---|---|---|---|---|
| قیمت روزانه `brsapi_historical_daily` | ✅ | `symbol, date(Jalali varchar), time, trade_count, trade_volume, trade_value, price_min/max/yesterday/first/last/close, gregorian_date, shamsi_date, created_at, updated_at` | ❌ (فقط `created_at`/`updated_at`) | ✅ (updated_at دارد ⇒ upsert بازنویسی می‌کند) | **۵٬۵۵۴٬۶۲۵** |
| حقیقی/حقوقی `brsapi_historical_real_legal` | ✅ | `symbol, date, buy/sell_real/legal_count/volume/value, gregorian_date, shamsi_date, created_at, updated_at` | ❌ | ✅ | **۴٬۸۹۷٬۶۵۹** |
| صف/عمق (order book) | ⚠️ فقط `orderbook_snapshots` (hypertable) | — | ❌ | — | نمونه‌برداری نشد |
| وضعیت نماد | ✅ `brsapi_symbol_details` | — | ❌ | — | **۱۳٬۹۳۳** |
| رویدادهای شرکتی `corporate_action_events` | ✅ | `symbol_id, ex_date, action_type, ratio, dps, source, codal_ref, notes, created_at` | ❌ (`created_at` فقط) | — | **۵۸۶** (فقط `capital_increase`، همه `dps=0`) |
| `corporate_actions` | ✅ ولی **۰ ردیف** | `symbol, action_type, ex_date, record_date, params, applied, source, raw_text` | ❌ | — | **۰** |
| NAV `brsapi_nav_records` | ✅ | — | ❌ | — | **۳٬۵۸۸** |
| ارز `brsapi_currency_history` | ❌ (خطا: `ProgrammingError`) | — | — | — | ستون/جدول متفاوت است |
| سکه `brsapi_gold_coin_history` | ✅ | — | ❌ | — | **۴۴٬۹۶۵** |
| کدال `brsapi_codal_announcements` | ✅ | — | ❌ | — | **۷۸٬۷۸۹** |
| ضریب تعدیل `daily_adjust_factors` | ✅ | `symbol_id, trade_date, adj_factor, computed_at` | ❌ | — | **۶۲۱٬۸۱۸** (بازه `2001-03-25`..`2026-10-04`) |
| اسنپ‌شات آپشن `brsapi_option_snapshots` | ❌ (خطا: `DBAPIError`) | — | — | — | — |

نمونهٔ ردیف واقعی (بدون داده شخصی):
```
brsapi_historical_daily: {symbol:'بزاگرس3', date:'1405-07-15', time:'12:50:39', trade_volume:'15588', price_min:'7790.0', ...}
brsapi_historical_real_legal: {symbol:'آ س پ', date:'1402-11-17', buy_real_count:'1067', buy_legal_count:'6', sell_real_count:'746', ...}
corporate_action_events: {ex_date:'2026-08-15', action_type:'capital_increase', ratio:'0.249395', dps:'0.00',
   notes:'CODAL آگهی ثبت افزایش سرمایه(اصلاحیه) | TSETMC re-based prev close 10320→8260 (f=0.800388, ratio=0.249395)'}
daily_adjust_factors: {symbol_id:'7234567890123459', trade_date:'2026-10-04', adj_factor:'1.0000000000', computed_at:'2026-10-07 11:07:18'}
```

### 🔴 یافتهٔ بحرانی داده: معنای `gregorian_date`
برای خودرو: `date` (که بک‌تست روی آن فیلتر می‌کند) از `1380-01-05` تا `1405-06-22` (تاریخ معاملاتی جلالی) است، ولی `gregorian_date` **`2026-07-16`..`2026-09-14`** و `shamsi_date` ثابت `1405-04-27`/`1405-…` است. عین خروجی:
```
('1402-10-11', 2026-07-18, '1405-04-27', 2744.0)
('1402-10-12', 2026-07-18, '1405-04-27', 2732.0)
('1402-10-13', 2026-07-18, '1405-04-27', 2755.0)
('1402-10-16', 2026-07-18, '1405-04-27', 2851.0)
```
⇒ چند تاریخ معاملاتی جلالی **یک `gregorian_date` مشترک** دارند ⇒ `gregorian_date`/`shamsi_date` **تاریخ sync/ingest است، نه تاریخ معامله**. کل جدول `gregorian_date` بازهٔ `2026-07-15..2026-10-08` دارد (پنجرهٔ سینک).

**اثر:** `services/signal_backtest_engine.py::_fetch_future_prices` صریحاً روی `gregorian_date` فیلتر می‌کند (با این توضیح که «تاریخ واقعی است») — ولی این ستون «زمان سینک» است ⇒ پنجرهٔ «قیمت‌های آینده» بر اساس ترتیب ingest انتخاب می‌شود، نه ترتیب معاملاتی. `AdvResolver` هم همین ستون را با `CURRENT_DATE - 30 days` فیلتر می‌کند.

---

## G2) TimescaleDB: bitemporal یا نسخه‌بندی؟

- Hypertableها عبارت‌اند از: `candlesticks_deprecated, commodity_prices, daily_history_deprecated, daily_real_legal, etf_nav, gold_currency_prices, intraday_trades_deprecated, market_ticks, orderbook_snapshots, shareholders, symbol_snapshots_deprecated`.
- **`brsapi_historical_daily` (جدول اصلی بک‌تست) hypertable نیست.**
- ستون‌های شبه‌knowledge_time فقط در ۹ جدول غیرقیمتی وجود دارد: `fact_financials.valid_from/valid_to`، `fund_insurance_policies.valid_from/valid_to`، `news_*.published_at` — **روی هیچ جدول قیمتی/حقیقی-حقوقی نیست.**
- `brsapi_historical_daily` هم `created_at` و هم `updated_at` دارد ⇒ **upsert گذشته را بازنویسی می‌کند** (بدون نسخه‌بندی).

⇒ **bitemporal نیست.** بازآزمایی دقیق گذشته ممکن نیست (knowledge_time ذخیره نمی‌شود).

---

## G3) نمونهٔ واقعی جدول‌های اصلی
در `audit_out/_tmp/partG.json` → `samples` (۵ ردیف برای هرکدام از `brsapi_historical_daily`, `brsapi_historical_real_legal`, `daily_adjust_factors`, `corporate_action_events`). هیچ داده شخصی/اعتبارنامه‌ای در این جدول‌ها نیست.

---

## G4) چرا ADV برای خودرو resolve نمی‌شود (fallback 1,000,000)؟

**منبع `AdvResolver`:** `backtesting/engine/adv.py` → `SELECT AVG(trade_volume) FROM brsapi_historical_daily WHERE symbol=:sym ... AND gregorian_date >= CURRENT_DATE - INTERVAL '30 days'`.

دلیل fallback در اجرای مستقیم ممیزی:
1. مسیر `BacktestSimulator` **sync** است و نمی‌تواند await کند؛ فقط `self.adv_resolver.peek()` (کش) را می‌خواند. در اجرای مستقیم، `Broker` اصلاً `adv_resolver` ندارد ⇒ `_resolve_daily_volume` مقدار `None` می‌دهد ⇒ fallback `average_daily_volume=1_000_000` (عین سطر `broker.py`: `No ADV resolved for '%s' — using fallback %d`).
2. `adv_resolver.resolve` اگر فراخوانی شود، مقدار واقعی می‌دهد — ولی **مقدارش مشکوک است:**
```
resolve خودرو -> 8423355627     # ~8.4 میلیارد سهم در روز
resolve فولاد -> 3969817853
resolve آ س پ ->  2755101
```
`8.4e9` برای خودرو غیرواقعی است (احتمالاً به‌خاطر ردیف‌های تکراری/سینک‌های متنوع و اینکه پنجره روی `gregorian_date`=زمان سینک است).

⇒ **ناهم‌خوانی شدید هزینه:** در مسیر sync با fallback `1e6`، لغزش به سقف ۱۵۰bps می‌خورد؛ اگر ADV واقعی (`~8.4e9`) تزریق شود، لغزش ≈۰ می‌شود. یعنی هزینهٔ بک‌تست به این وابسته است که آیا resolver pre-warm شده یا نه — تفاوت چند هزاربرابری.

---

## جمع‌بندی بخش G

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| G-01 | `gregorian_date`/`shamsi_date` = زمان سینک، نه تاریخ معامله؛ چند تاریخ معاملاتی یک gregorian مشترک دارند | **بحرانی** | جدول `brsapi_historical_daily` | افزودن `trade_date` واقعی |
| G-02 | `_fetch_future_prices` روی `gregorian_date` فیلتر می‌کند (ستون اشتباه) | بحرانی | `services/signal_backtest_engine.py` | فیلتر روی تاریخ معاملاتی |
| G-03 | `brsapi_historical_daily` hypertable نیست و bitemporal/نسخه‌بندی ندارد؛ upsert بازنویسی می‌کند | بالا | DB | افزودن knowledge_time |
| G-04 | ADV sync fallback ۱٬۰۰۰٬۰۰۰ در برابر مقدار resolve‌شدهٔ ~۸.۴e9 ⇒ تفاوت هزینهٔ چند هزاربرابری | بالا | `backtesting/engine/adv.py` + `broker.py` | pre-warm + محاسبهٔ درست ADV |
| G-05 | رویداد شرکتی فقط `capital_increase` و همه `dps=0`؛ `corporate_actions` صفر ردیف | بالا | DB | افزودن سود نقدی |
| G-06 | `brsapi_currency_history` و `brsapi_option_snapshots` با کوئری عمومی خطا دادند (نام ستون متفاوت) | پایین | DB | بازبینی اسکیما |
