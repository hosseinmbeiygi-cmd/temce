# ممیزی مرحله ۵ — فرانت‌اند، query cache، freshness، polling و WebSocket

**مسیر گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md`  
**تاریخ/زمان اجرا:** 2026-10-28 — 22:47 به وقت محلی میزبان (UTC+03:30)، 19:17 UTC  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)  
**نتیجهٔ نهایی: PARTIAL** — مسیر heatmap/envelope و تست‌های مرتبط اصلاح/تأیید شده‌اند، اما جدا شدن کامل `hasData`/`isFresh`/`isLive`/`isStale`، hookهای مشتق‌شده، WebSocket بازار و پوشش freshness در سایر ویجت‌ها هنوز کامل نیست.

> این گزارش بر اساس بازخوانی کد فعلی، diff، Git و اجرای مجدد تست‌هاست. خروجی‌های واقعی در بخش ۶ ثبت شده‌اند. تغییرات هم‌زمان قبلی (api-envelope، hook، banner، heatmap page، تست‌ها) حفظ شدند.

---

## ۱. مسیر گزارش و وجود فایل

| مورد | مسیر/وضعیت |
|---|---|
| گزارش این مرحله | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` — همین فایل |
| گزارش قبلی مرحله ۵ | وجود نداشت؛ overwrite انجام نشد |
| گزارش مرحله ۴ | `04_BACKEND_API_AGGREGATION_CACHE_run2.md` و `QA_STAGE_4.md` دست‌نخورده |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD ابتدا/انتها | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ `git diff --cached --stat` = ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete |
| فایل حذف‌شده توسط این ممیزی | هیچ (`git status | grep '^ D'` = 0) |
| عملیات ممنوع | هیچ: بدون reset --hard، clean، stash، checkout/restore مخرب، rebase، force push یا commit |
| تغییرات هم‌زمان قبلی | `frontend/src/lib/api-envelope.ts` (untracked)، `frontend/src/hooks/useMarketData.ts` (MM)، `frontend/src/lib/api.ts`، `frontend/src/app/heatmap/page.tsx`، `frontend/src/components/dashboard/LiveDataBanner.tsx`، `frontend/src/__tests__/useMarketData.test.tsx`، `goldApi.ts` — همه حفظ شدند |
| تغییر این ممیزی | فقط `LiveDataBanner.clockLabel` + یک تست بنر (بخش ۷) |

---

## ۳. هدف و مرز دامنه

**هدف:** جلوگیری از نمایش دادهٔ قدیمی به‌عنوان live؛ جدا کردن وجود داده از تازگی؛ بررسی query key/staleTime/refetchInterval/retry/error؛ بررسی WebSocket (پیام، timestamp، subscription، reconnect، پیام قدیمی)؛ و اجرای واقعی تست‌های `useMarketData.test.tsx`.

**در دامنه:** `frontend/src/hooks/useMarketData.ts`، `useWebSocket.ts`، `useGoldWS.ts`، `frontend/src/lib/api.ts`، `api-envelope.ts`، `goldApi.ts` (بخش WS)، `frontend/src/app/heatmap/page.tsx`، `LiveDataBanner.tsx`، کامپوننت‌های مصرف‌کنندهٔ hookها، تست‌های freshness/cache.

**خارج از دامنه:** تغییر UI گسترده، بک‌اند (به‌جز handoff)، deployment، BrsApi/DB/Redis زنده، و بازطراحی کامل WebSocket.

---

## ۴. Manifest فایل‌های خوانده‌شده

### کامل خوانده شد

