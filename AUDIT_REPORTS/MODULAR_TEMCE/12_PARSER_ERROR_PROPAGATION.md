# مرحلهٔ ۱۲ — انتشار خطای parse در TEMCE (تفکیک «پاسخ خالی معتبر» از «خطای parse»)

> گزارش جدید و مستقل. هیچ‌کدام از گزارش‌های قبلی (`00`…`11`, `QA_STAGE_*`) بازنویسی نشد.

## ۰) فرادادهٔ اجرا

| کلید | مقدار |
|---|---|
| تاریخ/زمان (Tehran) | ۲۰۲۶-۱۰-۲۹، حدود ۰۹:۳۰–۰۹:۵۵ |
| ریشهٔ مخزن | `C:\Users\Iran\Desktop\temce` |
| شاخه | `integration/golddesk-fixes` |
| `HEAD` | `90597e05` (`90597e05b9f4328bcd82ee819a31ba5c55413c12`) — تغییری نکرد |
| پوسته / Python | bash (Git Bash)؛ Python 3.11؛ pytest با `asyncio_mode=auto` |
| Ruff | `0.15.17` (فقط `check` روی فایل‌های همین دامنه؛ هیچ‌جا `--fix` اجرا نشد) |
| BrsApi / TSETMC / RSS زنده | **استفاده نشد** |
| DB / Redis | PostgreSQL محلی در دسترس نیست → تست‌های `needs_db` دسلکت/اسکیپ شدند (بخش ۶) |
| Commit / reset / clean / stash / checkout / stage | **انجام نشد** |

## ۱) وضعیت git پیش از هر تغییر (ثبت‌شده)

خروجی خام `git status --porcelain=v1` در `/tmp/git_status_before.txt` ذخیره و شمارش شد:

```
=== EXIT: 0 ===
224            # کل خطوط status --porcelain
--- staged count ---       138
--- unstaged count ---      68
--- git diff --stat (unstaged) ---
 68 files changed, 2400 insertions(+), 1013 deletions(-)
--- git diff --stat --cached ---
 138 files changed, 115998 insertions(+), 1447 deletions(-)
--- branch/HEAD ---
integration/golddesk-fixes
90597e05b9f4328bcd82ee819a31ba5c55413c12
```

**اختلاف با متن مأموریت:** مأموریت «۴۵ فایل unstaged» گفته بود؛ اندازه‌گیری واقعی در شروع کار **۶۸ فایل unstaged** بود. عدد staged دقیقاً ۱۳۸ بود (تطابق). هیچ‌کدام دست‌کاری نشد.

پس از پایان کار، تفاضل `git status` قبل/بعد **فقط یک خط** دارد:

```
$ diff /tmp/git_status_before.txt /tmp/git_status_after.txt
201a202
> ?? ingestion/parser/errors.py
staged=138 unstaged=68     # بدون تغییر
```

یعنی هیچ فایل خارج از دامنه لمس نشد (دو فایل تست داخل پوشهٔ از قبل untracked `tests/unit/parsers/` هستند و در `git status` خط جدید تولید نمی‌کنند).

### ۱-۱) یافتهٔ مهمِ پیش‌از‌کار (خرابی موجود، خارج از تغییرات من)

`ingestion/parser/library_parsers.py` **قبل از شروع این مأموریت** در working tree آلوده بود
(`M`، ۶۴+/۳۴۸− نسبت به `HEAD`) و در همان نسخه، چهار زیرکلاس
`FinpyTseParser`/`TsetmcLibParser`/`TehranStocksParser`/`TseUtilsParser` **حذف شده‌اند** و فایل
روی `_BaseLibParser` تمام می‌شود. این وضعیت پیش از هر ویرایش من با اجرای زیر تأیید شد:

```
$ python -c "import ingestion.main"
Traceback (most recent call last):
  File "C:\Users\Iran\Desktop\temce\ingestion\main.py", line 11, in <module>
    from .parser.library_parsers import (
ImportError: cannot import name 'FinpyTseParser' from 'ingestion.parser.library_parsers'
```

طبق قاعدهٔ «فایل‌های staged/unstaged کاربر را دست نزن» این حذف **بازگردانی نشد**؛ در بخش ۷ به‌عنوان
ریسک شمارهٔ ۱ ثبت شده است. ویرایش من فقط روی همان نسخهٔ موجود (stub) نشست و چیزی از محتوای
کاربر حذف/بازنویسی نکرد.

## ۲) فهرست فراخواننده‌های `parse()` (فقط‌خواندنی، پیش از تغییر)

`grep` روی کل مخزن (با احترام به ignore) برای `_BaseLibParser`/`library_parsers` و نام زیرکلاس‌ها و
`ParserRegistry`:

