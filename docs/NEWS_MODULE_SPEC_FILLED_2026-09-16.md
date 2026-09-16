# مشخصات فنی کامل — ماژول اخبار (نسخه تکمیل‌شده از کدبیس)

> تاریخ تکمیل: ۱۶ سپتامبر ۲۰۲۶ · مبنای کاوش: `docs/CODEBASE_DISCOVERY_2026-09-16.md` (کامیت `f8add5a3`)
> اصل حاکم حفظ شد: **فقط افزودن، هرگز حذف.** هر جای سند اصلی که `[پر کن]` داشت، با واقعیت کد فعلی پر شده و با نشان `📸 واقعیت کد` مشخص است.
> مواردی که تصمیم تیم می‌خواهند با نشان **🔴 تصمیم تیم** علامت خورده‌اند.

---

## فهرست مطالب
۰) اصل حفظ داده | ۱) نقشه تب‌ها | ۲) مدل داده | ۳) بک‌اند و لایه تجمیع | ۴) Deduplication و Tagging | ۵) Roadmap | ۶) سوالات باز *(پاسخ داده شد)* | ۷) Wireframe | ۸) اسکیمای API | ۹) نقش‌ها و پنل مدیریت | ۱۰) Backfill | ۱۱) مانیتورینگ کیفیت داده | ۱۲) Edge Case ها | ۱۳) معماری کامپوننت | ۱۴) برنامه تست | ۱۵) واژه‌نامه | ۱۶) خط لوله خودکار | ۱۷) Rollout | ۱۸) چک‌لیست نهایی | ۱۹) خلاصه اجرایی

---

## بخش ۰. اصل حاکم
فهرست اخبار فعلی و هر داده ذخیره‌شده دست‌نخورده می‌ماند؛ تغییرات فقط افزودنی‌اند.

📸 **واقعیت کد:** فهرست فعلی = `GET /api/v1/news` (`apps/api/endpoints/news.py`) + صفحه `frontend/src/app/news/page.tsx`. جدول فعلی `news_articles` (ORM: `models/news.py`) دست‌نخورده می‌ماند.

---

## بخش ۱. نقشه کامل تب‌ها

```
اخبار (منوی اصلی)
├── فهرست کلی اخبار (صفحه فعلی — حفظ و ارتقا)   ← frontend/src/app/news/page.tsx موجود
├── دسته‌بندی‌ها (بورس | ارز و طلا | اقتصاد کلان | اطلاعیه‌های کدال | بین‌الملل)
├── اخبار مهم/فوری (Breaking)                     ← جدید — جدول `is_breaking`
└── [صفحه اختصاصی هر خبر]                          ← جدید — روت frontend/src/app/news/[id]/page.tsx
```

### فیلترها (بالای فهرست، نه تب جدا)
جستجوی متنی | بازه زمانی | منبع | دسته‌بندی | نماد/دارایی مرتبط (تگ قابل کلیک از هر جای پلتفرم)

