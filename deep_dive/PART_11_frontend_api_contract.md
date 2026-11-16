# قسمت ۱۱ — فرانتاند و قرارداد API

| | |
|---|---|
| **مبنای اندازهگیری** | `73a6c52d` — همان مبنای قسمتهای ۰۵ تا ۱۰ (هفتمین قسمت متوالی بدون جابهجایی در لحظهٔ اندازهگیری). **پس از اتمام اندازهگیری و حین اعتبارسنجی نهایی، HEAD توسط فرایند همزمان به `e8c83049` و سپس `105002d7` رسید**؛ بررسی `git diff 73a6c52d..105002d7` نشان میدهد **هیچیک از فایلهای قرارداد مربوط به قسمت ۱۱ تغییر نکردهاند**، پس تمام شواهد `UIF-*` معتبراند (بند ۷). |
| **وضعیت worktree** | **۱۲۴ فایل Dirty** در لحظهٔ اندازهگیری (پس از کامیتهای همزمان به **۲۲ فایل untracked** کاهش یافت؛ جزئیات بند ۷). برخلاف قسمت ۱۰، این بار تغییرات **واقعی کد فرانتاند** توسط فرایند همزمان وجود دارد: `frontend/src/app/alerts/page.tsx` اصلاحشده و پوشهٔ untracked `frontend/src/components/alerts/` (شامل `MonitorWorkspace.tsx` با ۵۰۶ خط) اضافه شده است. **هیچکدام از فایلهای قرارداد** (`api.ts`, `api-envelope.ts`, `next.config.ts`, `Dockerfile.frontend`, composeها) جزو اصلاحشدهها نیستند، پس شواهد `UIF-*` معتبراند. اندازهگیریها **روی دیسک** انجام شد، نه `git show HEAD`. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست، compose، مهاجرت یا سندی تغییر نکرد.** |
| **یادداشت روش** | جستجوها مسیرمحدود و با مستثنا کردن `.freebuff/worktrees/`, `node_modules`, `.next`, `.git`, `__pycache__`, `venv`, `.turbo`, `.pytest_cache` انجام شدند. **هیچ تستی اجرا نشد، سرور بالا نیامد، درخواستی ارسال نشد** — تمام نتایج ایستااند. |
| **پیشوند یافتهها** | `UIF-*` (User Interface / Frontend) — چون سه namespace تکراری `FE-*` در مخزن وجود دارد (بند ۶‑ج). |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| درخت / فایل | تعداد | خط | یادداشت |
|---|---:|---:|---|
| `frontend/` | **۵۸۰ فایل** | **۱۴۵٬۸۶۵** | شامل lockfile، اسناد و پیکربندی |
| `frontend/src/` | **۵۲۴** | **۱۳۰٬۵۶۷** | — |
| `frontend/src/app/` | **۲۲۱** | **۶۴٬۹۴۳** | ۱۵۳ فایل `page.tsx`، **۱۵۳ مسیر متمایز** |
| `frontend/src/components/` | **۱۴۵** | **۲۴٬۲۰۲** | — |
| `frontend/src/lib/` | **۴۳** | **۱۳٬۵۰۷** | سه کلاینت API موازی در همین پوشه |
| `frontend/src/hooks/` | **۲۰** | **۳٬۶۰۵** | — |
| `frontend/src/types/` | **۵** | **۹۲۳** | در برابر ۳۳۳ تعریف نوع داخل صفحات |
| `frontend/src/__tests__/` | **۸۰** | **۱۲٬۳۸۴** | پوشش تستی قابلتوجه |
| `.ts` + `.tsx` در `src` | **۵۱۱** | **۱۱۷٬۶۶۷** | ۴۱۰ فایل `.tsx` |
| `page.tsx` | **۱۵۳** | — | **۲۴ صفحهٔ `PagePlaceholder`** (۱۵٫۷٪) |

فایلهای کلیدی (خط): `api-envelope.ts` ۲۰۷ · `api.ts` ۳۹۳ · `api-errors.ts` ۱۲۷ · `csrf.ts` ۴۱ · `goldApi.ts` ۱٬۳۶۸ · `options-api.ts` ۱۵۸ · `wsTicket.ts` ۳۰ · `market-mock.ts` ۷۹۳ · `useMarketData.ts` ۱٬۰۳۶ · `useApiMonitor.ts` ۶۸ · `useWebSocket.ts` ۳۱۰ · `providers.tsx` ۸۹ · `next.config.ts` ۵۷ · `Dockerfile.frontend` ۴۵ · `frontend/.env` ۱۵ · `schemas/common/responses.py` ۴۵ · `deploy/nginx/nginx.conf` ۹۰.