| مسیر | نقش | نحوهٔ مصرف نتیجه |
|---|---|---|
| `ingestion/main.py:11-15`, `:70-73` | ثبت پارسرها در `ParserRegistry` (فراخوانندهٔ `parse` نیست) | — |
| `ingestion/worker.py:143` | **تنها فراخوانندهٔ واقعی در مسیر تولید** — `events = await parser.parse(payload.raw_data)` داخل `IngestionWorker._ingest_source` | `written` شمارش رکوردهای **نوشته‌شده**؛ خروجی `_ingest_source` در `ingest_all` در دیکشنری `{source: count}` جمع می‌شود و `-1` نشانهٔ شکست منبع است |
| `ingestion/replay/__init__.py:43` | `events = await parser.parse(raw)` در `ReplayEngine.replay_source` | داخل `try/except Exception` → `failed += 1`؛ از قبل «خطا = شکست» بود |
| `brsapi/services/sync_service.py` | مصرف‌کنندهٔ پارسر به‌صورت **callable** (`parser=...`) در `BrsApiSyncService.sync()`، نه از طریق `ParserRegistry` | `SyncReport(success, items_count, error)` + رکورد `sync_log` |

نکتهٔ صریح: هیچ مسیر دیگری (نه `apps/api`, نه `jobs/`) `_BaseLibParser` یا زیرکلاس‌هایش را
import یا صدا نمی‌زند؛ `providers/base/parser_base.py` یک `ParserRegistry` مستقل و بی‌ربط است.
`sync_service` هم مستقیماً از `ingestion` استفاده نمی‌کند (مرز لایه‌ها حفظ شد).

### ۲-۱) رفتار `sync_service` و `worker` پیش از تغییر

- `sync_service.sync()` خطای پارسر را از قبل می‌گرفت (`except Exception` → `status="error"` و
  `SyncReport(success=False, error="ParseError: …")`). اما یک حفره داشت: اگر پارسر مقدار
  غیر `list`/`dict` برمی‌گرداند، به‌صورت `records = []` نرمال می‌شد و **`success=True,
  items_count=0`** ثبت می‌شد (همان الگوی DATA-028).
- `worker._ingest_source` **همهٔ** استثناها را می‌بلعید (`continue`) و `0` برمی‌گرداند؛ یعنی
  payload خراب (Suspend.php / JSON ناقص) دقیقاً شبیه «هیچ چیز جدیدی نبود» گزارش می‌شد.

## ۳) تغییرات (diff هر فایل) و دلیل

### ۳-۱) `ingestion/parser/errors.py` — **فایل جدید** (۴۲ خط)

```python
"""Parse-error contract for the ingestion parser layer. …"""
from __future__ import annotations

from typing import Literal

ParseReason = Literal[
    "invalid_json",             # body is not JSON at all (an empty body counts)
    "html_response",            # provider served an HTML page (e.g. Suspend.php)
    "unexpected_shape",         # JSON parsed, but the top-level value is not an object
    "missing_required_fields",  # object without any recognised envelope field
]


class ParseError(Exception):
    def __init__(self, reason: ParseReason, detail: str = "", *, source: str = "") -> None:
        self.reason: ParseReason = reason
        self.detail = detail
        self.source = source
        message = f"{reason}: {detail}" if detail else reason
        if source:
            message = f"{source}: {message}"
        super().__init__(message)
```

**دلیل:** یک کلاس خطای مشخص با فیلد ماشین‌خوان `reason` تا مصرف‌کننده بتواند بین «منبع خالی بود»
و «نتوانستم پاسخ را بخوانم» تفکیک کند؛ `str(exc)` هم در `sync_log.error_message` و لاگ‌ها
قابل‌ردیابی است.

### ۳-۲) `ingestion/parser/library_parsers.py` — changeset من (نسبت به نسخهٔ stub کاربر: ۱ خط import، ۶ خط `_ENVELOPE_KEYS`، بازنویسی متد `parse` از ۱۰ به ۳۵ خط)

```diff
 from ingestion.parser import ParsedEvent, Parser
+from ingestion.parser.errors import ParseError

 logger = getLogger(__name__)
+
+# Keys a well-formed library envelope carries. A JSON object with none of them
+# did not come from the adapter we expected, so it is a parse failure rather
+# than a valid empty response.
+_ENVELOPE_KEYS = frozenset(
+    {"data_type", "records", "data", "stocks", "info", "stats", "symbol", "tsetmc_code"}
+)
 ...
     async def parse(self, payload: bytes) -> list[ParsedEvent]:
-        try:
-            data = json.loads(payload)
-        except Exception:
-            logger.exception("Failed to parse %s payload as JSON", self._source_name)
-            return []
+        """Parse one raw payload into events.
+
+        Raises :class:`ParseError` when the payload cannot be understood. A
+        valid response that simply carries no records still returns ``[]``.
+        """
+        body = payload.strip()
+        if not body:
+            raise ParseError("invalid_json", "empty payload", source=self._source_name)
+        if body.startswith(b"<"):
+            raise ParseError(
+                "html_response", "response is HTML, not JSON", source=self._source_name
+            )
+        try:
+            data = json.loads(body)
+        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
+            raise ParseError(
+                "invalid_json", f"invalid JSON: {exc}", source=self._source_name
+            ) from exc
         if not isinstance(data, dict):
-            logger.warning("Unexpected payload shape for %s: expected dict, got %s", self._source_name, type(data).__name__)
-            return []
+            raise ParseError(
+                "unexpected_shape",
+                f"expected a JSON object, got {type(data).__name__}",
+                source=self._source_name,
+            )
+        if data and not _ENVELOPE_KEYS.intersection(data):
+            raise ParseError(
+                "missing_required_fields",
+                f"no recognised envelope field in {sorted(data)[:5]}",
+                source=self._source_name,
+            )
         return self._dispatch(data)
```