| فایل | نکته |
|---|---|
| `frontend/src/lib/api-envelope.ts` | کل؛ `readEnvelopeMeta`، `assertSuccessEnvelope`، `parseIsoInstant`، `isDataAsOfFresh` |
| `frontend/src/components/dashboard/LiveDataBanner.tsx` | کل |
| `frontend/src/__tests__/apiEnvelope.test.ts` | کل (۱۶ تست) |
| `frontend/src/__tests__/LiveDataBanner.test.tsx` | کل (۷ تست) |
| `frontend/src/__tests__/useMarketData.test.tsx` | کل (۱۰ تست) |
| `frontend/src/hooks/useWebSocket.ts` | کل (۲۳۰ خط) |
| `frontend/src/hooks/useGoldWS.ts` | کل |
| `frontend/src/lib/goldApi.ts` | بخش WS manager و `parseAsOf`/`GoldWSInfo` |
| `apps/api/endpoints/websocket.py` | پروتکل `/ws/market` و احراز هویت handshake |
| `src/gold_desk/ws_hub.py` (بخش as_of) | فرمت `as_of` پیام‌های gold WS |
| `frontend/vitest.config.ts` | محیط jsdom |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `frontend/src/hooks/useMarketData.ts` | بخش‌های ۱–۱۲۰، ۲۵۰–۷۰۰ و grep کامل `isLive`/queryها؛ کل ۸۴۳ خط خط‌به‌خط خوانده نشد |
| `frontend/src/lib/api.ts` | بخش `apiRequest`/`extractArray`/`safeExtractArray` (نه کل ۳۶۹ خط) |
| `frontend/src/app/heatmap/page.tsx` | بخش ۱۶۰–۲۶۰ (نه کل ۳۰۱ خط) |
| `frontend/src/app/markets/gold/page.tsx` | بخش `useLiveMarketData` و badgeها |
| `frontend/src/components/dashboard/*` | فقط نقاط مصرف `LiveDataBanner`/`isLive` (grep) |
| `frontend/src/hooks/usePrecomputeStatus.ts` | بخش WS/reconnect (بررسی کامل نشد) |
| `frontend/src/lib/api.ts` / `goldApi.ts` | بخش‌های envelope/error/WS |

### بررسی نشد

| مورد | دلیل |
|---|---|
| کل فرانت‌اند (همهٔ صفحات/کامپوننت‌ها) | خارج از دامنه/حجم بالا؛ فقط نقاط مرتبط grep/read شد |
| BrsApi/TSETMC/Redis زنده | ممنوع/بدون دسترسی؛ هیچ درخواست زنده‌ای ارسال نشد |
| اجرای کامل `npm test` و `npm run build` | فقط تست‌های مرتبط اجرا شد؛ build اجرا نشد |
| مرورگر واقعی/E2E | نیازمند backend/داده؛ انجام نشد |
| `node_modules/`، فایل‌های باینری/تولیدی | وابستگی/تولیدی |

---

## ۵. یافته‌های تأییدشده در برابر فرضیه‌ها

