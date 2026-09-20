# Runbook — کاناری rollout فلگ خواندن اخبار (`NEWS_READ_FROM_ITEMS`)

> پیاده‌سازی: `services/news_read_canary.py` · سیم‌کشی: `repositories/news_repository.py`
> وضعیت تست: ۱۶/۱۶ (`tests/unit/services/test_news_read_canary.py`) روی Postgres واقعی
> تاریخ: ۲۰۲۶-۰۹-۲۰

## ۱. چرا کاناری و نه یک فلگ ساده؟

سوییچ read path از `news_articles` (legacy) به `news_items` (migration 0054) یک تغییر **نقشه‌خوانی** است: اشکال می‌تواند به‌صورت «نتایج کم/بیشتر، ترتیب متفاوت» بروز کند نه فقط 500. پس رول‌اوت باید سه ویژگی داشته باشد:

1. **مقایسه زنده (shadow)** — تا وقتی فلگ روشن نیست، هر پاسخ legacy به‌صورت بی‌صدا روی اسکیمای جدید هم محاسبه و مقایسه می‌شود.
2. **برش تدریجی (canary)** — درصدی از ترافیک (hash پایدار، نه تصادفی) از اسکیمای جدید سرو می‌شود.
3. **توقف خودکار (auto-halt)** — اگر parity از آستانه پایین‌تر بیاید، هر ورکر خودش به `off` برمی‌گردد.

نوشتن همیشه به هر دو اسکیمای ادامه دارد (dual-write)، پس هر برگشت داده‌ای امن است.

## ۲. پیمانه مد — چهار حالت

| مد | چه کسی سرو می‌کند | shadow probe | کاربرد |
|----|-------------------|--------------|--------|
| `off` (پیش‌فرض) | legacy فقط | ❌ | وضعیت امروز |
| `shadow` | legacy فقط | ✅ هر درخواست | جمع‌آوری شواهد parity با صفر ریسک کاربر |
| `canary` | برش `NEWS_READ_CANARY_PERCENT`٪ از اسکیمای جدید، بقیه legacy | ✅ روی باقی‌مانده | رول‌اوت تدریجی |
| `full` | فقط اسکیمای جدید | ❌ | پایان رول‌اوت |

اولویت تشخیص مد (در `resolve_mode`):

```
Redis halt key  →  NEWS_READ_FROM_ITEMS=true (legacy bool ⇒ full)
→  Redis mode key (dial ران‌تایم، همه ورکرها)  →  NEWS_READ_MODE (پیش‌فرض دیپلوی)
```

بدون Redis: شمارنده‌ها و dial به حافظه فرآیند degrade می‌شوند (تک‌ورکر) — shadow مقایسه همچنان کار می‌کند.

## ۳. شاخص‌ها — پنجره یک‌ساعته

کلیدهای Redis با پیشوند `news:read_path:*` (TTL پنجره: ۱ ساعت):

| شاخص | معنا | آستانه نگرانی |
|------|------|----------------|
| `served` | کل درخواست‌های read | — |
| `served_items` | سروشده از news_items | درصد سهم مد |
| `compared` | probeهای مقایسه‌شده | حداقل `NEWS_READ_PARITY_MIN_SAMPLES` (پیش‌فرض 100) قبل از هر قضاوت |
| `parity_ok` / `parity_divergent` | نتیجه مقایسه صفحه | divergence هر تعداد = لاگ warning |
| `parity_percent` | ok ÷ compared | باید ≥ `NEWS_READ_PARITY_FLOOR_PERCENT` (پیش‌فرض 99) |

### تعریف parity (مهم!)

دو اسکیمای id مشترک ندارند: legacy `news_<24hex>`، جدید `ni_<BIGINT>`. پس parity = **کلید طبیعی** (URL مقاله که dual-write عیناً mirror می‌کند؛ fallback: title) + برابری total + برابری ترتیب صفحه. (این طراحی در جلسه با تست زنده اثبات شد: مقایسه id-tail همیشه divergent می‌بود و auto-halt می‌پرید.)

## ۴. تغییر مد در عملیات

```bash
# ۱) dial همه ورکرها بدون دیپلوی (admin):
curl -X POST "$API/api/v1/news/read-path/mode?mode=shadow" -H "Authorization: Bearer $ADMIN_JWT"

# ۲) مشاهده وضعیت:
curl "$API/api/v1/news/read-path/status" | jq
```

پاسخ status شامل: `mode` مؤثر، پنجره parity کامل، `halt` flag، و `items_share_percent`.

مسیر ارتقا (هر گام حداقل یک پنجره کامل — ۱ ساعت — و parity ≥ 99):

```
off → shadow → canary (10%) → canary (50%) → full
```

برای تغییر درصد canary: `NEWS_READ_CANARY_PERCENT` (پیش‌فرض 10) و ری‌استارت، یا از dial همان مد را دوباره set کنید بعد از تغییر env.

## ۵. auto-halt

Job زمان‌بندی‌شده (`NewsReadPathHalterJob` در scheduler) هر window را چک می‌کند:

- `compared ≥ min_samples` **و** `regression_parity_percent < floor` → ست کردن `news:read_path:halt` در Redis → همه ورکرها فوراً `off`.
- خاموشی halt: `NEWS_READ_HALT_ENABLED=false` (با احتیاط) یا `DELETE` کلید halt در Redis.
- پس از رفع ریشه مشکل: `POST /read-path/mode?mode=<desired>` halt را پاک و مد جدید را می‌نشاند.

### ۵.۱ پای دوم halter: نرخ خطای HTTP (۲۰۲۶-۰۹-۲۰)