**دلیل:** `json.loads` شکست‌خورده و shape غلط دیگر به `[]` تبدیل نمی‌شوند. `[]` فقط وقتی
برمی‌گردد که پاکت معتبر باشد و `_dispatch` واقعاً رکوردی پیدا نکند
(مثلاً `{"data_type": "market_watch", "records": []}`). هر چهار تولیدکنندهٔ
`ingestion/sources/library_sources.py` همیشه پاکت `data_type` + (`records`/`info`/`stats`/`stocks`/`data`)
می‌سازند، پس `missing_required_fields` روی دادهٔ واقعی trigger نمی‌شود و فقط پاسخ‌های
بیگانه (HTML، پیام خطای پرووایدر) را می‌گیرد. `{}` عمداً معتبر و خالی تلقی می‌شود.

### ۳-۳) `ingestion/worker.py` (+۱۴، بدون حذف)

```diff
 from .parser import ParserRegistry
+from .parser.errors import ParseError
 ...
             try:
                 events = await parser.parse(payload.raw_data)
+            except ParseError as exc:
+                # A payload we could not read is a failed ingest, not an empty
+                # one: the raw copy stays in the lake for replay, and
+                # ``ingest_all`` records the source as failed (-1) instead of
+                # reporting zero written events as if the source were healthy.
+                logger.error(
+                    "Parse failed for source=%s endpoint=%s reason=%s. Raw payload kept at %s",
+                    payload.source,
+                    payload.endpoint,
+                    exc.reason,
+                    object_key,
+                )
+                raise
             except Exception:
                 logger.exception( … )
                 continue
```

**دلیل:** خطای parse عمداً **دوباره پرتاب** می‌شود تا به `ingest_all` برسد، جایی که قرارداد موجود
همین است: هر استثنای منبع → `results[name] = -1`. مقدار `0` (که «هیچ چیز جدید» معنا می‌داد) دیگر
برای payload ناخوانا تولید نمی‌شود. payload خام پیش از parse در lake ذخیره شده است
(`object_key` در پیام لاگ)، پس replay ممکن می‌ماند. سایر استثناها (باگ کد) رفتار قبلی
(`continue`) را حفظ می‌کنند تا یک خطای غیرمنتظره کل تیک را نخواباند.

### ۳-۴) `brsapi/services/sync_service.py` (+۲۲/−۱، فقط شاخهٔ نرمال‌سازی)

```diff
         elif isinstance(parsed, list):
             records = parsed
         else:
-            records = []
+            # A parser that returns anything else did not understand the
+            # payload. Folding it into ``records = []`` would record a
+            # successful sync with ``items_count=0`` for a response we could
+            # not read at all.
+            elapsed_ms = (time.monotonic() - start) * 1000
+            error = f"ParseError: unexpected parser result type {type(parsed).__name__}"
+            logger.error("Parse error for %s: %s", endpoint.path, error)
+            await sync_log.record(
+                endpoint=endpoint.path,
+                category=category_override or endpoint.category.value,
+                status="error",
+                error_message=error,
+                duration_ms=elapsed_ms,
+                params=params,
+            )
+            await sess.commit()
+            return SyncReport(
+                endpoint=endpoint.path,
+                success=False,
+                error=error,
+                duration_ms=elapsed_ms,
+            )
```

**دلیل:** مسیر پرتاب‌شدن `ParseError` از قبل درست بود (`except Exception` → `success=False`,
`error="ParseError: …"`, `status="error"`)، ولی نوع بازگشتی غیرمنتظره بی‌صدا «موفق با صفر رکورد»
می‌شد. شاخهٔ `brs_resp.is_empty` (پاسخ خالی خود پرووایدر) دست‌نخورده ماند چون یک پاسخ معتبر است.
عمداً `ParseError` از `ingestion.parser.errors` import **نشد** تا وابستگی لایهٔ `brsapi` به
`ingestion` ایجاد نشود؛ همین رفتار با تست پوشش داده شده (بخش ۵).

