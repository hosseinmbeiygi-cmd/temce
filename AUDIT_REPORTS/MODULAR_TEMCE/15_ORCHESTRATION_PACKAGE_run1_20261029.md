# گزارش ممیزی مرحلهٔ ۱۲ — بستهٔ `orchestration/` (جریان‌های گردش‌کار)

- **شناسهٔ اجرا:** `RUN3-ORCHESTRATION-PACKAGE`
- **تاریخ:** 2026-10-29 (Asia/Tehran)
- **شاخه:** `integration/golddesk-fixes`
- **HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون تغییر)
- **دامنه:** کل بستهٔ `orchestration/` (۱۷ فایل) — بخشی که هیچ تست مستقیم و هیچ ممیزی اختصاصی نداشت. عامل‌های دیگر فقط `news_flow.py` را دست زده بودند.

> فایل جدید؛ هیچ گزارش قبلی بازنویسی نشد.

---

## ۱. خلاصهٔ مدیریتی

سه یافتهٔ واقعی پیدا و رفع شد:

| شناسه | عنوان | شدت | وضعیت |
|---|---|---|---|
| O1 | خطای timeout در `WorkflowRunner` به `"Unknown error"` تبدیل می‌شد (از دست رفتن علت) | P2 | ✅ رفع‌شده + تست |
| O2 | خطاهای بدنه‌ی خالی (مثل `raise ValueError`) به `"Unknown error"` تبدیل می‌شد | P2 | ✅ رفع‌شده + تست |
| O3 | سه flow استاب (`CodalFlow`/`FundFlow`/`MarketFlow`) موفقیتِ کاذب گزارش می‌کردند | P2 | ✅ رفع‌شده + تست |

هیچ داده‌ای حذف/تغییر نکرد؛ هیچ عملیات مخرب Git انجام نشد؛ بستهٔ `orchestration/` از DB/Redis/provider مستقل است و همه‌جا قابل‌تست است.

---

## ۲. موجودی بسته (فایل‌های بررسی‌شده)

| فایل | نقش | یافته |
|---|---|---|
| `runners.py` | اجراکنندهٔ ترتیبی/موازی workflow + retry/timeout/compensation | **O1، O2** |
| `contracts.py` | `Step`/`Workflow`/`WorkflowState`/`StepResult` | سالم |
| `context.py` | `WorkflowContext` | سالم |
| `checkpoints.py` | Checkpoint + store درون‌حافظه | سالم |
| `recovery.py` | طرح بازیابی از failure | سالم (فقط dispatcher) |
| `policies.py` | `RetryPolicy`/`TimeoutPolicy`/`CompensationPolicy` | سالم |
| `state_machine.py` | ماشین حالت workflow | سالم |
| `steps.py` | `FetchDataStep`/`TransformDataStep`/`ValidateDataStep`/`PersistDataStep`/`NotifyStep` | سالم |
| `signal_flow.py` / `backtest_flow.py` / `training_flow.py` | سازندهٔ workflow واقعی | سالم |
| `codal_flow.py` / `fund_flow.py` / `market_flow.py` / `news_flow.py` | flow استاب | **O3** (news قبلاً رفع شده بود) |
| `types.py` / `__init__.py` | نوع‌ها | سالم |

---

## ۳. یافته‌ها و علت ریشه‌ای

### O1 — گمشدن علتِ timeout (رفع‌شده)

- **فایل/خطوط:** `orchestration/runners.py:76-122` (`_execute_step_with_retry`).
- **شاهد اجرایی:** روی Python 3.11 مقدار `str(asyncio.TimeoutError())` و `str(TimeoutError())` رشتهٔ **خالی** است (اجرا شد: `''`). کد قبلی پیام شکست را از `str(last_error) or "Unknown error"` می‌ساخت؛ در نتیجه هر timeout روی مسیر `raise_on_timeout=True` به `"Unknown error"` تبدیل و علت واقعی گم می‌شد. اجرای واقعی: `Step a failed: Unknown error` برای یک timeout قطعی.
- **علت ریشه‌ای:** اتکا به `str(exc)` بدون fallback به نام کلاس استثنا.
- **اثر:** اپراتور از `StepResult.error` نمی‌توانست timeout را از خطای ناشناخته تشخیص دهد؛ مانع بازبینی و alerting درست.

### O2 — گمشدن پیام استثنای خالی‌بدنه (رفع‌شده)

- **شاهد:** `raise ValueError` بدون آرگومان → `str(exc)` خالی → همان `"Unknown error"`.
- **علت ریشه‌ای:** مشترک با O1.
- **اثر:** تشخیص‌ناپذیری خطاهای رایج (کلاس استثنا در دسترس بود ولی استفاده نمی‌شد).

### O3 — موفقیتِ کاذب در flowهای استاب (رفع‌شده)

- **فایل‌ها/خطوط:** `orchestration/codal_flow.py:11-13`، `fund_flow.py:11-13`، `market_flow.py:11-13`.
- **شاهد:** هر سه `Result.ok({"status": "completed"})` برمی‌گرداندند در حالی که فقط یک `logger.info` داشتند — دقیقاً همان الگوی `NewsFlow` که این‌بار در جای دیگری از عامل مربوطه رفع شده بود.
- **reachability:** هیچ‌کدام به هیچ روتر/job/سرویس wire نشده‌اند (grep کامل: تنها تعریف + یک تست منسوخ). یعنی **کد مرده** ولی هر اتصال آینده باعث «گزارش موفق برای کارِ انجام‌نشده» می‌شد.
- **علت ریشه‌ای:** عدم پیروی از الگوی «fail-closed» در استاب‌ها.
- **اثر:** خطر گزارش ingestion سالم در حالی که هیچ کاری انجام نشده — مغایر با اصل «هیچ موفقیتی بدون شاهد».

