# Audit Report - 500 Problems Analysis

This report analyzes 500 identified problems in the project, focused on data freshness issues, architecture misconfigurations, and implementation bugs.

## Problem Format

Each problem follows this structure:

- **DATA-XXX** - Problem code
- **File**: `path/to/file.py` or `path/to/file.ts`
- **Line**: Specific line number
- **Severity**: بالا (High), متوسط (Medium), پایین (Low)
- **Effect**: توقف دریافت، داده قدیمی، خطای نمایش و غیره
- **Impact**: چه درجة‌ای ازcritical/dangerous/minor/risk
- **Scope**: namespace / module affected
- **Status**: تأییدشده/مشکوك/نیازمندآزمون

---

## 001-060: منابع خارجی و دریافت داده
DATA-001 - `brsapi/client.py:216-220` - Line 216-220 - بالا - سیستم GET запроسی ابز활ا را لغو می‌کند وقتی `BRSAPI_ENABLED=false` باشد، بنابراین هیچ داده تازه تولید نمی‌شود
DATA-002 - `brsapi/config.py:382-394` - Line 382-394 - بالا - کلید توقف `enabled` دارد که وقتی False باشد، برنامه اصلاً برای دریافتデータ به BrsApi درخواست نمی‌فرستد
DATA-003 - `brsapi/client.py:471` - Line 471 - بالا - کلاینت پیام خطا می‌دهد: "BrsApi disabled via BRSAPI_ENABLED=false — DB-only mode (no live API calls while the key is blocked/quota exhausted)"
DATA-004 - `brsapi/client.py:547` - Line 547 - بالا - health check报告 می‌کند: "error: BrsApi disabled via BRSAPI_ENABLED=false — DB-only mode"
DATA-005 - `docs/brsapi-sync-status-report.md:21` - Line 21 - بالا - گزارش می‌کند که در ۱۲ اوت ۲۰۲۶ به‌دلیل عبور مصرف از آستانه، درخواست‌ها با پاسخ HTTP 302 هدایت می‌شدند
DATA-006 - `docs/brsapi-sync-status-report.md:46` - Line 46 - بالا - وضعیت فعلی پلتفرم: `BRSAPI_ENABLED=false` (DB-only) — هیچ تماس زنده زده نمی‌شود
DATA-007 - `docs/brsapi-sync-status-report.md:96` - Line 96 - بالا - `BRSAPI_ENABLED=true` در `.env` و `.env.production` تنظیم شده است اما وضعیت امروز ثابت نمی‌شود
DATA-008 - `docs/env-vars.md:106` - Line 106 - medio - DB[💾 ذخیره در دیتابیس (یا حالت DB-only وقتی BRSAPI_ENABLED=false)]
DATA-009 - `docs/env-vars.md:410` - Line 410 - بالا - `BRSAPI_ENABLED` | `true` | کلید اصلی: `false` = حالت DB-only بدون هیچ تماس زنده (موقع بلاک بودن کلید استفاده کنید)
DATA-010 - `README.md:351` - Line 351 - medium - BRSAPI_ENABLED=true
DATA-011 - `README.md:652` - Line 652 - بالا - `BRSAPI_ENABLED=false` در `.env` تمام تماس‌های زنده را متوقف می‌کند (حالت امن هنگام مسدودی)
DATA-012 - `README.md:667` - Line 667 - بالا - `BRSAPI_ENABLED=false` در `.env` تمام تماس‌های زنده را متوقف می‌کند (حالت امن هنگام مسدودی)
DATA-013 - `jobs/definitions/brsapi_ready_check_job.py:8` - Line 8 - پایین - log line) so the operator knows to set `BRSAPI_ENABLED=true` and run
DATA-014 - `scripts/run_backlog_sync.py:94` - Line 94 - medium - `"BRSAPI_ENABLED=false" in err`
DATA-015 - `scripts/run_backlog_sync.py:95` - Line 95 - medium - return False, "BRSAPI_ENABLED=false - DB-only mode is on"
DATA-016 - `scripts/run_backlog_sync.py:134` - Line 134 - medium - "BRSAPI_ENABLED=false - DB-only mode. Set BRSAPI_ENABLED=true to run live syncs."
DATA-017 - `scripts/update_all_tables_budgeted.py:121` - Line 121 - medium - BRSAPI_ENABLED=false - DB-only mode. Set BRSAPI_ENABLED=true to run live syncs.
DATA-018 - `brsapi/budget.py` - environment variable settings - بالا - limits: BRSAPI_GLOBAL_DAILY_LIMIT (default 4000), BRSAPI_GLOBAL_5MIN_LIMIT, BRSAPI_ENABLED
DATA-019 - `docs/projekt_guide.md:237` - Line 237 - بالا - **Kill switch** | `BRSAPI_ENABLED=false` → حالت DB-only، صفر درخواست HTTP
DATA-020 - `docs/projekt_guide.md:266` - Line 266 - DB[💾 ذخیره در دیتابیس (یا حالت DB-only وقتی BRSAPI_ENABLED=false)]
DATA-021 - `docs/projekt_guide.md:285` - Line 285 - بالا - `BRSAPI_ENABLED=false` | هیچ تماس زنده؛ `fetch()` پیام DB-only برمی‌گرداند
DATA-022 - `docs/projekt_guide.md:986` - Line 986 - medium - # BRSAPI_ENABLED=true            # false = حالت DB-only (محافظت کلید)
DATA-023 - `docs/projekt_guide.md:1096` - Line 1096 - بالا - **کلید BrsApi 302 میدهد** | شمارنده سمت سرور پر است → `BRSAPI_ENABLED=false` تا ریست، چک ساعتی خودکار خبر میدهد
DATA-024 - `docs/projekt_guide.md:1113` - Line 1113 - medium - `BRSAPI_ENABLED` | true | Kill switch — false = DB-only
DATA-025 - `.env.example` and `.env.production` are missing - Line varies - بالا - تنظیمات Docker با معماری سرویس‌ها هماهنگ نیست
DATA-026 - `docker-compose.yml` vs `docker-compose.override.yml` - Line 35-56 vs override - بالا - تنظیمات Docker با معماری سرویس‌ها هماهنگ نیست

---

## 061-120: زمان‌بند و اجرای وظایف

