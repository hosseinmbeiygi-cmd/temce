# ممیزی مستقل مرحله ۵ — فرانت‌اند/freshness/WebSocket (اجرای چهارم)

**مسیر این گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN4.md`  
**گزارش مرحله:** `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md`  
**گزارش‌های QA قبلی:** `QA_STAGE_5.md`، `QA_STAGE_5_RUN2.md`، `QA_STAGE_5_RUN3.md` — overwrite نشدند  
**تاریخ/زمان:** 2026-10-29 — 01:28 به وقت محلی (UTC+03:30)، 21:58 UTC  
**ریشهٔ مخزن:** `C:/Users/Iran/Desktop/temce`  
**شاخه:** `integration/golddesk-fixes`  
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)

**نتیجهٔ نهایی: PARTIAL** — freshness/render-time، hookهای مشتق‌شده، banner، WebSocket بازار و data_as_of مسیرهای اصلی اصلاح و تست شدند (فرانت ۵۵۶/۵۵۶، بک‌اند ۶۲/۶۲، tsc/build سبز)، اما `isLive` هنوز alias وجود داده است، چند endpoint بدون data_as_of باقی‌مانده‌اند و موارد DB/Redis/زنده BLOCKED هستند.

---

## ۱. مسیر گزارش و وجود فایل

| مورد | مسیر | وضعیت |
|---|---|---|
| گزارش مرحله | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_FRESHNESS_REALTIME.md` | ✅ موجود |
| QA این اجرا | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5_RUN4.md` | ✅ همین فایل |
| QAهای قبلی | `QA_STAGE_5.md`، `_RUN2.md`، `_RUN3.md` | ✅ دست‌نخورده |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD ابتدا/انتها | `90597e05...` → `90597e05...` (بدون commit) |
| staged قبلی | ۱۳۸ فایل؛ ۱۱۵٬۹۹۸ insert / ۱٬۴۴۷ delete — بدون تغییر |
| فایل حذف‌شده توسط این ممیزی | ۰ (`git status | grep '^ D'` خالی) |
| عملیات ممنوع | هیچ: بدون reset/clean/stash/checkout مخرب/commit |
| تغییرات این دور | فرانت: hooks/banner/components/WS/heatmap/gold/gold-fx؛ بک‌اند: market/brsapi/news/app/query/repo/layered؛ تست‌ها؛ همه unstaged/untracked روی staged قبلی |

---

## ۳. فایل‌های بررسی‌شده و بررسی‌نشده

### کامل خوانده شد

| فایل | نکته |
|---|---|
| `frontend/src/hooks/useMarketData.ts` | بخش‌های interface/helpers/همهٔ hookهای تغییریافته؛ ۸۴۳+ خط |
| `frontend/src/hooks/useWebSocket.ts` | کل |
| `frontend/src/components/dashboard/LiveDataBanner.tsx` | کل |
| `frontend/src/app/heatmap/page.tsx` | بخش query/banner/نمایش |
| `frontend/src/app/markets/gold/page.tsx` | بخش live/WS badge |
| `frontend/src/lib/api-envelope.ts` | کل |
| تست‌های `useMarketData`/`LiveDataBanner`/`useSymbolPrices`/`apiEnvelope` | کامل/اجرا |
| `apps/api/endpoints/market.py` | توابع latest و endpointهای تغییریافته |
| `apps/api/endpoints/brsapi.py` | endpointهای gold/currency/crypto/commodity |
| `apps/api/endpoints/news.py` | `_latest_published_at` و list_news |
| `apps/api/app.py` | `/cache-stats` |
| `brsapi/services/query_service.py` | `get_latest_indices`/`get_index_history` |
| `brsapi/repositories/base.py` | `bulk_insert`/`truncate` |
| `ingestion/storage/layered_pipeline.py` | `pipeline_store` |

### بخشی خوانده شد

| فایل | بخش |
|---|---|
| `frontend/src/hooks/useMarketData.ts` | endpointهای بدون timestamp (overview/events/ownership/value/flow) فقط سطحی |
| `apps/api/endpoints/news.py` | فقط list_news و helper |
| `apps/api/app.py` | فقط cache-stats |
| `brsapi/services/query_service.py` | فقط توابع index/latest مرتبط |
| `frontend/src/components/dashboard/*` | نقاط banner و empty-state |

### بررسی نشد

| مورد | دلیل |
|---|---|
| PostgreSQL/Redis/BrsApi زنده | ممنوع/بدون دسترسی |
| migrationها/DB واقعی | عملیات DB ممنوع؛ schema drift/viewهای materialized تأیید نشد |
| کل مجموعهٔ backend با `needs_db` | نیازمند PostgreSQL |
| E2E مرورگر | نیازمند backend/داده |
| `node_modules`/باینری | وابستگی/تولیدی |

---

## ۴. جدول الزام‌های پرامپت

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| 1 | مسیر گزارش و وجود فایل | بخش ۱ | **PASS** | — |
| 2 | فهرست فایل‌های بررسی‌شده/نشده | بخش ۳ | **PASS** | — |
| 3 | جدول الزام‌ها | همین جدول | **PASS** | — |
| 4 | برای هر اصلاح مسیر/diff/دلیل/تست | بخش ۶ | **PASS** | — |
| 5 | فرمان تست + نتیجهٔ واقعی | بخش ۷ | **PASS** | اجرای PG/Redis/E2E باقی است |
| 6 | حفظ staged/untracked؛ بدون commit | HEAD ثابت؛ ۱۳۸ staged؛ ۰ حذف | **PASS** | — |
| 7 | عدم درخواست زنده BrsApi/سرویس خارجی | هیچ کلاینت زنده اجرا نشد | **PASS (compliance)** | تأیید زنده **BLOCKED** |
| 8 | گزارش Markdown مستقل | همین فایل | **PASS** | — |
| 9 | وضعیت نهایی + کارهای باقی‌مانده | بخش ۱۰/۱۱ | **PARTIAL** | موارد BLOCKED/بک‌اند |
| 10 | timestamp آینده/null/نامعتبر live نشود | `api-envelope` ۱۶ تست؛ `useNow`/`isFresh/isStale`؛ banner unknown | **PARTIAL** | `isLive` هنوز alias وجود داده؛ چند endpoint بدون timestamp |
| 11 | stale/empty/error متمایز | `LiveDataBanner` ۹ تست؛ همهٔ مصرف‌کننده‌ها فیلدها را پاس می‌دهند | **PASS (offline)** | برای endpointهای بدون timestamp حالت «نامعلوم» است |
| 12 | WebSocket timestamp/subscription/reconnect/stale | `useSymbolPrices` ۷ تست؛ token/as_of/re-subscribe/stale | **PARTIAL** | بک‌اند WS هنوز `as_of` نمی‌فرستد |
| 13 | تست واقعی و قابل‌تکرار | فرانت ۵۵۶/۵۵۶؛ بک‌اند ۶۲/۶۲؛ tsc/build 0 | **PASS (offline)** | تست‌های PG/Redis/E2E اجرا نشدند |

---

## ۵. یافته‌های تأییدشده در برابر فرضیه‌ها

| ادعا | نتیجه | شاهد |
|---|---|---|
| `isFresh` در queryFn یخ می‌زد | ✅ رفع شد | `useNow` و محاسبه در render (`useMarketData.ts:170,389`) |
| hookهای مشتق‌شده freshness را نادیده می‌گرفتند | ✅ رفع شد | `useTickerItems`/`useTopStocks`/`useActiveSymbols`/`useTopPerformers`/`useIndexImpacts` از `hm.isFresh/isStale` استفاده می‌کنند |
| banner فقط با `isLive=true` stale را نشان می‌داد | ✅ رفع شد | `LiveDataBanner.tsx:41-78`؛ `hasData/isFresh/isStale` + unknown |
| همهٔ مصرف‌کننده‌ها متادیتای freshness را پاس می‌دهند | ✅ تأیید | grep: هیچ `LiveDataBanner state={{ isLive, isError, isLoading }}` باقی نمانده |
| WS بازار توکن handshake ندارد | ✅ رفع شد | `useWebSocket.ts:39-62` |
| WS timestamp سرور را overwrite می‌کند | ✅ رفع شد | `useWebSocket.ts:183` |
| WS stale/سبسکرایب مجدد ندارد | ✅ رفع شد | `useWebSocket.ts:85-101`؛ تست‌های ۶/۷ |
| صفحه gold با connected تنها LIVE می‌داد | ✅ رفع شد | `markets/gold/page.tsx:391-395` |
| `get_latest_indices` از created_at استفاده می‌کرد | ✅ رفع شد | `query_service.py:382-420` + تست جدید |
| endpointها data_as_of ندارند | ✅ برای indices/watch/brsapi/news/index-history اضافه شد | `market.py:36,108,529`؛ `brsapi.py:62+`؛ `news.py:36,209` |
| `market_dashboard`/economic-calendar/ownership/value-history data_as_of دارند | ❌ هنوز ندارند | frontend حالت «نامعلوم» نشان می‌دهد |
| ۱۰/۱۵ تست useMarketData | ❌ فایل ۱۳ تست دارد و ۱۳/۱۳ pass | اجرای واقعی |
| ۵۴۷/۵۴۸ تست فرانت | ❌ اجرای مستقل ۵۵۶/۵۵۶ | اجرای واقعی |

---

## ۶. اصلاحات: مسیر، diff، دلیل، تست

| # | مسیر | تغییر/دلیل | تست |
|---|---|---|---|
| F-1 | `frontend/src/hooks/useMarketData.ts:88-187` | `LiveDataResult` + `liveResult`/`envelopeResult`/`useNow`؛ `hasData/isFresh/isStale` و clock | `useMarketData.test.tsx` ۱۳ pass |
| F-2 | `useMarketData.ts:389+` | `useEnrichedHeatmap` عمومی، query key مشترک `["live-heatmap",500]`، حذف isFresh از query data | HTTP/UI + full suite |
| F-3 | `useMarketData.ts` hookهای مشتق/indices/news/quote/global/index-intraday | propagate freshness؛ خواندن data_as_of؛ unknown صادقانه | full suite |
| F-4 | `LiveDataBanner.tsx` | تفکیک fresh/stale/unknown/empty/error + `Banner` | ۹ تست |
| F-5 | `heatmap/page.tsx` | استفاده از hook مشترک، freshness جدا heatmap/treemap، حذف کش تکراری | full suite |
| F-6 | `useWebSocket.ts` | token handshake، timestamp سرور، `lastMessageAt/stale`، subscribe/unsubscribe اختلافی | `useSymbolPrices.test.ts` ۷ pass |
| F-7 | `markets/gold/page.tsx` | برچسب STALE برای سوکت باز ولی ساکت | full suite |
| F-8 | `markets/gold-fx/page.tsx` | حذف ادعای ثابت «بازار زنده» به «به‌روزرسانی خودکار» | — |
| F-9 | `brsapi/services/query_service.py:382-420` | `fetched_at` به‌جای `created_at` برای آخرین/تاریخچهٔ شاخص | `test_query_index_latest.py` ۲ pass |
| F-10 | `apps/api/endpoints/market.py` / `brsapi.py` / `news.py` | افزودن `data_as_of` و فیلد `error` به failureها | ۴۳ API pass |
| F-11 | `apps/api/app.py:1098+` | نمایش `_AGG_CACHE` در `/cache-stats` | — |
| F-12 | `brsapi/repositories/base.py` | dedupe کلید تکراری batch؛ `TRUNCATE` با opt-in محیطی | `test_bulk_upsert_repository.py` ۶ pass |
| F-13 | `ingestion/storage/layered_pipeline.py` | اصلاح شمارنده‌های dedup/hot/warm | — |
| F-14 | فایل‌های `Fund*` و `fund-analysis.ts` | فیلدهای optional + fallback؛ import `useMemo`؛ رفع ۲۱ خطای tsc | tsc 0؛ build 0 |

---

## ۷. تست‌ها — نتایج واقعی

| فرمان | Passed | Failed | Skipped | Exit |
|---|---|---|---|---|
| `frontend: ./node_modules/.bin/vitest run` | **556** (۵۷ فایل) | **0** | **0** | **0** |
| `frontend: tsc --noEmit` | — | **0** | — | **0** |
| `frontend: npm run build` | — | **0** | — | **0** (Compiled + 147/147) |
| `backend: pytest tests/unit/repositories/test_bulk_upsert_repository.py tests/unit/repositories/test_query_index_latest.py tests/unit/api/test_market_aggregate_cache.py tests/unit/api/test_market_dashboard_aggregates.py tests/unit/api/test_market_endpoint_contracts.py tests/unit/test_brsapi_sync_fixes.py` | **62** | **0** | 0 | **0** |
| `useMarketData.test.tsx` | **13** | 0 | 0 | 0 |
| `LiveDataBanner.test.tsx` | **9** | 0 | 0 | 0 |
| `useSymbolPrices.test.ts` | **7** | 0 | 0 | 0 |
| `apiEnvelope.test.ts` | **16** | 0 | 0 | 0 |

**اجرا نشده/موفق اعلام نمی‌شود:**
- تست‌های backend نیازمند PostgreSQL (`needs_db`)، Redis، و E2E مرورگر.
- تست زنده BrsApi/TSETMC.
- تأیید migration/DB واقعی، viewهای `mv_latest_*`/`vw_fund_symbols`، source-time و idempotency در `StorageLayer`.

---

## ۸. موارد BLOCKED

| مورد | مانع |
|---|---|
| تأیید DB واقعی/اجرای migration | PostgreSQL عملیاتی/تست در دسترس نیست؛ اجرای migration ممنوع |
| invalidate کش بین‌پروسه‌ای | Redis/pubsub/shared cache لازم است |
| WS واقعی و `as_of` بک‌اند | BrsApi/WS زنده و تغییر بک‌اند لازم است |
| E2E مرورگر | backend/داده زنده |
| viewهای latest/source-time/retention | migration و DB واقعی |

---

## ۹. کارهای باقی‌ماندهٔ دقیق

1. **semantics نهایی `isLive`:** اکنون alias وجود داده است (`isLive=hasData`). اگر قرارداد بخواهد `isLive ≡ hasData && isFresh` باشد، باید empty-stateهای `TripleChartsGroup`/سایر مصرف‌کننده‌ها به `hasData` منتقل شوند.
2. `data_as_of` برای `/market-dashboard`، `/economic-calendar`، `/market/flow-history`، `/market/value-history`، `/market/ownership-history` و ownership flows؛ فعلاً UI «نامعلوم» نشان می‌دهد.
3. `as_of` واقعی در پیام‌های WebSocket بازار از سمت بک‌اند.
4. invalidate کش بین‌پروسه‌ای/چند worker با Redis pub/sub یا shared cache.
5. migrationهای view (`mv_latest_brsapi_symbol_snapshot`، `vw_fund_symbols`) برای `fetched_at`؛ schema drift و orphan migration `brsapi/migrations/001`.
6. source-time/idempotency در `StorageLayer` (`_source_time`/`source_timestamp`) و جلوگیری از overwrite دادهٔ تازه‌تر در `daily_ohlcv`.
7. retention/کلید یکتا برای gold/currency/crypto و `market_snapshots`.
8. تست کامل backend با PostgreSQL/Redis و E2E مرورگر.
9. مستندسازی `ALLOW_TABLE_TRUNCATE=1` برای اسکریپت full-update و بررسی همهٔ callerهای `truncate`.
10. `apiGet`/`assertSuccessEnvelope` برای همهٔ endpointهای غیرمارکت (پوشش تست فعلی محدود است).
11. برچسب `داده زنده` در silver (و هر برچسب ثابت دیگر) یا گره زدن آن به timestamp.

---

## ۱۰. معیارهای پذیرش و نتیجه

| معیار | وضعیت |
|---|---|
| timestamp آینده/null/نامعتبر live نشود | ⚠️ PARTIAL — heatmap و endpointهای timestamp‌دار درست؛ `isLive` legacy و برخی hookها unknown |
| stale از empty و source error متمایز باشد | ✅ PASS (offline) — banner + تست‌ها |
| تست‌های مرتبط واقعی/قابل‌تکرار | ✅ PASS — ۵۵۶ فرانت، ۶۲ بک‌اند، tsc/build 0 |
| WebSocket پیام قدیمی را live نشان ندهد | ⚠️ PARTIAL — stale/`lastMessageAt`/timestamp سرور؛ `as_of` بک‌اند غایب |
| typecheck/build سالم | ✅ PASS |
| بدون DB/secret/commit | ✅ PASS |

**نتیجهٔ نهایی: PARTIAL** — مسیرهای اصلی frontend/freshness/WS و داده‌های timestamp‌دار اصلاح و تست شده‌اند، اما `isLive` legacy، endpointهای بدون data_as_of، `as_of` بک‌اند، و موارد DB/Redis/زنده باقی مانده‌اند. مرحله کامل/PASS اعلام نمی‌شود.

---

## ۱۱. تأیید ادعاهای قبلی

| ادعا | نتیجه |
|---|---|
| شاخه/HEAD `integration/golddesk-fixes` / `90597e05` | ✅ |
| ۱۵ تست sync-log | ✅ ۱۵/۱۵ |
| «useMarketData: ۱۰/۱۵» | ❌ ۱۳ تست، ۱۳/۱۳ pass |
| ۵۴۸ تست فرانت | ❌ ۵۵۶/۵۵۶ |
| tsc ۲۱ خطا | ❌ اکنون ۰ |
| build موفق | ✅ ۱۴۷/۱۴۷ |
| گزارش‌های old audit | ❌ یافت نشدند |
| staged/untracked حفظ شد | ✅ ۰ حذف، بدون commit |

---

## ۱۲. فایل‌های تغییر‌یافته/ایجادشده (این دور)

**Frontend:** `useMarketData.ts`، `useWebSocket.ts`، `LiveDataBanner.tsx`، `heatmap/page.tsx`، `markets/gold/page.tsx`، `markets/gold-fx/page.tsx`، ۱۲ کامپوننت dashboard، `Fund*`/`fund-analysis.ts`، تست‌های useMarketData/LiveDataBanner/useSymbolPrices.  
**Backend:** `apps/api/endpoints/market.py`، `brsapi.py`، `news.py`، `apps/api/app.py`، `brsapi/services/query_service.py`، `brsapi/repositories/base.py`، `ingestion/storage/layered_pipeline.py`.  
**Created:** `tests/unit/repositories/test_query_index_latest.py`، همین گزارش.  
**بدون commit؛ HEAD `90597e05`؛ staged/untracked قبلی حفظ شد؛ هیچ DB/BrsApi/secret استفاده نشد.**
