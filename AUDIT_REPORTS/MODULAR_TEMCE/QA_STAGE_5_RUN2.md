# ممیزی مستقل تکمیل مرحله ۵ — فرانت‌اند، freshness، polling و WebSocket

**مسیر این گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN2.md`  
**گزارش مرحله (مرجع اجرا):** `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` (۲۶٬۱۳۱ بایت)  
**گزارش مرحلهٔ هم‌زمان دیگر:** `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_API_CONTRACT.md` (۱۴٬۶۸۶ بایت)  
**گزارش QA موجود:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5.md` (۱۱٬۸۶۷ بایت) — overwrite نشد  
**تاریخ/زمان ممیزی:** 2026-10-28 — 22:56 به وقت محلی (UTC+03:30)  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)

**نتیجهٔ نهایی: PARTIAL** — قرارداد envelope و مسیر heatmap و تست‌ها سبزند (۳۳/۳۳ مرتبط، ۵۴۸/۵۴۸ کل)، اما جداسازی کامل `hasData/isFresh/isLive/isStale`، hookهای مشتق‌شده، WebSocket بازار (auth/timestamp/stale/resubscribe) و پوشش freshness در سایر ویجت‌ها باقی مانده است. تأیید زنده هم BLOCKED است.

---

## ۱. گزارش‌ها و وجود فایل

| گزارش | مسیر | وضعیت |
|---|---|---|
| گزارش مرحله (موضوع این پرامپت) | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` | ✅ موجود |
| گزارش مرحلهٔ دیگر (API contract) | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_API_CONTRACT.md` | ✅ موجود؛ مرتبط ولی عنوان/دامنهٔ متفاوت |
| QA موجود | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5.md` | ✅ موجود؛ overwrite نشد |
| QA این اجرا | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN2.md` | ✅ همین فایل |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD ابتدا/انتها | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ `git diff --cached --stat` = ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete |
| فایل حذف‌شده توسط این ممیزی | هیچ (`git status | grep '^ D'` = 0) |
| عملیات ممنوع | هیچ: بدون reset --hard، clean، stash، checkout/restore مخرب، rebase، force push یا commit |
| تغییر این ممیزی | فقط `LiveDataBanner.clockLabel` + یک تست بنر + همین گزارش |
| تغییرات قبلی/هم‌زمان | `api-envelope.ts`, `api.ts`, `useMarketData.ts`, `heatmap/page.tsx`, `LiveDataBanner.tsx`, `goldApi.ts`, تست‌ها — حفظ شدند |

---

## ۳. فایل‌های بررسی‌شده و بررسی‌نشده

### کامل خوانده شد

| فایل | نکته |
|---|---|
| `frontend/src/lib/api-envelope.ts` | ۲۰۷ خط؛ envelope/freshness |
| `frontend/src/components/dashboard/LiveDataBanner.tsx` | کامل |
| `frontend/src/__tests__/useMarketData.test.tsx` | ۱۰ تست |
| `frontend/src/__tests__/apiEnvelope.test.ts` | ۱۶ تست |
| `frontend/src/__tests__/LiveDataBanner.test.tsx` | ۷ تست |
| `frontend/src/hooks/useWebSocket.ts` | ۲۳۰ خط؛ WS بازار |
| `frontend/src/hooks/useGoldWS.ts` | کامل؛ stale از `as_of` |
| `apps/api/endpoints/websocket.py` | پروتکل/auth `/ws/market` |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `frontend/src/hooks/useMarketData.ts` | ۱–۱۲۰، ۲۵۰–۷۰۰ + grep کامل `isLive`؛ کل ۸۴۳ خط خط‌به‌خط نه |
| `frontend/src/lib/api.ts` | `apiRequest`/`extractArray` (نه کل ۳۶۹ خط) |
| `frontend/src/app/heatmap/page.tsx` | ۱۶۰–۲۶۰ |
| `frontend/src/lib/goldApi.ts` | بخش WS/error (نه کل) |
| `frontend/src/app/markets/gold/page.tsx` | بخش live/WS badge |
| کامپوننت‌های dashboard | فقط نقاط `LiveDataBanner` (grep) |

### بررسی نشد

| مورد | دلیل |
|---|---|
| کل فرانت‌اند/همهٔ صفحات | خارج از دامنه/حجم؛ فقط نقاط مرتبط |
| BrsApi/TSETMC/Redis زنده و E2E مرورگر | ممنوع/بدون دسترسی |
| `npm run build` | اجرا نشد؛ `tsc` قرمز است (بخش ۶) |
| `node_modules`/باینری/تولیدی | وابستگی/تولیدی |