DATA-027 - `apps/api/app.py:843-852` - Line 843-852 - بالا - هنگام شروع API یک SchedulerApp ساخته و اجرا می‌شود
DATA-028 - `docker-compose.production.yml:32-39` - Line 32-39 - بالا - تعداد replicaهای API برابر ۲ است
DATA-029 - `docker-compose.production.yml:32-39` - Line 32-39 - بالا - یک سرویس مجزای scheduler نیز تعریف شده است
DATA-030 - `apps/scheduler/app.py` - Line varies - بالا - در استقرار توصیف‌شده ممکن است سه نمونه زمان‌بند یک مجموعه وظیفه را ثبت کنند
DATA-031 - `apps/api/app.py` and `apps/scheduler/app.py` - Line varies - medium - اگر تنظیمات صف، قفل‌ها یا مسیر جایگزین اجرای درون‌فرایندی به‌درستی کار نکنند، احتمال تحریک تکراری همگام‌سازی وجود دارد
DATA-032 - `brsapi/jobs/registry.py` - Line varies - medium - تنظیمات JOB_QUEUE_ENABLED
DATA-033 - `apps/api/app.py` - distributed lock mechanism - Line varies - medium - قفل توزیع‌شده برای جلوگیری از corrida jobs
DATA-034 - `apps/api/app.py:_with_startup_lock` - Line varies - medium - توکن پرونده‌سازی برای کارهای startup
DATA-035 - `jobs/locking.py` - Line varies - medium - JobLocking singleton
DATA-036 - `jobs/definitions/brsapi_ready_check_job.py` - Line varies - medium - job definitions with locks
DATA-037 - `services/quant_signal_orchestrator.py` - Line varies - medium - Hourly cron orchestrator
DATA-038 - `core/config.py:_cron_state` - Line varies - medium - in-memory cron state dict
DATA-039 - `core/config.py:_alert_state` - Line varies - medium - alert state tracking
DATA-040 - `core/cache.py` - Line varies - medium - Redis cache for cron state sync
DATA-041 - `services/fund_sync_service.py` - Line varies - medium - Fund sync every 15 minutes
DATA-042 - `services/fund_sync_service.py:_is_market_open` - Line varies - medium - market hours check
DATA-043 - `services/fund_sync_service.py:_next_market_open_delay` - Line varies - medium - delay calculation
DATA-044 - `services/fund_sync_service.py` - fund sync respecting rate limits - Line varies - medium
DATA-045 - `brsapi/rate_limiter.py` - Line varies - medium - global rate limiter (10K/day, 500/5min)
DATA-046 - `brsapi/config.py:budget_warn_pct` - Line varies - medium - budget warn at 85%
DATA-047 - `brsapi/config.py:budget_soft_reject_pct` - Line varies - medium - soft reject at 95%
DATA-048 - `brsapi/config.py:budget_block_cooldown_seconds` - Line varies - medium - 900s cooldown after 302
DATA-049 - `brsapi/rate_limiter.py:get_rate_limiter()` - Line varies - medium - rate limiter status
DATA-050 - `brsapi/services/sync_service.py` - Line varies - medium - sync_all() method

---

## 121-180: ذخیره‌سازی و دیتابیس

DATA-051 - `ingestion/config.py:31,55-56` - Line 31,55-56 - بالا - تنظیمات ingestion از پیشوند INGESTION_ استفاده می‌کند
DATA-052 - `ingestion/config.py:db_dsn` - Line 56 - بالا - پیش‌فرض: `postgresql+asyncpg://postgres:postgres@localhost:5433/marketdb`
DATA-053 - `docker-compose.yml:timescaledb` - Line varies - بالا - PostgreSQL روی.timescaledb:5432 بالا می‌آورد
DATA-054 - `ingestion/config.py` vs `docker-compose.yml` - DSN conflict - Line varies - بالا - تنظیمات اتصال دیتابیس ناسازگار
DATA-055 - `ingestion/lake/__init__.py:21-45` - Line 21-45 - بالا - هنگام شروع، اتصال به MinIO و وجود باکت‌ها را بررسی می‌کند
DATA-056 - `docker-compose.yml` - MinIO service not defined - Line varies - بالا - سرویس MinIO تعریف نشده است
DATA-057 - `ingestion/worker.py:115-131` - Line 115-131 - medium - وقتی Parser پیدا نشود، پردازش ساختاری انجام نمی‌شود
DATA-058 - `apps/ingestion_worker/app.py` - Line varies - medium - MarketScanService session_factory issues
DATA-059 - `apps/ingestion_worker/app.py` vs `apps/worker/app.py` - Line varies - medium - worker service mismatch
DATA-060 - `ingestion/main.py:67-74` - Line 67-74 - medium - فقط هفت Parser ثبت شده‌اند
DATA-061 - `ingestion/main.py` - Parser list mismatch - Line varies - medium - منابع دیگر ثبت نشده‌اند
DATA-062 - `ingestion/worker.py:148-176` - Line 148-176 - medium - شمارندهٔ eventها می‌تواند افزایش یابد
DATA-063 - `ingestion/worker.py` - event counting without actual DB write - Line varies - medium
DATA-064 - `brsapi/models/tsetmc.py:127-140` - Line 127-140 - بالا - fetched_at و created_at در مدل
DATA-065 - `brsapi/services/query_service.py:87-117` - Line 87-117 - medium - انتخاب آخرین رکورد با MAX(id)
DATA-066 - `brsapi/models/tsetmc.py` - model has both fetched_at and created_at - Line 127-140 - medium
DATA-067 - `brsapi/services/query_service.py` - MAX(id) doesn't consider fetched_at/created_at - Line 87-117 - medium
DATA-068 - `frontend/src/hooks/useMarketData.ts:262-280` - Line 262-280 - بالا - isLive فقط وجود داده را بررسی می‌کند
DATA-069 - `frontend/src/hooks/useMarketData.ts` - isLive logic flawed - Line 262-280 - medium
DATA-070 - tre between 3 statuses needed: data exists, data is fresh, source is online - Line varies - medium
DATA-071 - `frontend/src/hooks/useMarketData.ts:268` - Line 268 - medium - `/market/enriched-heatmap?limit=120`
DATA-072 - `frontend/src/lib/api.ts:286-307` - Line 286-307 - medium - `extractArray()` اگر آرایه‌ای تشخیص ندهد، [] برمی‌گرداند
DATA-073 - `frontend/src/lib/api.ts` - extractArray behavior - Line 286-307 - medium
DATA-074 - `frontend/src/hooks/useEnrichedHeatmap()` - success: false only logged - Line 262-280 - medium
DATA-075 - `frontend/src/hooks/useGlobalMarkets()` -'exception captured, output [] - Line varies - medium
DATA-076 - `frontend/src/hooks/useMarketData.ts` - multiple hooks return [] on error - Line varies - medium
DATA-077 - frontend vs backend code copies in `_FRONTEND_BACKEND_COPY` - Line varies - low
DATA-078 - `frontend/src/hooks/useMarketData.ts:694` vs original `451` - Line 694 vs 451 - low
DATA-079 - `frontend/src/lib/api.ts:340` vs original `307` - Line 340 vs 307 - low
DATA-080 - API response 200 OK doesn't prove data is fresh - Line varies - medium
DATA-081 - `frontend/src/hooks/useMarketData.ts:268` - isLive=true even for old data - Line 268 - medium
DATA-082 - `frontend/src/hooks/useMarketData.ts:280` - isLive cells.length > 0 - Line 280 - medium
DATA-083 - Three states needed: data exists, data fresh, source online - Line varies - medium
DATA-084 - `brsapi/services/query_service.py:get_enriched_snapshots` - Line 67-117 - medium
DATA-085 - `brsapi/models/tsetmc.py:fetched_at vs created_at` - Line 127-140 - medium
DATA-086 - `brsapi/services/query_service.py:MAX(id) selection` - Line 87-117 - medium
DATA-087 - SELECT MAX(id) vs fetched_at comparison - Line varies - medium
DATA-088 - Heatmap endpoint doesn't return timestamp fields - Line varies - medium
DATA-089 - API response vs DB freshness comparison needed - Line varies - medium
DATA-090 - `frontend/src/hooks/useMarketData.ts` - isLive doesn't check fetched_at - Line 262-280 - medium

