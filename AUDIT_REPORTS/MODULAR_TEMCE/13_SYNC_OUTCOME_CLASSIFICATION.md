# مرحلهٔ ۱۳ — طبقه‌بندی outcome در `sync_service` (تفکیک «خالی معتبر» از «خطای خواندن/منبع»)

> گزارش جدید و مستقل. هیچ‌کدام از گزارش‌های قبلی (`00`…`12`, `QA_STAGE_*`) بازنویسی نشد.

## ۰) فرادادهٔ اجرا

| کلید | مقدار |
|---|---|
| تاریخ/زمان (Tehran) | ۲۰۲۶-۱۰-۲۹، حدود ۱۰:۵۰–۱۱:۱۵ |
| ریشهٔ مخزن | `C:\Users\Iran\Desktop\temce` |
| شاخه | `integration/golddesk-fixes` |
| `HEAD` | `90597e05` (`90597e05b9f4328bcd82ee819a31ba5c55413c12`) — تغییری نکرد |
| پوسته / Python | bash (Git Bash)؛ Python 3.11؛ pytest با `asyncio_mode=auto` |
| Ruff | `0.15.17` (فقط `check` روی فایل‌های همین دامنه؛ `--fix` اجرا نشد) |
| BrsApi / TSETMC / RSS زنده | **استفاده نشد** (همهٔ تست‌ها آفلاین/با fake) |
| DB / Redis | PostgreSQL محلی در دسترس نیست → تست‌های `needs_db` و تست‌های endpoint-وابسته **BLOCKED** |
| Commit / reset / clean / stash / checkout / stage | **انجام نشد** |

وضعیت git در پایان کار (بدون دست‌کاری، فقط شمارش):

```
$ git status --porcelain=v1 | awk '{print substr($0,1,2)}' | sort | uniq -c
     76  M      # unstaged
     36 ??      # untracked
    102 A       # staged (کاربر)
     23 M       # staged (کاربر)
     13 MM      # staged + unstaged
```

## ۱) مسئله و دامنه

فایل `tests/unit/brsapi/test_sync_outcomes.py` (untracked، ساختهٔ جریان موازی) به‌عنوان **spec** وجود داشت،
اما کل سمت تولیدِ آن workstream در درخت نبود. نتیجه:

```
$ python -m pytest tests/unit/brsapi/test_sync_outcomes.py -q
E   ImportError: cannot import name 'BrsApiMalformedResponseError' from 'brsapi.client'
ERROR tests/unit/brsapi/test_sync_outcomes.py
```

و حتی با فرض رفع import، این اجزا غایب بودند:

| مورد موردنیاز تست | وضعیت پیش از کار |
|---|---|
| `brsapi.parsers.errors.BrsApiParseError` | وجود نداشت |
| پارسرها روی shape نامعتبر | `logger.warning` + `return []` (خطا در قالب «خالی» پنهان می‌شد) |
| `BrsApiMalformedResponseError` / `BrsApiSourceError` | وجود نداشت |
| `BrsApiClient._parse_response(content, content_type)` | امضای تک‌آرگومانی؛ روی HTML و JSON شکسته `[]`/`{"_raw_text": …}` برمی‌گرداند |
| `BrsApiResponse.received_at` | وجود نداشت |
| `SyncReport.outcome` + طبقه‌بندی خطا | وجود نداشت |
| stamp کردن رکوردها با زمان دریافت واقعی | نبود؛ هر پارسر `now()` خودش را می‌زد |

## ۲) مصرف‌کننده‌هایی که تغییر پارسرها روی آن‌ها اثر می‌گذارد (فقط‌خواندنی، پیش از تغییر)

