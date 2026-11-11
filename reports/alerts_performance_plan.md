# Alerts Performance Plan (بهترین عملکرد)

## گلوگاه‌های فعلی (با آدرس)
1. کوئری تکراری داخل حلقه: `alert_jobs.py:124-177` برای هر نماد تا ۴ بار `evaluate_and_trigger` صدا می‌زند و هر بار `alert_service.py:229` یک SELECT می‌زند → با ۵۰۰ نماد ≈ ۲۰۰۰ کوئری در هر ران.
2. تاریخچه RSI/SMA تک‌تک: `alert_jobs.py:136-144` برای هر نماد یک SELECT روی `quotes` → N کوئری.
3. اسنپشات روزانه: `DISTINCT ON (symbol)` روی کل جدول `brsapi_symbol_snapshots` (:87-97) بدون ایندکس ترکیبی دیده‌شده.
4. ارسال تلگرام بلاکینگ: `alert_engine.py:127` داخل حلقه await می‌شود؛ یک timeout تلگرام کل ران را قفل می‌کند.
5. تراکنش طولانی: یک `commit` در انتها (:185)؛ با خطا وسط راه همه evaluations برمی‌گردد و lock طولانی می‌شود.
6. محاسبه کامل RSI هر ران + `json.loads` تکراری condition/channels در `alert_service.py:236-261`.

## کارهای پیشنهادی (به ترتیب اثر)
### P0 — حذف N×F کوئری (اثر ~10x)
- `alert_rows` که در :50 یک‌بار لود شده را به `evaluate_and_trigger` پاس بده؛ ارزیابی شرط در حافظه انجام شود، فقط history-insert دسته‌ای در انتها flush شود.
- patch: امضای جدید `evaluate_batch(alerts_for_symbol, values: dict[field, value])` → یک پاس، بدون SELECT داخلی.

### P0 — بچ‌کردن تاریخچه (اثر ~5x)
- یک کوئری برای همه نمادها با window function:
```sql
SELECT symbol, price_close FROM (
  SELECT symbol, price_close, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) rn
  FROM quotes WHERE symbol = ANY(:syms) AND price_close > 0
) t WHERE rn <= 30;
```
- ایندکس: `CREATE INDEX ix_quotes_symbol_date ON quotes(symbol, date DESC);`

### P0 — ایندکس اسنپشات + اسکیپ سریع
- `CREATE INDEX ix_snapshots_symbol_fetched ON brsapi_symbol_snapshots(symbol, fetched_at DESC);`
- نمادهای بدون snapshot امروز را از همان دیکشنری snapshots اسکیپ کن (همین حالا هست) ولی کوئری DISTINCT ON فقط با `WHERE symbol = ANY(:syms)` محدود شود تا فول‌اسکن نشود.

### P1 — تلگرام نان‌بلاکینگ
- ارسال را به صف پس‌زمینه (همان `accuracy_outcome_queue` که idempotency دارد) منتقل کن؛ engine فقط event ثبت کند. timeout کوتاه (۳ ثانیه) + retry با backoff.

### P1 — تراکنش‌های کوتاه + ایندکس‌های گمشده
- commit هر ۲۰۰ history-insert؛ `CREATE INDEX ix_gold_rules_enabled ON gold_alert_rules(enabled);` و پس از افزودن user_id: `(user_id, enabled)`.
- `json.loads` را یک‌بار هنگام لود alert_rows انجام بده و dict آماده نگه دار.

### P2 — کش RSI و زمان‌بندی
- RSI فقط وقتی closes عوض شده recompute شود (hash آخرین ۳۰ close نگه دار)؛ SMA با میانگین متحرک افزایشی.
- به‌جای polling همه‌نمادها هر ران، نمادها را shard کن (مثلاً هر دقیقه یک‌سوم) یا event-driven روی tick جدید.

## معیار پذیرش
- ران ۵۰۰ نماد: از ~۲۰۰۰+ کوئری به <۱۰ کوئری؛ زمان p95 زیر ۵ ثانیه؛ صفر double-fire زیر بار موازی (تست ۵۰ تسک همزمان).

## Implementation evidence (done)
- AlertService.evaluate_preloaded (services/alert_service.py): in-memory eval, zero SELECT; smoke-tested.
- EvaluateAlertsJob batched (jobs/definitions/alert_jobs.py): symbol-filtered DISTINCT ON + single window-function history query.
- Migration 0105 (migrations/versions/0105_alert_eval_indexes.py): 3 indexes, chain 0105->0104 verified.
- tests/unit/services/test_alert_service.py: 47 passed.
