# ۲۸ — API-05 تکمیلی: پاکت `data_as_of` برای `/stocks/v2`

**تاریخ:** 2026-10-29
**دامنه:** `apps/api/endpoints/stocks_v2.py` (۱۲ مسیر) + تست جدید
**وضعیت:** DONE (اصلاح + تست RED→GREEN)
**نسخه:** run1 — گزارش‌های قبلی بازنویسی نشدند.

---

## ۱. Git و وضعیت محیط

| فیلد | مقدار |
|---|---|
| شاخه | `integration/golddesk-fixes` |
| HEAD (شروع ممیزی این مرحله) | `46946947e1052eba933483b599733d40dd37749f` |
| `staged` (مجموعهٔ عامل هم‌زمان) | ۱۳۰ فایل — دست‌نخورده ماند |
| snapshot | `AUDIT_REPORTS/MODULAR_TEMCE/_snapshots/t22-stocksv2.txt` |
| پایگاه‌داده PostgreSQL | در دسترس نیست → تست‌های DB-محور BLOCKED |
| Redis | در دسترس نیست → تست‌های cross-process BLOCKED |

**نکتهٔ هم‌زمانی (صادقانه):** فایل `apps/api/endpoints/stocks_v2.py` در مجموعهٔ staged
عامل هم‌زمان بود (یک اصلاح ۲ خطی روی نام ستون‌ها). برای اینکه رگرسیون وارد نشود:
اصلاح من فقط روی working tree اعمال شد و در index هیچ چیزی را حذف/بازنویسی نکردم؛
پس از commit، index با `git add` (افزایشی) هم‌گام می‌شود تا تغییر آن عامل حفظ بماند.

---

## ۲. یافته (شفاف‌سازی API-05)

کاربر نهایی (پنل ۹تبهٔ `frontend/src/components/StockIntelligencePanel.tsx`) این مسیرها را
با `apiGet` می‌خواند، اما پاسخ‌ها «غیر-envelope» بودند: `{"success": true, "data": {...}}`
بدون کلید `data_as_of`.

قرارداد مشترک `schemas/common/responses.py::ApiResponse` مقدار `data_as_of` را تضمین می‌کند
تا مصرف‌کننده بتواند «تازه» را از «کهنه» تشخیص دهد (`frontend/src/lib/api-envelope.ts`).
در این ۱۲ مسیر، کلید اصلاً وجود نداشت:

| # | مسیر | منبع زمان موجود |
|---|---|---|
| ۱ | `GET /stocks/v2/{symbol}/tape` | `tape.quoted_at` |
| ۲ | `GET /stocks/v2/{symbol}/indicators` | `computed_at` (snapshot پیش‌محاسبه) |
| ۳ | `GET /stocks/v2/{symbol}/signal` | `tape.quoted_at` |
| ۴ | `GET /stocks/v2/{symbol}/peers` | ندارد (کوئری timestamp انتخاب نمی‌کند) |
| ۵ | `GET /stocks/v2/{symbol}/dossier` | ندارد (شناسنامه/سهامدار) |
| ۶ | `GET /stocks/v2/{symbol}/codal` | `publish_date` اطلاعیه‌ها |
| ۷ | `GET /stocks/v2/{symbol}/news` | `published_at` اخبار |
| ۸ | `GET /stocks/v2/{symbol}/history` | `date` آخرین کندل |
| ۹ | `GET /stocks/v2/{symbol}/volume-profile` | ندارد (دادهٔ امروز، فیلد زمانی سرو نمی‌شود) |
| ۱۰ | `GET /stocks/v2/market-pulse` | `macro.indicator_date` |
| ۱۱ | `GET /stocks/v2/monitoring` | ندارد (شمارندهٔ سلامت) |
| ۱۲ | `GET /stocks/v2/{symbol}/history/export.csv` | StreamingResponse (بدون پاکت — خارج از دامنه) |

**شدت:** P3 (بدهی قرارداد API؛ دادهٔ واقعی نمایش داده می‌شد، فقط تازگی قابل‌محاسبه نبود).

---

## ۳. علت ریشه‌ای

ماژول `stocks_v2.py` مستقل از الگوی envelope نوشته شده بود (نسخهٔ v2 با dict دستی).
در نتیجه هنگام افزودن قرارداد freshness (API-04) به `/market*`، این ماژول جا مانده بود و
مصرف‌کننده مجبور بود حدس بزند یا `isFresh: false` هارد-کد کند.

---

## ۴. اصلاح (کمینه)

سه helper داخلی در همان فایل:

- `_iso_ts(value)` → متن ISO-8601 برای یک timestamp منبع (`datetime`/`date`/str)، یا `None`.
- `_newest_ts(values)` → جدیدترین timestamp از میان مقادیر، یا `None` اگر همه غایب باشند.
- `_envelope(data, data_as_of=None)` → `{"success": True, "data": ..., "data_as_of": ...}`.

سپس هر مسیر، `data_as_of` را از **همان دادهٔ سروشده** می‌سازد (نه زمان ساخت پاسخ):
`quoted_at`، `computed_at`، `publish_date`، `published_at`، `date` کندل، `indicator_date`.
هرجا فیلد زمانی وجود ندارد، مقدار صریحاً `None` است (یعنی «تازگی نامعلوم»، نه «کهنه»).