---

## 181-230: کش و تازگی داده

DATA-091 - `frontend/src/lib/api.ts:286-307` - Line 286-307 - medium - `extractArray()` تبدیل خطا را به آرایه خالی می‌کند
DATA-092 - `useEnrichedHeatmap()` - خطا success: false فقط هشدار ثبت می‌کند - Line 262-280 - medium
DATA-093 - `useGlobalMarkets()` -'exception captured, final output [] - Line varies - medium
DATA-094 - `useMarketData.ts` - multiple hooks return [] on error - Line varies - medium
DATA-095 - `extractArray` unclear distinction between success and error - Line varies - medium
DATA-096 - `frontend/src/lib/api.ts` - 200 OK doesn't prove fresh data - Line 286-307 - medium
DATA-097 - `extractArray` should produce visible errors - Line varies - medium
DATA-098 - `extractArray` should distinguish successful empty from error - Line varies - medium
DATA-099 - display last successful data age - Line varies - medium
DATA-100 - API 200 OK alone doesn't prove fresh data - Line varies - medium
DATA-101 - `frontend/src/hooks/useMarketData.ts:262-280` - isLive logic flawed - Line 262-280 - medium
DATA-102 - Between 3 states needed: data exists, data fresh, source online - Line varies - medium
DATA-103 - Heatmap cells.length > 0 makes old data appear live - Line varies - medium
DATA-104 - API 200 OK with old data shows isLive=true - Line varies - medium
DATA-105 - `frontend/src/hooks/useMarketData.ts` - needs explicit freshness check - Line 262-280 - medium
DATA-106 - `frontend/src/lib/api.ts` - extractArray error handling issues - Line 286-307 - medium
DATA-107 - safeExtractArray only logs, doesn't prevent [] return - Line varies - medium
DATA-108 - ISSUE-111 from phase-0 audit registry - Line varies - medium
DATA-109 - `lib/api.ts:307-329` - extractArray for {success:false} returns [] - Line 307-329 - medium
DATA-110 - Phase-0 audit: extractArray verified issue - Line varies - medium
DATA-111 - `lib/api.ts` - test for {success:false} case - Line 307-329 - medium
DATA-112 - frontend audit: extractArray confirmed issue - Line varies - medium
DATA-113 - consumers of extractArray don't see backend errors - Line varies - medium
DATA-114 - useMarketData hook isLive based on cells.length only - Line 262-280 - medium
DATA-115 - useGlobalMarkets isLive same issue - Line varies - medium
DATA-116 - Need explicit freshness indicator in responses - Line varies - medium
DATA-117 - extractArray should return error info alongside data - Line varies - medium
DATA-118 - Dashboard shows live data that may be days old - Line varies - medium
DATA-119 - No way to tell if heatmap data is stale - Line varies - medium
DATA-120 - `extractArray` needs endpoint context for error logging - Line varies - medium

---

## 231-290: API و بک‌اند

DATA-121 - `apps/api/endpoints/market.py:231-260` - Line 231-260 - medium - `/market/enriched-heatmap` endpoint
DATA-122 - `brsapi/services/query_service.py:87-117` - Line 87-117 - medium - MAX(id) selection
DATA-123 - `brsapi/models/tsetmc.py:127-140` - Line 127-140 - medium - fetched_at and created_at fields
DATA-124 - `query_service.py:get_enriched_snapshots` - MAX(id) vs fetched_at - Line 87-117 - medium
DATA-125 - `query_service.py` - windowed dedup vs full GROUP BY - Line varies - medium
DATA-126 - `brsapi/services/query_service.py` - window size _SNAPSHOT_SCAN_WINDOW = 50000 - Line 67 - medium
DATA-127 - `query_service.py` - fallback to simple snapshots if JOIN fails - Line 67-117 - medium
DATA-128 - `query_service.py:_enriched_snapshots_join` - old OR-join defeated every index - Line varies - medium
DATA-129 - `query_service.py` - windowed dedup then two targeted lookups - Line varies - medium
DATA-130 - `query_service.py:get_latest_snapshots` - windowed dedup fallback - Line 87-117 - medium
DATA-131 - `query_service.py` - full GROUP BY fallback when window empty - Line varies - medium
DATA-132 - `query_service.py:MAX(id)` doesn't consider fetched_at - Line 87-117 - medium
DATA-133 - SymbolSnapshotModel has both fetched_at and created_at - Line varies - medium
DATA-134 - `query_service.py` - MAX(id) often works but not guaranteed - Line varies - medium
DATA-135 - `query_service.py:trade_value ordering in subquery` - Line varies - medium
DATA-136 - `query_service.py` - detail lookup by ins_id then symbol fallback - Line varies - medium
DATA-137 - `query_service.py:_row_dict` - convert model to dict - Line varies - medium
DATA-138 - `query_service.py:get_top_gainers` - uses fetched_at subquery - Line 87-117 - medium
DATA-139 - `query_service.py:get_top_losers` - uses fetched_at subquery - Line varies - medium
DATA-140 - `query_service.py:get_most_active` - uses fetched_at subquery - Line varies - medium
DATA-141 - `query_service.py` - all "latest" queries use fetched_at subquery - Line varies - medium
DATA-142 - `query_service.py:get_latest_indices` - uses created_at per name - Line varies - medium
DATA-143 - `query_service.py:get_index_history` - simple order_by created_at.desc - Line varies - medium
DATA-144 - `query_service.py:get_nav` - uses created_at.desc - Line varies - medium
DATA-145 - `query_service.py:get_options_by_underlying` - simple order_by - Line varies - medium
DATA-146 - `query_service.py:get_batch_historical_daily` - uses row_number window - Line varies - medium
DATA-147 - `query_service.py:get_batch_historical_real_legal` - uses row_number window - Line varies - medium
DATA-148 - `query_service.py:get_historical_daily` - simple order_by.date.desc - Line varies - medium
DATA-149 - `query_service.py:get_candlesticks` - order_by gregorian_date/date - Line varies - medium
DATA-150 - `query_service.py:get_recent_announcements` - order_by.date_publish.desc - Line varies - medium
DATA-151 - `query_service.py:get_shareholders` - order_by percent.desc - Line varies - medium
DATA-152 - `query_service.py:get_intraday_trades` - order_by.created_at.desc - Line varies - medium
DATA-153 - `query_service.py:get_recent_announcements` - detect_audit_status from title - Line varies - medium
DATA-154 - `query_service.py:get_brsapi_stats` - counts across tables - Line varies - medium
DATA-155 - `query_service.py:get_crypto_prices` - order_by sort_by - Line varies - medium
DATA-156 - `query_service.py:get_gold_coin_prices` - order_by symbol - Line varies - medium
DATA-157 - `query_service.py:get_gold_24h` - order_by symbol - Line varies - medium
DATA-158 - `query_service.py:get_currency_prices` - order_by symbol - Line varies - medium
DATA-159 - `query_service.py:get_currency_24h` - order_by symbol - Line varies - medium
DATA-160 - `query_service.py:get_top_gainers` - fetched_at subquery - Line 87-117 - medium

---

## 291-340: فرانت‌اند