شمارش مصرف: **۱۳۷ فایل** `@/lib/api` را وارد میکنند · ۶ فایل `api-envelope` · ۲۰ فراخوانی `fetch(` در ۹ فایل · ۹۳_use localStorage_ در ۲۱ فایل · **صفر** `as any` · ۳۳۳ تعریف `interface`/`type` داخل ۹۷ صفحه.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — لایهٔ پروکسی (دو لایهٔ رقیب)

```
مرورگر
  └─ GET /api/v1/market/...  (api.ts:5 API_BASE_URL = NEXT_PUBLIC_API_URL || '/api/v1')
       ├─ production: nginx.conf:44  location /api/ → backend_upstream (api:8000)
       │                                └─ api.py:1282 include_router(prefix=settings.api_prefix)
       └─ dev (without nginx): Next rewrite next.config.ts:36-38
                                source /api/v1/:path* → ${API_URL}${apiPrefix}/:path*
                                API_URL = process.env.API_URL || (prod ? http://api:8000 : 127.0.0.1:8000)
  └─ GET /api/v1/currency/...  → next.config.ts:32-34 → http://currency:8002/api/v1/currency/...
                                  ↑ سرویس «currency» در docker-compose.production.yml وجود ندارد
```

### ۲‑ب — لایهٔ قرارداد (پاکت)

```
api.ts:246  fetchWithTimeout(`${API_BASE_URL}${endpoint}`)
  └─ api.ts:195  withCsrf(headers, method)
  └─ api.ts:197  credentials: "include"
  └─ api.ts:250-255  silent refresh یکبار، سپس retry
  └─ api.ts:258-263  Handle 401 / ApiError
  └─ api.ts:270  assertSuccessEnvelope(payload, endpoint)   ← HTTP 200 + success:false خطا میشود
       └─ api-envelope.ts:135  بررسی پاکت
            ├─ getDataAsOf → ۱۶ محل مصرف تولیدی ( heatmap + useMarketData )
            ├─ isDataAsOfFresh → ۴ محل مصرف تولیدی
            ├─ readEnvelopeMeta → **صفر مصرف تولیدی** (فقط ۳ محل در تست)
            └─ isCacheHit → **صفر مصرف تولیدی** (فقط تست)
```

### ۲‑ج — لایهٔ دادهها

```
useMarketData.ts (۱٬۰۳۶ خط، ~۲۰ هوک)
  ├─ apiGet + extractArray  →  data
  ├─ getDataAsOf + isDataAsOfFresh  →  isFresh / isStale
  └─ LiveDataBanner  ← ۲۰ فایل مصرفکننده
market-mock.ts (۷۹۳ خط)
  ├─ type-only imports  →  TickerItem, QuoteItem, ... (سالم)
  ├─ getMarketSession()  →  useMarketData.ts:21 (زنده، محاسباتی)
  ├─ MARKET_SESSION      →  **صفر مصرف** (ثابت module-load)
  └─ SEARCH_SYMBOLS      →  TopNavbar.tsx:26,155,158  ← جستجوی سراسری با ۱۴ نماد ثابت
```

---

## ۳ — یافتهها

**توزیع شدت:** ۲ بحرانی · ۶ بالا · ۶ متوسط · ۲ کم = **۱۶ یافته**.