هیچ کوئری SQL، هیچ نام ستون و هیچ رفتاری تغییر نکرد؛ فقط شکل پاکت پاسخ.

---

## ۵. تست (RED → GREEN)

فایل جدید: `tests/unit/api/test_stocks_v2_freshness_envelope.py` (۱۱ تست، بدون DB و Redis
با stub کردن `StockReadThroughService`).

| مرحله | فرمان | نتیجه |
|---|---|---|
| RED | `python -m pytest tests/unit/api/test_stocks_v2_freshness_envelope.py -q -p no:cacheprovider --no-header` | `11 failed` (کلید `data_as_of` وجود نداشت) |
| GREEN | همان فرمان | `11 passed, 1 warning in 94.42s` |
| lint | `python -m ruff check apps/api/endpoints/stocks_v2.py tests/unit/api/test_stocks_v2_freshness_envelope.py` | `All checks passed!` (exit 0) |

پوشش تست: `tape`، `indicators` (با و بدون timestamp)، `signal`، `news`، `codal`، `history`،
`market-pulse` و حضور صریح کلید برای `peers`/`dossier`/`volume-profile`.

---

## ۶. رگرسیون

| فرمان | نتیجه |
|---|---|
| `python -m pytest tests/unit/api -q -p no:cacheprovider --no-header` | `7 failed, 325 passed, 5 skipped` در ۳۲۴.۸۰s |

۷ خطا **مرتبط با این تغییر نیست** و از نوع محدودیت محیط است:

```
RuntimeError: Cannot connect to PostgreSQL database. ... Tried: localhost:5432/market
core\database.py:180
```

فایل‌های خطادار: `tests/unit/api/test_gold_derivatives_endpoints.py` (۲) و
`tests/unit/api/test_gold_personal_surface_auth.py` (۵). هیچ‌کدام به `stocks_v2` مربوط نیستند و
خروجی‌شان در `create_app`/اتصال DB شکست می‌خورد. طبق قاعده، این‌ها BLOCKED هستند نه PASS.

---

## ۷. محدودیت‌ها

- تست‌ها DB-free هستند؛ رفتار SQL واقعی روی PostgreSQL verify نشد (BLOCKED).
- `export_history_csv` (StreamingResponse) عمداً دست نخورد؛ افزودن هدر
  `X-Data-As-Of` گام بعدی است.
- `data_as_of` برای `peers`/`dossier`/`volume-profile`/`monitoring` = `None`
  (کوئری این ماژول timestamp سرو نمی‌کند؛ تغییر SQL برای افزودن آن verify نشده و انجام نشد).

---

## ۸. فایل‌های تغییرکرده (این مرحله)

| فایل | نوع |
|---|---|
| `apps/api/endpoints/stocks_v2.py` | اصلاح (+49/−12) |
| `tests/unit/api/test_stocks_v2_freshness_envelope.py` | تست جدید (۱۱) |
| `AUDIT_REPORTS/MODULAR_TEMCE/28_STOCKS_V2_FRESHNESS_ENVELOPE_run1_20261029.md` | این گزارش |
| `AUDIT_REPORTS/MODULAR_TEMCE/_snapshots/t22-stocksv2.txt` | snapshot |

**معیار پذیرش این مرحله (محقق‌شده):** هر ۱۲ مسیر `/stocks/v2` کلید `data_as_of` را در پاکت
برمی‌گردانند؛ مقدار آن از timestamp منبع سروشده مشتق می‌شود یا صریحاً `None` است؛ تست ۱۱موردی
سبز و ruff پاک.

---

## ۹. Commit (ذخیرهٔ تغییرات)

| فیلد | مقدار |
|---|---|
| commit | `9a4bfe93` — `fix(audit): publish data_as_of envelope on /stocks/v2 (API-05 follow-up)` |
| والِد | `46946947` |
| فایل‌های commit | `apps/api/endpoints/stocks_v2.py`، `tests/unit/api/test_stocks_v2_freshness_envelope.py`، همین گزارش |
| آمار | ۳ فایل، +۴۳۱ / −۱۲ |

**روش امن (حفظ کار عامل هم‌زمان):** commit با index موقت ساخته شد
(`GIT_INDEX_FILE` + `git read-tree HEAD` + `git apply --cached` روی patch حاوی فقط hunkهای من).
`git apply --cached --check` پیش از commit با exit 0 تأیید شد.

**تأیید پس از commit:**

- `git show HEAD:apps/api/endpoints/stocks_v2.py` هنوز `close_value FROM indices` و
  `ON s.code = t.symbol` را دارد → یعنی اصلاح ۲خطیِ stagedِ عامل هم‌زمان **وارد commit من نشد**
  و دست‌نخورده ماند (نه حذف شد، نه بازنویسی).
- `git diff -- apps/api/endpoints/stocks_v2.py` خالی است → working tree == index؛
  تغییر آن عامل همچنان staged است (`M `).
- `git diff --cached --name-only` = **۱۳۰** → مجموعهٔ staged دست‌نخورده.
- index واقعی با `git add` (افزایشی) هم‌گام شد؛ هیچ `reset --hard`/`clean`/`stash`/`checkout` اجرا نشد.