| ادعا/فرضیه | نتیجه | شاهد |
|---|---|---|
| باگ `now - fetched_at <= 300000` برای timestamp آینده/null/نامعتبر | ✅ در `api-envelope` رفع/پوشش داده شده | `parseIsoInstant`/`isDataAsOfFresh`، ۱۶ تست |
| timestamp naive بک‌اند به‌عنوان UTC تفسیر می‌شود | ✅ تأیید | `parseIsoInstant("2026-10-28 12:00:00") === Date.UTC(...)`؛ تست |
| `useEnrichedHeatmap` از `data_as_of`/`fetched_at` استفاده می‌کند | ✅ تأیید (در queryFn) | `useMarketData.ts:287-317` |
| `isLive` در hookهای مشتق‌شده = وجود ردیف است | ❌ **باقی‌مانده**: `useTickerItems`/`useTopStocks`/`useActiveSymbols`/`useTopPerformers`/`useIndexImpacts` freshness را نادیده می‌گیرند | `useMarketData.ts:329,427,454,519,690`؛ تست‌ها هم `dataAsOf:null` را live می‌دانند |
| `isFresh` در زمان render بازمحاسبه می‌شود | ❌ در `queryFn` محاسبه و در دادهٔ query ذخیره می‌شود؛ با گذشت زمان بدون refetch کهنه نمی‌شود | `useMarketData.ts:303-317`؛ `refetchInterval: 30_000` |
| `LiveDataBanner` stale را از empty/error جدا می‌کند | ⚠️ فقط وقتی `isLive=true` و `dataAsOf` داده شده باشد؛ بیشتر مصرف‌کننده‌ها `dataAsOf` نمی‌دهند | `LiveDataBanner.tsx:32-39`؛ ۱۲ مصرف‌کننده بدون dataAsOf |
| `apiGet` پاسخ `success:false` را از empty جدا می‌کند | ✅ با throw | `api.ts:242-249`؛ ۱۶ تست envelope |
| تست‌های قبلی «۱۰/۱۵ به‌دلیل environment» | ❌ **بازتولید نشد**: فایل `useMarketData.test.tsx` فقط ۱۰ تست دارد و هر ۱۰ pass است؛ هیچ skip/fail محیطی نبود | اجرای vitest؛ بخش ۶ |
| WebSocket بازار باعث live شدن پیام قدیمی نمی‌شود | ❌ `timestamp: Date.now()` روی پیام می‌گذارد و `connected` به‌تنهایی LIVE نشان داده می‌شود | `useWebSocket.ts:147,181`؛ `markets/gold/page.tsx:68,393,456,479,481` |
| WebSocket بازار روی تغییر symbols دوباره subscribe می‌کند | ❌ effect با `[]` و subscribe فقط در `onopen` | `useWebSocket.ts:71-74,116-135,173` |
| WebSocket بازار احراز هویت handshake را انجام می‌دهد | ❌ URL توکن ندارد، در حالی که backend توکن می‌خواهد | `useWebSocket.ts:_getWsUrl`؛ `apps/api/endpoints/websocket.py:29-63` |
| `useGoldWS` کهنگی را از `as_of` محاسبه می‌کند | ✅ پیاده‌سازی خوب | `useGoldWS.ts:50-70`؛ `goldApi.ts` `parseAsOf` |
| صفحه gold از `useGoldWS` استفاده می‌کند | ❌ از `useMarketWebSocket` استفاده می‌کند و stale/age را نشان نمی‌دهد | `markets/gold/page.tsx:68` |
| گزارش‌های `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` | ❌ در worktree/index/history یافت نشدند؛ غیبت ثبت شد | `git ls-files`/`git log --all` |
| ۱۵ تست `test_sync_log_repository.py` | ✅ ۱۵/۱۵ pass (مستقل) | `pytest` خروجی ۱۵ passed |

---

## ۶. جدول ایرادها

شدت: **High** = نمایش stale/خطا به‌عنوان live؛ **Medium** = از دست رفتن دلیل کهنگی یا ریسک قرارداد؛ **Low** = کارایی/تست/مستندسازی.