| شناسه | شدت | خلاصه |
|---|---|---|
| `UIF-01` | 🔴 بحرانی | متغیر محیطی API در production باید در **زمان بیلد** تزریق شود Compose آن را در zaman اجرا میدهد |
| `UIF-02` | 🔴 بحرانی | جستجوی سراسری نوار بالا از ۱۴ نماد جعلی `market-mock` میخواند |
| `UIF-03` | 🟠 بالا | بکاند `cache_hit` میفرستد، هیچ صفحهای آن را نمیخواند |
| `UIF-04` | 🟠 بالا | `legal_disclaimer` در ۸ جای بکاند تنظیم میشود ولی فقط در آپشن نمایش مییابد |
| `UIF-05` | 🟠 بالا | ۲۴ صفحهٔ Placeholder، از جمله مسیرهای تحلیل بنیادی که بکاند کامل دارند |
| `UIF-06` | 🟠 بالا | ۳۳۳ نوع inline در ۹۷ صفحه در برابر ۵ فایل نوع مشترک |
| `UIF-07` | 🟠 بالا | سه کلاینت API موازی + ۲ فایل `fetch` خام که از قرارداد میگریزند |
| `UIF-08` | 🟠 بالا | `useApiMonitor` هوک مرده با آدرس `localhost` و مسیر اشتباه |
| `UIF-09` | 🟡 متوسط | ثابت `MARKET_SESSION` محاسبهشده در بارگذاری ماژول، بدون مصرف |
| `UIF-10` | 🟡 متوسط | ۱۵ مقدار `staleTime` متفاوت در مقابل آستانهٔ تازگی ۵ دقیقه |
| `UIF-11` | 🟡 متوسط | `extractArray` خطا را به `[]` بدل میکند؛ `safeExtractArray` بدون مصرف تولیدی |
| `UIF-12` | 🟡 متوسط | سه namespace تکراری `FE-*` و اسناد کهنهٔ قرارداد |
| `UIF-13` | 🟡 متوسط | رانش کد زندهٔ همزمان حین اندازهگیری |
| `UIF-14` | 🟡 متوسط | فایل `.env` محلی track نمیشود و وارد بیلد نمیشود — سه منبع حقیقت |
| `UIF-15` | 🟢 کم | انضباط ذخیرهٔ توکن و نبود `as any` (نقطهٔ قوت با ریسک جزئی) |
| `UIF-16` | 🟢 کم | مسیر WS ticket سرتاسر سالم است (نقطهٔ قوت + نکتهٔ نگهداری) |

### 🔴 `UIF-01` — جدایی زمان بیلد و زمان اجرا در متغیرهای `NEXT_PUBLIC_*`

**شواهد:**
```yaml
# docker-compose.production.yml:176-184
frontend:
  image: ghcr.io/.../frontend:${VERSION:-latest}
  environment:
    NEXT_PUBLIC_API_URL: http://nginx/api/v1
```
```typescript
// api.ts:5
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
```
```dockerfile
# Dockerfile.frontend:6-14
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build          ← تمام NEXT_PUBLIC_* اینجا inline میشود
```
```typescript
// next.config.ts:19,23
const apiUrl = process.env.API_URL || (process.env.NODE_ENV === "production" ? "http://api:8000" : "http://127.0.0.1:8000");
const currencyUrl = process.env.CURRENCY_API_URL || (process.env.NODE_ENV === "production" ? "http://currency:8002" : "http://127.0.0.1:8000");
```

**تحلیل:** Next.js متغیرهای `NEXT_PUBLIC_*` را هنگام `npm run build` در باندل مرورگر جایگذاری میکند. `Dockerfile.frontend` **هیچ `ARG`/`ENV`ای برای این متغیرها ندارد** (خطوط ۱–۴۵)، و اساساً `COPY frontend/ .` با `.dockerignore` ریشه همراه است که `.env` و `.env.*` را مستثنا میکند. بنابراین مقدار `http://nginx/api/v1` در Compose **نمیتواند به باندل برسد**؛ مرورگر مقدار پیشفرض `/api/v1` از `api.ts:5` را میگیرد. خوشبختانه این مقدار با هدف نهایی همخوانی دارد و nginx مسیر `/api/` را میپذیرد — یعنی **سیستم بهطور تصادفی کار میکند، نه بهعلت پیکربندی**.

دو لایهٔ پروکسی رقیب هم وجود دارد: `next.config.ts:36-38` مسیر `/api/v1/:path*` را به `http://api:8000` هدایت میکند که **nginx را دور میزند** (HEADers امنیتی `nginx.conf:29-36`، `/metrics`، `/healthz` و WebSocket upgrade را از دست میدهد). در production چون nginx جلوی frontend است، rewriteها عملاً deadاند؛ در dev که nginx نیست، rewriteها زندهاند و `API_URL` از `frontend/.env:7` (`http://127.0.0.1:8000`) میآید. رفتار دو محیط متفاوت است، بدون اینکه کد فرق کند.

علاوهبراین، production compose **سرویس `currency` ندارد** (سرویسها: `api`, `admin`, `worker`, `scheduler`, `redis`, `postgres`, `nginx`, `frontend`) در حالی که fallback production آن `http://currency:8002` است. سرویس `currency` فقط در `docker-compose.yml` توسعه وجود دارد.

**اثر:** impossibility of environment-specific frontend configuration; bypass ناخواستهٔ nginx؛ آدرس currency غیرقابل دسترس در استقرار production.

---

### 🔴 `UIF-02` — جستجوی سراسری با نمادهای ثابت جعلی

