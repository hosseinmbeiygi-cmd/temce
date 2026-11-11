# مرحلهٔ ۵ — API/Cache: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: API-03 (کش بین‌فرایندی)، API-05 (تصمیم mount/حذف)، `stocks_v2` بدون `data_as_of`.
هیچ سرویس زنده/DB لمس نشد؛ Redis محلی با اعتبارنامهٔ پیکربندی‌شده احراز هویت نکرد (پایین را ببینید).

---

## ۱) API-03 — invalidation بین‌فرایندی

**قبل:** `_AGG_CACHE` یک dict درون‌فرایندی با TTL=۳۰۰s بود. `invalidate_agg_cache()` از
`brsapi/services/sync_service.py:618,2041` در container سینک صدا زده می‌شد و فقط همان
process را خالی می‌کرد؛ API workerهای دیگر تا پایان TTL snapshot قدیمی را سرو می‌کردند.

**بعد:** یک توکن نسل در L2 نگه داشته می‌شود (`agg:cache_token`، TTL=۲۴h):
- `invalidate_agg_cache()` کش محلی را پاک می‌کند، توکن تازه می‌سازد و انتشار آن را روی loop
  جاری schedule می‌کند (`publish_agg_invalidation`, با strong-reference تا GC نشود).
- `_agg_cache_get()` حداکثر هر `_AGG_TOKEN_CHECK_INTERVAL=5s` یک‌بار توکن L2 را می‌خواند؛
  اگر با توکن محلی فرق داشت، کل کش محلی دور ریخته می‌شود.
- Redis در دسترس نباشد: فقط TTL محلی حاکم است؛ هیچ درخواستی fail نمی‌شود و تأخیر اضافه
  تحمیل نمی‌شود (تلاش خواندن هم throttle می‌شود).

**باند خطا:** بدترین حالت (L2 سالم، invalidation گم‌شده) = حداکثر ۵ ثانیه کهنه، به‌جای ۳۰۰ ثانیه.
اگر L2 در دسترس نباشد، همان ۳۰۰ ثانیه قبلی است (رفتار fallback، نه رگرسیون).

**تست‌ها** (`tests/unit/api/test_market_aggregate_cache_cross_process.py` — ۸ passed، ۱ skipped):
| تست | ادعا |
|---|---|
| `test_invalidate_publishes_a_generation_token` | invalidation توکن را در L2 می‌نویسد |
| `test_a_foreign_token_drops_this_process_copy` | دیدن توکن دیگران ⇒ دور ریختن کش محلی |
| `test_own_token_keeps_the_cached_value` | توکن خودی کش را باطل نمی‌کند |
| `test_token_checks_are_throttled_per_process` | یک خواندن L2 در هر بازه؛ بعد از بازه توکن جدید اثر می‌کند |
| `test_redis_down_degrades_to_local_ttl` | L2 خراب ⇒ کش گرم سرو می‌شود |
| `test_endpoint_refetches_after_a_foreign_invalidation` | `/market/asset-allocation`: cache_hit دوم، سپس miss بعد از invalidate خارجی |
| `test_real_redis_invalidation_reaches_the_other_instance` | دو نسخهٔ مستقل ماژول + Redis واقعی (در این محیط **skip**) |

**BLOCKED (محیط):** Redis محلی روی `localhost:6379` بالا است اما اعتبارنامهٔ
`settings.redis_url` را رد می‌کند (`AuthenticationError`). برای اثبات دو-فرایندی واقعی،
یک Redis در دسترس با همان DSN لازم است؛ تست مزبور به‌صورت خودکار skip می‌شود و با
Redis سالم اجرا می‌شود. تا آن زمان، اثبات با L2 جعلی (تست‌های بالا) پابرجاست.

**نکتهٔ سازگاری:** `invalidate_agg_cache()` هم‌زمان sync ماند؛ تست‌های موجود
(`tests/unit/test_sync_service_persistence_scope.py` — ۷ passed) که آن را monkeypatch
می‌کنند و تست‌های cache محلی (`test_market_aggregate_cache.py` — ۱۰ passed) دست‌نخورده سبزند.