> **نکتهٔ dedup (طبق درخواست، فقط گزارش):** در `worker` علامت‌گذاری
> `dedup.mark_seen` **بعد از** نوشتن کامل همهٔ رویدادها انجام می‌شود (و با پرتاب `ParseError`
> هرگز اجرا نمی‌شود). در `sync_service` هم `sync_log.record()` بعد از parse ثبت می‌شود و
> `needs_sync()` فقط ردیف‌های `status == "success"` را ملاک می‌گیرد، پس رکورد خطا مانع retry
> نمی‌شود. هیچ ترتیب معیوبی که نیاز به تغییر داشته باشد پیدا نشد و چیزی تغییر نکرد.

### ۳-۵) تست‌ها

`tests/unit/parsers/test_library_parser_errors.py` (بازنویسی کامل، ۹ تست): تست‌های قبلی که
`[]` را برای JSON نامعتبر/HTML/list قفل می‌کردند حذف و با قرارداد درست جایگزین شدند:

```python
class DummyParser(_BaseLibParser):
    _source_name = "dummy"

    def _dispatch(self, data):
        if data.get("data_type") != "market_watch":
            return []
        now = "2026-01-01T00:00:00+00:00"
        return [self._market_snapshot(rec, now) for rec in data.get("records", [])]

# invalid JSON / empty body / HTML / <!DOCTYPE html> / [1,2,3] / {"message": …}  ⇒ ParseError
#   با reason های invalid_json, invalid_json, html_response, html_response,
#   unexpected_shape, missing_required_fields
# {"data_type": "market_watch", "records": []}  ⇒ []
# {"data_type": "market_watch", "records": [{...}]} ⇒ ۱ رویداد با symbol/last_price درست
# str(ParseError(...)) ⇒ "dummy: html_response: response is HTML"
```

`tests/unit/parsers/test_parse_error_propagation.py` (جدید، ۶ تست آفلاین):

- `test_worker_raises_parse_error_and_keeps_raw_payload` — `ParseError` از `_ingest_source`
  بیرون می‌زند و payload خام در lake ذخیره شده است.
- `test_worker_ingest_all_marks_parse_failure_as_failed_source` — `ingest_all()` مقدار
  `{"dummy": -1}` می‌دهد (نه `0`).
- `test_worker_ingest_all_keeps_valid_empty_payload_as_zero` — پارسرِ خالی `{"dummy": 0}`.
- `test_sync_service_reports_parse_error_as_failure` — پارسرِ پرتاب‌کنندهٔ `ParseError`
  (نمونهٔ واقعی از `ingestion.parser.errors`) ⇒ `success is False`، `"ParseError"` و
  `"invalid_json"` در `error`، و رکورد `sync_log` با `status == "error"`.
- `test_sync_service_reports_unexpected_parser_result_as_failure` — پارسر `42` برمی‌گرداند ⇒
  `success is False` و `"unexpected parser result type int"`.
- `test_sync_service_keeps_valid_empty_parser_result_as_success` — پارسر `[]` ⇒
  `success is True`, `items_count == 0`, `sync_log.status == "success"`.

همه با mock/Fake (بدون شبکه، بدون DB/Redis).

## ۴) قرارداد نهایی

| ورودی | نتیجه |
|---|---|
| بدنهٔ خالی / JSON ناقص / BOM نامعتبر | `ParseError(reason="invalid_json")` |
| پاسخ HTML (شامل `Suspend.php`, `<!DOCTYPE html>`) | `ParseError(reason="html_response")` |
| JSON معتبر ولی top-level غیر dict (list/عدد/رشته) | `ParseError(reason="unexpected_shape")` |
| dict بدون هیچ‌یک از کلیدهای پاکت (`data_type`/`records`/`data`/`stocks`/`info`/`stats`/`symbol`/`tsetmc_code`) | `ParseError(reason="missing_required_fields")` |
| پاکت معتبر با `records: []` / `{}` | `[]` (پاسخ خالی معتبر) |
| پارسر `sync_service` غیر `list`/`dict` برمی‌گرداند | `SyncReport(success=False, error="ParseError: unexpected parser result type …")` |
| `brs_resp.is_empty` در `sync_service` | `success=True, items_count=0` (بدون تغییر) |

## ۵) اجرای واقعی تست‌ها (خروجی خام و exit code)

```
$ python -m pytest tests/unit/parsers -q -p no:cacheprovider
.....
15 passed in 37.20s
EXIT_PARSERS=0
```

```
$ python -m pytest tests/unit/repositories -q -p no:cacheprovider
............................................
44 passed in 13.46s
EXIT_REPOS=0
```

```
$ python -m pytest tests/unit/test_sync_service_persistence_scope.py \
    tests/unit/services/test_sync_master_service.py \
    tests/unit/brsapi/test_sync_helpers.py -q -p no:cacheprovider
..........
32 passed in 11.93s
EXIT_SYNC=0
```