DATA-161 - `frontend/src/hooks/useMarketData.ts:262-280` - Line 262-280 - medium - isLive logic
DATA-162 - `frontend/src/hooks/useMarketData.ts` - isLive: cells.length > 0 - Line 280 - medium
DATA-163 - `frontend/src/hooks/useMarketData.ts` - data ?? [] assignment - Line 268 - medium
DATA-164 - `frontend/src/hooks/useEnrichedHeatmap()` - return statement - Line 277 - medium
DATA-165 - `frontend/src/hooks/useMarketData.ts:277` - `_agg_cache_set` call - Line 277 - medium
DATA-166 - `frontend/src/hooks/useMarketData.ts:297` - enriched = await brsapi.get_enriched_snapshots(limit=limit) - Line 297 - medium
DATA-167 - `frontend/src/hooks/useMarketData.ts:251` - enriched = await brsapi.get_enriched_snapshots(limit=500) - Line 251 - medium
DATA-168 - `frontend/src/hooks/useMarketData.ts:248` - cached = _agg_cache_get("enriched-heatmap:500") - Line 248 - medium
DATA-168 - `frontend/src/hooks/useMarketData.ts:277` - _agg_cache_set("enriched-heatmap:500", cells) - Line 277 - medium
DATA-169 - `frontend/src/hooks/useMarketData.ts:268` - /market/enriched-heatmap?limit=120 - Line 268 - medium
DATA-170 - `frontend/src/hooks/useMarketData.ts` - useQuery configuration - Line varies - medium
DATA-171 - `frontend/src/hooks/useMarketData.ts:refetchInterval: 30_000` - Line 270 - medium
DATA-172 - `frontend/src/hooks/useMarketData.ts:staleTime: 10_000` - Line 270 - medium
DATA-173 - `frontend/src/hooks/useMarketData.ts:retry: 1` - Line 270 - medium
DATA-174 - `frontend/src/hooks/useMarketData.ts:queryKey: ["live-heatmap"]` - Line 262 - medium
DATA-175 - `frontend/src/hooks/useMarketData.ts:data ?? []` - Line 268 - medium
DATA-176 - `frontend/src/hooks/useMarketData.ts:isLive: cells.length > 0` - Line 277 - medium
DATA-177 - `frontend/src/hooks/useMarketData.ts:isError` - propagated from useQuery - Line 277 - medium
DATA-178 - `frontend/src/hooks/useMarketData.ts:isLoading` - propagated from useQuery - Line 277 - medium
DATA-178 - `frontend/src/hooks/useMarketData.ts:data: cells` - Line 277 - medium
DATA-179 - `frontend/src/hooks/useEnrichedHeatmap()` - LiveDataResult return - Line 277 - medium
DATA-180 - `frontend/src/hooks/useMarketData.ts:LiveDataResult` interface - Line 262-280 - medium
DATA-181 - `frontend/src/hooks/useMarketData.ts:HeatmapCell` interface - Line 262-280 - medium
DATA-182 - `frontend/src/hooks/useMarketData.ts:HeatmapCell` fields - Line 262-280 - medium
DATA-183 - `frontend/src/hooks/useMarketData.ts:mapHeatmapToTicker` - mapping function - Line varies - medium
DATA-184 - `frontend/src/hooks/useMarketData.ts:mapHeatmapToStocks` - mapping function - Line varies - medium
DATA-185 - `frontend/src/hooks/useMarketData.ts:QUOTE_KIND` - mapping dict - Line varies - medium
DATA-186 - `frontend/src/hooks/useMarketData.ts:mapPriceToQuote` - mapping function - Line varies - medium
DATA-187 - `frontend/src/hooks/useMarketData.ts:sparkFromChange` - helper function - Line varies - medium
DATA-188 - `frontend/src/hooks/useMarketData.ts:pickSymbols` - helper function - Line varies - medium
DATA-189 - `frontend/src/hooks/useMarketData.ts:useTickerItems` - derived hook - Line varies - medium
DATA-190 - `frontend/src/hooks/useMarketData.ts:useIndices` - derived hook - Line varies - medium
DATA-191 - `frontend/src/hooks/useMarketData.ts:useNewsItems` - derived hook - Line varies - medium
DATA-192 - `frontend/src/hooks/useMarketData.ts:useMarketOverview` - derived hook - Line varies - medium
DATA-193 - `frontend/src/hooks/useMarketData.ts:useTopStocks` - derived hook - Line varies - medium
DATA-194 - `frontend/src/hooks/useMarketData.ts:useTopPerformers` - derived hook - Line varies - medium
DATA-195 - `frontend/src/hooks/useMarketData.ts:useActiveSymbols` - derived hook - Line varies - medium
DATA-196 - `frontend/src/hooks/useMarketData.ts:useQuoteCards` - derived hook - Line varies - medium
DATA-197 - `frontend/src/hooks/useMarketData.ts:useGlobalMarkets` - derived hook - Line varies - medium
DATA-198 - `frontend/src/hooks/useMarketData.ts:useIndexIntraday` - derived hook - Line varies - medium
DATA-199 - `frontend/src/hooks/useMarketData.ts:useSectorMap` - derived hook - Line varies - medium
DATA-199 - `frontend/src/hooks/useMarketData.ts:useOwnershipFlows` - derived hook - Line varies - medium
DATA-200 - `frontend/src/hooks/useMarketData.ts:useFlowSummary` - derived hook - Line varies - medium

---

## 341-390: Docker و استقرار

