# گزارش جلسه — ماژول اخبار: از تصمیم‌های قفل‌شده تا نگاشت تیکر و E2E زنده

> تاریخ: ۱۹ سپتامبر ۲۰۲۶
> دامنه: **۱۶ کامیت** روی `main` (بعد از `1bd0f9e2`)
> حجم: ۳۱ فایل، **‎+۴٬۷۳۶ / ‎−۴۳ خط** (۹ فایل تست: ‎+۲٬۱۲۳)
> اعتبارسنجی: **۹۹ تست سبز** (۸۸ بسته news + ۱۱ rate-limit) + E2E زنده ۱۶/۱۶

---

## ۱️⃣ بنیان داده — اسکیمای جدید ماژول اخبار

| کامیت | محتوا |
|-------|-------|
| `1b6ae1e3` | **Migration 0054** — سه جدول افزودنی: `news_items` (با `dedup_hash` + unique جزئی، `legacy_article_id` UNIQUE، `is_breaking`)، `news_tags` (FK با CASCADE)، `news_ingestion_sources` (رجیستری منابع). FK سخت به `news_articles` نزده شد چون CREATE TABLE آن در migrations نیست |
| `aff06251` | تصمیم #۱ سند: ستون `published_at_ts` **TIMESTAMP** روی legacy + backfill یک‌باره ۱۵٬۵۸۱/۱۵٬۵۸۱ (۱۰۰٪) + ایندکس `DESC` — regex-guarded و fail-open |
| `6551156a` | **Backfill idempotent** از `news_articles` به `news_items` — ۱۵٬۵۸۱ ردیف، `--dry-run/--retag/--batch-size`، منابع با `last_fetched_at` تاریخی (نه now) |

**یافته‌های واقعی حین اجرا:**
- ستون legacy `symbols` رشته **JSON** است نه لیست کاما → تگ‌های اولیه با براکت ذخیره شدند؛ فیکس پارسر + حالت `--retag` (۷۰۸ ردیف بازسازی)
- در raw-string پایتون `\\|` به regex برسد یعنی pipeِ literal نه alternation → بک‌فیل اول صفر ردیف پر کرد؛ با ۹ بردار آزمون مستقل بازنویسی شد
- asyncpg پارامتر named ندارد (فقط `$n`) + کست صریح برای بافت‌های text/varchar

## ۲️⃣ نوشتن دوگانه (Dual-Write)

**کامیت:** `2d371fec` — `services/news_dual_write.py`

`NewsIngestionService._save_article` بعد از ذخیره legacy، مقاله را در `news_items` هم mirror می‌کند: `dedup_hash` = SHA-256(title نرمال‌شده NFKC + casefold + collapse + URL)، تگ‌های ساخت‌یافته در `news_tags`، upsert منبع با `last_fetched_at`. مسیر جدید **safe-mirror** است: خطایش هرگز مسیر legacy را نمی‌بلعد.

**دو باگ که تست DB واقعی گرفت:**
1. `repo.save` فقط flush می‌کند و commit در teardown است → rollback بعد از خطای mirror، INSERT legacy را هم می‌خورد → فیکس: **re-issue legacy save**
2. نسخه اول re-issue کل `_save_article` بود → **حلقه بی‌نهایت** → فیکس: پرچم `mirror=False`

E2E نهایی: دو اجرای `ingest()` پشت‌سرهم → `LEGACY=1, NEW=1`، بدون تکرار و خطا.

## ۳️⃣ API — فیلتر بازه زمانی روی هر ۵ روت

| کامیت | پوشش |
|-------|------|
| `c34dfb53` | `GET /news` · `/news/search` · `/news/symbol/{symbol}` با `?from/?to` |
| `c5dec179` | `/news/category/{category}` · `/news/trending` |

**قرارداد مشترک:** ISO-8601 · تاریخ بدون ساعت در `?to` = کل آن روز · naive = UTC · کران یک‌طرفه مجاز · ورودی خراب → payload خطای `ApiResponse` (نه 500)