| # | شدت | عنوان | شاهد (path:line) | بازتولید | اثر | وضعیت |
|---|---|---|---|---|---|---|
| FE-01 | High | `isFresh` در queryFn ذخیره می‌شود و با گذشت زمان کهنه نمی‌شود | `useMarketData.ts:303-317` | feed تازه را کش کنید، refetch را متوقف کنید و >۵ دقیقه صبر کنید؛ `isLive` همان true می‌ماند | داده کهنه به‌عنوان live | باز |
| FE-02 | High | hookهای مشتق‌شده freshness را دور می‌زنند | `useMarketData.ts:329,427,454,519,690` | feed با `cells` و بدون `dataAsOf`/`fetched_at` بدهید؛ `isLive=true` | timestamp null/نامعتبر live | باز |
| FE-03 | High | WebSocket بازار timestamp سرور را با `Date.now()` جایگزین می‌کند و silence/stale ندارد | `useWebSocket.ts:135-155,181` | پس از قطع پیام‌ها، `connected` true و badge LIVE می‌ماند؛ پیام قدیمی timestamp جدید می‌گیرد | قیمت کهنه/out-of-order به‌عنوان live | باز |
| FE-04 | High | WebSocket بازار توکن handshake ندارد | `useWebSocket.ts` `_getWsUrl`؛ backend `websocket.py:29-63` | با auth فعال، اتصال با 1008 رد می‌شود | WebSocket در production کار نمی‌کند یا unauthorized | باز |
| FE-05 | High | تغییر symbols باعث subscribe دوباره نمی‌شود | `useWebSocket.ts:71-74,116-135,173` | `symbols` را بعد از اتصال تغییر دهید | نمادهای جدید قیمت نمی‌گیرند | باز |
| FE-06 | Medium | banner دلیل stale را وقتی `isLive=false` است حفظ نمی‌کند | `LiveDataBanner.tsx:32-39` | hook با دادهٔ کهنه `isLive=false` برمی‌گرداند؛ banner «خالی» می‌گوید | stale از empty قابل‌تشخیص نیست | باز |
| FE-07 | Medium | صفحه heatmap freshness را بر اساس view/treemap جدا نمی‌کند | `heatmap/page.tsx:181-194,229-238` | heatmap خالی + treemap پر، یا dataAsOf null | warning نادرست/داده بدون freshness | باز |
| FE-08 | Medium | نمایش ساعت stale با `new Date(naive)` زمان محلی می‌سازد | `LiveDataBanner.tsx:15-21` (قبل) | `data_as_of` naive UTC؛ در UTC+03:30 ساعت ۳:۳۰ عقب | ساعت «آخرین به‌روزرسانی» نادرست | **رفع شد** |
| FE-09 | Medium | `apiGet` همهٔ `success:false`ها را throw می‌کند؛ پوشش همهٔ endpointها نیست | `api.ts:242-249` | endpoint غیرمارکت با success:false دارای data | ممکن است صفحه‌های دیگر به error غیرمنتظره بخورند | باز (ریسک/نیاز تست) |
| FE-10 | Medium | کش تکراری برای همان endpoint با limitهای مختلف | `useMarketData.ts:290` (`live-heatmap`, limit=120) vs `heatmap/page.tsx:181` (`market-enriched-heatmap`, default 500) | باز کردن heatmap page + داشبورد | دو درخواست/کش ناسازگار | باز |
| FE-11 | Medium | بقیهٔ hookها `isLive = rows.length > 0` دارند و data_as_of ندارند | `useMarketData.ts:349,384,507,565,589,619,638,722,756,797,819,842` | backend قدیمی/بدون timestamp | وجود داده = live | باز؛ handoff بخش ۰۴ |
| FE-12 | Low | interface `LiveDataResult` فیلد `hasData`/`isFresh`/`isStale` ندارد | `useMarketData.ts:86-96` | هر مصرف‌کننده | نمی‌تواند empty/stale/error را از هم جدا کند | باز |
| FE-13 | Low | mock اولیهٔ heatmap page تا اولین پاسخ API نمایش داده می‌شود | `heatmap/page.tsx:170-210` | کندی شبکه | ممکن است چند لحظه داده ساختگی دیده شود (بدون badge live) | باز |
| FE-14 | Low | برچسب‌های «زنده» ثابت در برخی صفحات | `markets/gold-fx/page.tsx:88,133`؛ `markets/silver/page.tsx:292` | مشاهدهٔ صفحه | ادعای live بدون timestamp | باز |
| FE-15 | Low | نبود تست integration برای queryFn/freshness واقعی و WS | `useMarketData.test.tsx` (mock useQuery)؛ تست WS وجود ندارد | — | شکاف اطمینان | باز |
| FE-16 | Low (خارج دامنه) | `tsc --noEmit` با ۲۱ خطا در کامپوننت‌های fund شکست می‌خورد | `FundAnalysisModal`/`FundCompareModal`/`FundDetailDrawer`/`FundScorecardPanel` | `tsc --noEmit` | build/typecheck قرمز مستقل از این مرحله | باز |

---

## ۷. علت ریشه‌ای

1. **تازگی به‌جای محاسبه در render، در دادهٔ query ذخیره شد.** `isFresh` فقط در لحظهٔ fetch درست است؛ cache/refetch متوقف‌شده آن را کهنه نمی‌کند.
2. **`isLive` بین hookها معنای متفاوت دارد:** گاهی «داده exists» (وجود ردیف) و گاهی «داده تازه» (heatmap). interface واحد `hasData/isFresh/isStale` ندارد.
3. **banner برای stale به `isLive=true` وابسته است**؛ اگر hook کهنگی را با `isLive=false` بیان کند، دلیل stale از دست می‌رود.
4. **WebSocket بازار timestamp سرور/`as_of` را نمی‌خواند** و `connected` را با «زنده بودن داده» یکی می‌گیرد؛ همچنین subscription بعد از تغییر symbols و auth token را مدیریت نمی‌کند.
5. **قرارداد envelope جدید (`apiGet` throw) سراسری است** ولی فقط مسیرهای مارکت تست شده‌اند.
6. **دو کش موازی** برای همان endpoint با limitهای مختلف، و مصرف‌نشدن `data_as_of` در بسیاری از hookها.