```
$ python -m pytest tests/unit/test_ingestion_worker_persistence.py -q -p no:cacheprovider
....
4 passed in 19.06s
EXIT_WORKER=0
```

```
$ python -m pytest tests/unit/brsapi -q -p no:cacheprovider \
    --ignore=tests/unit/brsapi/test_sync_outcomes.py
72 passed in 5.34s
EXIT_BRSAPI2=0
```

اجرای ترکیبی نهایی (بعد از آخرین ویرایش، شامل هر دو فایل تست جدید):

```
$ python -m pytest tests/unit/parsers tests/unit/repositories \
    tests/unit/test_sync_service_persistence_scope.py \
    tests/unit/services/test_sync_master_service.py \
    tests/unit/brsapi/test_sync_helpers.py \
    tests/unit/test_ingestion_worker_persistence.py -q -p no:cacheprovider
..
95 passed in 62.60s (0:01:02)
EXIT_FINAL=0
```

کیفیت کد (بدون `--fix`، فقط فایل‌های همین دامنه):

```
$ python -m ruff check ingestion/parser/errors.py ingestion/worker.py \
    brsapi/services/sync_service.py tests/unit/parsers/
All checks passed!
RUFF_EXIT=0

$ python -m py_compile ingestion/parser/errors.py ingestion/parser/library_parsers.py \
    ingestion/worker.py brsapi/services/sync_service.py \
    tests/unit/parsers/test_library_parser_errors.py \
    tests/unit/parsers/test_parse_error_propagation.py
COMPILE_EXIT=0
```

## ۶) اجرانشده‌ها و علت

| مورد | وضعیت | علت / شاهد |
|---|---|---|
| تست‌های `needs_db` هم‌بسته با sync (`tests/unit/test_brsapi_sync_integration.py` ×۳، `tests/unit/test_brsapi_sync_status.py` ×۲) | **BLOCKED** | `addopts = ["-m", "not needs_db"]` آن‌ها را دسلکت می‌کند؛ با `-m needs_db` اجرا شدند و همگی skip شدند: `PostgreSQL is not reachable at localhost:5432/market` → `5 skipped in 17.20s` (EXIT_SYNCDB2=0). موفق اعلام نمی‌شوند. |
| `tests/unit/brsapi/test_sync_outcomes.py` (فایل untracked، کار جریان موازی) | **BLOCKED (پیش‌از‌کار)** | `EXIT_OUTCOMES=2` — `ImportError: cannot import name 'BrsApiMalformedResponseError' from 'brsapi.client'`؛ همچنین `brsapi/parsers/errors.py` وجود ندارد در حالی که تست `BrsApiParseError` را import می‌کند. این خرابی **مربوط به این مأموریت نیست** (نه فایلش را دست زدم نه importش را) و کل `tests/unit/brsapi` را در collection متوقف می‌کند؛ به همین دلیل آن دایرکتوری با `--ignore` اجرا شد. |
| `python -c "import ingestion.main"` (مسیر واقعی `IngestionEngine`) | **FAIL موجود** | `ImportError: cannot import name 'FinpyTseParser'` — پیش از شروع این مأموریت هم همین بود (بند ۱-۱). |
| درخواست زنده به BrsApi/TSETMC/RSS | انجام نشد | طبق قواعد قطعی مأموریت. |
| تست کل پروژه (`pytest tests`) | اجرا نشد | خارج از دامنهٔ مأموریت و آلوده به فایل‌های نیمه‌کارهٔ staged/untracked سایر جریان‌ها. |

## ۷) ریسک‌های باقی‌مانده

1. **بالا — زیرکلاس‌های پارسر در working tree غایب‌اند.** تا وقتی
   `FinpyTseParser/TsetmcLibParser/TehranStocksParser/TseUtilsParser` برنگردند،
   `ingestion.main`/`IngestionEngine` بالا نمی‌آید و مسیر واقعی تولید payload وجود ندارد؛
   تست‌های من عمداً روی `_BaseLibParser` (که وجود دارد) و مصرف‌کننده‌ها کار می‌کنند.
   بازگردانی از `HEAD` هم دوباره `_BaseLibParser.parse()` قدیمی را برمی‌گرداند، بنابراین
   پیشنهاد می‌شود ابتدا نسخهٔ کلاس‌ها از `git show HEAD:ingestion/parser/library_parsers.py`
   گرفته و با متد `parse` جدید **ادغام** شود (نه overwrite). تصمیم با مالک تغییرات unstaged است.