📸 **واقعیت کد — فیلترهای هم‌اکنون فعال در فرانت:**
- تب دسته‌بندی: `all | market | companies | economic | political | international` (`page.tsx:22`)
- جستجوی متنی سمت کلاینت + refresh دستی (`POST /news/refresh`)
- فیلتر بازه زمانی، منبع و تگ نماد: **یافت نشد** — باید به `GET /news` اضافه شود (`published_at` فعلاً string است — 🔴 تصمیم تیم #۱ در بخش ۲)
- فیلتر نماد در بک‌اند موجود است: `GET /news/symbol/{symbol}`

### صفحه اختصاصی خبر
متن کامل + منبع اصلی با لینک + تگ‌های نماد/دارایی مرتبط (قابل کلیک، می‌برد به صفحه آن نماد/دارایی) + اخبار مرتبط پیشنهادی (بر اساس تگ/دسته مشترک).

📸 **واقعیت کد:** صفحه اختصاصی خبر در فرانت **یافت نشد** (فقط فهرست با بازشدن fullContent در کارت). لینک تگ نماد می‌تواند به روت موجود `/symbol/{symbol}` یا جزئیات `/stocks/v2/{symbol}/dossier` وصل شود.

---

## بخش ۲. مدل داده بک‌اند

```sql
-- افزودنی؛ جداول موجود (news_articles، stock_news_sentiment) دست‌نخورده
```

📸 **واقعیت کد — وضعیت فعلی که مبنا قرار می‌گیرد:**

| جدول فعلی | اسکیمای واقعی (`models/news.py:8`) |
|-----------|-----------------------------------|
| `news_articles` | `id` String(50) PK · `title` String(500) NOT NULL · `summary` Text · `content` Text · `source` String(100) idx · `url` Text (**unique** از migration `0040` به‌عنوان `uq_news_articles_url`) · `category` String(50) idx · `symbols` **Text** (تگ‌ها CSV) · `published_at` **String(40)** idx ⚠️ · `sentiment` String(20) default 'neutral' · `sentiment_score` Float · `data_source` String(20) default 'rss' · `created_at`/`updated_at` |
| `stock_news_sentiment` (`models/stock_enterprise.py:171`) | `symbol` · `isin` · `industry` · `title` · `body` · `source` · `published_at` **DateTime** · `sentiment` · `sentiment_score` Double · `impact_tag` + Index `ix_news_symbol_pub (symbol, published_at)` |

**جدول‌های پیشنهادی سند (news_items/news_tags/news_ingestion_sources) در کدبیس: یافت نشد** — طبق اصل «فقط افزودن» باید ساخته شوند. دو مسیر:

🔴 **تصمیم تیم #۱ — ستون `published_at`:**
- (الف) migration افزودنی: ستون جدید `published_at_ts TIMESTAMP` + backfill با cast از رشته، index جدید؛ ستون قدیمی دست‌نخورده (سازگارترین با اصل سند) ✅ پیشنهادی
- (ب) alter همان ستون با cast (تمیزتر ولی ریسک داده تاریخ‌های بد parse نمی‌شوند)

🔴 **تصمیم تیم #۲ — مبناى جدول اخبار:**
- (الف) جدول‌های جدید `news_items`/`news_tags` طبق سند + sync یک‌طرفه از `news_articles` فعلی تا تجمیع بدون ریسک شروع شود ✅ پیشنهادی
- (ب) افزودن ستون‌های `is_breaking`/`dedup_hash` به همان `news_articles` و جدول `news_tags` جدید که به آن ارجاع می‌دهد (کمتر duplicate ولی به جدول legacy وابسته می‌شود)

اسکیمای پیشنهادی سند با اصلاحات واقعیت کد:
```sql
CREATE TABLE news_items (
    id BIGSERIAL PRIMARY KEY,
    legacy_article_id VARCHAR(50),            -- 📸 پیوند به news_articles فعلی (String(50) PK دارد)
    title TEXT NOT NULL,
    body TEXT,
    source VARCHAR(100),
    source_url TEXT,
    published_at TIMESTAMP,                   -- با تصمیم #۱ backfill می‌شود
    category VARCHAR(50),                     -- 📸 مقادیر موجود: market/companies/economic/political/international
    is_breaking BOOLEAN DEFAULT false,
    dedup_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_news_published ON news_items(published_at DESC);
CREATE INDEX idx_news_category ON news_items(category);
CREATE UNIQUE INDEX idx_news_dedup ON news_items(dedup_hash) WHERE dedup_hash IS NOT NULL;

CREATE TABLE news_tags (
    id BIGSERIAL PRIMARY KEY,
    news_id BIGINT NOT NULL REFERENCES news_items(id),
    tag_type VARCHAR(20),                     -- stock_symbol | asset | commodity | ...
    tag_value VARCHAR(50),
    confidence NUMERIC
);
CREATE INDEX idx_news_tags_value ON news_tags(tag_type, tag_value);

CREATE TABLE news_ingestion_sources (
    id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(100),                 -- 📸 مقدار واقعی = کلید فید، مثل isna_bourse / fardaye_bourse
    source_type VARCHAR(20),                  -- 📸 'rss' (مقدار data_source فعلی)
    endpoint_url TEXT,
    is_active BOOLEAN DEFAULT true,
    last_fetched_at TIMESTAMP
);
```

---

## بخش ۳. بک‌اند — لایه تجمیع (Aggregation Layer)

📸 **واقعیت کد — لایه تجمیع هم‌اکنون تا حد زیادی وجود دارد:**

```
services/news_ingestion.py (NewsIngestionService.ingest)
├── providers/news/domestic/rss_domestic_provider.py  ← RssAdapter فعلی (۳۹ فید، fetch موازی asyncio.gather)
├── services/news_filter.py    ← Validator فعلی (min_content_length=30، تاریخ، whitelist/blacklist، keyword، symbol)
├── services/news_dedup.py     ← Deduplicator فعلی (in-memory)
├── providers/news/sentiment/classifier.py ← lexicon-based (rule)
└── repositories/news_repository.py → models/news.py (news_articles)
```

- `NormalizedNewsItem` پیشنهادی سند معادل همان `NewsItem` در `domain/news/news_item.py` است (فیلدها: id, title, summary, content, source, url, category, symbols, publish_date, sentiment, data_source) — ✅ از همین استفاده شود، نه interface جدید.
- **آداپتور کدال:** `SyncCodalJob` (`jobs/definitions/` + مسیر BrsApi `/Codal/Announcement.php`) اطلاعیه‌ها را دارد ولی به pipeline اخبار **متصل نیست** — اتصال آن به‌عنوان `CodalDisclosureAdapter` فقط افزودنی است.
- **اضافه کردن منبع جدید فقط یک entry در `DOMESTIC_RSS_FEEDS` یا یک Provider جدید است** — معماری موجود همین را پشتیبانی می‌کند. ✅
- دسته‌بندی فعلی با keyword matching فارسی انجام می‌شود (`_CATEGORY_KEYWORDS` در `news_ingestion.py:27-53`).

🔴 **تصمیم تیم #۳ — دسته‌بندی:** مقادیر ذخیره‌شده فعلی `market | companies | economic | political | international` هستند ولی endpoint اعتبارسنجی روی `company` (مفرد) دارد (`news.py:23`) و فرانت `companies` (جمع) — یعنی فیلتر `company` در `/news/category/company` **هیچ نتیجه‌ای برنمی‌گرداند** (باگ واقعی موجود). سند جدید `stock_market` هم پیشنهاد می‌دهد. گزینه‌ها:
- (الف) فقط اضافه‌کردن aliasهای جدید (`stock_market` → نگاشت به `market`) در لایه نرمال‌سازی، بدون تغییر داده فعلی ✅ پیشنهادی
- (ب) اصلاح `VALID_CATEGORIES` به `companies` (فیکس باگ) + نگاشت سند

---

## بخش ۴. Deduplication و Tagging نماد

### ۴.۱. تشخیص تکراری
📸 **واقعیت کد:**
- الگوریتم فعلی: `NewsDeduplicator` (`services/news_dedup.py`) — `hash(normalize(title))` + **TTL در-memory ۸۶۴۰۰ ثانیه (۲۴ ساعت)**؛ before/after در هر ingest شمرده می‌شود (`stats["duplicates"]`).
- حفاظت پایدار DB: `exists_by_url_or_title(url, title)` قبل از insert (`repositories/news_repository.py:33,92`) + unique index روی `url` (migration `0040`).
- ⚠️ شکاف واقعی: dedup عنوان در حافظه است — ری‌استارت scheduler حافظه را پاک می‌کند؛ «شباهت بالا + بازه ۲ ساعته» فعلاً پیاده نیست (فقط hash دقیق عنوان).
- **اقدام افزودنی مطابق سند:** ستون `dedup_hash` پایدار + unique index (بخش ۲) و منطق شباهت (فاصله لوانشتین/جاکارد روی عنوان نرمال‌شده + پنجره زمانی) در لایه بک‌اند قبل از insert. نگه‌داشتن نسخه منبع معتبرتر = ترتیب اولویت فیدها (ISNA/BoursePress بالاتر از تجمیعی‌ها) — فهرست فعلی ۳۹ فید مبنای اولویت است.

### ۴.۲. Tagging نماد/دارایی
📸 **واقعیت کد — وضعیت فعلی ضعیف است:**
- `providers/news/parser.py:72-79`: `extract_symbols` فقط روی **لیست هاردکد ۶ نماد** (`فولاد، فملی، وبانک، کگل، خودرو، شپنا`) substring match می‌زند و نتیجه در ستون `symbols` (TEXT) ذخیره می‌شود.
- فاز اول سند (لیست نمادها از DB) کاملاً قابل تأمین است: جدول `symbols` (`models/market_data.py:23`) نماد+نام دارد؛ برای صندوق‌ها `funds.symbol` و `brsapi/constants.py::BRSAPI_ETF_SYMBOLS` (~۲۰۰ نماد واقعی). لیست استثنائات (بخش ۱۲) به‌صورت config/جدول اضافه می‌شود.
- ثبت با confidence (دقیق=بالا / جزئی=متوسط) در `news_tags` جدید — ساختار فعلی `symbols` TEXT دست‌نخورده می‌ماند.
- فاز NER: 🔴 **تصمیم تیم #۴** — پاسخ سوال باز ۳ را ببینید (زیرساخت فعلی فقط lexicon است).

---

## بخش ۵. Roadmap پیشنهادی *(تطبیق‌یافته با کد)*
۱) لایه تجمیع + Adapter منابع فعلی → **عمدتاً موجود است**؛ باقی‌مانده: CodalAdapter به pipeline
۲) Deduplication پایدار (dedup_hash + شباهت)
۳) Tagging rule-based از جدول `symbols`/`funds` (جایگزینی لیست ۶ نمادی)
۴) دسته‌بندی و فیلتر پیشرفته (+ فیکس باگ company/companies، فیلتر بازه زمانی/منبع در API)
۵) صفحه اختصاصی خبر + اخبار مرتبط (فرانت: روت جدید `/news/[id]`)
۶) اتصال تگ‌ها به صفحات سایر ماژول‌ها (`/symbol/*`، funds، gold)
۷) (اختیاری) ارتقا Tagging به NLP واقعی ← مشروط به تصمیم #۴