---

## ۸. تغییرات کد و دلیل هرکدام (یک fix کوچک)

| # | فایل/خط | diff | دلیل | تست |
|---|---|---|---|---|
| C-1 | `frontend/src/components/dashboard/LiveDataBanner.tsx:5,15-21` | `clockLabel` از `new Date(iso)` به `parseIsoInstant(iso)` + `new Date(instant)` تغییر کرد | `data_as_of` بک‌اند naive-UTC است؛ `new Date` آن را محلی می‌خواند و ساعت بنر را با offset اشتباه نشان می‌داد | `LiveDataBanner.test.tsx::formats a naive backend timestamp as UTC, not as browser-local time` |
| C-2 | `frontend/src/__tests__/LiveDataBanner.test.tsx` | یک تست جدید برای naive UTC | pin کردن رفتار timezone | همان |

**تلاش بازگردانده‌شده:** ابتدا `isLive` hookهای مشتق‌شده را به `hm.isLive` تغییر دادم، اما چون `LiveDataBanner` حالت «isLive=false» را «بخش خالی می‌ماند» تفسیر می‌کند، این تغییر باعث پیام نادرست برای دادهٔ کهنه/موجود می‌شد. تغییر برگردانده شد (کد به حالت قبلی) و به‌عنوان FE-02/FE-06 در کارهای باقی‌مانده ثبت شد. هیچ تغییر ناتمامی باقی نمانده است.

---

## ۹. فرمان‌های تست، نتیجه و exit code

> همه در `frontend/` با `vitest` (v4.1.9، jsdom)؛ بدون backend/BrsApi/DB زنده.

| فرمان | Passed | Failed | Skipped | Exit |
|---|---|---|---|---|
| `./node_modules/.bin/vitest run src/__tests__/useMarketData.test.tsx src/__tests__/apiEnvelope.test.ts src/__tests__/LiveDataBanner.test.tsx` | **33** | **0** | **0** | **0** |
| تفکیک: `useMarketData.test.tsx` | **10** | 0 | 0 | — |
| تفکیک: `apiEnvelope.test.ts` | **16** | 0 | 0 | — |
| تفکیک: `LiveDataBanner.test.tsx` | **7** | 0 | 0 | — |
| Baseline قبل از تست/فیکس بنر | 32 | 0 | 0 | 0 |
| `./node_modules/.bin/tsc --noEmit --pretty false` | — | **21 خطا** | — | **2** |

- **ادعای «۱۰/۱۵ passing به‌دلیل environment» بازتولید نشد:** فایل `useMarketData.test.tsx` ۱۰ تست دارد (نه ۱۵) و هر ۱۰ pass است؛ هیچ skip/fail محیطی مشاهده نشد.
- ۲۱ خطای `tsc` همه در کامپوننت‌های fund خارج از دامنه‌اند (`FundAnalysisModal`, `FundCompareModal`, `FundDetailDrawer`, `FundScorecardPanel`)؛ **هیچ خطایی در فایل‌های Phase 5** (`useMarketData`, `api-envelope`, `LiveDataBanner`, `heatmap/page`, `api.ts`, `useWebSocket`) وجود ندارد. این شکست typecheck پنهان نشده و به‌عنوان FE-16 ثبت شد.
- `npm test` کامل، `npm run build`، E2E مرورگر، و تست WS زنده اجرا نشدند.

### تست‌های اجرانشده و علت

