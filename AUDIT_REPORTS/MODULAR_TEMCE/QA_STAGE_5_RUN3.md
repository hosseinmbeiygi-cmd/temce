# ممیزی مستقل مرحله ۵ — فرانت‌اند، freshness، polling و WebSocket (اجرای سوم)

**مسیر این گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN3.md`  
**گزارش مرحله (مرجع):** `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` (۲۶٬۱۳۱ بایت)  
**گزارش QA قبلی:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN2.md` (۲۰٬۱۶۹ بایت) و `QA_STAGE_5.md` — overwrite نشدند  
**تاریخ/زمان ممیزی:** 2026-10-28 — 23:23 به وقت محلی (UTC+03:30)، 19:53 UTC  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)

**نتیجهٔ نهایی: PARTIAL** — مسیر envelope/heatmap و تست‌ها سبزند (۳۳/۳۳ مرتبط، ۵۴۸/۵۴۸ کل)، اما freshness در hookهای مشتق‌شده، جداسازی `hasData/isFresh/isLive/isStale`، و WebSocket بازار برآورده نشده‌اند؛ تست‌ها هم بخشی از رفتار نادرست را pin می‌کنند. تأیید زنده BLOCKED است.

> این گزارش بر اساس بازخوانی کد فعلی، diff، Git و اجرای مجدد تست‌ها/تایپ‌چک نوشته شده است. هیچ ادعای گزارش قبلی بدون شاهد بازتولید نشده است.

---

## ۱. گزارش‌ها و وجود فایل

| گزارش | مسیر | وضعیت |
|---|---|---|
| گزارش مرحله (موضوع این پرامپت) | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` | ✅ موجود |
| گزارش مرحلهٔ دیگر | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_API_CONTRACT.md` | ✅ موجود؛ دامنهٔ متفاوت/مرتبط |
| QA قبلی | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5.md`، `QA_STAGE_5_RUN2.md` | ✅ موجود؛ overwrite نشدند |
| QA این اجرا | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN3.md` | ✅ همین فایل |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD ابتدا/انتها | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ `git diff --cached --stat` = ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete |
| فایل حذف‌شده توسط این ممیزی | هیچ (`git status | grep '^ D'` = 0) |
| عملیات ممنوع | هیچ: بدون reset --hard، clean، stash، checkout/restore مخرب، rebase، force push یا commit |
| تغییرات هم‌زمان | `frontend/src/lib/api-envelope.ts`، `api.ts`، `useMarketData.ts`، `heatmap/page.tsx`، `LiveDataBanner.tsx`، `goldApi.ts`، تست‌ها — حفظ شدند |
| تغییرات این ممیزی | فقط گزارش؛ هیچ کد جدیدی در این اجرا تغییر نکرد (کد از RUN2 بازبینی شد) |

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
| `frontend/src/hooks/useWebSocket.ts` | کل ۲۳۰ خط |
| `frontend/src/hooks/useGoldWS.ts` | کل |
| `apps/api/endpoints/websocket.py` | پروتکل/auth `/ws/market` |
| `frontend/src/__tests__/useSymbolPrices.test.ts(x)` | ۴ تست WS بازار |
| `frontend/src/__tests__/GoldWebSocket.test.tsx` | ۱۰ تست WS طلا |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `frontend/src/hooks/useMarketData.ts` | ۱–۱۲۰، ۲۵۰–۷۰۰ + grep کامل `isLive`/queryها؛ کل ۸۴۳ خط خط‌به‌خط نه |
| `frontend/src/lib/api.ts` | `apiRequest`/`extractArray` (نه کل ۳۶۹ خط) |
| `frontend/src/app/heatmap/page.tsx` | ۱۶۰–۲۶۰ |
| `frontend/src/lib/goldApi.ts` | WS/error (نه کل) |
| `frontend/src/app/markets/gold/page.tsx` | live/WS badge |
| کامپوننت‌های dashboard | فقط نقاط `LiveDataBanner` |

### بررسی نشد

| مورد | دلیل |
|---|---|
| کل فرانت‌اند/همهٔ صفحات | خارج از دامنه/حجم؛ فقط نقاط مرتبط |
| BrsApi/TSETMC/Redis زنده، E2E مرورگر | ممنوع/بدون دسترسی |
| `npm run build` | `tsc` قرمز است (۲۱ خطا خارج از دامنه) |
| `node_modules`/باینری/تولیدی | وابستگی/تولیدی |

---