---

## ۴. جدول الزام‌های پرامپت

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| 1 | شناسایی ریشه/شاخه/HEAD/status/diff | `pwd`، `git rev-parse`، `git status --short --branch` | **PASS** | — |
| 2 | حفظ staged/untracked؛ عدم عملیات مخرب Git | HEAD ثابت؛ ۱۳۸ staged؛ ۰ حذف؛ بدون reset/clean/stash/commit | **PASS** | — |
| 3 | عدم درخواست زنده BrsApi/TSETMC | هیچ کلاینت زنده اجرا نشد | **PASS (compliance)** | E2E زنده **BLOCKED** |
| 4 | عدم DB destructive/secret | هیچ DB/secret استفاده نشد | **PASS** | — |
| 5 | گزارش‌های قدیمی سرنخ؛ تأیید مستقل | `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` یافت نشد؛ ۱۵/۱۵ sync-log؛ شاخه/HEAD؛ `useMarketData` staged | **PASS** | — |
| 6 | خواندن فایل‌های مرتبط + manifest | بخش ۳ | **PARTIAL** | کل `useMarketData.ts`/فرانت کامل خوانده نشد |
| 7 | fix کوچک/هدفمند | فقط `LiveDataBanner.clockLabel` + تست | **PASS** | — |
| 8 | گزارش در فایل، بدون overwrite | `05...` و `QA_STAGE_5_RUN2.md` | **PASS** | — |
| 9 | ساختار کامل گزارش | همین گزارش | **PASS** | — |
| 10 | انجام واقعی مأموریت | کد/تست/Git بررسی و اجرا شد | **PASS** | — |
| 11 | ردیابی JSON→hook→query key/cache→UI | heatmap/envelope/consumerها؛ ۱۰ تست | **PARTIAL** | همهٔ صفحات/مصرف‌کننده‌ها ردیابی نشدند |
| 12 | timestamp آینده/null/نامعتبر live نشود | `api-envelope.ts:162,198`؛ ۱۶ تست | **PARTIAL** | hookهای مشتق‌شده `rows.length>0`؛ banner بدون dataAsOf |
| 13 | `hasData`/`isFresh`/`isLive`/`isStale` جدا | `LiveDataResult` فقط `isLive` دارد (`useMarketData.ts:86-96`) | **FAIL/PARTIAL** | جداسازی کامل نشده |
| 14 | query key/staleTime/refetch/retry/error | hookها/صفحه heatmap؛ full tests | **PASS (offline)** | کش تکراری heatmap؛ hookهای بدون timestamp |
| 15 | WebSocket پیام/timestamp/subscription/reconnect/پیام قدیمی | `useWebSocket.ts:31-55,130,147`؛ `useGoldWS` خوب | **PARTIAL/FAIL** | توکن، as_of، stale، resubscribe |
| 16 | اجرای `useMarketData.test.tsx` و دسته‌بندی | ۱۰ تست، ۱۰ pass، ۰ skip | **PASS** | ادعای «۱۰/۱۵» اشتباه بود |
| 17 | معیار پذیرش: freshness/error/test | بخش ۹ | **PARTIAL** | رفع موارد FE-01..FE-06 |
| 18 | بدون commit | HEAD ثابت | **PASS** | — |

---

## ۵. اصلاحات: مسیر، diff، دلیل، تست

| # | مسیر/خط | diff/شاهد | دلیل | تست | مالکیت |
|---|---|---|---|---|---|
| F-1 | `frontend/src/lib/api-envelope.ts:89-209` | افزودن `readEnvelopeMeta`/`parseIsoInstant`/`isDataAsOfFresh`/`assertSuccessEnvelope` | جدا کردن success/empty/error و timestamp معتبر | `apiEnvelope.test.ts` ۱۶ pass | قبلی/هم‌زمان؛ تأیید شد |
| F-2 | `frontend/src/lib/api.ts:242-249` | parse + `assertSuccessEnvelope` | `success:false` به empty تبدیل نشود | ۴ تست envelope/transport | قبلی؛ تأیید شد |
| F-3 | `frontend/src/hooks/useMarketData.ts:287-317` | `HeatmapFeed` + `dataAsOf` + `isFresh` از `data_as_of`/`fetched_at` | استفاده از freshness envelope | ۱۰ تست hook | قبلی؛ تأیید شد |
| F-4 | `frontend/src/app/heatmap/page.tsx:181-238` | حذف `try/catch` پنهان‌کننده؛ mock فقط پیش از پاسخ؛ banner | خطا/empty پنهان نشود | full suite pass | قبلی؛ تأیید شد |
| F-5 | `LiveDataBanner.tsx:32-61` | `dataAsOf` + `isStale` + پیام stale | نمایش کهنگی | ۶ تست اولیه + ۱ تست جدید | قبلی؛ تأیید شد |
| F-6 | `LiveDataBanner.tsx:5,15-21` | `clockLabel` از `new Date(iso)` به `parseIsoInstant(iso)` | naive-UTC به‌عنوان UTC نمایش داده شود | `formats a naive backend timestamp as UTC…` | **این ممیزی** |
| F-7 | `apiEnvelope.test.ts` / `LiveDataBanner.test.tsx` | تست‌های future/null/malformed/timezone | pin کردن قرارداد | ۱۶ + ۷ pass | قبلی + این ممیزی |

