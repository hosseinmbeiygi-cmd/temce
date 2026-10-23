# گزارش خطاهای پنهان و ناپیدا — Iran Market Platform
> تاریخ: ۱۴۰۴/۰۶/۰۴ | بررسی: فرانت + بک‌اند + منطق مالی + ingestion

## چکیده
- **بحرانی (کرش در ران‌تایم):** ۳ مورد
- **مهم (محاسبه مالی غلط / دیتا گم می‌شود):** ۸ مورد
- **متوسط (UX مخفی / ریسک امنیتی):** ۷ مورد
- **کم (استایل/پرفورمنس):** ۵ مورد
- قبلا فیکس شد: `frontend/src/lib/fund-checklist-real.ts:523` (بیلد Turbopack شکسته) → الان OK

---

## ۱) بحرانی — همین الان کرش می‌کند

### 1.1 `services/quant_signal_orchestrator.py:657,682,685,689,694,697,700,714,717,721,724,727,729,750,752` — `NameError: _stage_time`
```python
import time
_t0 = time.monotonic()
logger.info("... %.2fs", _stage_time.monotonic() - _t0, ...) # ← NameError
_t1 = _stage_time.monotonic() # ← 15 جای دیگر همین
```
`_stage_time` هیچ‌جا تعریف نشده (باید `time` باشد).
**اثر:** اولین درخواست `GET /multi-market-signals` یا کرون ساعتی `warm_signal_cache` کل پایپ‌لاین را با 500 می‌اندازد.
**فیکس:** همه `_stage_time.monotonic()` → `time.monotonic()`

### 1.2 `frontend/src/app/backtest/page.tsx:314-318` — `setState` داخل رندر
```ts
const [prevStrategies,setPrevStrategies]=useState(strategies);
if(strategies && strategies!==prevStrategies){
  setPrevStrategies(strategies); // ← داخل بدنه کامپوننت، نه useEffect
  setFormData(prev=>...)
}
```
**اثر:** هر refetch رفرنس strategies عوض می‌شود → ست‌استیت حین رندر → فلیکر + پاک شدن پارامترهای کاربر + ریسک لوپ.
**فیکس:** ببر داخل `useEffect(()=>{...},[strategies])`

### 1.3 `frontend/src/app/options/page.tsx:126-135` — race زنجیره + `alert` بلاک‌کننده
- `loadChain` بدون `AbortController`/requestId: کلیک سریع 3 نماد → جواب کند قبلی جواب جدید را بازنویسی می‌کند.
- `handleQuickBuy` با `alert()` ترد اصلی را فریز می‌کند.
**فیکس:** `toast` از `sonner` + `AbortController` + گارد `mounted`.

---

## ۲) مهم — محاسبه غلط ولی بدون کرش (پول/سیگنال اشتباه)

### 2.1 `core/indicators.py:232-245` — `compute_trend_strength(period)` پارامتر نادیده
حلقه روی کل تاریخ `for i in range(1,len(closes))` می‌چرخد نه `period` آخر — با 100 کندل و `period=14` کل 99 کندل امتیاز می‌گیرد.

### 2.2 `services/feature_engine.py:357-363` — `float_turnover_pct` 100 برابر غلط
```python
float_shares = enriched.get("free_float_pct",0) # درصد 0-100
f["float_turnover_pct"]=100*f["trade_value"]/(float(float_shares)*last_price)
```
باید `shares_count * free_float_pct/100` باشد — الان 8x متورم.

### 2.3 `services/feature_engine.py:408-412` — `net_inst_ratio` مخرج غلط
همین اشتباه + `int(pct)` → جریان حقوقی تصادفی ±25 امتیاز.

### 2.4 `domain/options/margin_engine.py:128-134` — تشخیص covered_call اشتباه
`long_stock_qty >= total_contracts*contract_size` ولی `quantity` تعداد قرارداد است نه سهم → مارجین اشتباه (اضافه یا صفر برای naked).

### 2.5 `domain/options/pricing.py:30-35` — `gamma=inf` با sigma کوچک
`T=0.001, sigma=0.0001` → `gamma = pdf/(S*sigma*sqrt(T))` → `inf` → JSON `Infinity` → `JSON.parse` در فرانت SyntaxError.

### 2.6 `domain/options/var_calculator.py:65-66` — `cvar=nan` در بازار صعودی
`returns` همه مثبت → `np.mean([])=nan` → API مقدار `NaN` برمی‌گرداند و JS می‌شکند.