---

## ۴. اصلاحات انجام‌شده (حداقل دامنه)

### 4.1 `orchestration/runners.py`

- افزودن helper `_describe_error(exc, default=...)`:
  - اگر پیام غیرخالی باشد همان را برمی‌گرداند؛
  - برای `TimeoutError` پیام `"TimeoutError: step exceeded its timeout"`؛
  - در نهایت fallback به `type(exc).__name__`.
- `_execute_step_with_retry`: مسیر `TimeoutError` حالا به `retry.should_retry/delay_for` احترام می‌گذارد و پیام شکست نهایی از `_describe_error` می‌آید (به‌جای `str(last_error) or "Unknown error"`).
- `AsyncWorkflowRunner._execute_step` و دو `state.error = str(exc)` در دو `run()` به `_describe_error` منتقل شدند.
- *توجه:* رفتار retry روی Timeout با سیاست سراسری سازگار شد؛ تنظیمات پیش‌فرض را تغییر نداد (چون keyهای پیش‌فرض نصفه‌اند و خارج از دامنه است — بند ۶).

### 4.2 `orchestration/{codal,fund,market}_flow.py`

- هر سه به الگوی `NewsFlow` منتقل شدند: لاگ `error` + `Result.fail("not_implemented: …")`.

### 4.3 تست‌های جدید

- `tests/unit/orchestration/test_workflow_runner_errors.py` (۴ تست)
- `tests/unit/orchestration/test_placeholder_flows_fail_closed.py` (۳ تست پارامتری)

---

## ۵. فرمان‌ها، تست‌ها و exit codeها

همه با `$env:PYTHONUTF8=1` و `python` (3.11.9).

| موضوع | فرمان | نتیجه | exit |
|---|---|---|---|
| تست جدید خطاها — **قبل از اصلاح (RED)** | `python -m pytest tests/unit/orchestration/test_workflow_runner_errors.py -q -p no:cacheprovider --no-header` | `3 failed, 1 passed` | 1 |
| تست جدید استاب‌ها — **قبل از اصلاح (RED)** | `python -m pytest tests/unit/orchestration/test_placeholder_flows_fail_closed.py -q -p no:cacheprovider --no-header` | `3 failed` | 1 |
| همان دو تست — **بعد از اصلاح (GREEN)** | `python -m pytest tests/unit/orchestration tests/unit/test_news_stub_paths.py -q -p no:cacheprovider --no-header` | `9 passed` | 0 |
| مجموعهٔ ترکیبی این مرحله | `python -m pytest tests/unit/orchestration tests/unit/test_news_stub_paths.py tests/unit/test_runtime_ddl_consistency.py -q -p no:cacheprovider --no-header` | `13 passed` | 0 |
| ruff | `python -m ruff check orchestration/ tests/unit/orchestration/` | `All checks passed!` | 0 |

---

## ۶. موارد باز / خارج از دامنه (بدون رفع، مستندشده)

1. **پیش‌فرض‌شکستهٔ retry در `policies.py`:** `RetryPolicy.retry_on_exceptions=(Exception,)` همراه با `TimeoutPolicy.raise_on_timeout=True` یعنی حتی `ValueError` منطقی هم ۴ بار با backoff نمایی (۱+۲+۴=۷ ثانیه در اجرای واقعی مشاهده‌شد) retry می‌شود. این یک **تصمیم رفتاری** است؛ در این مرحله تنظیمات تغییر داده نشد و فقط Timeout با همان سیاست هم‌آهنگ شد. پیشنهاد: سیاست retry بر اساس نوع خطا تفکیک شود.
2. **شکاف هم‌روندی در `AsyncWorkflowRunner`:** به‌جای `asyncio.gather`، taskها به‌ترتیب `await` می‌شوند؛ پس `max_concurrency` عملاً موازی نیست. این یک بازطراحی است (خارج از دامنهٔ رفع باگ، بدون آزمون محلی معتبر).
3. **کد مردهٔ `orchestration/signal_flow.py`/`backtest_flow.py`/`training_flow.py`:** سازندهٔ workflow واقعی‌اند ولی هیچ‌جا wire نشده‌اند؛ تصمیم «حذف یا اتصال» یک تصمیم محصولی است.
4. **`recovery.execute_recovery` فقط dispatcher است** (به‌جز replay بقیه را `True` برمی‌گرداند) — نیازمند تصمیم محصولی و بستر اجرای واقعی.

---

## ۷. معیارهای پذیرش این مرحله

| معیار | نتیجه | شاهد |
|---|---|---|
| علت خطای timeout/استثنای خالی حفظ شود | ✅ PASS | RED→GREEN `3 failed→4 passed` |
| flow استاب موفقیتِ کاذب گزارش نکند | ✅ PASS | RED→GREEN `3 failed→3 passed` |
| تست بدون ضعیف‌کردن assertion | ✅ PASS | تست‌ها ابتدا RED بودند |
| ruff | ✅ PASS | exit 0 |
| هیچ شکست جدیدی در دامنه | ✅ PASS | `13 passed` |
| ادعای «کل پروژه بررسی شد» | ❌ مطرح نشد | فقط بستهٔ `orchestration/` |

---

## ۸. نتیجهٔ نهایی

- بستهٔ `orchestration/` که پیش‌تر بدون تست و بدون ممیزی بود، اکنون ۷ تست مستقیم دارد و سه باگ واقعی (O1/O2/O3) با علت ریشه‌ای و شاهد اجرایی رفع شد.
- وضعیت این مرحله: **PASS** برای O1/O2/O3؛ چهار مورد باز/خارج‌از‌دامنه در بند ۶ مستند شد و به‌اشتباه رفع‌شده اعلام نشد.