```typescript
// TopNavbar.tsx:26
import { SEARCH_SYMBOLS } from "@/lib/market-mock";
// :155-158
? SEARCH_SYMBOLS.filter(...)
: SEARCH_SYMBOLS.slice(0, 5);
```
```typescript
// market-mock.ts:778-793
export const SEARCH_SYMBOLS: SearchSymbol[] = [
  { symbol: "فولاد", name: "فولاد مبارکه", market: "بورس" },
  ... ۱۴ ورودی ثابت ...
];
```

در سمت بکاند دو endpoint واقعی وجود دارد:
```
apps/api/endpoints/symbols.py:93   @router.get("/search")   Search symbols by name or symbol code
apps/api/endpoints/watchlist.py:19 @router.get("/search")   Search symbols to add to watchlist
all_symbols.json                   ۶۸۱ خط فهرست نمادها
```

**تحلیل:** جستجوی نوار بالا — مسیر اصلی یافتن نماد — **هرگز به API نمیرود** و فقط ۱۴ نماد hardcoded را فیلتر میکند. نمادهای جدی مانند «سپا» یا نمادهای newly added هرگز قابل جستجو نیستند. الگوی تکراری سری: «دادهٔ ساختگی به کاربر میرسد» (`SIG-01`, `BT-02`, `MLD-02`) اینبار در لایهٔ ناوبری.

**اثر:** پوشش ناقص بازار + ناسازگاری با فهرست ۶۸۱ خطی بکاند.

---

### 🟠 `UIF-03` — `cache_hit` بدون مصرفکنندهٔ production

بکاند چهار بار صریحاً پرچم را میفرستد:
```python
apps/api/endpoints/market.py:306,355,784,830
return ApiResponse(..., data_as_of=cached_as_of, cache_hit=True)
```
قرارداد مرورگر هم آن را implement میکند:
```typescript
// api-envelope.ts:125  export function isCacheHit(response: unknown): boolean
```
ولی **تمام فراخوانیهای `isCacheHit(` فقط در `apiEnvelope.test.ts`اند** (خطوط ۵۷، ۱۸۶). `readEnvelopeMeta` نیز فقط ۴ بار در تعریف و ۳ بار در تست ظاهر میشود. `getDataAsOf` برعکس ۱۶ مصرف تولیدی واقعی دارد و `isDataAsOfFresh` ۴ مصرف.

**اثر:** کاربر نمیتواند بین «دادهٔ تازه» و «دادهٔ کششده» تمایز قائل شود، اگرچه پروتکل آن را حمل میکند. همان الگوی «ساختهشده وصلنشده» که در `JOB-01` و `DOM-03` دیدیم.

---

### 🟠 `UIF-04` — سلب مسئولیت حقوقی تولید میشود ولی نمایش داده نمیشود

بکاند ۸ محل تنظیم `legal_disclaimer` دارد:
```
forecast.py:24 · forecast_engine.py:24 · options_frontend.py:84,101,189,224
quant_signal_orchestrator.py:95,135
```
فرانتاند فقط ۶ بار میخواند، **همه مربوط به آپشن**:
```
app/options/components/tabs/BacktestTab.tsx:191
app/options/components/tabs/ForecastTab.tsx:174
app/options/components/tabs/SignalsTab.tsx:210
lib/options-api.ts:27,63,102
```

**اثر:** پیشبینیها و سیگنالهای کمی (که مسئولیت حقوقی بیشتری دارند) متن هشدار را دریافت میکنند ولی هرگز به کاربر نمیرسانند. خطر انطباقی، نه فقط زیبایی.

---

### 🟠 `UIF-05` — ۲۴ صفحهٔ Placeholder در برابر بکاند کامل

از ۱۵۳ مسیر، ۲۴ صفحه تنها `PagePlaceholder` رندر میکنند (۱۵٫۷٪):
```
data-transfer · plugins · plugins/rahavard · widgets · signals/register
fundamental/{balance-sheet,capital-increase,cashflow,dps,eps,income,production,ratios}
markets/{futures,futures/salaf,sales,tabaei}
markets/stocks/{bonds,closing,dividends,maskan,rights,suspended,tal}
```
نمونه:
```tsx
// fundamental/balance-sheet/page.tsx (تمام ۱۲ خط)
<PagePlaceholder title="ترازنامه" description="تحلیل ترازنامه شرکتهای بورسی" />
```
در حالی که بکاند آماده است:
```
fundamental.py:16  /ratios/{symbol}   :24 /dcf/{symbol}   :32 /score/{symbol}
codal_professional.py  — ۲۹ endpoint حرفهای ISA/IFRS (تأییدشده در قسمت ۱۰)
```
یعنی **شکاف در رابط کاربری است، نه در سرویس**. قسمت ۱۰ ثابت کرد ۳۰ ماژول کدال واقعاً وصلاند؛ بیشتر مسیرهایIER در منو هستند ولی پیادهسازی نشدهاند.