### 2.7 `brsapi/repositories/base.py:316-321` — `bulk_insert` تعداد دروغین
`ON CONFLICT DO NOTHING` صفر سطر می‌نویسد ولی `len(records)` برمی‌گرداند → داشبورد «سینک موفق» دروغین.

### 2.8 `brsapi/services/sync_service.py:255` — dedup هرگز چک نمی‌شود
`if dedup_seconds>0 and not params:` ولی تمام سینک‌های نمادی `params={"l18":...}` دارند → شرط false → هر درخواست API را می‌کوبد و لیمیتر 500/5دقیقه منفجر می‌شود.

---

## ۳) متوسط — پنهان (UX/امنیت)

### 3.1 `frontend/src/hooks/useMarketData.ts:199-213` — fallback ساکت به mock
`retry:1` + `extractArray` → `[]` → همه هوک‌ها بی‌سروصدا `TICKER_ITEMS/INDICES/NEWS` mock را نشان می‌دهند — کاربر فکر می‌کند دیتا زنده است.

### 3.2 `frontend/src/lib/api.ts:144-157` — `AbortError` هندل نشده
`fetchWithTimeout` تایم‌اوت را `DOMException: aborted` پرتاب می‌کند ولی ترجمه به «تایم‌اوت 60ثانیه» نمی‌شود.

### 3.3 `frontend/src/lib/api.ts:172-180` — طوفان 401
چند درخواست موازی 401 هرکدام `_handle401` → چند `fetch(/auth/logout)` + چند `location.href`.

### 3.4 `frontend/src/lib/api.ts:325-374` — `extractArray` همه خطاها را قورت می‌دهد
`{success:false,error:"DB down"}` → `[]` → UI «0 آیتم» بدون خطا.

### 3.5 `frontend/next.config.ts:17-18` — fallback به `NEXT_PUBLIC_API_URL` در سرور
در پروداکشن `API_URL=http://api:8000` اگر ست نباشد، سرور خودش را fetch می‌کند → لوپ/500.

### 3.6 `domain/options/tree_pricing.py:61-62` — عبارات مرده
```python
r - q - 0.5*sigma**2
sigma**2 * dt
```
بدون انتساب — قیمت درخت 5-10% خطا.

### 3.7 `brsapi/services/sync_service.py:360-376` — race سینک همزمان
دو ورکر همزمان `SELECT` می‌بینند رکورد نیست → هر دو `INSERT` → یکی `DO NOTHING` → آپدیت گم می‌شود. باید `ON CONFLICT DO UPDATE`.

---

## ۴) کم — کیفیت/پرفورمنس

- `frontend/src/components/layout/TickerBar.tsx:94` `Date.now()` داخل رندر (impure) — با گارد `mounted` پوشانده شده ولی باید به `useInterval` برود.
- `<img>` به‌جای `next/image` در `crypto/*`, `crypto-market`, `crypto-exchange` → LCP کند.
- `key={i}` ایندکسی در `options/page.tsx:337,360,491`, `TickerBar:104` → با سورت/فیلتر، رندر اشتباه.
- `admin/page.tsx:8` `CardAction` ایمپورت بلااستفاده.
- `funds/page.tsx:175` `navSymbols.join(",")` در `queryKey` تا 2k کاراکتر، هر فیلتر refetch طوفانی.

---

## ۵) لینت — خلاصه
- فرانت: `npm run lint` → `11 error / 129 warning` (140 مشکل). خطاهای اصلی همین‌های بالا.
- بک‌اند: `ruff` → `F821` فقط همین `_stage_time` بحرانی + بقیه `I001` مرتب‌سازی ایمپورت.

---

## ۶) اولویت فیکس پیشنهادی
1. `quant_signal_orchestrator.py` → `time.monotonic()` (5 دقیقه)
2. `feature_engine.py` + `margin_engine.py` → فرمول float و مارجین (مالی)
3. `core/indicators.py` + `pricing/var` → گارد صفر/NaN
4. `useMarketData` + `api.ts extractArray` → نمایش خطا به‌جای mock ساکت
5. `next.config.ts` → حذف fallback `NEXT_PUBLIC_API_URL`
6. `backtest/page.tsx` + `options/page.tsx` → انتقال ست‌استیت به effect + toast