| تست/بررسی | علت |
|---|---|
| کل مجموعهٔ vitest فرانت‌اند | فقط تست‌های مرتبط freshness/cache اجرا شد؛ اجرای کامل می‌تواند شامل محیط/سرویس‌های بیرونی باشد |
| `npm run build` / `tsc` سبز | typecheck فعلاً ۲۱ خطای خارج از دامنه دارد؛ build اجرا نشد |
| E2E مرورگر با backend واقعی | نیازمند backend/DB/BrsApi؛ ممنوع/در دسترس نبود |
| تست WebSocket (auth, resubscribe, stale) | زیرساخت mock WS و backend زنده فراهم نبود؛ تست موجود نیست |
| تست integration واقعی queryFn برای freshness | تست فعلی `useQuery` را mock می‌کند و مسیر queryFn heatmap را اجرا نمی‌کند |

---

## ۱۰. خطرات باقی‌مانده و وابستگی‌ها

1. **نمایش stale به‌عنوان live** تا زمانی که `isFresh` در render بازمحاسبه نشود و hookهای مشتق‌شده freshness را propagate نکنند.
2. **WebSocket بازار** بدون توکن handshake، بدون `as_of`/last-message، بدون resubscribe و با overwrite timestamp؛ ممکن است در production اصلاً وصل نشود یا ساکت بماند و LIVE نمایش داده شود.
3. **banner** بدون `hasData` نمی‌تواند stale را از empty جدا کند؛ بیشتر مصرف‌کننده‌ها `dataAsOf` نمی‌دهند.
4. **هوک‌های indices/news/quotes/global/treemap/flow** timestamp ندارند و `isLive=rows.length>0` است؛ برای رفع نیاز به `data_as_of` از بخش ۰۴ یا handoff صریح.
5. **`apiGet` throw سراسری** ممکن است رفتار endpointهای non-market با `success:false` را تغییر دهد؛ نیازمند تست/بازبینی قرارداد.
6. **دو کش موازی heatmap** با limitهای ۱۲۰ و ۵۰۰ باعث بار اضافی/داده ناسازگار می‌شود.
7. **typecheck قرمز** در فایل‌های fund خارج از دامنه؛ build/CI ممکن است شکست بخورد.
8. **هیچ تأیید زنده‌ای** برای WS/BrsApi/backend انجام نشد.

---

## ۱۱. معیارهای پذیرش و وضعیت

| معیار | وضعیت | شاهد |
|---|---|---|
| timestamp آینده/null/نامعتبر داده را live نشان ندهد | ⚠️ PARTIAL | `api-envelope` و `useEnrichedHeatmap` درست‌اند؛ ولی hookهای مشتق‌شده و banner بدون dataAsOf همچنان existence-based هستند |
| stale data از data-empty و source error متمایز باشد | ⚠️ PARTIAL | envelope/dataAsOf و banner اضافه شده؛ اما بیشتر مصرف‌کننده‌ها dataAsOf نمی‌دهند و `isLive=false` دلیل stale را حفظ نمی‌کند |
| تست‌های مرتبط نتیجهٔ واقعی و قابل‌تکرار داشته باشند | ✅ PASS برای ۳۳ تست مرتبط | ۳۳ pass، ۰ fail، ۰ skip؛ خروجی ثبت شد |
| typecheck/build سالم | ❌ FAIL (خارج دامنه) | `tsc --noEmit` → ۲۱ خطا (۰ در فایل‌های Phase 5) |
| WebSocket بدون نمایش پیام قدیمی به‌عنوان live | ❌ FAIL/PARTIAL | FE-03/FE-04/FE-05؛ نیازمند اصلاح |
| هیچ دادهٔ عملیاتی/secret لمس نشود | ✅ PASS | هیچ DB/BrsApi/secret استفاده نشد |

**نتیجهٔ نهایی: PARTIAL** — بخشی از قرارداد freshness (envelope، تست‌ها، timestamp UTC) انجام شده، اما جداسازی کامل `hasData/isFresh/isLive/isStale`، hookهای مشتق‌شده، WebSocket بازار و پوشش سایر ویجت‌ها باقی مانده است. مرحله کامل اعلام نمی‌شود.

---

## ۱۲. تأیید ادعاهای نشست/گزارش قبلی