---

### 🟠 `UIF-06` — تکثر انواع پاسخ در سطح صفحه

| شاخص | مقدار |
|---|---:|
| فایلهای `frontend/src/types/` | ۵ (۹۲۳ خط) |
| صفحات دارای `interface`/`type` inline | **۹۷ از ۱۵۳** |
| تعداد تعریفات inline | **۳۳۳** |

هیچ کلاینت OpenAPI تولیدشده وجود ندارد، اگرچه بکاند Pydantic و `apps/api/openapi_security.py` دارد. هر صفحه شکل پاسخ را دوباره مینویسد؛ تغییر در `schemas/common/responses.py` (۴۵ خط) بهطور خودکار به ۹۷ صفحه سرایت نمیکند. `as any` صفر است،_postype discipline خوب است ولی تکثر نوع مشکل را حل نمیکند.

---

### 🟠 `UIF-07` — سه کلاینت موازی و مسیرهای گریز از قرارداد

| فایل | خط | الگوی base URL |
|---|---:|---|
| `lib/api.ts` | ۳۹۳ | `NEXT_PUBLIC_API_URL \|\| '/api/v1'` |
| `lib/goldApi.ts` | ۱٬۳۶۸ | `process.env.NEXT_PUBLIC_API_URL \|\| "/api/v1"` در خط ۴۱۴ (مستقل) |
| `lib/options-api.ts` | ۱۵۸ | بدون استخراج base جداگانه |
| `lib/wsTicket.ts` | ۳۰ | از `apiPost` مرکزی استفاده میکند (سالم) |

فراخوانی خام `fetch(` در ۹ فایل: ۳ بار در `api.ts` (داخلی)، ۴ بار `auth-context.tsx`، ۵ بار `app/backtest/compose/page.tsx`، ۱ بار `useApiMonitor.ts`، ۲ بار `app/data-import/page.tsx`، ۲ بار `app/decision-engine/page.tsx` و غیره.

**دو فایلی که `@/lib/api` را وارد نمیکنند و nevertheless `fetch` میزنند:**
```
frontend/src/app/backtest/compose/page.tsx   5 فراخوانی
frontend/src/hooks/useApiMonitor.ts          1 فراخوانی
```
این مسیرها `assertSuccessEnvelope`, `withCsrf`, timeout, silent refresh و تبدیل `success:false` به خطا را **از دست میدهند**. `goldApi.ts` از `apiGet` مرکزی میخواند ولی base URL خودش را جداگانه میسازد — دو منبع حقیقت برای یک آدرس.

---

### 🟠 `UIF-08` — هوک مانیتورینگ مرده با آدرس اشتباه

```typescript
// useApiMonitor.ts:10
export function useApiMonitor(baseUrl: string = "http://localhost:8000") {
// :26
const response = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(5000) });
// :62  setInterval(checkBackend, 30000)
```

۱۶ رخداد نام `useApiMonitor` در کل `frontend/src` وجود دارد: **همه در خود فایل و تست آن** (`useApiMonitor.test.ts`). هیچ صفحهای آن را mount نمیکند. علاوهبراین آدرس پیشفرض `localhost:8000` در مرورگر به ماشین کاربر refer میشود، و مسیر `/health` دقیقاً در `apps/api/app.py` تعریف نشده (nginx `/healthz` را به backend هدایت میکند). اگر روزی mount شود، در production هم CORS و هم 404 میدهد.

---

### 🟡 `UIF-09` — ثابتی که هرگز خوانده نمیشود

```typescript
// market-mock.ts:319
export const MARKET_SESSION = getMarketSession();
```
جستجو: **۱ رخداد** — همان تعریف. `getIranianHoliday` (خط ۲۳۹) فقط داخل `market-mock.ts` استفاده میشود (خطوط ۲۶۸، ۳۰۷). در مقابل `getMarketSession()` بهصورت تابع توسط `useMarketData.ts:21` فراخوانی میشود و زنده است. الگوی آشنا: «نسخهٔ درست وصل است، نسخهٔ ثابت مرده است» — خطر آن است که کد آینده به ثابت module-load مراجعه کند و وضعیت بازار تا رفرش صفحه قدیمی بماند.

---

### 🟡 `UIF-10` — پانزده استراتژی تازگی در یک فایل