## ۲) API-05 — تصمیم mount/حذف

طبقه‌بندی (گزارش ۲۶، commit `fc51c74b`) بازبینی و تصمیم ثبت شد: **هیچ‌کدام mount نمی‌شوند**؛
هیچ فایلی هم حذف نمی‌شود (حذف کد نیازمند تأیید مالک است).

| ماژول | حکم | دلیل |
|---|---|---|
| monitoring | unmounted | هیچ scrape هدف‌گیری وجود ندارد؛ mount بدون احراز هویت `/metrics` و `/data-quality` را افشا می‌کند |
| scanner | unmounted | POST پرهزینه و بدون مصرف‌کننده؛ سرویس از مسیر mount‌شدهٔ backtests استفاده می‌شود |
| ime | unmounted | تکرار read-only سطح `/gold/ime` که mount است؛ بقیهٔ مسیرها مصرف‌کننده ندارند |
| comprehensive_analysis | unmounted | هم‌پوشان با `/analysis/overview` |
| symbol_alerts | unmounted | زیرسیستم فقط از همین router در دسترس؛ معادل زندهٔ owner-scoped: `/alerts` |
| proposals | unmounted | زیرسیستم مرده (فقط از همین router) |
| sentiment | unmounted | زیرسیستم مرده (فقط از همین router) |

**قفل تصمیم:** `tests/unit/api/test_api05_mount_decisions.py` (۳ تست):
وجود ماژول‌ها، عدم mount آن‌ها، و ارجاع متقابل بلوک تصمیم در `apps/api/router.py`.
هر mount آیندهٔ یکی از این‌ها تست را می‌شکند تا دلیل تصمیم به‌روز شود.
شرط بازبینی برای هر ماژول در docstring تست آمده است (مصرف‌کنندهٔ واقعی + نقش/احراز هویت).

**تست‌ها:** `test_api05_mount_decisions.py` + `test_api_router_surface_inventory.py` = ۱۱ passed.

## ۳) `stocks_v2` و `data_as_of`

در working tree همهٔ ۱۱ مسیر `apps/api/endpoints/stocks_v2.py` (tape, indicators, signal,
peers, dossier, codal, news, history, CSV, volume-profile, market-pulse, monitoring)
`data_as_of` می‌دهند — مقدار واقعی یا `None` صریح. `tests/unit/api/test_stocks_v2_freshness_envelope.py`
۱۱ تست سبز دارد. **این تغییر از عامل هم‌زمان است (uncommitted) و توسط این نشست فقط تأیید شده،
نه نوشته شده.**

## ۴) اجرای تست

| مجموعه | نتیجه |
|---|---|
| `tests/unit/api/test_market_aggregate_cache_cross_process.py` | ۸ passed، ۱ skipped (Redis auth) |
| `tests/unit/api/test_market_aggregate_cache.py` (مال عامل هم‌زمان) | ۱۰ passed |
| `tests/unit/api/test_api05_mount_decisions.py` + `test_api_router_surface_inventory.py` | ۱۱ passed |
| `tests/unit/test_sync_service_persistence_scope.py` | ۷ passed |
| `tests/unit/api` (کل) | ۳۴۲ passed، ۶ skipped، ۷ failed |

۷ شکست `tests/unit/api` همگی «Cannot connect to PostgreSQL database at localhost:5432/market»
هستند (`test_gold_derivatives_endpoints.py`، `test_gold_personal_surface_auth.py`) — همان
TEST-01 شناخته‌شده (تست HTTP بدون marker `needs_db`)؛ ربطی به این برش ندارند.

**محدودیت‌ها:** اثبات با Redis واقعی skip شد (اعتبارنامه)؛ مرورگر/E2E اجرا نشد؛ هیچ
endpoint جدیدی mount/حذف نشد؛ توکن به‌صورت fire-and-forget منتشر می‌شود (اگر process
بلافاصله پس از sync بمیرد، انتشار از دست می‌رود و باند ۵ثانیه‌ای به TTL برمی‌گردد).