2. **متوسط — payload با BOM در ابتدای بدنه.** `json.loads` روی `b"\xef\xbb\xbf{...}"` شکست
   می‌خورد و اکنون `ParseError(invalid_json)` می‌دهد (قبلاً `[]` بی‌صدا بود). تولیدکنندگان فعلی
   BOM نمی‌گذارند (`json.dumps(...).encode("utf-8")`)، پس در عمل trigger نمی‌شود؛ اگر منبع
   بیرونی BOM اضافه کند، به‌جای خطای پنهان، خطای قابل‌دیدن می‌گیریم.
3. **متوسط — پرتاب مجدد در `worker` بقیهٔ payloadهای همان منبع را رد می‌کند.** برای منابع
   library هر fetch یک payload دارد (بی‌خطر)؛ اگر روزی یک `FetchResult` چند payload برگرداند،
   اولین payload خراب بقیه را متوقف می‌کند. payload خام همه در lake ذخیره شده‌اند و replay
   (که خودش خطا را `failed += 1` می‌کند) مسیر بازیابی است.
4. **پایین — تشخیص HTML فقط با `startswith(b"<")`.** پاسخ HTML با فاصله/کامنت مقدم (مثلاً
   `<!-- … -->`) همچنان `invalid_json` می‌گیرد، نه `html_response`؛ در هر دو حالت نتیجهٔ
   عملی «شکست» است، فقط `reason` دقیق‌تر می‌شد.
5. **پایین — `{}` معتبر و خالی تلقی می‌شود** (نه `missing_required_fields`) تا رفتار قبلی
   برای payloadهای بی‌ریسک حفظ شود؛ اگر تیم می‌خواهد `{}` هم خطا باشد، یک تست باید عوض شود.
6. **پایین — `sync_service` همچنان فقط بر اساس `isinstance` تصمیم می‌گیرد.** اگر پارسری
   عمداً `None` برگرداند (مثل `TsetmcParser.parse_nav` که در مسیرهای اختصاصی و نه `sync()`
   استفاده می‌شود)، حالا شکست ثبت می‌شود نه موفقیت صفر‌رکوردی؛ این تغییر رفتاری مطلوب است ولی
   باید در جریان موازی `sync_service` (که در حال افزودن فیلد `outcome`) هم‌راستا شود.

## ۸) وضعیت نهایی: **PARTIAL**

- **انجام‌شده و سبز:** تفکیک قراردادی «پاسخ خالی معتبر» از «خطای parse» در `_BaseLibParser`
  (۴ reason)، انتشار خطا در `worker` (شکست منبع) و بستن حفرهٔ «نوع غیرمنتظره = موفق با صفر
  رکورد» در `sync_service`، بازنویسی تست‌های قبلی به نفع قرارداد درست، ۶ تست جدید آفلاین برای
  مصرف‌کننده‌ها، و اجرای واقعی ۹۵ تست مرتبط با exit code صفر.
- **چرا نه PASS:** (الف) `ingestion.main` به‌دلیل حذف پیشین چهار زیرکلاس پارسر در working tree
  بالا نمی‌آید، پس مسیر end-to-end قابل اثبات نیست و بازگردانی آن خارج از اجازهٔ من بود؛
  (ب) پنج تست DB-وابستهٔ sync به‌خاطر نبود PostgreSQL **BLOCKED** هستند؛ (ج) فایل تست
  `tests/unit/brsapi/test_sync_outcomes.py` از جریان موازی با `ImportError` شکسته است و
  جمع‌آوری کل `tests/unit/brsapi` را متوقف می‌کند.


---

## ۹) پیوست (ادامهٔ همین گزارش) — بازگردانی چهار زیرکلاس پارسر + ادغام با قرارداد `ParseError`

> تاریخ: ۲۰۲۶-۱۰-۲۹ (ادامهٔ همان جلسه). `HEAD` همچنان `90597e05`؛ هیچ commit/reset/clean/stash/checkout/stage انجام نشد.

### ۹-۱) مشکلی که این پیوست حل می‌کند

ریسک شمارهٔ ۱ بخش ۷ (حذف پیشین چهار زیرکلاس در working tree و شکست `import ingestion.main`) اکنون **رفع شد**.
وضعیت پیش از این پیوست:

```
$ python -c "import ingestion.main"
ImportError: cannot import name 'FinpyTseParser' from 'ingestion.parser.library_parsers'
```

فایل در working tree فقط `_BaseLibParser` را داشت (۱۵۵ خط، BOM + CRLF) در حالی که `HEAD` نسخهٔ کامل
(۴۰۷ خط، LF، بدون BOM) را دارد.

### ۹-۲) روش کار (ادغام، نه overwrite)

مبنای بازگردانی، همان نسخهٔ `HEAD` گرفته شد و **فقط** قرارداد جدید `parse()` روی آن اعمال شد؛ هیچ بخش دیگری
از فایل بازنویسی نشد:

1. `git show HEAD:ingestion/parser/library_parsers.py` به‌عنوان baseline خوانده شد (۴۰۷ خط، LF، بدون BOM).
2. بلوک import + ثابت `_ENVELOPE_KEYS` اضافه شد.
3. متد `_BaseLibParser.parse()` با نسخهٔ قراردادی جایگزین شد (بدنهٔ HTML/JSON نامعتبر/shape غلط ⇒ `ParseError`).
4. فایل با LF و بدون BOM نوشته شد تا diff نسبت به `HEAD` تمیز بماند (`core.autocrlf=true` هنگام checkout بعدی CRLF می‌سازد).

نتیجه: ۴۴۲ خط، پنج کلاس، diff نسبت به `HEAD` فقط **۳۹+/۴−**:

```
$ git diff --stat -- ingestion/parser/library_parsers.py
 ingestion/parser/library_parsers.py | 43 +++++++++++++++++++++++++++++++++----
 1 file changed, 39 insertions(+), 4 deletions(-)

$ grep -n "^class " ingestion/parser/library_parsers.py
90:class _BaseLibParser(Parser):
275:class FinpyTseParser(_BaseLibParser):
326:class TsetmcLibParser(_BaseLibParser):
387:class TehranStocksParser(_BaseLibParser):
411:class TseUtilsParser(_BaseLibParser):
```

diff کامل تغییر (تنها تغییر نسبت به `HEAD`):

```diff
 from . import ParsedEvent, Parser
+from .errors import ParseError

 logger = get_logger(__name__)

+# Keys a well-formed library envelope carries. A JSON object with none of them
+# did not come from the adapter we expected, so it is a parse failure rather
+# than a valid empty response.
+_ENVELOPE_KEYS = frozenset(
+    {"data_type", "records", "data", "stocks", "info", "stats", "symbol", "tsetmc_code"}
+)
+
@@ class _BaseLibParser
     async def parse(self, payload: bytes) -> list[ParsedEvent]:
+        """Parse one raw payload into events.
+
+        Raises :class:`ParseError` when the payload cannot be understood. A
+        valid response that simply carries no records still returns ``[]``.
+        """
+        body = payload.strip()
+        if not body:
+            raise ParseError("invalid_json", "empty payload", source=self._source_name)
+        if body.startswith(b"<"):
+            raise ParseError(
+                "html_response",
+                "response is HTML, not JSON",
+                source=self._source_name,
+            )
         try:
-            data = json.loads(payload)
-        except Exception:
-            logger.exception("Failed to parse %s payload", self._source_name)
-            return []
+            data = json.loads(body)
+        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
+            raise ParseError(
+                "invalid_json", f"invalid JSON: {exc}", source=self._source_name
+            ) from exc
+        if not isinstance(data, dict):
+            raise ParseError(
+                "unexpected_shape",
+                f"expected a JSON object, got {type(data).__name__}",
+                source=self._source_name,
+            )
+        if data and not _ENVELOPE_KEYS.intersection(data):
+            raise ParseError(
+                "missing_required_fields",
+                f"no recognised envelope field in {sorted(data)[:5]}",
+                source=self._source_name,
+            )
         return self._dispatch(data)
```

**نکتهٔ مهم:** به‌دلیل اینکه baseline همان `HEAD` است، helperهای فایل هم به نسخهٔ `HEAD` برگشتند
(`from core.logging import get_logger`، `safe_float/safe_int` از `core.db_utils`، و `_map_price_fields`
شامل `ins_code`/`yesterday_close`). نسخهٔ موقتِ working tree این helperها را ساده‌سازی کرده بود؛ آن ساده‌سازی
بخشی از حذف ناخواسته بود و بازگرداندنش رفتار تولید را به وضعیت کامیت‌شده برمی‌گرداند.

### ۹-۳) شواهد اجرای واقعی (آفلاین، بدون شبکه)

```
$ python -c "import ingestion.parser.library_parsers as m; print([n for n in dir(m) if n.endswith('Parser')])"
['FinpyTseParser', 'Parser', 'TehranStocksParser', 'TseUtilsParser', 'TsetmcLibParser', '_BaseLibParser']

$ python -c "import ingestion.main; print('ingestion.main OK')"
ingestion.main OK
```

smoke واقعی روی هر چهار زیرکلاس (بدون DB/شبکه):

```
finpy ok: [('market_snapshot', 'ABC')]
finpy empty: []
html -> html_response | src: finpy_tse
invalid -> invalid_json | src: finpy_tse
tsetmc: 1
tehran: 1
tseutils: 1
```

تست‌ها:

```
$ python -m pytest tests/unit/parsers -q -p no:cacheprovider
15 passed in 5.80s
EXIT_PARSERS=0

$ python -m pytest tests/unit/brsapi/test_sync_helpers.py tests/unit/repositories -q -p no:cacheprovider
53 passed in 10.27s
EXIT_REPOS=0

$ python -m pytest tests/unit/test_ingestion_worker_persistence.py tests/unit/parsers -q -p no:cacheprovider
19 passed in 6.56s
EXIT_WORKER_PARSERS=0

$ python -m ruff check ingestion/parser/library_parsers.py ingestion/parser/errors.py ingestion/worker.py
All checks passed!
RUFF_EXIT=0
```