| مسیر | نحوهٔ مصرف | اثر تغییر |
|---|---|---|
| `brsapi/services/sync_service.py:sync()` | `parser(brs_resp.data)` داخل `try/except Exception` | استثنا → `SyncReport(success=False, outcome="parse_error")` |
| `brsapi/jobs/registry.py:748` | `parser=self._get_parser(...)` به `sync()` داده می‌شود | همان مسیر بالا |
| `apps/api/endpoints/brsapi.py:1271` (`sync_section`) | `parser=cfg["parser"]` به `sync()` | همان مسیر بالا + افشای `outcome` در پاسخ |
| `apps/api/endpoints/brsapi.py:1350` (download live) | `cfg["parser"](result.value.data)` مستقیم، داخل `try/except` → HTTP 500 «Parse error» | پیام خطا صریح‌تر می‌شود، کرش نمی‌کند |
| `sync_transactions` / `sync_shareholders` / `sync_candlesticks` | parser callable داخلی که `TsetmcParser.*` را صدا می‌زند | استثنا به `sync()` می‌رسد و `parse_error` می‌شود |
| `brsapi/jobs/registry.py:_get_parser` fallback | `mapping.get(ep.path, TsetmcParser.parse_all_symbols)` | برای endpoint ناشناخته، shape غلط حالا خطا می‌دهد (پیش‌تر `[]`) |

## ۳) قرارداد نهایی

| ورودی | نتیجه |
|---|---|
| `parse_all_symbols("garbage")` / `parse_shareholders(None)` / `parse_transactions({"unexpected": []})` | `BrsApiParseError` |
| `CommodityParser.parse("garbage")` / `CryptoParser.parse("garbage")` / `ImeParser.parse_futures("garbage")` | `BrsApiParseError` |
| `parse_all_symbols([])` / `parse_shareholders({"data": []})` / `parse_candlesticks({"status": "no_data"})` / `parse_transactions({})` / `parse_transactions({"code_http":200,"successful":true,"data":{}})` | `[]` (پاسخ خالی معتبر) |
| بدنهٔ HTML / `<!DOCTYPE html>` | `BrsApiMalformedResponseError` («HTML page instead of JSON») |
| JSON شکسته | `BrsApiMalformedResponseError` («invalid JSON: …») |
| `{"code_http":402,"successful":false,"message_error":"quota exhausted"}` | `BrsApiSourceError` («BrsApi provider error (HTTP 402): …») |
| `{"status": "no_data"}` | داده معتبر؛ `BrsApiResponse.is_empty is True` |
| خطای fetch شامل malformed/HTML/invalid JSON | `SyncReport(success=False, outcome="malformed")` |
| خطای fetch شامل quota/302/Suspend/blocked/rate limit/budget | `outcome="provider_blocked"` |
| خطای fetch شامل timeout | `outcome="timeout"` |
| سایر خطاهای fetch | `outcome="source_error"` |
| پارسر استثنا بدهد یا نوع غیر `list`/`dict` برگرداند | `outcome="parse_error"` |
| پاسخ معتبر بدون رکورد | `success=True, items_count=0, outcome="empty"` |
| dedup | `success=True, skipped=True, outcome="skipped"` |
| خطای DB (rollback شده) | `outcome="storage_error"` |
| نوشتن موفق | `outcome="success"` |
| `SyncReport` ساخته‌شده در مسیرهای دیگر | پیش‌فرض `outcome="unknown"` (تا ادعای موفقیت کاذب نشود) |

## ۴) تغییرات و diff هر فایل

> `git diff --stat` این فایل‌ها با `HEAD` شامل ویرایش‌های **از قبل موجودِ** جریان موازی هم هست؛
> در ادامه فقط hunkهای همین کار نشان داده شده است.

### ۴-۱) `brsapi/parsers/errors.py` — **فایل جدید**

```python
"""Parse-error contract for BrsApi response parsers. …"""

from __future__ import annotations


class BrsApiParseError(ValueError):
    """The payload did not have the shape the parser understands. …"""
```

**دلیل:** یک نوع خطای مشخص برای «نمی‌توانم این پاسخ را بخوانم». subclass از `ValueError` انتخاب شد تا
handlerهای موجود `except ValueError` نشکنند، ولی مصرف‌کنندهٔ دقیق بتواند فقط همین نوع را بگیرد.

### ۴-۲) `brsapi/parsers/tsetmc.py` (+۵۸/−۱۲ نسبت به `HEAD`)

```diff
 import jdatetime
 
+from brsapi.parsers.errors import BrsApiParseError
+
 logger = getLogger(__name__)

         if not isinstance(data, list):
-            logger.warning("AllSymbols: expected list, got %s", type(data).__name__)
-            return []
+            raise BrsApiParseError(
+                f"AllSymbols: expected a JSON list, got {type(data).__name__}"
+            )
```