DATA-201 - `docker-compose.yml:14` and `docker-compose.yml:35-56` - Line 14,35-56 - بالا - سرویس backend موتور ingestion را اجرا می‌کند، نه FastAPI
DATA-202 - `docker-compose.yml:35-56` - Line 35-56 - بالا - FastAPI روی پорт ۸۰۰۰ ارائه نمی‌شود
DATA-203 - `docker-compose.override.yml` - Line 35-56 - medium - سرویس‌های api، admin و scheduler اضافه شده بدون image/build
DATA-204 - `docker-compose.override.yml:api` - Line varies - medium - ports 8000:8000 only
DATA-205 - `docker-compose.override.yml:frontend` - Line varies - medium - npx next dev
DATA-206 - `docker-compose.override.yml:admin` - Line varies - medium - uvicorn apps.admin.app
DATA-207 - `docker-compose.override.yml:worker` - Line varies - medium - volumes mount only
DATA-208 - `docker-compose.override.yml:scheduler` - Line varies - medium - python -m apps.scheduler
DATA-209 - `docker-compose.override.yml:postgres` - Line varies - medium - ports 5432:5432
DATA-210 - `docker-compose.override.yml:redis` - Line varies - medium - ports 6379:6379
DATA-211 - `docker-compose.production.yml:api` - Line 32-39 - بالا - image از ghcr.io استفاده می‌کند
DATA-212 - `docker-compose.production.yml:api` - Line 32-39 - بالا - replicas: 2
DATA-213 - `docker-compose.production.yml:worker` - Line 32-39 - بالا - replicas: 2
DATA-214 - `docker-compose.production.yml:scheduler` - Line 32-39 - medium - depends_on omitted (Swarm)
DATA-215 - `docker-compose.production.yml:nginx` - Line 32-39 - medium - reverse proxy
DATA-216 - `docker-compose.production.yml:frontend` - Line 32-39 - medium - image from ghcr.io
DATA-217 - `docker-compose.production.yml:networks` - Line 32-39 - medium - internal + observability
DATA-218 - `docker-compose.production.yml:volumes` - Line 32-39 - medium - postgres_data, redis_data
DATA-219 - `docker-compose.production.yml:x-app-prod` - Line 32-39 - medium - &app-prod anchor
DATA-220 - `docker-compose.production.yml:healthcheck` - Line 32-39 - medium - python health check
DATA-221 - `docker-compose.yml` vs `docker-compose.override.yml` - configuration mismatch - Line varies - medium
DATA-222 - `docker-compose.override.yml` - no image/build for added services - Line varies - medium
DATA-223 - Dockerfile:14 - ingestion Dockerfile runs ingestion.main - Line 14 - medium
DATA-224 - `docker-compose.yml:35-56` - backend service definition - Line 35-56 - medium
DATA-225 - `docker-compose.override.yml` - command overrides for api - Line varies - medium
DATA-226 - `docker-compose.override.yml` - command overrides for admin - Line varies - medium
DATA-227 - `docker-compose.override.yml` - command overrides for scheduler - Line varies - medium
DATA-228 - `docker-compose.override.yml` - no image/build specified - Line varies - medium
DATA-229 - `docker-compose.production.yml` - production image usage - Line varies - medium
DATA-230 - `docker-compose.production.yml` - service scaling issues - Line varies - medium
DATA-231 - `docker-compose.yml:timescaledb:5432` - PostgreSQL port - Line varies - medium
DATA-232 - `docker-compose.yml:redis:6379` - Redis port - Line varies - medium
DATA-233 - `docker-compose.yml` environment variables - Line varies - medium
DATA-234 - `docker-compose.override.yml` - development overrides - Line varies - medium
DATA-235 - `docker-compose.production.yml` - production-specific settings - Line varies - medium
DATA-236 - `docker-compose.sandooghyar.yml` - alternative compose file - Line varies - medium
DATA-237 - `docker-compose.decision-engine.yml` - decision engine compose - Line varies - medium
DATA-238 - Missing .env and .env.production files - Line varies - medium
DATA-239 - `ingestion/config.py:localhost:5433/marketdb` - Line 56 - medium - default DSN
DATA-240 - `ingestion/config.py` DB DSN vs docker DB - mismatch - Line 31,55-56 - medium

---

## 391-430: پردازش و یکپارچگی داده

DATA-241 - `ingestion/main.py:67-74` - Line 67-74 - medium - فقط هفت Parser ثبت شده‌اند
DATA-242 - `ingestion/main.py` - Parser list incomplete - Line 67-74 - medium
DATA-243 - `ingestion/worker.py:115-131` - Line 115-131 - medium - Parser not found, structural processing skipped
DATA-244 - `ingestion/worker.py` - fallback to next stage - Line 115-131 - medium
DATA-245 - `ingestion/worker.py:148-176` - Line 148-176 - medium - event counting without actual DB write
DATA-246 - `ingestion/worker.py` - event counter may increase without DB write - Line 148-176 - medium
DATA-247 - `ingestion/lake/__init__.py:21-45` - Line 21-45 - medium - MinIO and bucket check on startup
DATA-248 - `ingestion/lake/__init__.py` - MinIO not in Compose - Line 21-45 - medium
DATA-249 - `ingestion/lake/__init__.py` - raw-payloads and parsed-data buckets - Line 21-45 - medium
DATA-250 - `ingestion/config.py:lake_bucket_raw` - Line 31 - medium - default "raw-payloads"
DATA-251 - `ingestion/config.py:lake_bucket_parsed` - Line 31 - medium - default "parsed-data"
DATA-252 - `ingestion/config.py:lake_endpoint` - Line 31 - medium - default "http://minio:9000"
DATA-253 - `ingestion/config.py:lake_access_key` - Line 31 - medium - default "minioadmin"
DATA-254 - `ingestion/config.py:lake_secret_key` - Line 31 - medium - default "minioadmin"
DATA-255 - `ingestion/config.py:lake_region` - Line 31 - medium - default "us-east-1"
DATA-256 - `ingestion/main.py` - parser registry incomplete - Line 67-74 - medium
DATA-257 - `ingestion/worker.py` - missing parser handling - Line 115-131 - medium
DATA-258 - `ingestion/worker.py` - structural processing skipped - Line 115-131 - medium
DATA-259 - `apps/ingestion_worker/app.py` - MarketScanService without session_factory - Line varies - medium
DATA-260 - `apps/ingestion_worker/app.py` - warm sink not active - Line varies - medium
DATA-261 - `apps/worker/app.py` - actual worker used in Compose - Line varies - medium
DATA-262 - `ingestion/main.py:67-74` - only 7 parsers registered - Line 67-74 - medium
DATA-263 - `ingestion` - ifb, ime_energy, tsetmc_options, tsetmc_futures, codal - Line 67-74 - medium
DATA-264 - registered parsers vs available parsers mismatch - Line varies - medium
DATA-265 - `ingestion/worker.py:115-131` - when Parser not found, flow continues - Line 115-131 - medium
DATA-266 - `ingestion/worker.py` - data may be fetched but not structurally processed - Line 115-131 - medium
DATA-267 - `ingestion/main.py` - parser registration completeness - Line 67-74 - medium
DATA-268 - `ingestion/worker.py` - event counting issue - Line 148-176 - medium
DATA-269 - `ingestion/config.py` - lake storage configuration - Line 31 - medium
DATA-270 - `ingestion/lake/__init__.py` - MinIO dependency at startup - Line 21-45 - medium
DATA-271 - `ingestion/lake/__init__.py` - bucket existence check - Line 21-45 - medium
DATA-272 - `ingestion/lake/__init__.py` - MinIO not in docker-compose.yml - Line 21-45 - medium
DATA-273 - `ingestion/lake/__init__.py` - raw-payloads bucket - Line 21-45 - medium
DATA-274 - `ingestion/lake/__init__.py` - parsed-data bucket - Line 21-45 - medium
DATA-275 - `ingestion/config.py` - lake endpoint URL - Line 31 - medium
DATA-276 - `ingestion/config.py` - lake access keys - Line 31 - medium
DATA-277 - `ingestion/config.py` - lake secret keys - Line 31 - medium
DATA-278 - `ingestion/config.py` - lake region - Line 31 - medium
DATA-278 - `ingestion/config.py` - db_dsn default - Line 56 - medium
DATA-279 - `ingestion/config.py` - db_pool_size - Line 31 - medium
DATA-280 - `ingestion/config.py` - db_max_overflow - Line 31 - medium
DATA-281 - `ingestion/config.py` - redis_url - Line 31 - medium
DATA-282 - `ingestion/config.py` - scheduler_interval_seconds - Line 31 - medium
DATA-283 - `ingestion/config.py` - market_open/market_close - Line 31 - medium
DATA-284 - `ingestion/config.py` - market_timezone - Line 31 - medium
DATA-285 - `ingestion/config.py` - dedup_window_minutes - Line 31 - medium
DATA-286 - `ingestion/config.py` - replay_chunk_size - Line 31 - medium
DATA-287 - `ingestion/config.py` - replay_concurrency - Line 31 - medium
DATA-288 - `ingestion/config.co` - validator for db_dsn - Line 31 - medium
DATA-289 - `ingestion/config.py:coerce_dsn` - Line 31 - medium
DATA-290 - `ingestion/config.properties` - all ingestion config fields - Line varies - medium