---

## بخش ۶. سوالات باز *(پاسخ از کد)*

- ✅ **منابع فعلی خبر دقیقاً کدامند؟** — فقط **RSS داخلی**: ۳۹ فید از ۶ خانواده خبرگزاری (`providers/news/domestic/rss_domestic_provider.py`):
  - فردا (`fardaye_*` — ۲۳ فید)، بورس‌پرس (`boursepress_*` — ۴)، اکوایران (`ecoiran_latest`)، تجارت‌نیوز (`tejarat_*` — ۴)، اقتصادآنلاین (`eghtesadonline_*` — ۳)، ایسنا (`isna_*` — ۴: اقتصادی/انرژی/صنعت/بازار سرمایه)
  - بدون کلید/API خارجی؛ کدال فقط از مسیر جدا (`SyncCodalJob`) و به اخبار وصل نیست؛ منبع بین‌الملل: **یافت نشد**.
- 🔴 **آیا محتوای کامل خبر مجاز به نمایش است؟** — تصمیم حقوقی است، ولی واقعیت فنی: RSS فعلی عمدتاً `description` می‌دهد؛ کد `(description || content || title)` را ذخیره می‌کند (`news_ingestion.py:258`) و فرانت آن را به‌عنوان `fullContent` نمایش می‌دهد (`page.tsx:61,244`). سیاست پیشنهادی سازگار با کد: **خلاصه RSS + لینک منبع** (ستون `content` پر نمی‌شود چون RSS فاقد متن کامل است — کپی‌رایت هم خودبه‌خود محترم می‌ماند).
- 🔴 **زیرساخت/بودجه NLP واقعی؟** — وضعیت فعلی: **lexicon-based (rule)** در `providers/news/sentiment/` (lexicon + preprocessor + scorer)؛ هیچ NLP/ML فارسی در dependencies نیست (transformers/hazm: یافت نشد؛ MLها کامنت‌شده‌اند). تا تصمیم بودجه، Tagging را rule-based (فاز اول سند) نگه دارید.