```diff
+        if data is None:
+            raise BrsApiParseError("Transaction: payload is None, not a JSON document")
+
         # Unwrap BrsApi envelope: {"data": {"transaction": [...]}}
         if isinstance(data, dict):
+            if not data:
+                # Valid empty response: the provider answered, with no rows.
+                return []
             inner = data.get("data")
             if isinstance(inner, dict):
                 items = inner.get("transaction")
                 if isinstance(items, list):
                     data = items
-                else:
-                    logger.warning("Transaction: no 'transaction' list in data envelope")
+                elif not inner:
                     return []
-            else:
-                logger.warning("Transaction: expected dict, got %s", type(data).__name__)
+                else:
+                    raise BrsApiParseError(
+                        "Transaction: 'data' envelope has no 'transaction' list"
+                    )
+            elif isinstance(inner, list):
+                data = inner
+            elif isinstance(data.get("transaction"), list):
+                data = data["transaction"]
+            elif {"code_http", "successful", "status"} & set(data):
+                # Provider envelope without rows (e.g. ``{"status": "no_data"}``).
                 return []
+            else:
+                raise BrsApiParseError(
+                    "Transaction: unrecognised envelope keys "
+                    f"{sorted(data)[:5]}"
+                )
 
         if not isinstance(data, list):
-            logger.warning("Transaction: expected list, got %s", type(data).__name__)
-            return []
+            raise BrsApiParseError(
+                f"Transaction: expected a JSON list, got {type(data).__name__}"
+            )
```

```diff
     @classmethod
     def parse_shareholders(cls, data: Any) -> list[dict[str, Any]]:
         """``/Tsetmc/Shareholder.php`` response."""
+        if data is None:
+            raise BrsApiParseError("Shareholder: payload is None, not a JSON document")
+        if isinstance(data, dict):
+            if not data:
+                return []
+            inner = data.get("shareholders", data.get("data"))
+            if isinstance(inner, list):
+                data = inner
+            elif {"code_http", "successful", "status"} & set(data):
+                return []
+            else:
+                raise BrsApiParseError(
+                    "Shareholder: unrecognised envelope keys "
+                    f"{sorted(data)[:5]}"
+                )
         if not isinstance(data, list):
-            logger.warning("Shareholder: expected list, got %s", type(data).__name__)
-            return []
+            raise BrsApiParseError(
+                f"Shareholder: expected a JSON list, got {type(data).__name__}"
+            )
```

**دلیل:** تفکیک «پاکت خالی معتبر» از «شکل ناخوانا». `parse_candlesticks` عمداً دست‌نخورده ماند
(در spec فقط حالت خالی معتبرش لازم بود و شکل غیر dict/list آن بیرون از دامنهٔ این مأموریت است).

### ۴-۳) `brsapi/parsers/commodity.py` / `crypto.py` / `ime.py` (هرکدام +۷/−۲)

```diff
 import json
 from datetime import UTC, datetime
 from logging import getLogger
 from typing import Any
 
+from brsapi.parsers.errors import BrsApiParseError
+
 logger = getLogger(__name__)

         else:
-            logger.warning("Commodity: unexpected data type %s", type(data).__name__)
-            return []
+            raise BrsApiParseError(
+                f"Commodity: unexpected data type {type(data).__name__}"
+            )
```

(`crypto.py` همان الگو با پیام `Crypto: …`؛ `ime.py` در `_ensure_list` که
`parse_futures/options/certificates/funds/physical_trades` از آن استفاده می‌کنند.)

### ۴-۴) `brsapi/client.py` (+۸۶/−۵)

طبقه‌بندی خطای جدید (پیش از `BrsApiResponse`):

```python
class BrsApiMalformedResponseError(Exception):
    """The HTTP body was not the JSON document BrsApi promised. …"""


class BrsApiSourceError(Exception):
    """BrsApi answered HTTP 200 with a provider-level error envelope. …"""


_HTML_CONTENT_TYPE_MARKERS = ("text/html", "application/xhtml")
_HTML_BODY_PREFIXES = ("<!doctype html", "<html", "<?xml", "<!--")


def _looks_like_html(content_type: str, text: str) -> bool:
    lowered_type = (content_type or "").lower()
    if any(marker in lowered_type for marker in _HTML_CONTENT_TYPE_MARKERS):
        return True
    head = text.lstrip()[:200].lower()
    return head.startswith(_HTML_BODY_PREFIXES)


def _raise_for_provider_error(data: dict[str, Any]) -> None:
    if data.get("successful") is not False:
        return
    code = data.get("code_http")
    message = (
        data.get("message_error")
        or data.get("message")
        or data.get("status")
        or "provider error"
    )
    prefix = f"BrsApi provider error (HTTP {code})" if code is not None else "BrsApi provider error"
    raise BrsApiSourceError(f"{prefix}: {message}")
```