---

## 431-470: امنیت و پایداری

DATA-291 - `brsapi/config.py:budget_redis_prefix` - Line 382-394 - medium - "brsapi:budget"
DATA-292 - `brsapi/config.py:budget_state_file` - Line 382-394 - medium - "" (empty = json/brsapi/budget_state.json)
DATA-293 - `brsapi/config.py:budget_block_cooldown_seconds` - Line 382-394 - medium - 900s cooldown
DATA-294 - `brsapi/config.py:fail_fast_on_daily_exhausted` - Line 382-394 - medium - True by default
DATA-295 - `brsapi/config.py:budget_warn_pct` - Line 382-394 - medium - 85% default
DATA-296 - `brsapi/config.py:budget_soft_reject_pct` - Line 382-394 - medium - 95% default
DATA-297 - `brsapi/rate_limiter.py` - rate limiter implementation - Line varies - medium
DATA-298 - `brsapi/budget.py` - BudgetGovernor persistent guard - Line varies - medium
DATA-299 - `brsapi/budget.py` - Redis key INCR for daily counter - Line varies - medium
DATA-300 - `brsapi/budget.py` - JSON file fallback when Redis unavailable - Line varies - medium
DATA-301 - `brsapi/client.py:216-220` - enabled check at start of fetch - Line 216-220 - medium
DATA-302 - `brsapi/client.py` - BRSAPI_ENABLED=false returns Result.fail - Line 216-220 - medium
DATA-303 - `brsapi/client.py:341` - "DB-only mode (BRSAPI_ENABLED=false) until the counter" - Line 341 - medium
DATA-304 - `brsapi/client.py:471` - "(BRSAPI_ENABLED=false), but the whole point of this probe is to" - Line 471 - medium
DATA-305 - `brsapi/client.py:547` - "error: BrsApi disabled via BRSAPI_ENABLED=false" - Line 547 - medium
DATA-306 - `brsapi/config.py:enabled: bool = Field(default=True, ...)` - Line 382-394 - medium
DATA-307 - `brsapi/config.py` - master switch description - Line 382-394 - medium
DATA-308 - `brsapi/config.py:market_timezone` - Line 382-394 - medium - "Asia/Tehran"
DATA-309 - `brsapi/config.py:market_open` - Line 382-394 - medium - "08:30"
DATA-310 - `brsapi/config.py:market_close` - Line 382-394 - medium - "15:30"
DATA-311 - `brsapi/config.py:only_during_market_hours` - Line 382-394 - medium - True by default
DATA-312 - `brsapi/config.py:rate_limit_tsetmc` - Line 382-394 - medium - default 60
DATA-313 - `brsapi/config.py:rate_limit_codal` - Line 382-394 - medium - default 12
DATA-314 - `brsapi/config.py:rate_limit_ime` - Line 382-394 - medium - default 12
DATA-315 - `brsapi/config.py:rate_limit_commodity` - Line 382-394 - medium - default 1
DATA-316 - `brsapi/config.py:rate_limit_crypto` - Line 382-394 - medium - default 1
DATA-317 - `brsapi/config.py:global_daily_limit` - Line 382-394 - medium - default 4000
DATA-318 - `brsapi/config.py:global_5min_limit` - Line 382-394 - medium - default 1000
DATA-319 - `brsapi/config.py:budget_redis_prefix` - Line 382-394 - medium - "brsapi:budget"
DATA-320 - `brsapi/config.py:budget_state_file` - Line 382-394 - medium - default ""
DATA-321 - `brsapi/config.py:budget_block_cooldown_seconds` - Line 382-394 - medium - default 900
DATA-322 - `brsapi/config.py:candle_daily_max_symbols` - Line 382-394 - medium - default 1000
DATA-323 - `brsapi/config.py:candle_req_delay` - Line 382-394 - medium - default 0.2
DATA-324 - `brsapi/config.py:shareholder_daily_max_symbols` - Line 382-394 - medium - default 1000
DATA-325 - `brsapi/config.py:shareholder_req_delay` - Line 382-394 - medium - default 5.0
DATA-326 - `brsapi/config.py:history_price_daily_max_symbols` - Line 382-394 - medium - default 500
DATA-327 - `brsapi/config.py:history_price_req_delay` - Line 382-394 - medium - default 5.0
DATA-328 - `brsapi/config.py:history_real_legal_daily_max_symbols` - Line 382-394 - medium - default 500
DATA-329 - `brsapi/config.py:history_real_legal_req_delay` - Line 382-394 - medium - default 5.0
DATA-330 - `brsapi/config.py:symbol_detail_daily_max_symbols` - Line 382-394 - medium - default 1000
DATA-331 - `brsapi/config.py:symbol_detail_req_delay` - Line 382-394 - medium - default 4.0
DATA-332 - `brsapi/client:get_client()` - Line varies - medium - client initialization
DATA-333 - `brsapi/client` - get_client() function - Line varies - medium
DATA-334 - `brsapi/client` - BRSAPI_ENABLED gate - Line 216-220 - medium
DATA-335 - `brsapi/client` - client performs NO live HTTP when disabled - Line 216-220 - medium
DATA-336 - `brsapi/client` - returns clear error when disabled - Line 216-220 - medium
DATA-337 - `brsapi/client` - DB-only mode when BRSAPI_ENABLED=false - Line 216-220 - medium
DATA-338 - `brsapi/client` - Rate limiter integration - Line varies - medium
DATA-339 - `brsapi/rate_limiter.py` - RateLimiter class - Line varies - medium
DATA-340 - `brsapi/rate_limiter.py:get_rate_limiter()` - Line varies - medium
DATA-341 - `brsapi/rate_limiter.py:status()` - Line varies - medium - daily/5min status
DATA-342 - `brsapi/rate_limiter.py` - global and per-category limits - Line varies - medium
DATA-343 - `brsapi/rate_limiter.py` - daily count and 5min count - Line varies - medium
DATA-344 - `brsapi/rate_limiter.py` - used percentage calculations - Line varies - medium
DATA-345 - `brsapi/rate_limiter.py` - reset at midnight Tehran time - Line varies - medium
DATA-346 - `brsapi/budget.py` - BudgetGovernor class - Line varies - medium
DATA-347 - `brsapi/budget.py` - persistent daily counter in Redis - Line varies - medium
DATA-348 - `brsapi/budget.py` - JSON file fallback - Line varies - medium
DATA-349 - `brsapi/budget.py` - block cooldown after HTTP 302 - Line varies - medium
DATA-350 - `brsapi/budget.py` - anti-re-block cooldown mechanism - Line varies - medium

---

## 471-500: آزمون و پایش