`useMarketData.ts` دارای ۱۵ مقدار `staleTime` است:
```
10_000 · 60_000 (×5) · 90_000 (×4) · 120_000 (×3) · 300_000 (×2)
```
در حالی که `api-envelope.ts:21` میگوید:
```typescript
export const DEFAULT_FRESHNESS_MS = 5 * 60 * 1000;  // ۳۰۰٬۰۰۰ میلیثانیه
```
دو هوک با `staleTime: 300_000` دقیقاً در آستانهٔ تازگی قرار دارند: لحظهای که React Query data را تازه میداند، `isDataAsOfFresh` آن را کهنه اعلام میکند. نتیجه:/wp رفتار ناپایدار بنر («تازه»/«کهنه») بسته به اینکه کدام ساعت خوانده شود.

---

### 🟡 `UIF-11` — خاموش کردن خطا توسط `extractArray`

```typescript
// api.ts:339-361
export function extractArray<T>(response: unknown): T[] {
  if (Array.isArray(response)) return response as T[];
  ... // جستجو در data/items/results/list/records/content/docs
  return [];                    ← هر شکل ناشناخته = آرایهٔ خالی
}
// :385-392
export function safeExtractArray(...) {
  if (obj.success === false || obj.error || obj.detail) console.warn(...);
  return extractArray<T>(response);   ← باز هم []
}
```

`api.ts:270` با `assertSuccessEnvelope` از مسیر `apiGet` محافظت میکند (نقطهٔ قوت واقعی). ولی `safeExtractArray` **هیچ مصرفکنندهٔ productionای ندارد** (فقط تست) و `extractArray` توسط `useMarketData` و صفحات دیگر گسترده استفاده میشود. هر پاسخ ساختارناشناخته به «صفحهٔ خالی» تبدیل میشود، نه «خطا» — همان تمایزی که `LiveDataBanner` için طراحی شده است.

---

### 🟡 `UIF-12` — تکثر namespace شناسههای حسابرسی فرانتاند

سهnamespaceمستقل و متداخل:
```
FE-01 … FE-14     در frontend/src و docs/frontend-audit-1404-06.md (۱۰۴ خط)
FE-###            در docs/audits/ISSUE_CATALOG_1000.md (۱٬۳۸۶ خط، ۲۸۵ رخداد)
C1…C5، F2/F4، DEP-02  در اسناد مختلف
```
نتیجه: شناسهٔ `FE-04` هم به یک endpoint آپشن، هم به یک آیتم کاتالوگ هزارگانه refer میکند. بههمین دلیل این قسمت از پیشوند `UIF-*` استفاده میکند (جستجو: **صفر** تداخل). اسناد `docs/FRONTEND_BACKEND_REPORT.md` (۲۳۶ خط) و `frontend-audit-1404-06.md` وضعیت pre-fix را توصیف میکنند و با کد زنده همخوانی کامل ندارند — چهارمین مورد «سند کهنه» پس از `DOM-16`.

---

### 🟡 `UIF-13` — رانش کد همزمان حین اندازهگیری

```
 M frontend/src/app/alerts/page.tsx
?? frontend/src/components/alerts/      (شامل MonitorWorkspace.tsx, ۵۰۶ خط)
```
`MonitorWorkspace.tsx` عجولانه به نظر سالم است: ۱ بار `@/lib/api` را وارد میکند، **صفر** `fetch(` خام، و `describeApiError` را بهکار میگیرد. ولی چون untracked است، نمیتوان آن را با `HEAD` مقایسه کرد. تمام اعداد این گزارش **روی دیسک** اندازهگیری شدند. فایلهای قرارداد (`api.ts`, `api-envelope.ts`, `next.config.ts`, `Dockerfile.frontend`, هر دو compose) **تغییرنشده باقیاند**، بنابراین `UIF-01` تا `UIF-12` معتبراند.

---

### 🟡 `UIF-14` — سه منبع حقیقت برای آدرس API

| منبع | مقدار | وضعیت |
|---|---|---|
| `frontend/.env:7,11,15` | `API_URL=http://127.0.0.1:8000`، `NEXT_PUBLIC_API_URL=/api/v1`، `CURRENCY_API_URL=http://127.0.0.1:8002` | **untracked** (NOT in git) و توسط `.dockerignore` مستثنا |
| `docker-compose.yml:186-187` | `NEXT_PUBLIC_API_URL=http://api:8000`، `CURRENCY_API_URL=http://currency:8002` | dev |
| `docker-compose.production.yml:180` | `NEXT_PUBLIC_API_URL=http://nginx/api/v1` | محلی (به `UIF-01` مراجعه شود) |