```diff
     raw_bytes: bytes | None = None                   # Raw HTTP body (for audit)
     fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
+    # Naive UTC timestamp of when the body arrived; sync stamps stored rows and
+    # the raw-payload log with this instead of a per-parser ``now()``.
+    received_at: datetime | None = None
     elapsed_ms: float = 0.0
```

```diff
                 resp = await self._client.get(url, params=params)
                 elapsed = (asyncio.get_event_loop().time() - start) * 1000
+                received_at = datetime.now(UTC).replace(microsecond=0, tzinfo=None)
 
                 raw_bytes = resp.content
 
                 if resp.status_code == 200:
-                    data = self._parse_response(resp.content)
+                    data = self._parse_response(
+                        resp.content, resp.headers.get("content-type", "")
+                    )
@@
                         raw_bytes=raw_bytes if self._raw_sink_enabled else None,
+                        received_at=received_at,
                         elapsed_ms=elapsed,
```

```diff
-    def _parse_response(self, content: bytes) -> Any:
+    def _parse_response(self, content: bytes, content_type: str = "") -> Any:
+        """Decode one HTTP body, rejecting non-JSON and provider error envelopes. …"""
+        text = content.decode("utf-8", errors="replace")
+        if _looks_like_html(content_type, text):
+            raise BrsApiMalformedResponseError(
+                "BrsApi returned an HTML page instead of JSON "
+                "(suspend/block page)"
+            )
         try:
-            return json.loads(content)
-        except json.JSONDecodeError:
-            # Sometimes BrsApi returns plain text on error
-            return {"_raw_text": content.decode("utf-8", errors="replace")}
+            data = json.loads(content)
+        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
+            raise BrsApiMalformedResponseError(
+                f"BrsApi returned invalid JSON: {exc}"
+            ) from exc
+        if isinstance(data, dict):
+            _raise_for_provider_error(data)
+        return data
```

**دلیل:** پیش‌تر یک پاسخ HTML/قطعه‌JSON به داده تبدیل می‌شد و در نهایت «sync موفق با صفر رکورد» ثبت می‌کرد.
`fetch()` این استثناها را همان‌جا به `Result.fail(message)` تبدیل می‌کند، پس هیچ callerی کرش نمی‌کند و
پیام قابل‌طبقه‌بندی (`malformed`) به `sync()` می‌رسد.

### ۴-۵) `brsapi/services/sync_service.py` (فقط hunkهای این کار)

```diff
 from dataclasses import dataclass, field
+from datetime import UTC, datetime
 from logging import getLogger
-from typing import Any
+from typing import Any, Literal
```

```python
SyncOutcome = Literal[
    "success", "empty", "skipped", "parse_error", "malformed",
    "provider_blocked", "timeout", "source_error", "storage_error", "unknown",
]


def _classify_fetch_error(error: str | None) -> SyncOutcome:
    text = (error or "").lower()
    if any(k in text for k in ("malformed", "html", "invalid json", "not json")):
        return "malformed"
    if any(k in text for k in ("timeout", "timed out")):
        return "timeout"
    if any(
        k in text
        for k in ("quota", "302", "suspend", "blocked", "rate limit", "budget", "cooldown", "429")
    ):
        return "provider_blocked"
    return "source_error"


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.replace(microsecond=0)
```

```diff
     error: str | None = None
+    # One of :data:`SyncOutcome`. ``success`` says whether anything went wrong;
+    # ``outcome`` says what actually happened (empty vs unreadable vs blocked).
+    outcome: str = "unknown"
     skipped: bool = False
```

ثبت `outcome` در تمام مسیرهای `sync()`:

| خط | مسیر | مقدار |
|---|---|---|
| dedup skip | `skipped=True` | `"skipped"` |
| fetch failure | `success=False` | `_classify_fetch_error(result.error)` |
| `brs_resp.is_empty` | `success=True, items_count=0` | `"empty"` |
| استثنای پارسر | `success=False, error="ParseError: …"` | `"parse_error"` |
| نوع بازگشتی غیر `list`/`dict` | `success=False` | `"parse_error"` |
| `not records` | `success=True, items_count=0` | `"empty"` |
| خطای DB | `success=False, error="DBError: …"` | `"storage_error"` |
| موفق | `success=True, items_count=total` | `"success"` |

stamp زمان دریافت (پیش از `# 4. Store`):

```diff
+        # Stamp rows with the actual receive time of this response (naive UTC,
+        # second-truncated) instead of a per-parser ``now()``: a retry or a slow
+        # parse must not shift the (symbol, fetched_at) dedup key.
+        received_at = _naive_utc(getattr(brs_resp, "received_at", None))
+        if received_at is not None:
+            for rec in records:
+                if isinstance(rec, dict) and "fetched_at" in rec:
+                    rec["fetched_at"] = received_at
+
         # 4. Store
```

```diff
                     status_code=brs_resp.status_code,
                     params=params,
+                    receive_time=received_at,
                 )
```

> سایر تغییرات دیده‌شده در `git diff` این فایل (`replace_filter`, افزودن `commit()` در دو مسیر،
> `invalidate_agg_cache`, پیام `DBError after …`) **از قبل** در working tree بودند و دست نخوردند.

### ۴-۶) افشای `outcome` در پاسخ API (`apps/api/endpoints/brsapi.py`, فقط +۳ خط)

```diff
                     "success": report.success,
+                    "outcome": report.outcome,
                     "items_count": report.items_count,
```

در هر سه شاخهٔ `POST /brsapi/manage/sync/{section_id}`: NAV، candlestick و مسیر عمومی.

### ۴-۷) تست‌ها

دو تست قدیمی که قرارداد سهل‌گیرانه را قفل کرده بودند، به قرارداد جدید منتقل شدند (تضعیف نشدند):

```diff
-def test_parse_shareholders_non_list_returns_empty():
+def test_parse_shareholders_valid_empty_envelope_stays_empty():
     assert TsetmcParser.parse_shareholders({"data": []}) == []
-    assert TsetmcParser.parse_shareholders(None) == []
-    assert TsetmcParser.parse_shareholders("garbage") == []
+
+
+def test_parse_shareholders_malformed_payload_raises():
+    with pytest.raises(BrsApiParseError):
+        TsetmcParser.parse_shareholders(None)
+    with pytest.raises(BrsApiParseError):
+        TsetmcParser.parse_shareholders("garbage")
```

```diff
-    # None data
-    assert TsetmcParser.parse_transactions(None) == []
-
-    # Missing transaction key
-    assert TsetmcParser.parse_transactions({"code_http": 200, "successful": True, "data": {}}) == []
+    # Provider envelope carrying an empty data payload
+    assert TsetmcParser.parse_transactions({"code_http": 200, "successful": True, "data": {}}) == []
+
+    with pytest.raises(BrsApiParseError):
+        TsetmcParser.parse_transactions(None)
+    with pytest.raises(BrsApiParseError):
+        TsetmcParser.parse_transactions({"unexpected": []})
```

دو نقص در **harness** فایل spec (بدون تغییر هیچ assertion):

```diff
 async def _run_sync(client, *, parser=lambda data: data, dedup_seconds=0, received_at=None):
+    if received_at is not None:
+        # The receive time is a property of the fetched response, so give the
+        # client the value the test wants that response to carry.
+        client.received_at = received_at
     session = FakeSession()
```

```diff
     monkeypatch.setattr(
         sync_service_module.RawPayloadRepository, "store", capture_store,
     )
+    async def capture_insert(self, records, **kwargs):
+        return len(records)
+
+    monkeypatch.setattr(
+        sync_service_module.BulkUpsertRepository, "bulk_insert", capture_insert,
+    )
```

**چرا لازم بود:** تست اول `received_at` را فقط به helper می‌داد (که آن را دور می‌ریخت) و تست دوم
`bulk_insert` را patch نمی‌کرد، پس با `FakeSession` (بدون `execute`) هرگز نمی‌توانست سبز شود.
assertionها دست‌نخورده‌اند.

## ۵) اجرای واقعی تست‌ها (خروجی خام و exit code)