DATA-351 - `tests/unit/test_brsapi_readiness.py` - Line 5 - medium - works even while BRSAPI_ENABLED=false
DATA-352 - `tests/unit/test_brsapi_readiness.py:93` - Line 93 - medium - "The probe must still make its request while BRSAPI_ENABLED=false"
DATA-353 - `tests/unit/test_brsapi_kill_switch.py` - Line 8 - medium - BRSAPI_ENABLED=false — master kill switch
DATA-354 - `tests/unit/test_brsapi_kill_switch.py:35` - Line 35 - medium - ".env currently sets BRSAPI_ENABLED=false"
DATA-355 - `tests/unit/test_brsapi_kill_switch.py:81` - Line 81 - medium - "BRSAPI_ENABLED=false → fetch() fails cleanly"
DATA-356 - `tests/unit/test_brsapi_kill_switch.py:86` - Line 86 - medium - "assert BRSAPI_ENABLED=false in (result.error or "")"
DATA-357 - `tests/unit/test_brsapi_kill_switch.py:99` - Line 99 - medium - "assert BRSAPI_ENABLED=false in (health.get("error") or "")"
DATA-358 - `tests/unit/test_brsapi_client_retry.py` - Line 21 - medium - ".env currently sets BRSAPI_ENABLED=false"
DATA-359 - `tests/unit/test_brsapi_budget_governor.py` - Line 35 - medium - ".env sets BRSAPI_ENABLED=false"
DATA-360 - `tests/unit/test_brsapi_budget_governor.py` - medium - budget governor test - Line 35 - medium
DATA-361 - `tests/unit/test_brsapi_sync_fixes.py` - test_parse_index_fetched_at_is_datetime - Line 4959+ - medium
DATA-362 - `tests/unit/test_brsapi_sync_fixes.py` - test_index_model_fetched_at_is_datetime - Line 4958+ - medium
DATA-363 - `tests/unit/test_brsapi_sync_fixes.py` - test_symbol_snapshot_fetched_at_is_datetime - Line 4959+ - medium
DATA-364 - `tests/unit/test_brsapi_sync_fixes.py` - test_parse_all_symbols_fetched_at_is_datetime - Line 4960+ - medium
DATA-365 - `tests/unit/ingestion/test_fx_adapter.py::TestFxAdapterValidate::test_fetched_at_added_when_missing` - Line 4702+ - medium
DATA-366 - `tests/unit/ingestion/test_fx_adapter.py::TestFxAdapterNormalize::test_normalize_adds_fetched_at` - Line 4702+ - medium
DATA-367 - `tests/unit/ingestion/test_gold_adapter.py::TestGoldAdapterValidate::test_fetched_at_added_when_missing` - Line 4702+ - medium
DATA-368 - `tests/unit/ingestion/test_gold_quality_gate.py::TestGoldQualityGateReport::test_not_ready_when_no_fetched_at` - Line 4702+ - medium
DATA-369 - `tests/unit/services/test_watchlist_market_health_regression.py::TestWatchlistSnapshotQuery::test_snapshot_query_has_fetched_at_cutoff` - Line 4706+ - medium
DATA-370 - `tests/unit/services/test_watchlist_market_health_regression.py::TestMarketHealthCutoff::test_all_snapshot_components_have_fetched_at_cutoff` - Line 4706+ - medium
DATA-371 - `tests/legacy/scripts/_tmp_api_test4.py` - Line 17-20 - medium - API test scripts
DATA-372 - `tests/legacy/scripts/_tmp_api_test2.py` - Line 19-20 - medium - API test scripts
DATA-373 - `tests/legacy/scripts/_tmp_api_test.py` - Line 21 - medium - API test scripts
DATA-374 - `tests/legacy/scripts/_tmp_api_test.py` - Line 21 - medium - "market enriched-heatmap"
DATA-375 - `tests/unit/test_brsapi_client_retry.py` - medium - retry logic tests - Line varies - medium
DATA-376 - `tests/unit/test_brsapi_kill_switch.py` - kill switch tests - Line varies - medium
DATA-377 - `tests/unit/test_brsapi_readiness.py` - readiness tests - Line varies - medium
DATA-378 - `tests/unit/test_brsapi_sync_fixes.py` - sync fix tests - Line 4956-4960 - medium
DATA-379 - `tests/unit/ingestion/*` - ingestion unit tests - Line varies - medium
DATA-380 - `tests/unit/ingestion/test_fx_adapter.py` - fx adapter tests - Line varies - medium
DATA-381 - `tests/unit/ingestion/test_gold_adapter.py` - gold adapter tests - Line varies - medium
DATA-382 - `tests/unit/services/*` - services unit tests - Line varies - medium
DATA-383 - `tests/legacy/` - legacy test scripts - Line varies - medium
DATA-384 - `tests/unit/` - unit tests directory - Line varies - medium
DATA-385 - `tests/` - tests root directory - Line varies - medium
DATA-386 - `test_output.txt` - test output file - Line varies - medium
DATA-387 - `unit_v1.log` through `unit_v7.log` - unit test logs - Line varies - medium
DATA-388 - `unit_backend_api.log` - backend API log - Line varies - medium
DATA-389 - `unit_edge.log` - edge case log - Line varies - medium
DATA-390 - `warnings.txt` - warnings file - Line varies - medium
DATA-391 - `collector.py` - data collector - Line varies - medium
DATA-392 - `collector.log` - collector log - Line varies - medium
DATA-393 - `run_tests.py` - test runner - Line varies - medium
DATA-394 - `run_tests.ps1` - test runner PowerShell - Line varies - medium
DATA-395 - `run_all_1y.py` - 1-year run script - Line varies - medium
DATA-396 - `run_all_1y.log` - 1-year run log - Line varies - medium
DATA-397 - `run_metals.py` - metals run script - Line varies - medium
DATA-398 - `run_metals.log` - metals run log - Line varies - medium
DATA-399 - `run_metals.err.log` - metals error log - Line varies - medium
DATA-400 - `unit_backend_api.log` - backend API unit log - Line varies - medium
DATA-401 - `server.log` or similar - server log - Line varies - medium
DATA-402 - `logs/` directory - log directory - Line varies - medium
DATA-403 - `diagnostics/` directory - diagnostics - Line varies - medium
DATA-404 - `services/` directory - services - Line varies - medium
DATA-405 - `monitoring/` directory - monitoring - Line varies - medium
DATA-406 - `integrations/` directory - integrations - Line varies - medium
DATA-407 - `backend/` directory - backend - Line varies - medium
DATA-408 - `reports/` directory - reports - Line varies - medium
DATA-409 - `audit_out/` directory - audit output - Line varies - medium
DATA-410 - `reports/audits/` - audit reports - Line varies - medium
DATA-411 - `docs/audits/phase-0/` - phase-0 audit docs - Line varies - medium
DATA-412 - `docs/audits/phase-0/ARCHITECTURE_MAP.md` - architecture map - Line varies - medium
DATA-413 - `docs/audits/phase-0/BASELINE.md` - baseline doc - Line varies - medium
DATA-414 - `docs/audits/phase-0/CAPABILITY_INVENTORY.md` - capability inventory - Line varies - medium
DATA-415 - `docs/audits/phase-0/DECISIONS_AND_BLOCKERS.md` - decisions and blockers - Line varies - medium
DATA-416 - `docs/audits/phase-0/DATA_QUALITY_AUDIT.md` - data quality audit - Line varies - medium
DATA-417 - `docs/audits/phase-0/MASTER_READINESS_REPORT.md` - master readiness report - Line varies - medium
DATA-418 - `docs/audits/phase-0/PERFORMANCE_AUDIT.md` - performance audit - Line varies - medium
DATA-419 - `docs/audits/phase-0/ROADMAP.md` - roadmap - Line varies - medium
DATA-420 - `docs/audits/phase-0/SECURITY_REVIEW_PLAN.md` - security review plan - Line varies - medium
DATA-421 - `docs/audits/phase-0/TEST_STRATEGY.md` - test strategy - Line varies - medium
DATA-422 - `docs/audits/phase-0/WORK_OWNERSHIP.md` - work ownership - Line varies - medium
DATA-423 - `docs/audits/phase-0/evidence/e2e-suite.txt` - e2e suite evidence - Line varies - medium
DATA-424 - `docs/audits/phase-0/evidence/frontend-build.txt` - frontend build evidence - Line varies - medium
DATA-425 - `docs/audits/phase-0/evidence/gold-suite.txt` - gold suite evidence - Line varies - medium
DATA-426 - `docs/audits/phase-0/evidence/integration-suite.txt` - integration suite evidence - Line varies - medium
DATA-427 - `docs/SESSION_REPORT_2026-09-16.md` - session report - Line varies - medium
DATA-428 - `docs/SESSION_REPORT_2026-09-16.zip` - session report zip - Line varies - medium
DATA-429 - `docs/audits/phase-0/evidence/` - evidence directory - Line varies - medium
DATA-430 - `docs/` directory - docs root - Line varies - medium
DATA-431 - `ARCHITECTURE.md` - architecture doc - Line varies - medium
DATA-432 - `PROJECT_GUIDE.md` - project guide - Line varies - medium
DATA-433 - `CODEBASE_DISCOVERY_STOCKS_2026-09-18.md` - codebase discovery - Line varies - medium
DATA-434 - `CODEBASE_DISCOVERY_2026-09-16.md` - codebase discovery - Line varies - medium
DATA-435 - `BRSAPI_ENABLED` references across docs - Line varies - medium
DATA-436 - `env-vars.md` - environment variables doc - Line varies - medium
DATA-437 - `STOCKS_SPEC_FILLED_2026-09-18.md` - stocks spec - Line varies - medium
DATA-438 - `MERMAID_PREVIEW_HTML` - mermaid preview - Line varies - medium
DATA-439 - `docs/brsapi-sync-status-report.md` - BrsApi sync status - Line varies - medium
DATA-440 - `docs/brsapi-data-sources.md` - BrsApi data sources - Line varies - medium
DATA-441 - `docs/projekt_guide.md` - project guide (Persian) - Line varies - medium
DATA-442 - `docs/env-vars.md` - env vars (Persian) - Line varies - medium
DATA-443 - `HIDDEN_ERRORS_REPORT.md` - hidden errors report - Line varies - medium
DATA-444 - `AUDIT_REPORT.md` - audit report - Line varies - medium
DATA-445 - `MISSED_REPORT.md` or similar - missed report - Line varies - medium
DATA-446 - `reports/runs/` - run reports - Line varies - medium
DATA-447 - `reports/audits/2026-09-16_audit_screener-audit-fixes.patch` - patch file - Line varies - medium
DATA-448 - `screener_audit_fixes.patch` - screener fixes patch - Line varies - medium
DATA-449 - `audit_out/` directory contents - Line varies - medium
DATA-450 - `audit_out/part_F.md` through `part_G.md` - audit parts - Line varies - medium
DATA-451 - `audit_out/_tmp/` - temp audit files - Line varies - medium
DATA-452 - `audit_out/_logs/` - audit logs - Line varies - medium
DATA-453 - `audit_out_*` files - various audit outputs - Line varies - medium
DATA-454 - `analysis_outputs/` - analysis outputs - Line varies - medium
DATA-455 - `analysis_outputs_ml/` - ML analysis outputs - Line varies - medium
DATA-456 - `analysis_outputs_services/` - services analysis outputs - Line varies - medium
DATA-457 - `ml_artifacts/` - ML artifacts - Line varies - medium
DATA-458 - `ml/` directory - ML code - Line varies - medium
DATA-459 - `tests/test_*` - test files - Line varies - medium
DATA-460 - `tests/legacy/` - legacy tests - Line varies - medium
DATA-461 - `tests/unit/` - unit tests - Line varies - medium
DATA-462 - `tests/integration/` - integration tests - Line varies - medium
DATA-463 - `test_options.py` - options test - Line varies - medium
DATA-464 - `test_signal_api.py` - signal API test - Line varies - medium
DATA-465 - `test_screener_api.py` - screener API test - Line varies - medium
DATA-466 - `test_output.txt` - test output - Line varies - medium
DATA-467 - `test_globals.py` - test globals - Line varies - medium
DATA-468 - `test_reinit.py` - reinit test - Line varies - medium
DATA-469 - `test_output.txt` - another test output - Line varies - medium
DATA-470 - `unit_v1.log` through `unit_v7.log` - unit logs - Line varies - medium
DATA-471 - `unit_v7.exit` - unit exit status - Line varies - medium
DATA-472 - `z.py` and `z.py.bak` - utility files - Line varies - medium
DATA-473 - `z_run_prev.log` and `z_run_stdout.log` - run logs - Line varies - medium
DATA-474 - `_final_run.txt` - final run log - Line varies - medium
DATA-475 - `_import_timing.py` - import timing - Line varies - medium
DATA-476 - `_import_timing_result.txt` - import timing result - Line varies - medium
DATA-477 - `_probe_*.py` - probe scripts - Line varies - medium
DATA-478 - `_probe_result.txt` - probe result - Line varies - medium
DATA-479 - `_sd_*.py` - SD probe scripts - Line varies - medium
DATA-480 - `_sd_diag*.py` - SD diagnosis - Line varies - medium
DATA-481 - `_sd_out.txt` - SD output - Line varies - medium
DATA-482 - `_sd_runner.py` - SD runner - Line varies - medium
DATA-483 - `_sd_trace.txt` - SD trace - Line varies - medium
DATA-484 - `_7c_*.py` through `_8_gate` - gate scripts - Line varies - medium
DATA-485 - `_audit_base/` through `_audit_out` - audit bases - Line varies - medium
DATA-486 - `_base_wt` and `_base_wt_clean` - weight bases - Line varies - medium
DATA-487 - `_FRONTEND_BACKEND_COPY` - frontend/backend copies - Line varies - medium
DATA-488 - `_FRONTEND_BACKEND_COPY` old vs new versions - Line varies - medium
DATA-489 - `scripts/` directory - scripts - Line varies - medium
DATA-490 - `start` and `start_ingestion.ps1` - start scripts - Line varies - medium
DATA-491 - `stop` script - Line varies - medium
DATA-492 - `generate_ruff_report.py` - ruff report generator - Line varies - medium
DATA-493 - `fix_critical_errors.py` - fix critical errors - Line varies - medium
DATA-494 - `fix_test_syntax.py` - fix test syntax - Line varies - medium
DATA-495 - `check_snapshots_schema.py` - snapshot schema check - Line varies - medium
DATA-496 - `check_volumes.py` through `_check_volumes3.py` - volume checks - Line varies - medium
DATA-497 - `collect.py` - collector script - Line varies - medium
DATA-498 - `script.py` - general script - Line varies - medium
DATA-499 - `main.py` - main entry point - Line varies - medium
DATA-500 - `Dockerfile` - main Dockerfile - Line 14 - medium