| ادعا | نتیجه |
|---|---|
| شاخه `integration/golddesk-fixes`/HEAD `90597e05` | ✅ مستقل تأیید شد |
| ۱۵ تست `test_sync_log_repository.py` | ✅ ۱۵/۱۵ pass |
| `useMarketData.test.tsx` «۱۰/۱۵» | ❌ فایل ۱۰ تست دارد، ۱۰/۱۰ pass؛ ۱۵ تستی وجود ندارد |
| گارد future-date در `useMarketData.ts` (staged) | ✅ diff staged موجود است؛ اکنون با `api-envelope` جایگزین/تکمیل شده |
| گزارش‌های `AUDIT_BATCH_*`/`ROOT_CAUSE_VERIFICATION` | ❌ در worktree/index/history یافت نشدند |

---

## ۱۳. کارهای باقی‌مانده (دقیق)

1. `isFresh`/`isStale` را در render با یک clock/ticker (یا `useSyncExternalStore`) بازمحاسبه کنید؛ آن را در query data ذخیره نکنید.
2. `LiveDataResult` را به `hasData`، `isFresh`، `isLive`، `isStale` جدا کنید و همهٔ hookها را به آن منتقل کنید.
3. `useTickerItems`، `useTopStocks`، `useActiveSymbols`، `useTopPerformers`، `useIndexImpacts` را به freshness heatmap feed وصل کنید و تست‌های `dataAsOf:null` را اصلاح/تکمیل کنید.
4. `LiveDataBanner` را به `hasData`/`isStale` مستقل مجهز کنید؛ `dataAsOf` را از همهٔ مصرف‌کننده‌ها (IndexCards، TopStocksToday، QuoteCards، NewsStrip، …) پاس دهید تا stale از empty/error متمایز شود.
5. صفحه heatmap: freshness هر view را جدا کنید (heatmap و treemap)، `data_as_of` treemap را بخوانید، و `dataAsOf:null` را live حساب نکنید.
6. WebSocket بازار: توکن احراز هویت را به URL اضافه کنید، روی تغییر symbols `subscribe/unsubscribe` بفرستید، `as_of`/timestamp سرور را حفظ کنید (یا از backend بخواهید)، `lastMessageAt/stale` را نگه دارید، پیام‌های قدیمی/out-of-order را نادیده بگیرید.
7. صفحه gold: از `useGoldWS` (age/stale) یا ادغام وضعیت آن با `useMarketWebSocket` استفاده کند؛ برچسب LIVE فقط با دادهٔ تازه.
8. hookهای indices/news/quotes/global/treemap/flow: `data_as_of` از بک‌اند بگیرند (handoff بخش ۰۴) یا freshness را «نامعلوم» و نه live اعلام کنند.
9. `apiGet`/`assertSuccessEnvelope` را برای همهٔ endpointها (نه فقط مارکت) تست و مستند کنید؛ سیاست `success:false` با دادهٔ partial را مشخص کنید.
10. کش تکراری heatmap را یکپارچه کنید (query key/limit/staleTime) یا مستند کنید.
11. تست‌های integration queryFn (data_as_of/fetched_at آینده/null/کهنه) و تست‌های WS (auth/resubscribe/stale/out-of-order) اضافه کنید.
12. ۲۱ خطای typecheck خارج از دامنه را رفع یا build را مستند مسدود کنید؛ `npm run build` و مجموعهٔ کامل vitest را اجرا کنید.
13. برچسب‌های ثابت «زنده» در `gold-fx`/`silver` را به freshness واقعی گره بزنید یا برچسب را بردارید.
14. E2E با backend/داده واقعی (در صورت رفع محدودیت دسترسی) — فعلاً **BLOCKED**.

---

## ۱۴. فایل‌های ایجاد/تغییر‌یافته

**تغییر یافته:**
- `frontend/src/components/dashboard/LiveDataBanner.tsx` (fix timezone ساعت)
- `frontend/src/__tests__/LiveDataBanner.test.tsx` (تست naive UTC)

**ایجاد شده:**
- `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` (همین گزارش)

**تغییر نکرده/حفظ‌شده:** همهٔ تغییرات هم‌زمان قبلی `api-envelope.ts`، `useMarketData.ts`، `api.ts`، `heatmap/page.tsx`، `goldApi.ts`، تست‌ها، staged/untracked و `AUDIT_REPORTS` قبلی. بدون commit؛ HEAD `90597e05`.