---

## بخش ۷. Wireframe
*(بدون تغییر نسبت به سند — مستقل از کد)*
فقط یک واقعیت: فهرست فعلی فرانت **page-based** است (`page`, `totalPages`, دکمه صفحه بعد — `page.tsx:42,132`) نه infinite scroll. یا infinite scroll اضافه شود یا وایرفریم به pagination برگردد — 🔴 تصمیم UI کوچک، پیش‌فرض: حفظ pagination فعلی در فاز ۱.

## بخش ۸. اسکیمای API

📸 **واقعیت کد — شکل فعلی پاسخ (همین حفظ می‌شود، فقط فیلدها اضافه می‌شوند):**
```jsonc
// GET /api/v1/news?page=1&pageSize=50   ← پارامتر واقعی page_size است نه pageSize
// پوشش: ApiResponse<PaginatedResult<NewsResponse>>
{
  "success": true,
  "data": {
    "items": [{
      "id": "news_xxx",             // String(50)، نه عددی
      "title": "...",
      "summary": "...",
      "source": "isna_bourse",       // 📸 کلید فید، نه نام نمایشی
      "url": "https://...",           // source_url
      "published_at": "2026-09-16T08:30:00", // فعلاً string
      "category": "market",
      "symbols": ["فولاد"],           // فعلاً از ستون TEXT
      "sentiment": "positive",
      "sentiment_score": 0.85,
      "trending": true,               // computed: |score|>0.3 && label != neutral
      // فاز جدید: "isBreaking": false, "tags": [{"type":"stock_symbol","value":"فولاد","confidence":0.9}]
    }],
    "total": 123, "page": 1, "page_size": 50, "total_pages": 3
    // hasMore معادل has_next (property موجود PaginatedResult)
  },
  "error": null
}
```

