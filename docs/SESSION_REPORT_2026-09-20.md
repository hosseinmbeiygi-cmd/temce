# گزارش جلسه — کاناری مسیر خواندن اخبار: طراحی، پنجره shadow واقعی و tripwire خطا

> تاریخ: ۲۰ سپتامبر ۲۰۲۶
> دامنه: **۱۱ کامیت** روی `main` (بعد از `20d10914`)
> حجم: ۵۸ فایل، **‎+۷٬۱۷۶ / ‎−۴۲۰ خط**
> اعتبارسنجی: **۲۱/۲۱ تست کاناری** + پنجره shadow واقعی یک‌ساعته روی سرور dev

---

## ۱️⃣ استراتژی rollout کاناری — از فلگ بولی به پیمانه چهارحالته

**کامیت:** `faa804f8` — `services/news_read_canary.py` + `docs/RUNBOOK_NEWS_READ_CANARY.md`

فلگ بولی `NEWS_READ_FROM_ITEMS` به پیمانه rollout کامل ارتقا یافت:

| حالت | رفتار |
|------|-------|
| `off` | فقط legacy (پیش‌فرض، رفتار قبلی) |
| `shadow` | legacy سرو می‌کند + probe موازی روی news_items + مقایسه parity |
| `canary` | برش قطعی hash-based (پیش‌فرض ۱۰٪) به items؛ بقیه legacy با probe سایه |
| `full` | فقط items (معادل فلگ بولی) |

**اجزای کلیدی:**
- **دک e_runtime**: endpoint ادمین `POST/GET /news/read-path/{mode,status}` — فلپ بدون دیپلوی، Redis مشترک بین ورکرها + fallback حافظه‌ای
- **parity با کلید طبیعی**: مقایسه id بین دو اسکیما به‌طرuri غلط است (legacy `news_<24hex>` vs `ni_<BIGINT>`) — parity = URL (mirror دقیق dual-write) با fallback title + برابری total و ترتیب
- **تفکیک جهت divergence**: `items_superset` (بهبود عمدی alias/املایی — مسیر جدید *بیشتر* پیدا می‌کند) جدا از `true_divergence` (رگرسیون)؛ فقط رگرسیون به آستانه auto-halt شارژ می‌شود
- **Halter خودکار**: job زمان‌بندی‌شده؛ عبور `regression_parity_percent` از کف (پیش‌فرض ۹۹٪ با حداقل ۵۰ نمونه) → halt key مشترک → همه ورکرها فوراً `off`

## ۲️⃣ درس‌های داده‌ای پنجره — سه فیکس هم‌ترازی (کامیت `3a345d24`)

قبل از پنجره رسمی، probeهای اولیه divergent بودند؛ ریشه‌یابی سه‌لایه:

1. **ترتیب نامعین tieها** — burstهای یک‌ثانیه‌ای بدون tie-breaker قطعی در دو کوئری با پلن متفاوت ترتیب متفاوت می‌دهند → هر دو مسیر روی `published_at_ts + id` قطعی شدند
2. **body ناقص بک‌فیل** — backfill اولیه `body` را از `summary` (سقف ۵۰۰) کپی می‌کرد در حالی که legacy روی `content` کامل جستجو می‌کند → فیکس اسکریپت + **اسکریپت ترمیم idempotent** (`scripts/repair_news_items_body.py`): ۲٬۴۰۳ ردیف ترمیم شد
3. **published_at ناسازگار dual-write** — mirror مقدار رندشده می‌نوشت ولی legacy fallback میکروثانیه‌ای داشت → mirror همان مقدار fallback را می‌نویسد (خوانده‌شده از DB بعد از flush)

## ۳️⃣ پنجره shadow واقعی یک‌ساعته ⭐ محور جلسه

**کامیت گزارش:** `0c323948` — گزارش کامل: `docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md` · داده خام: `reports/parity_window_run1.jsonl`

اجرا: سرور uvicorn واقعی + Postgres native، پیمانه shadow با endpoint ادمین (توکن JWT واقعی)، ترافیک‌ساز `scripts/news_parity_window.py` (میکس ۵۰٪ list / ۲۰٪ search / ۳۰٪ symbol با کوئری‌ها و نمادهای دواملای عربی/فارسی)، ۱۰۹ نمونه status در ~۶۷ دقیقه.

| معیار | نتیجه |
|-------|-------|
| `served / compared` | ۱۷۰۰ / ۱۷۰۰ |
| رگرسیون واقعی (`true_divergence`) | **۰** ✅ |
| divergence | ۱۵۸ (۹.۳٪) — **۱۰۰٪ `items_superset`**، هم‌خوان با سهم روت symbol دواملای لیست |
| `regression_parity_percent` | **۱۰۰** ✅ |
| auto-halt | بی‌رویداد ✅ |