علاوهبراین `docs/FRONTEND_BACKEND_REPORT.md` و کامنت `production compose:181-182` به `frontend/.env.sentry.example` ارجاع میدهند، ولی `Dockerfile.frontend` هیچ build arg برای متغیرهای Sentry مرورگر ندارد —فعالسازی browser Sentry در production نمیتواند فعال شود مگر اینکه image متفاوتی scaffold شود.

---

### 🟢 `UIF-15` — انضباط توکن (نقطهٔ قوت) با ریسک جزئی

```typescript
// api.ts:15
// access token + user are kept in module memory only — never localStorage,
```
```typescript
// auth-context.test.tsx:125,156
it("sets user/tokens, never writes them to localStorage, ...", ...);
expect(localStorage.getItem("auth")).toBeNull();
```
جلوگیری از XSS پایدار واقعی است. ولی ۹۳_use localStorage_ در ۲۱ فAIL وجود دارد بدون namespace یا versioning — کلیدهای مربوط به UI/Cache میتوانند با استقرارهای جدید ناسازگار شوند. صفر `as any` در ۵۱۱ فایل TS/TSX نکتهٔ مثبت دیگری است.

---

### 🟢 `UIF-16` — مسیر WS ticket سرتاسر سالم (نقطهٔ قوت)

```
wsTicket.ts:26-30  fetchWsTicket() → apiPost("/auth/ws-ticket")
  → auth.py:407   @router.post("/ws-ticket")  (rate-limited :426)
  → tokens.py:270 create_ws_ticket()  · TTL 60s · hashed key
  → tokens.py:296 consume_ws_ticket()  via cache.pop (GETDEL) — single use
مصرفکنندگان: useWebSocket.ts:181-189 · usePrecomputeStatus.ts:382-397 · goldApi.ts:478-486
```
همهٔ مصرفکنندگان `null` را بهعنوان «نمیتوان connect کرد» treating میکنند، نه «بدون احراز هویتconnect شو». backend قدیمی query-string token را صریحاً رد میکند (`websocket.py:65-72`, `FE-06`). تنها نکتهٔ نگهداری: `WS_TICKET_TTL_SECONDS = 60` در TypeScript بهصورت literal تکرار شده (`wsTicket.ts:14`).

---

## ۴ — حدسهای ردشده

| حدس | نتیجه | شاهد |
|---|---|---|
| «تمام فرانتاند از کلاینت مرکزیuse میکند» | **رد** — ۱۳۷ فایل وارد میکنند ولی ۲ فایل `fetch` خام میزنند | `backtest/compose/page.tsx`, `useApiMonitor.ts` |
| «پاکت خطا به `[]` تبدیل میشود چون بررسی نمیشود» | **رد** — `assertSuccessEnvelope` در `api.ts:270` صریحاً فراخوانی میشود | بند ۲‑ب |
| «توکنها در localStorageاند» | **رد** — فقط memory، و تست صریحاً `null` را assert میکند | `api.ts:15`, `auth-context.test.tsx:156` |
| «هیچ تست قراردادی وجود ندارد» | **رد** — ۸۰ فایل تست / ۱۲٬۳۸۴ خط؛ `apiEnvelope.test.ts` با ۷ assert تازگی | بند ۱ |
| «هیچ بکاندی برای تحلیل بنیادی وجود ندارد» | **رد** — `fundamental.py` ۳ endpoint + `codal_professional.py` ۲۹ endpoint | `UIF-05` |
| «جستجو از فهرست زنده بکاندuse میکند» | **رد** — ۱۴ نماد ثابت از `market-mock.ts` | `UIF-02` |
| «سرویس currency در production مستقر است» | **رد** — فقط در `docker-compose.yml` توسعه وجود دارد | `UIF-01` |
| «`useApiMonitor` در داشبورد نشان داده میشود» | **رد** — فقط خود فایل + تست آن | `UIF-08` |

---

## ۵ — نقاط قوت تأییدشده