## ۴. جدول الزام‌های پرامپت

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| 1 | شناسایی ریشه/شاخه/HEAD/status/diff | `pwd`، `git rev-parse`، `git status --short --branch` | **PASS** | — |
| 2 | حفظ staged/untracked؛ عدم عملیات مخرب Git | HEAD ثابت؛ ۱۳۸ staged؛ ۰ حذف؛ بدون reset/clean/stash/commit | **PASS** | — |
| 3 | عدم درخواست زنده BrsApi/TSETMC | هیچ کلاینت زنده اجرا نشد | **PASS (compliance)** | E2E زنده **BLOCKED** |
| 4 | عدم DB destructive/secret | هیچ DB/secret استفاده نشد | **PASS** | — |
| 5 | گزارش‌های قدیمی سرنخ؛ تأیید مستقل | `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` یافت نشد؛ ۱۵/۱۵ sync-log؛ شاخه/HEAD | **PASS** | — |
| 6 | خواندن فایل‌های مرتبط + manifest | بخش ۳ | **PARTIAL** | کل `useMarketData.ts`/فرانت خوانده نشد |
| 7 | fix کوچک/هدفمند | در این اجرا کد جدیدی تغییر نکرد؛ fix timezone در RUN2 موجود است | **PASS** | — |
| 8 | گزارش در فایل، بدون overwrite | `05...` و `QA_STAGE_5_RUN3.md` | **PASS** | — |
| 9 | ساختار کامل گزارش | همین گزارش | **PASS** | — |
| 10 | انجام واقعی مأموریت | کد/تست/Git اجرا و بررسی شد | **PASS** | — |
| 11 | ردیابی JSON→hook→query key/cache→UI | heatmap/envelope/consumerها | **PARTIAL** | همهٔ صفحات ردیابی نشدند |
| 12 | timestamp آینده/null/نامعتبر live نشود | `api-envelope.ts:162,198`؛ ۱۶ تست | **PARTIAL** | hookهای مشتق‌شده/بنر بدون dataAsOf |
| 13 | `hasData`/`isFresh`/`isLive`/`isStale` جدا | `LiveDataResult` فقط `isLive` دارد (`useMarketData.ts:86-96`) | **FAIL/PARTIAL** | جداسازی کامل نشده |
| 14 | query key/staleTime/refetch/retry/error | hookها/heatmap page؛ full tests | **PASS (offline)** | کش تکراری heatmap؛ hookهای بدون timestamp |
| 15 | WebSocket پیام/timestamp/subscription/reconnect/پیام قدیمی | `useWebSocket.ts:31-55,130,147`؛ `useGoldWS` خوب | **PARTIAL/FAIL** | توکن، as_of، stale، resubscribe |
| 16 | اجرای `useMarketData.test.tsx` و دسته‌بندی | ۱۰ تست، ۱۰ pass، ۰ skip | **PASS** | ادعای «۱۰/۱۵» اشتباه بود |
| 17 | معیار پذیرش: freshness/error/test | بخش ۹ | **PARTIAL** | FE-01..FE-07 |
| 18 | بدون commit | HEAD ثابت | **PASS** | — |

---

## ۵. اصلاحات: مسیر، diff، دلیل، تست

| # | مسیر/خط | diff/شاهد | دلیل | تست | مالکیت |
|---|---|---|---|---|---|
| F-1 | `frontend/src/lib/api-envelope.ts:89-209` | `readEnvelopeMeta`/`parseIsoInstant`/`isDataAsOfFresh`/`assertSuccessEnvelope` | جدا کردن success/empty/error و timestamp معتبر | `apiEnvelope.test.ts` ۱۶ pass | قبلی؛ تأیید شد |
| F-2 | `frontend/src/lib/api.ts:242-249` | parse + `assertSuccessEnvelope` | `success:false` به empty تبدیل نشود | ۴ تست transport/envelope | قبلی؛ تأیید شد |
| F-3 | `frontend/src/hooks/useMarketData.ts:287-317` | `HeatmapFeed` + `dataAsOf`/`isFresh` از `data_as_of`/`fetched_at` | استفاده از freshness envelope | ۱۰ تست hook | قبلی؛ تأیید شد |
| F-4 | `frontend/src/app/heatmap/page.tsx:181-238` | حذف `try/catch` پنهان؛ mock فقط پیش از پاسخ؛ banner | خطا/empty پنهان نشود | full suite pass | قبلی؛ تأیید شد |
| F-5 | `LiveDataBanner.tsx:32-61` | `dataAsOf` + `isStale` + پیام stale | نمایش کهنگی | ۶ تست + ۱ تست جدید | قبلی؛ تأیید شد |
| F-6 | `LiveDataBanner.tsx:5,15-21` | `clockLabel` با `parseIsoInstant` به‌جای `new Date(iso)` | naive-UTC به‌عنوان UTC نمایش داده شود | `formats a naive backend timestamp as UTC…` | RUN2/این مرحله |
| F-7 | تست‌های `apiEnvelope`/`LiveDataBanner` | future/null/malformed/timezone | pin کردن قرارداد | ۱۶ + ۷ pass | قبلی + RUN2 |