**نکته:** تلاش اولیه برای propagate کردن `hm.isLive` به hookهای مشتق‌شده پس از مشاهدهٔ ناسازگاری معنایی banner (isLive=false به معنی «بخش خالی») برگردانده شد؛ به‌عنوان FE-02/FE-06 در کارهای باقی‌مانده ثبت شد.

---

## ۶. فرمان‌های تست و نتیجهٔ واقعی

> محیط: `C:/Users/Iran/Desktop/temce/frontend` — Node v24.16.0، vitest v4.1.9/jsdom. بدون backend زنده.

| فرمان | Passed | Failed | Skipped | Exit |
|---|---|---|---|---|
| `./node_modules/.bin/vitest run src/__tests__/useMarketData.test.tsx src/__tests__/apiEnvelope.test.ts src/__tests__/LiveDataBanner.test.tsx` | **33** | **0** | **0** | **0** |
| تفکیک `useMarketData.test.tsx` | **10** | 0 | 0 | — |
| تفکیک `apiEnvelope.test.ts` | **16** | 0 | 0 | — |
| تفکیک `LiveDataBanner.test.tsx` | **7** | 0 | 0 | — |
| **کل مجموعه:** `./node_modules/.bin/vitest run` | **548** (57 فایل) | **0** | **0** | **0** |
| `./node_modules/.bin/tsc --noEmit --pretty false` | — | **21 خطا** | — | **1** |

- ادعای «۱۰/۱۵ passing به‌دلیل environment» **بازتولید نشد**: فایل `useMarketData.test.tsx` فقط ۱۰ تست دارد و هر ۱۰ pass است؛ ۱۵ تستی وجود ندارد و هیچ skip/fail محیطی نبود.
- گزارش QA موجود «۵۴۷ تست» گفته بود؛ اجرای مستقل این ممیزی **۵۴۸ تست** (با تست جدید بنر) را نشان می‌دهد؛ ۰ failed.
- ۲۱ خطای `tsc` همه در کامپوننت‌های fund خارج از دامنه‌اند (`FundAnalysisModal`, `FundCompareModal`, `FundDetailDrawer`, `FundScorecardPanel`)؛ **۰ خطا در فایل‌های Phase 5**. این شکست typecheck پنهان نشده است.
- `npm run build`، E2E مرورگر، و تست‌های زندهٔ WS/BrsApi اجرا نشدند.

### تست‌های اجرانشده و علت

| تست/بررسی | علت |
|---|---|
| `npm run build` | `tsc` خارج از دامنه ۲۱ خطا دارد؛ build اجرا نشد |
| E2E مرورگر با backend/داده واقعی | نیازمند backend/BrsApi؛ ممنوع/در دسترس نبود |
| تست auth/resubscribe/stale/out-of-order برای `useMarketWebSocket` | زیرساخت WS mock/زنده فراهم نبود؛ تست موجود نیست |
| تست integration واقعی queryFn heatmap | تست‌ها `useQuery` را mock می‌کنند و queryFn را اجرا نمی‌کنند |

---

## ۷. جدول ایرادها