1. **مرکزیت پاکت:** `assertSuccessEnvelope` در تک نقطهٔ `api.ts:270`، با تبدیل HTTP 200 + `success:false` به خطا (خطوط ۲۶۶–۲۶۹).
2. **مدیریت تازگی:** `api-envelope.ts` مستقل از transport است، ۸ helper صادر میکند، `FUTURE_SKEW_MS = 2min` و timestamp آینده را رد میکند؛ ۲۰ فایل `LiveDataBanner` رندر میکنند.
3. **احراز هویت:** silent refresh تکبار با جلوگیری از race (`api.ts:233-239,250`)، حفظ هویت `AbortError` (خطوط ۲۰۱–۲۱۱)، CSRF در ۵ فایل.
4. **WS**: ticket تکمصرفه با hash در Redis — جایگزینی کامل توکن طولانیمدت در query string.
5. **عدم جایگزینی مخفی mock:** `useMarketData.ts:84` صریحاً مینویسد صفحات نباید mock راRpcAsAs data نشان دهند؛ imports از `market-mock` فقط type و `getMarketSession`اند. **این نقطه، حدس «جایگزینی mock در فرانتاند» را رد میکند** — برخلاف `MLD-02` در بکاند.
6. **پوشش تستی:** ۸۰ فایل / ۱۲٬۳۸۴ خط، شامل تستهای abort/timeout، envelope و monitor.

---

## ۶ — خوشههای ریسک تازه

| خوشه | یافتهها | شدت | اثر مرکب |
|---|---|---|---|
| **AI — قرارداد بیلد زمان / اجرا زمان** | `UIF-01`, `UIF-14` | 🔴 بحرانی | پیکربندی production ناکارآمد، دور زدن nginx، دو لایهٔ پروکسی، سرویس currency غایب |
| **AJ — دادهٔ ساختگی در ناوبری** | `UIF-02`, `UIF-09` | 🔴 بحرانی | جستجوی سراسری ۱۴ نماد ثابت + ثابت module-load مرده |
| **AK — قرارداد ساختهشده وصلنشده** | `UIF-03`, `UIF-04`, `UIF-08`, `UIF-11` | 🟠 بالا | `cache_hit`، سلب مسئولیت حقوقی، مانیتورینگ و safe-extract همگی در production خوانده نمیشوند |
| **AL — تکثر سطحی** | `UIF-05`, `UIF-06`, `UIF-07`, `UIF-10`, `UIF-12`, `UIF-13` | 🟠 بالا | ۲۴ صفحه خالی، ۳۳۳ نوع تکراری، ۳ کلاینت، ۱۵ staleTime، ۳ namespace شناسه |

**پیوند با قسمتهای قبل:** `AI` مستقیم به `CFG-01` (محیط production) و `EX-13` (مستقرسازی جداگانه) وصل است؛ `AJ` ادامهٔ الگوی `SIG-01 → BT-02 → MLD-02` است؛ `AK` همان الگوی `JOB-01` و `DOM-03` است؛ `AL` گسترش `K` و `AH` است.

---

## ۷ — اعتبارسنجی و محدوده

- تمام اعداد با اسکن Python مسیرمحدود روی دیسک بازشماری شدند؛ `.freebuff/worktrees/` استثنا شد (پروتکل قسمت ۰۸).
- **آلودگی متن مخلوط یافت نشد**: CJK/Cyrillic در متن فارسی اسکن و پاکسازی شد.
- توزیع شدت از ردیفهای جدول بازشماری شد: ۲ + ۶ + ۶ + ۲ = ۱۶.
- **هیچ تست، سرور، دیتابیس یا Redis اجرا نشد**؛ تمام یافتهها ایستا و مبتنیبر کداند.
- `git diff --name-only -- deep_dive .workbuddy-ai/memory` = **۰** تغییر trackشده؛ تنها فایل Markdown جدید `PART_11_frontend_api_contract.md` ساخته شد.
- **رانش HEAD حین اعتبارسنجی نهایی:** هنگام اجرای آخرین بررسی، HEAD از `73a6c52d` به `e8c83049` (`fix(alerts): add missing alert_monitors endpoint file`) و سپس به `105002d7` (`refactor(db): R10 — add Jalali date tracking to transactions`) حرکت کرد و تعداد فایلهای Dirty از ۱۲۴ به ۲۲ رسید. دستور `git diff --name-only 73a6c52d..105002d7 -- <فایلهای قرارداد قسمت ۱۱>` **هیچ خروجیای نداد** — یعنی `api.ts`, `api-envelope.ts`, `api-errors.ts`, `csrf.ts`, `goldApi.ts`, `options-api.ts`, `wsTicket.ts`, `market-mock.ts`, `useMarketData.ts`, `useApiMonitor.ts`, `TopNavbar.tsx`, `next.config.ts`, `Dockerfile.frontend` و هر دو compose **دستنخورده باقیاند**. تنها کامیتها یک migration و یک endpoint هشدار را اضافه کردند. بنابراین تمام اعداد و یافتهها معتبراند، ولی مبنای زمانی اندازهگیری `73a6c52d` است.