**نکته:** تلاش برای propagate کردن `hm.isLive` به hookهای مشتق‌شده در RUN2 پس از مشاهدهٔ ناسازگاری معنایی banner برگردانده شد؛ به‌عنوان FE-02/FE-06 در کارهای باقی‌مانده ثبت شده است.

---

## ۶. فرمان‌های تست و نتیجهٔ واقعی

> محیط: `C:/Users/Iran/Desktop/temce/frontend` — vitest v4.1.9/jsdom. بدون backend زنده.

| فرمان | Passed | Failed | Skipped | Exit |
|---|---|---|---|---|
| `./node_modules/.bin/vitest run src/__tests__/useMarketData.test.tsx src/__tests__/apiEnvelope.test.ts src/__tests__/LiveDataBanner.test.tsx` | **33** | **0** | **0** | **0** |
| تفکیک `useMarketData.test.tsx` | **10** | 0 | 0 | — |
| تفکیک `apiEnvelope.test.ts` | **16** | 0 | 0 | — |
| تفکیک `LiveDataBanner.test.tsx` | **7** | 0 | 0 | — |
| کل مجموعه: `./node_modules/.bin/vitest run` | **548** (۵۷ فایل) | **0** | **0** | **0** |
| `./node_modules/.bin/tsc --noEmit --pretty false` | — | **21 خطا** | — | **1** |

- ادعای «۱۰/۱۵ passing به‌دلیل environment» **بازتولید نشد**: فایل `useMarketData.test.tsx` ۱۰ تست دارد و هر ۱۰ pass است؛ ۱۵ تستی وجود ندارد.
- QA قبلی «۵۴۷ تست» گفته بود؛ اجرای مستقل این ممیزی **۵۴۸ تست** (با تست جدید بنر) را نشان می‌دهد؛ ۰ failed.
- ۲۱ خطای `tsc` همه در کامپوننت‌های fund خارج از دامنه‌اند؛ **۰ خطا در فایل‌های Phase 5** (خروجی فیلترشده). این شکست پنهان نشده است.
- `npm run build`، E2E مرورگر، و تست‌های زندهٔ WS/BrsApi اجرا نشدند.

### تست‌های اجرانشده و علت

| تست/بررسی | علت |
|---|---|
| `npm run build` | `tsc` خارج از دامنه ۲۱ خطا دارد |
| E2E مرورگر با backend/داده واقعی | نیازمند backend/BrsApi؛ ممنوع/در دسترس نبود |
| تست auth/resubscribe/stale برای `useMarketWebSocket` | تست موجود فقط ۴ مسیر پایه را پوشش می‌دهد؛ زیرساخت WS/auth فراهم نبود |
| تست integration queryFn heatmap | تست‌ها `useQuery` را mock می‌کنند و queryFn واقعی را اجرا نمی‌کنند |

---

## ۷. جدول ایرادها