**نکات پیاده‌سازی:** فیلتر **در DB** داخل زیرکوئری `DISTINCT ON` تزریق شد (نه post-page مثل category) تا total و صفحه‌بندی درست بمانند · ستون فیلتر `COALESCE(published_at_ts, created_at)` · سرویس فقط کران‌های داده‌شده را forward می‌کند (امضای فراخوانی بدون بازه دست‌نخورده).

**باگ production-bound که تست Postgres گرفت:** asyncpg به ستون **naive** پارامتر **aware** نمی‌دهد (`can't subtract offset-naive and offset-aware`) — یعنی هر `?from` واقعی 500 می‌داد. فیکس `_naive_utc()` در مرز repo. جالب: fixture خود تست هم اول با همان خطا شکست خورد.

## ۴️⃣ سوییچ Read Path با فلگ

**کامیت:** `1502c3df` — `NEWS_READ_FROM_ITEMS` (پیش‌فرض False)

فلگ فقط **خواندن** را عوض می‌کند؛ نوشتن همیشه dual است → روشن/خاموش کردن در هر جهت بی‌خطر. اجزا: `models/news_items.py` (آینه DDL)، `repositories/news_items_read_repo.py`، روتینگ در `NewsRepository`. مزیت مسیر جدید: `published_at` **TIMESTAMP واقعی بدون پارس رشته**، `get_by_symbol` روی تگ ساخت‌یافته با ایندکس (نه LIKE روی TEXT)، id با پیشوند `ni_` جدا از legacy.

## ۵️⃣ Observability منابع

**کامیت‌ها:** `5691cd45` + `a292a8bf`

`NewsSourceHealthService` گزارش سه‌بخشی می‌دهد: **stale** (`last_fetched_at` قدیمی‌تر از `NEWS_SOURCE_STALE_MINUTES`، پیش‌فرض ۱۲۰ = ۱۲ run از‌دست‌رفته) · **never_fetched** (>۲۴ ساعت بدون fetch موفق) · **unregistered** (منبع نویسنده خارج از registry). Job هر ۱۰ دقیقه + endpoint `GET /news/sources/health` + هشدار تلگرام با cooldown یک‌ساعته (کلید Redis) + `?notify=true` صادقانه (`alert_fired: true/false`).

**باگ مهم: ناسازگاری ساعت.** محاسبه elapsed اول در پایتون بود؛ timestampهای naive این اسکیما ترکیب server-local/UTC‌اند و `now()` دیتابیس به Tehran برمی‌گشت → ردیف stale سیدشده «تازه» دیده می‌شد. فیکس: کل محاسبه به **SQL** منتقل شد (`EXTRACT(EPOCH FROM now() - …)`).

**یافته زنده:** هر ۳۷ منبع stale بودند (ingestion چند ساعت ران نشده بود) — و بعداً لاگ E2E همان را مستقل تأیید کرد: tejaratnews 404، isna 403، boursepress 500.

## ۶️⃣ نگاشت تیکر تگ‌ها به نمادها/صندوق‌ها ⭐ محور اصلی جلسه

**کامیت‌ها:** `471e5689` · `f340ee2b` · `516f317e` · `ccb49b02` · `0fd9e0b8`

مسئله: تگ انسانی (`وبانک`، `فملی`) با نماد کانونی DB (`وبانك`، `فملي` — ۴۲۶/۵۱۱ نماد با نویسه عربی) جور نمی‌شود.

```
news_tags.tag_value ──> NewsTagSymbolMapper ──> news_tag_symbol_map ──> symbols/funds
        (وبانک)        resolve: manual > exact        (0059)            (وبانك)
                       > arabic_fallback
```