```
$ python -m pytest tests/unit/brsapi/test_sync_outcomes.py -q -p no:cacheprovider
...................
19 passed in 4.15s
EXIT_TARGET=0
```

```
$ python -m pytest tests/unit/brsapi tests/unit/test_brsapi_shareholder_parser.py \
    tests/unit/test_brsapi_candlesticks.py tests/unit/test_brsapi_sync_fixes.py \
    "tests/unit/test_trades_e2e.py::test_brsapi_parser_handles_transaction_response" \
    "tests/unit/test_trades_e2e.py::test_brsapi_parser_handles_empty_response" \
    -q -p no:cacheprovider
120 passed, 1 warning in 28.92s
EXIT_BRSAPI=0
```

```
$ python -m pytest tests/unit/test_sync_service_persistence_scope.py \
    tests/unit/services/test_sync_master_service.py tests/unit/brsapi/test_sync_helpers.py \
    tests/unit/parsers tests/unit/repositories -q -p no:cacheprovider
..............................................
93 passed in 12.89s
EXIT_SYNC=0
```

```
$ python -m ruff check brsapi/parsers/errors.py brsapi/parsers/tsetmc.py \
    brsapi/parsers/commodity.py brsapi/parsers/crypto.py brsapi/parsers/ime.py \
    brsapi/client.py brsapi/services/sync_service.py apps/api/endpoints/brsapi.py \
    tests/unit/brsapi/test_sync_outcomes.py tests/unit/test_brsapi_shareholder_parser.py \
    tests/unit/test_trades_e2e.py services/market_service.py
All checks passed!
RUFF_EXIT=0

$ python -m py_compile brsapi/parsers/errors.py brsapi/parsers/tsetmc.py \
    brsapi/parsers/commodity.py brsapi/parsers/crypto.py brsapi/parsers/ime.py \
    brsapi/client.py brsapi/services/sync_service.py apps/api/endpoints/brsapi.py
COMPILE_EXIT=0
```

اثبات مسیر API (invoke مستقیم با client/service استاب، بدون DB/شبکه):

```
generic     -> {'endpoint': '/Test', 'section_id': 'all-symbols', 'success': False,
                'outcome': 'malformed', 'items_count': 0, 'duration_ms': 0.0,
                'skipped': False, 'error': 'HTML page'}
candlestick -> {'endpoint': '/Candlestick', 'section_id': 'candlestick', 'success': False,
                'outcome': 'parse_error', 'items_count': 0, 'duration_ms': 0.0,
                'skipped': False, 'error': 'bad shape'}
nav         -> {'endpoint': '/Nav', 'section_id': 'nav', 'success': True,
                'outcome': 'empty', 'items_count': 0, 'duration_ms': 0.0,
                'skipped': False, 'error': None}
```

## ۶) اجرانشده‌ها و علت

| مورد | وضعیت | شاهد |
|---|---|---|
| ۶ تست endpoint در `tests/unit/test_trades_e2e.py` | **BLOCKED** | `RuntimeError('Cannot connect to PostgreSQL database…')` — `6 failed, 9 passed in 80.24s`, `EXIT_TRADES=1`. تست‌های پارسر همان فایل (۲ تست دامنهٔ این کار) سبزند. |
| ۵ تست `needs_db` هم‌بسته با sync (`test_brsapi_sync_integration.py`, `test_brsapi_sync_status.py`) | **BLOCKED** | `sssss` → `5 skipped in 2.10s`, `EXIT_NEEDSDB=0`؛ PostgreSQL محلی نیست. موفق اعلام نمی‌شوند. |
| `tests/unit/services` (کامل) | جزئی | ۲۳ خطا در یک اجرا / ۱۳ در اجرای بعدی: `test_adjusted_price_reader.py` (نیاز به DB، `password authentication failed for user "market"`) و `test_indicator_calculation.py` (assertهای ichimoku/stochastic، خارج از دامنه). |
| درخواست زنده به BrsApi/TSETMC/RSS | انجام نشد | طبق قواعد مأموریت. |
| `pytest tests` (کل پروژه) | اجرا نشد | مخزن آلوده به فایل‌های نیمه‌کارهٔ staged/untracked سایر جریان‌ها و تست‌های DB-وابسته. |

## ۷) ریسک‌های باقی‌مانده