**Endpointهای موجود که حفظ می‌شوند** (`apps/api/endpoints/news.py`) + جدیدها:
| متد | مسیر | وضعیت |
|-----|------|-------|
| GET | `/news` | موجود (+ افزودن پارامترهای `source`, `from`, `to`, `tagType`, `tagValue`) |
| POST | `/news` | موجود (سازگاری فرانت) |
| GET | `/news/search` | موجود |
| GET | `/news/symbol/{symbol}` | موجود — مبناى کلیک تگ نماد |
| GET | `/news/category/{category}` | موجود (با فیکس اعتبارسنجی) |
| GET | `/news/trending` | موجود |
| POST/GET | `/news/refresh(+ /status)` | موجود |
| GET | `/news/breaking` | **جدید** (سند) |
| GET | `/news/{id}` | **جدید** (سند) — الان id فقط در لیست است |

⚠️ شکل صفحه‌بندی پاسخ سند (`items/pagination.page/pageSize/hasMore`) با واقعیت (`data.items/total/page/page_size/total_pages`) فرق دارد — فرانت فعلی به شکل واقعی وابسته است؛ **شکل فعلی حفظ شود**، سند به‌روز گردد.

---

## بخش ۹. نقش‌ها و پنل مدیریت

📸 **واقعیت کد:** RBAC موجود = **admin | analyst | user | viewer** (`core/enums/rbac.py`، ذخیره در `users.roles`، JWT + MFA/TOTP + revocation). الگوی سند (Viewer/Analyst/Admin) منطبق است؛ نقش میانی واقعی `user` نام دارد.
- مسیرهای news فعلاً `_optional_auth` هستند (`router.py:347-349`) — خواندن عمومی ✅
- پنل مدیریت (منابع خبری، اصلاح تگ، Breaking دستی) → زیر `/api/v1/admin` با `_require_admin` (الگوی موجود: روت `/jobs` همین dependency را دارد) + Audit Log روی جدول موجود `audit_logs` (`models/audit_log.py`) نه جدول جدید.