| # | شدت | عنوان | شاهد (path:line) | بازتولید | اثر | وضعیت |
|---|---|---|---|---|---|---|
| FE-01 | High | `isFresh` در queryFn ذخیره و با گذشت زمان کهنه نمی‌شود | `useMarketData.ts:303-317` | refetch را متوقف کنید و >۵ دقیقه صبر کنید؛ `isLive` true می‌ماند | داده کهنه live | باز |
| FE-02 | High | hookهای مشتق‌شده freshness را نادیده می‌گیرند | `useMarketData.ts:329,427,454,519,690` | feed با cells و بدون timestamp؛ `isLive=true` | null/نامعتبر live | باز |
| FE-03 | High | WebSocket بازار توکن handshake ندارد | `useWebSocket.ts:31-55`؛ `apps/api/endpoints/websocket.py:29-63` | auth فعال؛ اتصال 1008 | WS در production کار نمی‌کند | باز |
| FE-04 | High | timestamp سرور با `Date.now()` جایگزین و stale/age ندارد | `useWebSocket.ts:116-155,181` | قطع پیام‌ها؛ `connected` true و LIVE | قیمت کهنه live | باز |
| FE-05 | High | تغییر symbols دوباره subscribe نمی‌شود | `useWebSocket.ts:72,130,173` | symbols را پس از open تغییر دهید | نماد جدید قیمت نمی‌گیرد | باز |
| FE-06 | Medium | banner دلیل stale را در `isLive=false` حفظ نمی‌کند | `LiveDataBanner.tsx:32-39` | hook کهنه `isLive=false`؛ banner «خالی» می‌گوید | stale از empty قابل‌تشخیص نیست | باز |
| FE-07 | Medium | heatmap page freshness را بر اساس view/treemap جدا نمی‌کند | `heatmap/page.tsx:181-194,229-238` | heatmap خالی + treemap پر یا dataAsOf null | warning نادرست | باز |
| FE-08 | Medium | `apiGet` همهٔ `success:false` را throw می‌کند؛ پوشش همهٔ endpointها نیست | `api.ts:242-249` | endpoint غیرمارکت با success:false | خطای غیرمنتظره در صفحات دیگر | باز |
| FE-09 | Medium | کش تکراری heatmap با limitهای مختلف | `useMarketData.ts:290` vs `heatmap/page.tsx:181` | heatmap + dashboard | دو cache/درخواست ناسازگار | باز |
| FE-10 | Medium | سایر hookها `isLive=rows.length>0` و بدون data_as_of | `useMarketData.ts:349,384,507,565,589,619,638,722,756,797,819,842` | backend قدیمی | وجود داده=live | باز؛ handoff بخش ۰۴ |
| FE-11 | Low | `LiveDataResult` فاقد `hasData/isFresh/isStale` | `useMarketData.ts:86-96` | همهٔ مصرف‌کننده‌ها | تفکیک empty/stale/error ناقص | باز |
| FE-12 | Low | برچسب‌های ثابت «زنده» | `markets/gold-fx/page.tsx:88,133`؛ `markets/silver/page.tsx:292` | مشاهدهٔ صفحه | ادعای live بدون timestamp | باز |
| FE-13 | Low | تست integration queryFn/WS وجود ندارد | `useMarketData.test.tsx` mock؛ تست WS بازار محدود | — | شکاف اطمینان | باز |
| FE-14 | Low (خارج دامنه) | ۲۱ خطای `tsc` در fund | خروجی `tsc` | `tsc --noEmit` | build/typecheck قرمز | باز |
| FE-15 | Medium | ساعت بنر برای naive-UTC محلی محاسبه می‌شد | `LiveDataBanner.tsx:15-21` (قبل) | `data_as_of` naive؛ UTC+03:30 | ساعت ۳:۳۰ عقب | **رفع شد** |

---

## ۸. علت ریشه‌ای

1. **محاسبهٔ freshness در queryFn و ذخیرهٔ آن** به‌جای محاسبهٔ مجدد در render؛ cache کهنه می‌شود ولی `isFresh` کهنه نمی‌شود.
2. **معنای متفاوت `isLive`**: گاهی «وجود داده» و گاهی «دادهٔ تازه»؛ interface واحد ندارد.
3. **banner وابسته به `isLive=true`** برای نمایش stale؛ اگر hook کهنگی را با `isLive=false` بیان کند، دلیل stale گم می‌شود.
4. **WebSocket بازار `connected` را با «دادهٔ زنده» یکی می‌گیرد** و auth/`as_of`/resubscribe را پیاده نکرده است.
5. **قرارداد envelope جدید (`apiGet` throw) سراسری است** ولی فقط مسیرهای مارکت تست شده‌اند.
6. **دو cache موازی** برای یک endpoint با limitهای مختلف.

---

## ۹. معیارهای پذیرش و نتیجه