| # | شدت | عنوان | شاهد (path:line) | بازتولید | اثر | وضعیت |
|---|---|---|---|---|---|---|
| FE-01 | High | `isFresh` در queryFn ذخیره و با گذشت زمان کهنه نمی‌شود | `useMarketData.ts:303-317` | refetch را متوقف و >۵ دقیقه صبر کنید؛ `isLive` true می‌ماند | داده کهنه live | باز |
| FE-02 | High | hookهای مشتق‌شده freshness را نادیده می‌گیرند | `useMarketData.ts:329,427,454,519,690` | feed با cells و بدون timestamp؛ `isLive=true` | null/نامعتبر live | باز |
| FE-03 | High | WS بازار توکن handshake ندارد | `useWebSocket.ts:31-55`؛ `apps/api/endpoints/websocket.py:29-63` | auth فعال؛ اتصال 1008 | WS در production کار نمی‌کند | باز |
| FE-04 | High | WS timestamp سرور را با `Date.now()` جایگزین و stale/age ندارد | `useWebSocket.ts:116-155,181` | قطع پیام‌ها؛ connected true و LIVE | قیمت کهنه live | باز |
| FE-05 | High | تغییر symbols دوباره subscribe نمی‌شود | `useWebSocket.ts:72,130,173` | symbols را پس از open تغییر دهید | نماد جدید قیمت نمی‌گیرد | باز |
| FE-06 | Medium | banner دلیل stale را در `isLive=false` حفظ نمی‌کند | `LiveDataBanner.tsx:32-39` | hook کهنه isLive=false | stale از empty قابل‌تشخیص نیست | باز |
| FE-07 | Medium | heatmap page freshness را بر اساس view/treemap جدا نمی‌کند | `heatmap/page.tsx:181-194,229-238` | heatmap خالی + treemap پر | warning نادرست | باز |
| FE-08 | Medium | `apiGet` همهٔ `success:false` را throw می‌کند؛ پوشش همهٔ endpointها نیست | `api.ts:242-249` | endpoint غیرمارکت با success:false | خطای غیرمنتظره | باز |
| FE-09 | Medium | کش تکراری heatmap با limitهای مختلف | `useMarketData.ts:290` vs `heatmap/page.tsx:181` | heatmap + dashboard | دو cache/درخواست | باز |
| FE-10 | Medium | سایر hookها `isLive=rows.length>0` و بدون data_as_of | `useMarketData.ts:349,384,507,565,589,619,638,722,756,797,819,842` | backend قدیمی | وجود داده=live | باز؛ handoff بخش ۰۴ |
| FE-11 | Low | `LiveDataResult` فاقد `hasData/isFresh/isStale` | `useMarketData.ts:86-96` | همهٔ مصرف‌کننده‌ها | تفکیک ناقص | باز |
| FE-12 | Medium (تست) | تست‌ها رفتار نادرست را pin می‌کنند | `useMarketData.test.tsx:113-138` (`dataAsOf:null` → `isLive=true`)؛ `LiveDataBanner.test.tsx:31` | اجرای تست | اطمینان کاذب؛ acceptance را نقض می‌کند | باز |
| FE-13 | Low | تست integration queryFn/WS وجود ندارد | `useMarketData.test.tsx` mock؛ `useSymbolPrices.test` فقط ۴ مسیر | — | شکاف اطمینان | باز |
| FE-14 | Low | برچسب‌های ثابت «زنده» | `markets/gold-fx/page.tsx:88,133`؛ `markets/silver/page.tsx:292` | مشاهدهٔ صفحه | ادعای live بدون timestamp | باز |
| FE-15 | Low (خارج دامنه) | ۲۱ خطای `tsc` در fund | خروجی `tsc` | `tsc --noEmit` | build/typecheck قرمز | باز |
| FE-16 | Medium | ساعت بنر برای naive-UTC محلی محاسبه می‌شد | `LiveDataBanner.tsx:15-21` (قبل) | `data_as_of` naive؛ UTC+03:30 | ساعت ۳:۳۰ عقب | **رفع شد** |

---

## ۸. علت ریشه‌ای

1. **محاسبهٔ تازگی در queryFn و ذخیرهٔ آن** به‌جای محاسبهٔ مجدد در render؛ cache کهنه می‌شود ولی `isFresh` کهنه نمی‌شود.
2. **معنای متفاوت `isLive`**: گاهی «وجود داده» و گاهی «دادهٔ تازه»؛ interface واحد ندارد.
3. **banner وابسته به `isLive=true`** برای نمایش stale؛ اگر hook کهنگی را با `isLive=false` بیان کند، دلیل stale گم می‌شود.
4. **WS بازار `connected` را با «دادهٔ زنده» یکی می‌گیرد** و auth/`as_of`/resubscribe را پیاده نکرده است.
5. **قرارداد envelope (`apiGet` throw) سراسری است** ولی فقط مسیرهای مارکت تست شده‌اند.
6. **تست‌های hook، semantics نادرست را pin می‌کنند** و queryFn واقعی/WS را پوشش نمی‌دهند.

---

## ۹. معیارهای پذیرش و نتیجه

| معیار | وضعیت | شاهد |
|---|---|---|
| timestamp آینده/null/نامعتبر live نشود | ⚠️ PARTIAL | `api-envelope`/heatmap feed درست؛ hookهای مشتق‌شده/بنر نه |
| stale از empty و source error متمایز باشد | ⚠️ PARTIAL | envelope/data_as_of/banner موجود؛ مصرف‌کننده‌ها/`isLive=false` ناقص |
| تست‌های مرتبط واقعی/قابل‌تکرار | ✅ PASS | ۳۳/۳۳ مرتبط، ۵۴۸/۵۴۸ کل، ۰ fail/skip |
| WebSocket پیام قدیمی را live نشان ندهد | ❌ FAIL/PARTIAL | FE-03/04/05 |
| typecheck/build سالم | ❌ FAIL (خارج دامنه) | ۲۱ خطا، ۰ در Phase 5 |
| بدون DB/secret/commit | ✅ PASS | — |