1. **متوسط — `outcome` فقط در حافظه است، نه در `sync_log`.** تاریخچهٔ sync (و صفحهٔ admin) همچنان
   فقط `status` + `error_message` را می‌بیند؛ برای نمایش «چرا شکست خورد» در تاریخچه، یک ستون/فیلد
   پایدار لازم است. در این مأموریت عمداً به schema دست نزدم.
2. **متوسط — فرانت‌اند هنوز مصرف نمی‌کند.** `frontend/src/app/{sync,data,admin}/page.tsx` تایپ
   `SyncResult` را بدون `outcome` دارند و فقط `items_count`/`error` را نشان می‌دهند.
3. **متوسط — طبقه‌بندی بر مبنای کلمه‌های پیام خطاست.** `_classify_fetch_error` رشته‌های
   «malformed/html/invalid json/timeout/quota/302/…» را می‌گردد؛ اگر پیام‌های `client.py` بازنویسی
   شوند، طبقه‌بندی بی‌صدا به `source_error` می‌افتد. راه آینده: `Result` حامل کد خطای ساختاری باشد.
4. **پایین — سخت‌گیری جدید پارسرها می‌تواند در jobهای دیگر ظاهر شود.** `_get_parser` برای endpoint
   ناشناخته `parse_all_symbols` را برمی‌گرداند؛ اگر آن endpoint دیکشنری برگرداند، حالا `parse_error`
   ثبت می‌شود (پیش‌تر `[]`). این رفتار مطلوب است ولی باید در پایش اولین اجراها دیده شود.
5. **پایین — `parse_candlesticks` هنوز سهل‌گیر است** (شکل غیر dict/list → `[]`). برای یکدستی کامل
   باید در گام بعدی همان قرارداد را بگیرد؛ در spec این کار نبود.
6. **پایین — stamping فقط روی رکوردهایی که از قبل `fetched_at` دارند** اعمال می‌شود (تا ستون‌های
   بدون این فیلد دست‌کاری نشوند). پارسرهایی که `fetched_at` ندارند همچنان ساعت خودشان را ندارند.
7. **پایین — حذف `{"_raw_text": …}`** از `_parse_response`: هیچ مصرف‌کننده‌ای در مخزن به آن تکیه
   نمی‌کرد (grep شد)، ولی هر اسکریپت بیرونی که به این رفتار وابسته بود، حالا استثنا می‌گیرد.

## ۸) وضعیت نهایی: **PASS** (برای این workstream) — با موارد BLOCKED بیرونی

- **سبز و اثبات‌شده:** `tests/unit/brsapi/test_sync_outcomes.py` (۱۹ تست) کامل پاس می‌شود؛
  ۱۲۰ تست brsapi/پارسر و ۹۳ تست sync/parsers/repositories سبز؛ ruff و py_compile بدون خطا؛
  رفتار واقعی هر سه شاخهٔ API با استاب تأیید شد.
- **چرا نه PASS مطلق:** ۶ تست endpoint در `test_trades_e2e.py` و ۵ تست `needs_db` به‌خاطر نبود
  PostgreSQL **BLOCKED** هستند؛ ۱۳–۲۳ خطای `tests/unit/services` (DB و indicator) خارج از دامنه و
  از قبل موجود است؛ و `outcome` هنوز در تاریخچهٔ sync/فرانت‌اند دیده نمی‌شود (ریسک ۱ و ۲).

## ۹) پیوست — دو اصلاح هم‌زمان در همین جلسه (خارج از دامنهٔ اصلی، برای ردیابی)

| فایل | تغییر | شاهد |
|---|---|---|
| `services/market_service.py` | در `_build_sectors` متغیر `result` تعریف نشده بود (NameError که در `get_sector_summary` بلعیده می‌شد و لیست خالی برمی‌گرداند) و برچسب پیش‌فرض بخش `"ساری"` بود؛ به `for sec in sectors.values()`، `return list(sectors.values())` و پیش‌فرض `"سایر"` اصلاح شد | `pytest tests/unit/services/test_market_service.py tests/unit/services/test_all_services.py` → `128 passed in 6.32s`, `EXIT_MARKET=0` |
| `apps/api/endpoints/brsapi.py` | افزودن `"outcome": report.outcome` به سه پاسخ `manage/sync` (بند ۴-۶) | خروجی استاب در بند ۵ |