| معیار | وضعیت | شاهد |
|---|---|---|
| timestamp آینده/null/نامعتبر live نشود | ⚠️ PARTIAL | `api-envelope`/heatmap feed درست؛ hookهای مشتق‌شده و banner بدون dataAsOf نه |
| stale از empty و source error متمایز باشد | ⚠️ PARTIAL | envelope/data_as_of/banner موجود؛ مصرف‌کننده‌ها و `isLive=false` ناقص |
| تست‌های مرتبط نتیجهٔ واقعی/قابل‌تکرار | ✅ PASS | ۳۳/۳۳ مرتبط، ۵۴۸/۵۴۸ کل، ۰ fail/skip |
| WebSocket پیام قدیمی را live نشان ندهد | ❌ FAIL/PARTIAL | FE-03/04/05 |
| typecheck/build سالم | ❌ FAIL (خارج دامنه) | ۲۱ خطا، ۰ در Phase 5 |
| بدون DB/secret/commit | ✅ PASS | — |

**نتیجهٔ نهایی: PARTIAL** — لایهٔ envelope و مسیر heatmap و کل تست‌ها سبزند، اما معیارهای freshness در hookهای مشتق‌شده/سایر ویجت‌ها، جداسازی `hasData/isStale`، و WebSocket بازار برآورده نشده‌اند. مرحله کامل اعلام نمی‌شود.

---

## ۱۰. تأیید ادعاهای قبلی

| ادعا | نتیجه |
|---|---|
| شاخه/HEAD `integration/golddesk-fixes` / `90597e05` | ✅ تأیید |
| ۱۵ تست `test_sync_log_repository.py` | ✅ ۱۵/۱۵ pass (مستقل) |
| «useMarketData.test.tsx: ۱۰/۱۵» | ❌ ۱۰ تست، ۱۰ pass؛ ۱۵ تستی وجود ندارد |
| گارد future-date در staged `useMarketData.ts` | ✅ diff staged موجود؛ با api-envelope تکمیل شده |
| گزارش‌های `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` | ❌ یافت نشدند (worktree/index/history) |
| QA موجود: ۵۴۷ تست | ⚠️ اجرای مستقل ۵۴۸ تست (۰ fail) نشان داد |
| ۵ staged حفظ شده/بدون commit | ✅ تأیید |

---

## ۱۱. کارهای باقی‌مانده (دقیق)

1. `isFresh`/`isStale` را در render با clock/ticker (`useSyncExternalStore`/interval) بازمحاسبه کنید، نه در query data.
2. `LiveDataResult` را به `hasData`، `isFresh`، `isLive`، `isStale` جدا کنید و همهٔ hookها را منتقل کنید.
3. `useTickerItems`/`useTopStocks`/`useActiveSymbols`/`useTopPerformers`/`useIndexImpacts` را به freshness heatmap وصل و تست‌ها را اصلاح کنید.
4. `LiveDataBanner` را به `hasData/isStale` مستقل مجهز کنید و `dataAsOf` را از همهٔ مصرف‌کننده‌ها پاس دهید.
5. صفحه heatmap: freshness هر view (heatmap/treemap) را جدا کنید و `dataAsOf:null` را live حساب نکنید.
6. WebSocket بازار: توکن handshake، subscribe/unsubscribe روی تغییر symbols، حفظ `as_of`/timestamp سرور، `lastMessageAt/stale`، نادیده گرفتن پیام قدیمی/out-of-order.
7. صفحه gold: استفاده از `useGoldWS` (age/stale) یا ادغام با `useMarketWebSocket`؛ LIVE فقط با داده تازه.
8. hookهای indices/news/quotes/global/treemap/flow: دریافت `data_as_of` از بک‌اند (handoff بخش ۰۴) یا اعلام freshness نامعلوم.
9. تست `apiGet`/`assertSuccessEnvelope` برای همهٔ endpointها و سیاست `success:false` با داده partial.
10. یکپارچه‌سازی کش `live-heatmap` و `market-enriched-heatmap` (key/limit/staleTime).
11. افزودن تست integration queryFn (data_as_of/fetched_at آینده/null/کهنه) و تست‌های WS (auth/resubscribe/stale/out-of-order).
12. رفع ۲۱ خطای `tsc` خارج از دامنه و اجرای `npm run build`.
13. گره زدن برچسب‌های ثابت «زنده» در `gold-fx`/`silver` به freshness یا حذف آن‌ها.
14. E2E مرورگر با backend/داده واقعی — **BLOCKED** تا رفع محدودیت دسترسی.

---

## ۱۲. فایل‌های تغییر‌یافته/ایجادشده

**تغییر یافته:**
- `frontend/src/components/dashboard/LiveDataBanner.tsx` (fix timezone ساعت)
- `frontend/src/__tests__/LiveDataBanner.test.tsx` (تست naive-UTC)

**ایجاد شده:**
- `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN2.md` (همین گزارش)

**بدون commit؛ HEAD `90597e05`؛ staged/untracked قبلی حفظ شد؛ هیچ DB/BrsApi/secret استفاده نشد.**