## بخش ۱۰. Backfill تاریخی
📸 آرشیو RSS عمیق وجود ندارد (فیدها فقط آخرین آیتم‌ها را می‌دهند) — پس: جمع‌آوری از لحظه راه‌اندازی شروع می‌شود. داده تاریخی موجود در `news_articles` (از دوره‌های قبل) با backfill به `news_items` منتقل می‌شود تا «اخبار مرتبط» از روز اول معنادار باشد.

## بخش ۱۱. مانیتورینگ کیفیت داده
- **آستانه هشدار منبع مرده [پر کن]:** 📸 مقدار پیشنهادی از واقعیت کد: **۲ ساعت** (= ۲ برابر دوره ingestion که هر ۱۰ دقیقه است — یعنی ۱۲ run متوالی بدون آیتم جدید از یک منبع). قابلیت سنجش: `job_runs` (job_type='news_ingestion') + شمارش per-source که باید در stats ingest ذخیره شود.
- نرخ Tagging موفق / نرخ dedup: آمار هم‌اکنون در `stats` ingest هست (`fetched/duplicates/filtered/saved/errors`) — باید per-run در DB ثبت شود (جدول جدید یا `job_runs.result`).
- متریک‌های پایه Prometheus/Sentry از قبل در API فعال‌اند.

## بخش ۱۲. Edge Case ها *(وضعیت فعلی هرکدام از کد)*
| Edge Case | وضعیت فعلی |
|-----------|------------|
| خبر اصلاح‌شده منبع | ⚠️ فعلاً dedup عنوان/URL آن را رد می‌کند (به‌روزرسانی درجا **یافت نشد**) — مطابق سند: upsert بر `dedup_hash` لازم است |
| خبر بدون تاریخ | fallback موجود: `publish_date` خالی → `created_at` هنگام پاسخ (`news.py:31-35`) ✅ |
| محتوای کوتاه | فیلتر موجود: `min_content_length=30` (`news_ingestion.py:129`) ✅ |
| نام مشترک/تگ اشتباه | فعلاً لیست ۶ نمادی substring match می‌زند — لیست استثنائات قابل تنظیم + confidence جزئی در طرح جدید (بخش ۴.۲) |

## بخش ۱۳. معماری کامپوننت فرانت‌اند
📸 موجود: `frontend/src/app/news/page.tsx` (تک‌فایل: فیلتر+کارت+pagination). کامپوننت‌های سند (`NewsFilterBar/NewsCard/NewsTagChips/RelatedNewsList`) جدید هستند؛ `NewsCard` از کارت فعلی استخراج و **reusable برای صفحات نماد/صندوق** می‌شود (صفحه نماد هم‌اکنون `GET /stocks/v2/{symbol}/news` را صدا می‌زند).

## بخش ۱۴. برنامه تست
📸 زیرساخت: pytest (۳۵۸ فایل) + Vitest (۲۳ فایل). تست‌های news موجود: `tests/unit/services/test_news_service.py`، `tests/unit/providers/test_news_parser.py`، `tests/integration/test_news_ingestion_flow.py`، `tests/fixtures/sample_news.py`.
- Unit جدید: Deduplication (شباهت+پنجره زمانی)، Tagging rule-based (confidence دقیق/جزئی)
- Integration جدید: Adapter→dedup→tag→save (الگوی `test_news_ingestion_flow` موجود)
- E2E جدید: فیلتر/باز کردن خبر/مرتبط‌ها (الگوی `frontend/src/__tests__/*.test.tsx`)

## بخش ۱۵. واژه‌نامه
*(بدون تغییر — مستقل از کد)*

