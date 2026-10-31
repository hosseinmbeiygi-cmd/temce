# مرحله ۰۵ — قرارداد پاکت API در فرانت‌اند (`success` / `data_as_of` / `cache_hit`)

**شاخه:** `integration/golddesk-fixes`
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)
**تاریخ:** 2026-10-28 — حدود ۱۳:۵۵ به وقت محلی (UTC+03:30)
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`
**دامنه:** لایهٔ مصرف قرارداد در `frontend/` — همان handoff صریح مرحله ۴
(`04_BACKEND_API_AGGREGATION_CACHE_run2.md` §۷، بند ۸ و جدول معیارها: «`extractArray` هنوز `success` را نادیده می‌گیرد»).

> این گزارش فقط بر پایهٔ کد فعلی، diff واقعی، اجرای تست‌ها و وضعیت Git نوشته شده است.
> خروجی خام تست‌ها در بخش ۶ آمده و هیچ تستی بدون اجرا موفق اعلام نشده است.

---

## ۱. مسئله‌ای که این مرحله می‌بندد

`schemas/common/responses.py:8-27` هر پاسخ را در `ApiResponse` می‌پیچد:
`success`, `data`, `error`, `message`, `data_as_of`, `cache_hit`.

سمت فرانت‌اند سه حالتِ متفاوت را یکی می‌دید:

| حالت واقعی | پاسخ بک‌اند | رفتار قبلی فرانت |
|---|---|---|
| داده هست | `success:true`, `data:[…]` | رندر درست |
| موفق و خالی (بازار بسته / نماد بدون معامله) | `success:true`, `data:[]`, `data_as_of` | «داده‌ای نیست» |
| منبع داده خطا داده | `success:false`, `error:{…}` (معمولاً HTTP 200) | **همان «داده‌ای نیست»** — و در `heatmap` با دادهٔ mock جایگزین می‌شد |

سه شاهد مشخص در کدِ قبل از این مرحله:

1. `frontend/src/lib/api.ts:356` — `safeExtractArray` فقط `console.warn` می‌کرد و باز هم `[]` برمی‌گرداند.
2. `frontend/src/hooks/useMarketData.ts:271-273` — `success:false` فقط لاگ می‌شد؛ کوئری «موفق با صفر ردیف» تلقی می‌شد.
3. `frontend/src/app/heatmap/page.tsx` (قبل) — `queryFn` تمام خطاها را `catch { return [] }` می‌کرد و صفحه وقتی API هیچ نمی‌داد `generateMockHeatmap()` را به‌جای دادهٔ واقعی رندر می‌کرد؛ یعنی «خطای منبع» شبیه «نقشهٔ بازار» دیده می‌شد.

`data_as_of` و `cache_hit` هم در کل `src/` (به‌جز چند فرم پیش‌بینی) مصرف نمی‌شدند:
`grep -rn "data_as_of\|cache_hit" frontend/src --include=*.ts(x)` قبل از تغییر فقط ۵ نتیجه در `ForecastTab`/`ForecastPanel`/`predictions` داشت و هیچ‌کدام به پاکت `market/*` وصل نبود.

---

## ۲. آنچه ساخته/تغییر شد

### ۲-۱. ماژول جدید `frontend/src/lib/api-envelope.ts` (۲۱۵ خط)

تنها جای خواندن پاکت. بدون هیچ import — تا هم `api.ts` (لایهٔ انتقال) و هم هوک‌ها/صفحات بتوانند بدون کشیدن transport از آن استفاده کنند.

| نماد | خط | کار |
|---|---|---|
| `DEFAULT_FRESHNESS_MS` | ۲۱ | آستانهٔ تازگی ۵ دقیقه (هم‌راستا با `isDataFresh` داشبورد) |
| `ApiEnvelopeMeta` | ۲۶ | `success/dataAsOf/cacheHit/errorMessage/errorCode/errorDetail` |
| `ApiEnvelopeError` | ۴۷ | خطای «پاکت ناموفق»؛ پیام عمومی، متن داخلی در `detail` (قاعدهٔ C3) |
| `readEnvelopeMeta` | ۸۹ | خواندن پاکت؛ پاسخ برهنه ⇒ `success:null` (نه `success:true`) |
| `getDataAsOf` / `isCacheHit` | ۱۲۰ / ۱۲۵ | دسترسی سریع به متادیتا |
| `assertSuccessEnvelope` | ۱۳۵ | `success:false` ⇒ `throw` (فقط همین حالت؛ آرایه/بدنهٔ برهنه دست‌نخورده) |
| `parseIsoInstant` | ۱۶۲ | ISO سخت‌گیرانه؛ `"12"` را رد می‌کند، naive را UTC می‌خواند |
| `isDataAsOfFresh` | ۱۹۸ | تازگی با رد کردن زمان آینده (۲ دقیقه اسکیو) |

### ۲-۲. `frontend/src/lib/api.ts` (+۹ خط)

```diff
+import { assertSuccessEnvelope } from './api-envelope';
…
-  return response.json() as Promise<T>;
+  const payload = (await response.json()) as T;
+  // HTTP 200 با `success:false` یعنی منبع داده خطا داده است؛ …
+  assertSuccessEnvelope(payload, endpoint);
+  return payload;
```

اثر: تمام ۷۶ فراخوانِ `apiGet/apiPost/...` در `src/` اکنون شکستِ پاکت را به‌صورت rejection می‌بینند؛ React Query حالت `isError` را روشن می‌کند و صفحه دیگر آن را «خالی» نمی‌خواند. مسیر خطای HTTP (غیر ۲xx) عوض نشده است.

### ۲-۳. `frontend/src/hooks/useMarketData.ts` (بازنویسی `useEnrichedHeatmap`)

```diff
-  queryFn: async (): Promise<HeatmapCell[]> => { … const arr = extractArray(…);
-    if (arr.length === 0 && res?.success === false) console.warn(…); return arr; }
+  queryFn: async (): Promise<HeatmapFeed> => {
+    const cells = extractArray<HeatmapCell>(res);
+    const dataAsOf = getDataAsOf(res);
+    const checkedAt = Date.now();
+    const isFresh = cells.length > 0 && (dataAsOf
+      ? isDataAsOfFresh(dataAsOf, { now: checkedAt })
+      : cells.every((cell) => isRowFresh(cell, checkedAt)));
+    return { cells, dataAsOf, isFresh };
+  }
```

- `data_as_of` پاکت مرجع تازگی است؛ فقط اگر پاکت آن را نداشت، `fetched_at` هر ردیف بررسی می‌شود (منطق گاردِ تاریخ آیندهٔ مرحله ۰ حفظ شد).
- `Date.now()` از بدنهٔ هوک به `queryFn` منتقل شد تا خطای `react-hooks/purity` که روی نسخهٔ قبلی همین تابع بود بسته شود (بازهٔ refetch ۳۰ ثانیه‌ای کهنگی را به‌روز می‌کند).

### ۲-۴. `frontend/src/components/dashboard/LiveDataBanner.tsx` (+۲۰ خط)

پروپ اختیاری `dataAsOf` اضافه شد:

```ts
// بدون `dataAsOf` هیچ ادعایی دربارهٔ تازگی نمی‌کنیم (ویجت‌های قدیمی دست‌نخورده).
const isStale =
  state.isLive && state.dataAsOf != null &&
  !isDataAsOfFresh(state.dataAsOf, { thresholdMs: DEFAULT_FRESHNESS_MS });
if (state.isLive && !isStale) return null;
```

سه حالت اکنون از هم جدا هستند: دادهٔ تازه (هیچ)، دادهٔ کهنه (هشدار با ساعت `data_as_of`)، خطای درخواست (بنر ارتباط). ده ویجت داشبورد که فقط `{isLive,isError,isLoading}` می‌فرستند رفتار قبلی خود را دارند.

### ۲-۵. `frontend/src/app/heatmap/page.tsx`

- `try/catch` دور هر دو کوئری حذف شد: خطا به React Query می‌رسد.
- `mockCells` فقط «placeholder پیش از اولین پاسخ» است؛ بعد از پاسخ موفق (حتی خالی) یا خطا، دادهٔ ساختگی رندر نمی‌شود:
  `const cells = heatmapFeed ? heatmapFeed.cells : heatmapError ? [] : mockCells;`
- `LiveDataBanner` با `dataAsOf={heatmapFeed?.dataAsOf}` بالای کارت نصب شد.

### ۲-۶. `frontend/src/lib/goldApi.ts` (+۱۱ خط)

`api.ts` اکنون قبل از `goldApi` پاکت را رد می‌کند؛ برای اینکه نگاشت C3 (`snapshot_unavailable`) از دست نرود، یک شاخه اضافه شد:

```ts
if (error instanceof ApiEnvelopeError) {
  console.warn(`[goldApi] ${label}: backend reported failure`, error.detail ?? error.message);
  return new GoldAPIError(`${label}: داده در دسترس نیست`, { code: error.code ?? code, … });
}
```

بدون این شاخه، تست موجود `GoldApiLayer.test.ts` («`success:false` ⇒ unavailable») می‌شکست — یعنی یک رگرسیون واقعی، نه تستِ ناکارآمد.

---

## ۳. تست‌های جدید

| فایل | تعداد | پوشش |
|---|---|---|
| `frontend/src/__tests__/apiEnvelope.test.ts` | ۱۶ | خواندن پاکت (ریشه/تودرتو/برهنه)، پرتاب `success:false` بدون لو دادن متن داخلی، `parseIsoInstant` (Z، `+03:30`، naive، نامعتبر)، `isDataAsOfFresh` (تازه/کهنه/آینده/غایب)، و مسیر واقعی `apiGet` با `fetch` استاب‌شده |
| `frontend/src/__tests__/LiveDataBanner.test.tsx` | ۶ | خاموشی هنگام لود، خاموشی برای دادهٔ تازه، خاموشی برای ویجت‌های بدون `dataAsOf`، هشدار کهنگی، بنر خطا، تفکیک «موفق و خالی» از «خطا» |

`useMarketData.test.tsx` هم به‌جای آرایهٔ خام، شکل جدید `{cells, dataAsOf}` را به کوئری استاب می‌دهد؛ **تمام assertions قبلی دست‌نخورده‌اند** (هیچ assertion حذف یا ضعیف نشد).

---

## ۴. فایل‌های بررسی‌شده

| فایل | وضعیت |
|---|---|
| `schemas/common/responses.py` | ✅ کامل (تعریف پاکت) |
| `frontend/src/lib/api.ts` | ✅ کامل |
| `frontend/src/lib/goldApi.ts` | ✅ کامل (الگوی موجودِ پاکت‌آگاه) |
| `frontend/src/hooks/useMarketData.ts` | ✅ کامل |
| `frontend/src/components/dashboard/LiveDataBanner.tsx` | ✅ کامل |
| `frontend/src/app/heatmap/page.tsx` | ✅ کامل |
| `frontend/src/components/ui/Card.tsx` | ✅ کامل (سبک بنر/کارت) |
| `frontend/src/__tests__/useMarketData.test.tsx` | ✅ کامل |
| `frontend/src/__tests__/GoldApiLayer.test.ts` | ✅ بخش پاکت و `installFetch` |
| `frontend/src/__tests__/setup.ts` | ✅ کامل |
| `frontend/vitest.config.ts` | ✅ کامل |
| سایر ۷۰ فراخوانِ `extractArray` در `src/` | ❌ بررسی/تغییر نشدند (بخش ۵) |
| `apps/api/endpoints/*` | ❌ در این مرحله بازخوانی نشد (مرحله ۴ پوشش داده؛ فقط قرارداد مصرف شد) |

---

## ۵. آنچه عمداً انجام نشد

1. **۷۰ مصرف‌کنندهٔ دیگر `extractArray`** (صفحات `markets/*`, `instruments`, `codal`, …) به `data_as_of` وصل نشدند. آن‌ها اکنون خطای پاکت را به‌درستی به React Query می‌دهند، ولی برچسب «کهنه» ندارند.
2. **مالکیت کش `cache_hit`**: فقط خوانده و در دسترس گذاشته شد؛ هیچ صفحه‌ای بر اساس آن «banner کش» نشان نمی‌دهد (طبق کامنت `responses.py:22-24` این کار بخش ۰۵ بود، اما بدون تعیین متن/آستانهٔ محصولی، نمایش آن حدس می‌شد).
3. **`data/page.tsx:255` و `FundForms.tsx:527`** که خودشان `success` را دستی چک می‌کنند، دست‌نخورده ماندند (اکنون شاخهٔ خطایشان عملاً غیرقابل‌وصول است، اما حذفشان تغییر بی‌ربط است).
4. **هیچ commit، stage، reset یا stash** انجام نشد.

---

## ۶. اجرای تست‌ها (خروجی واقعی)

| فرمان | نتیجه |
|---|---|
| `cd frontend && npx vitest run` | **۵۷ فایل / ۵۴۷ تست — همه pass، ۰ failed** — `Duration 64.08s` |
| `npx vitest run src/__tests__/useMarketData.test.tsx src/__tests__/LiveDataBanner.test.tsx src/__tests__/apiEnvelope.test.ts src/__tests__/GoldApiLayer.test.ts` | **۴۱ pass / ۰ failed** |
| `npx vitest run … + silent-refresh` (پس از افزودن تست‌ها) | **۵۷ pass / ۰ failed** |
| `npx tsc --noEmit` | **۲۱ خطای از پیش موجود** در ۴ فایل `Fund*` — **۰ خطا در فایل‌های این مرحله** |
| `npx eslint` روی ۷ فایل تغییر‌یافته | **۰ error**؛ ۱ warning از پیش موجود (`useCallback` بی‌استفاده در `heatmap/page.tsx`) |

اجرانشده‌ها: هیچ تست بک‌اندی در این مرحله لازم نبود و اجرا نشد؛ تست end-to-end مرورگر اجرا نشد (بخش ۷).

---

## ۷. مسدود / تأییدنشده

| مورد | دلیل |
|---|---|
| اجرای واقعی صفحه در مرورگر با بک‌اند زنده | PostgreSQL خاموش، Redis ناموجود، BrsApi در cooldown — طبق مراحل ۰ تا ۴. هیچ درخواست زنده‌ای ارسال نشد. |
| تأیید `data_as_of` واقعیِ `/market/enriched-heatmap` | همان محدودیت؛ فقط قرارداد و رفتار با fixture تأیید شد. |
| `next build` | به‌خاطر ۲۱ خطای تایپ از پیش موجود در `Fund*` شکست می‌خورد؛ به آن‌ها دست نزدم. |
| invalidate کش بین‌پروسه‌ای | خارج از دامنهٔ این مرحله (مرحله ۴ آن را BLOCKED ثبت کرد). |

---

## ۸. وضعیت Git

| مورد | مقدار |
|---|---|
| HEAD ابتدا/انتها | `90597e05…` → `90597e05…` (بدون commit) |
| staged | ۱۳۸ فایل، ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete — **دست‌نخورده** |
| فایل حذف‌شده | ۰ (`git status --porcelain | grep '^ D'` خالی) |
| تغییرات این مرحله | ۴ فایل ویرایش‌شده + ۱ فایل ویرایش‌شدهٔ تست + ۳ فایل جدید (همه unstaged/untracked) |

فایل‌های این مرحله:
```
 M frontend/src/lib/api.ts
 M frontend/src/lib/goldApi.ts
 M frontend/src/hooks/useMarketData.ts
 M frontend/src/components/dashboard/LiveDataBanner.tsx
 M frontend/src/app/heatmap/page.tsx
 M frontend/src/__tests__/useMarketData.test.tsx
?? frontend/src/lib/api-envelope.ts
?? frontend/src/__tests__/apiEnvelope.test.ts
?? frontend/src/__tests__/LiveDataBanner.test.tsx
```

---

## ۹. کارهای باقی‌مانده (به ترتیب)

1. وصل کردن `data_as_of` به بقیهٔ صفحات بازار (`markets/*`, `instruments`, `codal`, `data`) با همان `LiveDataBanner`.
2. تصمیم محصولی دربارهٔ نمایش `cache_hit` (متن بنر، آستانه) و پیاده‌سازی آن در یک کامپوننت مشترک.
3. حذف شاخه‌های مردهٔ `!res.success` در صفحه‌هایی که اکنون `apiRequest` خودش پرتاب می‌کند.
4. رفع ۲۱ خطای تایپ `Fund*` (پیش‌نیاز `next build`).
5. تأیید رفتاری با بک‌اند زنده وقتی PostgreSQL/Redis/BrsApi در دسترس باشند.