**یافته عملیاتی مهم:** burst چهار‌دقیقه‌ای PostgreSQL OOM (۰۴:۱۶–۰۴:۲۴ UTC) — ۳۳۸ درخواست 500 روی کوئری `COUNT + DISTINCT ON` legacy زیر بار همزمان ingestion + ترافیک + double-read سایه. parity آسیب ندید (probeهای ناموفق safe-fail‌اند) ولی **halter این را هرگز ندید** → اقدام ۵.

**Reconciliation شمارنده‌ها:** `served=1700` در برابر ۱۰۶۲ درخواست کلکتور — کلید: `served` شامل خواندن‌های داخلی jobها (ingestion/sentiment) از همان مسیر routing است. ۴۲۹ها (۹ مورد) رفتار محافظتی rate limiter بود.

**تصمیم:** پیمانه آماده ارتقا به `canary` است.

## ۴️⃣ زنجیره فاند + dbcompat (ادامه جلسه قبل)

| کامیت | محتوا |
|-------|-------|
| `94155223` → `4b83883b` | پنج کامیت زنجیره فاند: backend core (۷ سرویس + migrations ۰۰۵۵–۰۰۵۸)، API layer، فیکس گارد نظارتی باز (`require_regulator_admin` تعریف‌شده ولی wire نشده بود!)، frontend، تست‌ها — **۱۰۶/۱۰۶ + ۱۴ vitest** |
| `35de6ae1` + `2edb7bea` | **`core/dbcompat.py`** — چهار helper برای سه دام تکرارشونده (`as_bigint_id`/`as_text_id`/`naive_utc`/`commit_now`)، هرکدام با امضای خطای واقعی در docstring؛ مهاجرت لایه news + بخش به `core/README.md` موجود (بازنویسی ناخواسته در کامیت اول، بازگردانی + افزودن صحیح در دوم) |

## ۵️⃣ Tripwire نرخ خطای HTTP در halter (کامیت `b7598839`)

بستن حفره‌ای که پنجره shadow نشان داد: parity به خطاهای زیرساختی نابیناست — درخواست 5xx هیچ صفحه‌ای برای مقایسه تولید نمی‌کند.

- `MetricsMiddleware` هر پاسخ `/api/v1/news*` را در همان window می‌شمارد (`http_total` / `http_5xx`؛ مسیر استثنا = 500)
- halter پای دوم **مستقل** گرفت: `5xx ≥ ۲۰٪` با حداقل ۱۰۰ نمونه → همان halt key (گیت parity نپیماید؛ burst دقیقاً وقتی می‌آید که نمونه parity کم است)
- تنظیمات: `NEWS_READ_HTTP_ERROR_{HALT_ENABLED,MAX_PERCENT,MIN_TOTAL}` (true/20/100) · `http_5xx_percent` در status endpoint
- **باگی که تست گرفت:** `startswith("/api/v1/news")` با `/api/v1/newsarchive` هم match می‌شد → مرز دقیق prefix
- شبیه‌سازی OOM-like (۱۲۰ درخواست، ۳۳٪ خطا، صفر parity) → halt با reason شفاف ✅ · **۲۱/۲۱ تست**

## 📊 جمع‌بندی

| بعد | وضعیت |
|-----|-------|
| کاناری rollout | طراحی کامل + runbook + halter دولپه + tripwire خطا |
| پنجره shadow | **رگرسیون ۰/۱۷۰۰** — آماده ارتقا به canary |
| داده news_items | سه فیکس هم‌ترازی + ترمیم ۲٬۴۰۳ body |
| تست | ۲۱/۲۱ کاناری + ۱۰۶/۱۰۶ فاند + ۹۷/۹۷ news |

**باقی‌مانده برای جلسه بعد:**
- پنجره canary (ارتقای پیمانه) با Redis بالا — شرط چندورکر
- ری‌استارت سرور dev برای فعال‌شدن tripwire (کد فعلی سرور از قبلِ کامیت tripwire است)
- پنجره canary روی head جدید باید فیلدهای `http_*` در status نشان دهد
- ۲۶۰ فایل modified از refacorهای cross-cutting (`utc_now_naive`) — جلسه خودش را می‌خواهد

**درس تکرارشونده جلسه:** سیستم‌های rollout فقط وقتی قابل اعتمادند که پنجره واقعی بگیرند — هر سه یافته بحرانی جلسه (tie-breaker، OOM نادیده halter، گیت parity که بازرسی http را می‌پراند) در تست‌های واحد نامرئی بودند و فقط زیر ترافیک زنده خود را نشان دادند.