| بخش | جزئیات |
|-----|--------|
| Migration 0059 | `resolved_id` **TEXT عمدی** — `funds.id` VARCHAR ولی `symbols.id` BIGINT (زنده تأیید شد) |
| نرمال‌سازی | فولد عربی→فارسی، **ZWNJ→فاصله (نه حذف!)**، ارقام عربی+فارسی، casefold |
| Auto-map | idempotent — پوشش **۱۰۰٪** هر ۵ تگ کورپوس: ۳ exact + `فملی→فملي`، `وبانک→وبانك` |
| Read path | `get_by_symbol` روی همه واریانت‌های املا + aliasهای persisted — fail-open |
| شفافیت API | `SymbolMatchMeta` در `message` پاسخ: `matched` + `maps` با `match_type`/`confidence` — best-effort |
| Admin API | `GET /news-tag-map` (view/search/filter) · `/stats` · `POST /{tag}/manual` (اعتبارسنجی target) · `DELETE` · `GET /{tag}/verify` (dry) — همه admin-only با **audit_logs** (actor از JWT sub) |
| سند | بخش ۲۰ سند ماژول اخبار (۷ زیربخش) + لینک از ۴.۲، جدول API و فهرست |

**چهار دام واقعی که کد را تغییر داد:**
1. ZWNJ حذف می‌شد نه فولد → `سرمايه‌گذاري ≠ سرمایه گذاری` برای همیشه
2. asyncpg برای ستون BIGINT نوع پایتون native می‌خواهد — حتی با `CAST` در SQL
3. JOIN پلی‌مورف `bigint = text` در سطح plan رد می‌شود → `CAST(s.id AS TEXT)`
4. تداخل شماره migration با زنجیره فاند (۰۰۵۶–۰۰۵۸ untracked) → renumber به ۰۰۵۹، زنجیره تک-head

## ۷️⃣ E2E زنده — سه‌لایه اعتبارسنجی کامل

**کامیت:** `0fd9e0b8` — `scripts/e2e_news_symbol_meta.sh` (بازتولیدپذیر: `bash scripts/e2e_news_symbol_meta.sh [port]`)

سرور uvicorn واقعی + Postgres واقعی؛ **۱۶/۱۶ چک سبز**: symbol lookup با meta (واریانت + alias با confidence) → admin list/stats → manual override → audit trail → **آیتم alias-دار از طریق نماد کانونی پیدا شد** → delete + verify خالی → پاک‌سازی کامل.

**باگی که فقط E2E می‌گرفت — مسابقه response↔commit:** `get_session` سراسری بعد از *ارسال پاسخ* کامیت می‌کند؛ `verify`ِ بلافاصله بعد از POST ردیف را نمی‌دید. فیکس: **کامیت صریح قبل از پاسخ** در mutationهای مدیریتی (durability قبل از visibility). همچنین پروکسی سیستم روی localhost بای‌پس شد (`NO_PROXY="*"`).

## 📊 جمع‌بندی

| بعد | وضعیت |
|-----|-------|
| تست‌ها | ۹۹ سبز (۸۸ news + ۱۱ rate-limit) — اکثراً روی Postgres واقعی |
| Migrationها | 0054 (بنیان) · 0054-افزودنی (published_at_ts) · **0059 (نگاشت)** — زنجیره تک-head تا 0059 |
| وضعیت DB | `news_items` کاملاً هم‌تراز legacy (۱۵٬۵۸۱) · dual-write فعال · فلگ خواندن آماده کاناری |
| E2E | اسکریپت بازتولیدپذیر + چرخه verify→manual→audit→read→delete سبز |

**باقی‌مانده برای جلسه بعد (عمداً دست‌نخورده):**
- زنجیره fund (فایل‌های untracked ۰۰۵۵–۰۰۵۸ + endpointها) — فقط شماره‌ها برای رفع تداخل renumber شد
- سوییچ production فلگ `NEWS_READ_FROM_ITEMS` (پیشنهاد: چند روز dual-write، بعد کاناری؛ rollback = یک env var)
- استراتژی alias برای تیکرهای جدید: گزارش `match_type=unmapped` از `/news-tag-map` + `set_manual`
- درس عملیاتی جلسه: سه دام تکرارشونده — **type پلی‌مورف PK**، **naive/aware datetime**، **commit-after-response** — کاندیدای الگوی مشترک در `core/`