## بخش ۱۶. خط لوله خودکار دریافت داده
📸 **نگاشت هر جزء سند به کد فعلی:**
| جزء سند | واقعیت کد |
|---------|-----------|
| Scheduler هر منبع با فرکانس خودش | `NewsIngestionJob` هر **۱۰ دقیقه** (در بازه ۵-۱۵ دقیقه سند ✅)؛ فرکانس per-source فعلاً یکسان — افزودنی: فاصله‌های جدا per-feed |
| Adapter fetch مستقل + retry | ✅ موجود (`asyncio.gather` + throttle در `providers/news/domestic/throttling.py`؛ خرابی یک فید بقیه را نمی‌شکند) |
| Validator (عنوان خالی/URL نامعتبر) | ✅ `NewsFilter` (طول حداقل ۳۰)؛ اعتبارسنجی صریح URL افزودنی کوچکی است |
| Upsert با چک dedup_hash | جزئی: فعلاً `exists_by_url_or_title` — dedup_hash پایدار باید اضافه شود |
| Audit Log با job_type='news_fetch' | ✅ معادل موجود: جدول `job_runs` (`job_type='news_ingestion'`) — جدول `ingestion_run_logs` جدید لازم نیست (تصمیم: از `job_runs` استفاده شود) |

## بخش ۱۷. Rollout بدون اختلال
*(منطق سند حفظ)* — مرحله ۱: migration کاملاً افزودنی (سه جدول جدید + ستون‌های جدید، بدون alter روی news_articles). مرحله ۲: چند روز dual-write هم‌زمان ingestion فعلی. مرحله ۳: فیلترها/تگ‌های UI تدریجی. API فعلی دست‌نخورده — فرانت فعلی نمی‌شکند.

## بخش ۱۸. چک‌لیست نهایی
- [ ] هیچ داده/فیچر فعلی حذف نشده → API و جدول فعلی حفظ
- [ ] Deduplication پایدار (dedup_hash + شباهت) کار می‌کند
- [ ] Tagging از جدول symbols/funds فعال + قابل اصلاح دستی (پنل admin)
- [ ] تگ → صفحات سایر ماژول‌ها (`/symbol/*`، funds، gold)
- [ ] مانیتورینگ: per-source stats در job_runs + هشدار ۲ ساعت
- [ ] Rollout سه‌مرحله‌ای بدون downtime

## بخش ۱۹. خلاصه اجرایی
```
هدف: تبدیل فهرست ساده تیتر به مرکز اطلاعاتی مرتبط با کل پلتفرم.
وضعیت انطباق: لایه تجمیع، validator، دسته‌بندی keyword، sentiment و scheduler از قبل موجودند؛
کار واقعی = dedup پایدار + tagging واقعی (جایگزینی لیست ۶ نمادی) + صفحه اختصاصی خبر + ۳ جدول افزودنی.
نکته کلیدی سند تأیید می‌شود: این ماژول پس از تکمیل داده نمادها/دارایی‌های ماژول‌های دیگر اجرا شود
(جدول symbols/funds مبنای tagging هستند و همین حالا آماده‌اند).
```

---

## 🔴 جمع‌بندی موارد نیازمند تصمیم تیم
| # | تصمیم | گزینه‌ها | پیشنهاد |
|---|-------|----------|---------|
| ۱ | `published_at` string → TIMESTAMP | ستون جدید+backfill / alter با cast | ستون جدید (افزونی خالص) |
| ۲ | مبناى جدول: news_items جدید vs توسعه news_articles | جدول جدید+sync از legacy / ستون‌های افزودنی روی legacy | جدول جدید (اصل سند) |
| ۳ | دسته‌بندی company/companies/stock_market + فیکس باگ اعتبارسنجی | alias در نرمال‌سازی / اصلاح VALID_CATEGORIES | هر دو: فیکس باگ + alias |
| ۴ | NER/NLP واقعی برای Tagging | rule-based فعلی + لیست DB / مدل فارسی (بودجه+infra) | فعلاً rule-based |
| ۵ | کپی‌رایت: نمایش متن کامل vs خلاصه+لینک | — (واقعیت فنی: RSS فقط description دارد) | خلاصه+لینک |
| ۶ | UI: infinite scroll vs pagination فعلی | — | حفظ pagination در فاز ۱ |
| ۷ | شکل صفحه‌بندی API سند vs شکل فعلی | تغییر فرانت به شکل سند / به‌روزرسانی سند به شکل فعلی | به‌روزرسانی سند (شکل فعلی) |
