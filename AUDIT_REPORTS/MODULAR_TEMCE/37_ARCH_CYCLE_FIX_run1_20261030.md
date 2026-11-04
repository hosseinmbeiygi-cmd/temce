# ۳۷ — AUD-ARCH-01: حذف وارونگی `brsapi.services → apps.api` — run1، ۳۰ اکتبر ۲۰۲۶

**AUD-ARCH-01:** **PARTIAL** — چرخه‌ها از ۲۹ خام/۱۶ کانونیک به **۱۵ خام/۹ کانونیک**
کاهش یافت و همهٔ چرخه‌های `apps.api`/`brsapi.services` حذف شدند؛ ۹ چرخهٔ داخلی
`backtesting.*` باقی است.
تغییرات commit نشده‌اند.

---

## ۱) وارونگی لایه

`brsapi/services/sync_service.py` برای پاک‌کردن کش تجمیع، دو بار
`from apps.api.endpoints.market import invalidate_agg_cache` داشت (خطوط ۶۱۸ و ۲۰۳۹).
این وابستگی services → api، همراه با
`apps.api → apps.scheduler → jobs → jobs.definitions → brsapi.services`، چند چرخه می‌ساخت.

**اصلاح:** بخش لایه‌خنثیِ invalidation (تولید و انتشار توکن نسل در Redis) به
`core/agg_invalidation.py` منتقل شد:

- `AGG_TOKEN_KEY` / `AGG_TOKEN_TTL` / `new_agg_token()` / `publish_agg_token()`
- `market.py` همان ماژول را مصرف می‌کند (کش محلی و منطق خواندن توکن در API می‌ماند)؛
- `sync_service` مستقیم توکن جدید منتشر می‌کند و دیگر API را import نمی‌کند.

**نکتهٔ رفتاری:** اگر sync داخل فرایند API اجرا شود، پاک‌سازی محلی دیگر هم‌زمان نیست؛
فرایند API با دیدن توکن جدید (throttle ۵ ثانیه‌ای) کش را دور می‌ریزد. این همان پنجرهٔ
طراحی‌شدهٔ API-03 است و از TTL پنج‌دقیقه‌ای بسیار کوچک‌تر است.

---

## ۲) اثبات کاهش چرخه

| شاخص | قبل | بعد |
|---|---|---|
| ماژول‌های دو‌سطحی | ۱۴۶ | ۱۴۶ |
| چرخهٔ خام | ۲۹ | **۱۵** |
| چرخهٔ کانونیک | ۱۶ | **۹** |
| چرخهٔ شامل `brsapi.services` یا `apps.api` | ۵+ | **۰** |

۹ چرخهٔ باقی‌مانده همگی داخلی‌اند: `backtesting.engine/strategies/portfolio/market/orders/
microstructure` (نمونه: `backtesting.market → backtesting.engine → backtesting.market`).

---

## ۳) تست‌ها

| فایل | نتیجه |
|---|---|
| `tests/unit/api/test_market_dashboard_aggregates.py` | ۲۰ passed |
| `tests/unit/api/test_market_aggregate_cache.py` | passed |
| `tests/unit/api/test_market_aggregate_cache_cross_process.py` | passed (Redis reachable) |
| `tests/unit/test_sync_service_persistence_scope.py` | passed |
| مجموع | **۴۵ passed / ۱ skipped** |

**تغییر قرارداد تست (صریح):** دو تست در `test_sync_service_persistence_scope.py` قبلاً
`market.invalidate_agg_cache` را monkeypatch می‌کردند؛ حالا
`core.agg_invalidation.publish_agg_token` را patch می‌کنند. قرارداد («sync اسنپ‌شات باید
کش تجمیع را بی‌اعتبار کند؛ sync غیراسنپ‌شات نه») تغییر نکرده، فقط seam عوض شده است.

`market._AGG_TOKEN_TTL` نیز برای سازگاری با تست `token_outlives_the_cache_it_protects`
از `core.agg_invalidation` re-export شد.

---

## ۴) فایل‌ها

```
core/agg_invalidation.py            جدید (~۲۵ خط)
apps/api/endpoints/market.py        مصرف core؛ حذف تعریف محلی توکن/TTL
brsapi/services/sync_service.py     دو call site: انتشار توکن از core
tests/unit/test_sync_service_persistence_scope.py  seam جدید
```

## ۵) باقی‌مانده

- ۹ چرخهٔ داخلی `backtesting.*`؛ پیشنهاد اسلایس بعدی: انتقال قراردادهای مشترک
  (Order/ExecutionContext) به `backtesting/contracts.py` و شکستن
  `engine ↔ strategies/portfolio/market`.
- اعمال گارد CI (import-linter) بعد از رسیدن به صفر چرخه؛ افزودن dependency جدید نیاز
  به approval دارد.
- commit slice جاری: **BLOCKED** (درخت مشترک).