Parity نابیناست به خطاهای زیرساختی: درخواست 5xx هیچ صفحه‌ای برای مقایسه
تولید نمی‌کند — پس burst چنددقیقه‌ای PostgreSQL OOM در پنجره shadow همین روز
(۳۳۸ درخواست 500 در ۸ دقیقه) از دید parity **و** halter گذشت. پای دوم:

- `MetricsMiddleware` هر پاسخ `/api/v1/news*` را در همان window می‌شمارد
  (`http_total` / `http_5xx`؛ مسیر unhandled-exception هم با status فرضی 500).
- halter مستقل از گیت parity: `http_total ≥ NEWS_READ_HTTP_ERROR_MIN_TOTAL`
  **و** `http_5xx_percent ≥ NEWS_READ_HTTP_ERROR_MAX_PERCENT` → همان halt key.
- متغیرها: `NEWS_READ_HTTP_ERROR_HALT_ENABLED` (پیش‌فرض true)،
  `NEWS_READ_HTTP_ERROR_MAX_PERCENT` (پیش‌فرض ۲۰)،
  `NEWS_READ_HTTP_ERROR_MIN_TOTAL` (پیش‌فرض ۱۰۰).
- هر دو پای یک key مشترک دارند؛ دلیل halt در فیلد `reason` پاسخ halter job
  و `http_5xx_percent` در `/news/read-path/status` دیده می‌شود.

## ۶. نقشه برگشت (rollback)

| سناریو | اقدام | اثر |
|--------|-------|-----|
| divergence دیده شد | `mode=off` (یا خودکار توسط halter) | فوری، همه ورکرها، صفر from-items |
| canary ولی کاربر شکایت | `mode=off` | همان بالا |
| full و مشکل | `mode=off` | برگشت کامل چون dual-write هر دو را پر نگه داشته |
| بدترین حالت: اسکیمای جدید خراب | `mode=off` + فلگ dual-write را جداگانه ببندید (کامیت جدا) | خواندن/نوشتن کاملاً legacy |

**قابل اطمینان بودن برگشت از داده:** نوشتن هرگز از مسیر کاناری عبور نمی‌کند؛ read path فقط مصرف‌کننده است.

## ۷. نقطه‌های کد

| قطعه | فایل | نقش |
|------|------|-----|
| تصمیم مسیر | `services.news_read_canary.decide` | pure، تست‌پذیر بدون DB |
| مقایسه parity | `services.news_read_canary.compare_page` | کلید طبیعی، نه id |
| شمارنده‌ها | `services.news_read_canary._incr/window_stats` | Redis با fallback حافظه |
| مسیریابی | `NewsRepository._route` (list/search/get_by_symbol) | فقط read |
| dial/halt | `POST/GET /news/read-path/{mode,status}` | status عمومی، mode فقط admin |
| halter | `NewsReadPathHalterJob` (scheduler) | توقف خودکار |

## ۸. پنجره shadow واقعی — اجرا و نتیجه (۲۰۲۶-۰۹-۲۰)

پنجره یک‌ساعته روی سرور dev واقعی (uvicorn + Postgres native) با
`python scripts/news_parity_window.py --port 3211 --minutes 60` اجرا شد.
گزارش کامل: **`docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md`** ·
داده خام: `reports/parity_window_run1.jsonl` (۱۰۹ نمونه status).

| معیار | نتیجه |
|-------|-------|
| `served/compared` | 1700 / 1700 |
| رگرسیون واقعی (`true_divergence`) | **0** ✅ |
| divergence (همه `items_superset` = بهبود alias) | 158 (۹.۳٪، هم‌خوان با سهم روت symbol دواملیا) |
| `regression_parity_percent` | **100.0** ✅ |
| auto-halt | بی‌رویداد ✅ |

**تصمیم:** پیمانه آماده ارتقا به `canary` روی dev است. یادداشت عملیاتی مهم:
شمارنده‌های این ران in-memory بودند (Redis پایین) — قبل از canary در محیط
چندورکر حتماً Redis را بالا بیاورید؛ و halter فقط divergence parity را می‌بیند،
پس نرخ خطای HTTP (مثل burst چنددقیقه‌ای OOM که در همین پنجره ۳۳۸ درخواست شد)
را باید جداگانه پایش کرد.

### ۸.۱ پنجره canary واقعی — برش ۱۰٪ (۲۰۲۶-۰۹-۲۰)

داده: `reports/parity_window_canary_run1.jsonl` (۵۹ نمونه، 14:29→15:29 UTC).

| معیار | نتیجه |
|-------|-------|
| `served / served_items` | ۲٬۴۳۶ / ۲۴۴ — سهم items **۱۰.۰۲٪** (دقیقاً برش تنظیم‌شده؛ میانگین پنجره ۱۰.۷۸٪ با انحراف معیار ۰.۸۹) |
| `regression_parity_percent` | **۱۰۰** — هر ۲۰۰ divergence = `items_superset` ✅ |
| خطای HTTP سرور | **صفر** از ۲٬۵۴۷ درخواست /news (پنجره shadow: ۳۳۸×500 + ۹×429) — صفر OOM |
| نرخ divergence افزایشی نیمه دوم | ۹.۸٪ — مطابق انتظار (۳۰٪ ترافیک symbol × ۲/۷ نماد دواملا) |
| هم‌سازگاری شمارنده‌ها | هر سه اتحاد حسابداری MATCH (`served−items=compared`، `ok+div=compared`، `superset+true=div`) |
| auto-halt | بی‌رویداد ✅ |

**تصمیم:** برش hash قطعی و پایدار عمل می‌کند؛ مسیر items زیر ترافیک واقعی
هم‌پوشانی کامل با legacy دارد. گام بعدی طبق runbook: پنجره با Redis بالا
(پایداری dial/شمارنده بین ری‌استارت‌ها) و سپس ارتقا به `full`.