**نتیجهٔ نهایی: PARTIAL** — envelope و مسیر heatmap و تست‌ها سبزند، اما معیارهای freshness در hookهای مشتق‌شده/سایر ویجت‌ها، جداسازی `hasData/isStale`، و WebSocket بازار برآورده نشده‌اند. مرحله کامل اعلام نمی‌شود.

---

## ۱۰. تأیید ادعاهای قبلی

| ادعا | نتیجه |
|---|---|
| شاخه/HEAD `integration/golddesk-fixes` / `90597e05` | ✅ تأیید |
| ۱۵ تست `test_sync_log_repository.py` | ✅ ۱۵/۱۵ pass (مستقل) |
| «useMarketData.test.tsx: ۱۰/۱۵» | ❌ ۱۰ تست، ۱۰ pass؛ ۱۵ تستی وجود ندارد |
| ۵۴۷ تست QA قبلی | ⚠️ اجرای مستقل ۵۴۸ تست (۰ fail) |
| گارد future-date در staged `useMarketData.ts` | ✅ diff staged موجود؛ با api-envelope تکمیل شده |
| گزارش‌های `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` | ❌ یافت نشدند |
| ۵ staged حفظ شده/بدون commit | ✅ تأیید |

---

## ۱۱. کارهای باقی‌مانده (دقیق)

1. `isFresh`/`isStale` را در render با clock/ticker (`useSyncExternalStore`/interval) بازمحاسبه کنید، نه در query data.
2. `LiveDataResult` را به `hasData`، `isFresh`، `isLive`، `isStale` جدا کنید و همهٔ hookها را منتقل کنید.
3. `useTickerItems`/`useTopStocks`/`useActiveSymbols`/`useTopPerformers`/`useIndexImpacts` را به freshness heatmap وصل کنید.
4. تست‌های `dataAsOf:null` را اصلاح کنید: داده بدون timestamp باید `isLive=false` باشد.
5. `LiveDataBanner` را به `hasData/isStale` مستقل مجهز کنید و `dataAsOf` را از همهٔ مصرف‌کننده‌ها پاس دهید.
6. صفحه heatmap: freshness هر view (heatmap/treemap) را جدا کنید و `dataAsOf:null` را live حساب نکنید.
7. WebSocket بازار: توکن handshake، subscribe/unsubscribe روی تغییر symbols، حفظ `as_of`/timestamp سرور، `lastMessageAt/stale`، نادیده گرفتن پیام قدیمی/out-of-order.
8. صفحه gold: استفاده از `useGoldWS` (age/stale) یا ادغام با `useMarketWebSocket`؛ LIVE فقط با داده تازه.
9. hookهای indices/news/quotes/global/treemap/flow: دریافت `data_as_of` از بک‌اند (handoff بخش ۰۴) یا اعلام freshness نامعلوم.
10. تست `apiGet`/`assertSuccessEnvelope` برای همهٔ endpointها و سیاست `success:false` با داده partial.
11. یکپارچه‌سازی کش `live-heatmap` و `market-enriched-heatmap` (key/limit/staleTime).
12. افزودن تست integration queryFn (data_as_of/fetched_at آینده/null/کهنه) و تست‌های WS (auth/resubscribe/stale/out-of-order).
13. رفع ۲۱ خطای `tsc` خارج از دامنه و اجرای `npm run build`.
14. گره زدن برچسب‌های ثابت «زنده» در `gold-fx`/`silver` به freshness یا حذف آن‌ها.
15. E2E مرورگر با backend/داده واقعی — **BLOCKED**.

---

## ۱۲. فایل‌های تغییر‌یافته/ایجادشده

**تغییر این ممیزی:** هیچ فایل کدی (فقط گزارش).  
**تغییرات موجود از RUN2:** `frontend/src/components/dashboard/LiveDataBanner.tsx` + `frontend/src/__tests__/LiveDataBanner.test.tsx` (fix timezone و تست).  
**ایجاد شده:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN3.md` (همین گزارش).

**بدون commit؛ HEAD `90597e05`؛ staged/untracked قبلی حفظ شد؛ هیچ DB/BrsApi/secret استفاده نشد.**