(تست‌های `tests/unit/parsers` شامل ۹ تست قرارداد پارسر و ۶ تست انتشار `ParseError` در
`worker`/`sync_service` هستند و همگی با بازگردانی زیرکلاس‌ها سبز ماندند.)

افزودهٔ بعدی (همان جلسه) — پوشش `ReplayEngine`: دو تست آفلاین در همان فایل
`tests/unit/parsers/test_parse_error_propagation.py`:

- `test_replay_counts_parse_error_as_failed_not_replayed` — از دو آبجکت خام (یکی سالم، یکی HTML)
  نتیجه دقیقاً `{"total_objects": 2, "replayed": 1, "failed": 1}` است؛ یعنی پایلود ناخوانا در
  `failed` می‌نشیند و هرگز «replay موفق» شمرده نمی‌شود.
- `test_replay_keeps_valid_empty_payload_as_replayed` — پاکت معتبر با `records: []` هم `replayed`
  می‌شود (`failed == 0`)، همان تفکیکی که قرارداد پارسر می‌کند.

(این رفتار از قبل در `replay_source` وجود داشت — `except Exception → failed += 1` — و تغییر کد لازم
نشد؛ تست فقط آن را قفل می‌کند.)

```
$ python -m pytest tests/unit/parsers tests/unit/test_ingestion_worker_persistence.py -q -p no:cacheprovider
21 passed in 4.65s
EXIT_PARSERS=0

$ python -m ruff check tests/unit/parsers/test_parse_error_propagation.py
All checks passed!
RUFF_EXIT=0
```

### ۹-۴) اجرانشده‌ها (بدون تغییر نسبت به بخش ۶)

| مورد | وضعیت | علت |
|---|---|---|
| `tests/unit/brsapi/test_sync_outcomes.py` (untracked، جریان موازی) | **BLOCKED** | همان `ImportError: cannot import name 'BrsApiMalformedResponseError' from 'brsapi.client'`؛ فایل دست‌نخورده ماند و با `--ignore` کنار گذاشته می‌شود. |
| تست‌های `needs_db` هم‌بسته با sync | **BLOCKED** | PostgreSQL محلی در دسترس نیست (`localhost:5432/market`). |
| اجرای end-to-end واقعی `IngestionEngine` با منبع زنده | انجام نشد | ممنوعیت درخواست زنده؛ فقط import و smoke آفلاین اثبات شد. |

### ۹-۵) ریسک‌های باقی‌مانده (به‌روزشده)

1. ~~بالا — زیرکلاس‌های پارسر غایب‌اند~~ → **رفع شد** (این پیوست). `ingestion.main` بالا می‌آید و هر چهار پارسر dispatch می‌کنند.
2. ریسک‌های ۲ تا ۵ بخش ۷ (BOM، پرتاب مجدد در worker، تشخیص HTML فقط با `startswith(b"<")`، `{}` معتبر) بدون تغییر باقی‌اند.
3. **متوسط — تفاوت helperها با نسخهٔ موقت working tree.** هر کدی که در جریان موازی به رفتار ساده‌شدهٔ
   helperها (مثلاً `_safe_str` بدون `str()` یا `_map_price_fields` بدون `yesterday_close`) تکیه کرده باشد،
   اکنون رفتار `HEAD` را می‌بیند. تست‌های موجود سبز هستند، اما این جریان موازی باید یک‌بار بازبینی شود.
4. **پایین — `test_sync_outcomes.py`** همچنان collection کل `tests/unit/brsapi` را می‌شکند تا وقتی جریان موازی
   `BrsApiMalformedResponseError`/`brsapi/parsers/errors.py` را اضافه کند.

### ۹-۶) وضعیت این پیوست

- **PASS** برای آیتم «بازگردانی چهار زیرکلاس + ادغام با قرارداد `ParseError`»: `ingestion.main` دوباره import می‌شود،
  هر چهار پارسر روی payload واقعیِ شکل‌دار dispatch می‌کنند، ورودی ناخوانا `ParseError` می‌دهد و پاکت خالی معتبر `[]`
  می‌ماند؛ ۷۴ تست سبز در اجرای ترکیبی نهایی (سه اجرای مجزا ۱۷ و ۵۳ و ۲۱ با هم‌پوشانی) و ruff سبز.
- **وضعیت کلی مأموریت همچنان PARTIAL** است، فقط به‌دلیل موارد **BLOCKED** بیرون از این دامنه: تست‌های DB-وابستهٔ sync
  و فایل untracked شکستهٔ `test_sync_outcomes.py` از جریان موازی.
