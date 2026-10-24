# handoff — از دستیار ۳ (frontend-infra) به دستیار ۲ (backend-infra / API)

تاریخ: ۲۰۲۶-۱۰-۲۴ · branch مبدأ: `fix/frontend-infra` (کار در همین درخت، بدون commit تا تصمیم branch)

هیچ‌کدام از این تغییرات را من نمی‌توانم اعمال کنم: همه در `src/**.py` یا
`migrations/**` اند و در محدودهٔ ممنوعیت من اند. برای هر مورد: **فایل، خط، تغییر
مطلوب، دلیل، و چیزی که فرانت از من انتظار دارد.**

---

## ۰) ⛔ بلاکر — C1 در موتور انجام شده، ولی schemaِ API آن را می‌شکند

این مهم‌ترین مورد این فایل است و مستقل از بقیه، merge را تهدید می‌کند.

- **دستیار ۱ (موتور) C1 را تمام کرده است**:
  `src/gold_desk/scorer.py:66-68` سه فیلد `raw_total` / `available_weight` /
  `data_coverage_pct` را در `ScoreResult` دارد، `:216-218` آنها را پر می‌کند و
  `:225-226` وقتی `available_weight < MIN_SCORE_COVERAGE_WEIGHT` (ثابت
  `constants.py:151 = 60`) باشد `decision = "NO_DATA"` می‌گذارد.
- **ولی schema سیم (محدودهٔ شما) هنوز آن را رد می‌کند**:
  `src/gold_desk/schemas.py:74-79` →
  `decision: Literal["GREEN", "YELLOW", "RED"]` و هیچ‌کدام از سه فیلد C1 در
  `ScoreBlock` نیست.
- **تأییدشده با اجرا** (نه حدس):
  ```
  $ ScoreBlock(total=0, decision="NO_DATA", components={})
  ValidationError: decision  Input should be 'GREEN', 'YELLOW' or 'RED'
  ScoreBlock fields: ['total','decision','components','hard_stop_active','hard_stop_reason']
  ```
- **زنجیرهٔ نتیجه**: `snapshot_service.py:325-327` همان `score_result.decision` را
  مستقیم به `ScoreBlock(...)` می‌دهد → با پوشش داده < ۶۰ یک **ValidationError**
  داخل `build_snapshot` می‌شود → `api.py:95-103` آن را می‌گیرد و
  `{"success": false, …}` برمی‌گرداند. یعنی **کل `/snapshot` (و تمام صفحاتی که به
  آن وابسته‌اند) در حالت کمبود داده کرش می‌کند**، درحالی‌که کل point همین است که
  در کمبود داده باید `NO_DATA` نشان داده شود.
- **تغییر مطلوب (کوچک و افزایشی)**:
  1. `schemas.py:76` → `decision: Literal["GREEN", "YELLOW", "RED", "NO_DATA"]`
  2. افزودن سه فیلد با پیش‌فرض سازگار:
     `raw_total: int = 0`, `available_weight: int = 100`, `data_coverage_pct: float = 100.0`
  3. `snapshot_service.py:325` → پاس دادن همان سه مقدار از `score_result`
- **سمت من (انجام‌شده، منتظر این تغییر)**: تایپ فرانت هر سه فیلد را (اختیاری) دارد،
  `Decision` عضو `NO_DATA` را دارد، و چهار مسیر رندر decision از یک منبع مشترک
  (`frontend/src/lib/gold-decision.ts`) تغذیه می‌کنند؛ تست
  `frontend/src/__tests__/GoldNoData.test.tsx` (۸ تست) رندر `NO_DATA` را می‌پوشاند.
  تا وقتی این تغییر انجام نشود، آن مسیر در production قابل رسیدن نیست — نه اینکه
  فرانت کار نمی‌کند.
- **مقیاس (اشتباه متداول)**: `available_weight` و `data_coverage_pct` در موتور
  **۰ تا ۱۰۰** اند، نه ۰ تا ۱. فرانت بر اساس کد موتور این را فرض کرده
  (`Math.round(coverage)` + «٪»). اگر روزی به کسر تغییر کند، UI عدد را ۱٪ نشان می‌دهد.

## ۱) C3 — ۵۰۳ واقعی برای `/snapshot`، `/score`، `/signals/recent`

- **فایل/خط**: `src/gold_desk/api.py:95-103` (`get_snapshot`)، `:109-116` (`get_score`)،
  و مسیر `/signals/recent` در `:1180`.
- **واقعیت امروز**: هر سه در خطا **HTTP 200** با بدنهٔ
  `{"success": false, "data": null, "error": {"message": str(exc)}}` برمی‌گردانند.
  متن خطای داخلی (`str(exc)`) روی سیم بیرون می‌زند.
- **تغییر مطلوب**: `raise HTTPException(503)` با بدنهٔ
  `{"success": false, "error": "snapshot_unavailable"}`؛ جزئیات فقط در `logger.exception`.
- **دلیل**: امروز `isServiceUnavailable` هرگز true نمی‌شود و `undefined` بودن
  `r.data` باعث می‌شد React Query دادهٔ undefined رد کند.
- **سمت من (انجام‌شده)**: `frontend/src/lib/goldApi.ts` لایهٔ `goldCall`/`unwrapGoldPayload`
  **هر دو شکل** را می‌پذیرد (۲۰۰ با `success:false` و ۵۰۳ با کد C3). پس می‌توانید
  مستقل از ترتیب merge تغییر دهید؛ اپ در هیچ میانی نمی‌شکند.

## ۲) C5 — پاکت `POST /dca/plan` و `chat_id` در بدنهٔ `/telegram/test`

- `src/gold_desk/api.py:199-200` → `@router.post("/dca/plan", response_model=DCAResponse)`
  پاسخ **برهنه** می‌دهد. فرانت `r.data` می‌خواند، پس `planDCA` امروز همیشه
  `undefined` برمی‌گرداند (تست `GoldApiLayer.test.ts` همین را به‌خوبی ثابت می‌کند).
  **مطلوب**: `{"success": true, "data": DCAResponse}`.
- `src/gold_desk/api.py:378` → `async def test_telegram(chat_id: str | None = None)`:
  FastAPI این پارامتر را **query** می‌خواند؛ فرانت chat_id را در **body** می‌فرستد
  (`goldApi.ts:124`)، پس امروز chat_id نادیده گرفته می‌شود و تست همیشه به
  chat_id پیش‌فرض می‌رود. **مطلوب**: پذیرش از بدنهٔ JSON، با نگه‌داشتن query برای سازگاری.

## ۳) C4 — `current_score` اجباری است؛ حذف فرانت بدون این تغییر 422 می‌دهد

- `src/gold_desk/schemas.py:116` → `current_score: int = Field(..., ge=0, le=100)` **Required**.
- `src/gold_desk/api.py:799` → `DCAPlanCreate.current_score: int = Field(60, ...)` (optional ✅).
- `src/gold_desk/api.py:1047` → `GET /portfolio/dca` آن را `Query(60, ...)` می‌خواند (optional ✅).
- **مطلوب**: در `DCARequest` آن را optional کنید و وقتی نیامد از snapshot سرور
  بگیرید (`hotpath.get_hot_snapshot()` همان چیزی است که route های دیگر استفاده می‌کنند).
- ⚠️ **هماهنگی الزامی**: من در این رفع ارسال `current_score` را از فرانت حذف کردم
  (`goldApi.planDCA`، `DCACalculator.tsx`، `portfolio/page.tsx`). اگر این تغییر
  سمت شما هم‌زمان merge **نشد**، `POST /gold/dca/plan` جواب 422 می‌گیرد.
  لایهٔ client حالا فیلد را strip می‌کند، پس راه‌فرار وجود ندارد.

## ۴) C7 — payload `/portfolio` دو چیز لازم دارد تا UI کامل شود

- `src/gold_desk/portfolio.py:28-41` (dataclass `HoldingPnL`) فیلد **`id` ندارد**،
  پس `DELETE /portfolio/holdings/{holding_id}` از UI قابل صدا زدن نیست.
  **مطلوب**: `id` را در خروجی `GET /portfolio` بگذارید.
  ← دکمهٔ حذف دارایی در `portfolio/page.tsx` **مشروط به وجود `id`** ساخته شده؛
  با اضافه شدن `id` خودبه‌خود فعال می‌شود (تست: `GoldFrontendSurfaces.test.tsx`).
- `priced_cost` در `portfolio.py:414-452` یک متغیر محلی است و در پاسخ نیست.
  **مطلوب**: expose کردنش (C7) تا مخرج P&L («روی هزینهٔ چند قیمت‌دار») دیده شود.
  فرانت آن را optional خوانده و تا نبودش متن جایگزین نشان می‌دهد.
- `pnl_pct` و `current_value` و `pnl_irt` در dataclass nullable اند و تایپ فرانت
  اصلاح شد؛ اگر روزی back‌اند اینها را صفر کند (به‌جای None)، UI «—» را از دست
  می‌دهد و صفرِ جعلی می‌بیند. لطفاً None را None نگه دارید.

## ۵) C9 + امنیت token

- `src/gold_desk/api_token.py:32` → `Scope = Literal["read", "write", "admin"]`؛
  **`metrics` وجود ندارد**، پس scrape پیکربندی‌شده در
  `monitoring/golddesk-prometheus.yml` (که bearer token از فایل می‌خواند) امروز
  401 می‌گیرد. **مطلوب**: افزودن scope `metrics` و مجاز کردن `/metrics` با آن.
- `src/gold_desk/api_token.py:28` →
  `SALT = os.getenv("<REDACTED>", <پیش‌فرضِ hard-code شده>)` — مقدار آن را اینجا نمی‌نویسم (قاعدهٔ ۵؛ در `api_token.py:28` و تاریخ commit پیدا است).
  **مطلوب**: حذف پیش‌فرض (fail-fast اگر ست نشده). من در `docker-compose.yml`
  آن را با `:?` اجباری کردم، ولی مسیر غیر-داکر (dev مستقیم / pytest) هنوز
  پیش‌فرض را بی‌صدا مصرف می‌کند.
  ⚠️ تغییر salt = باطل شدن token های صادرشده با پیش‌فرض قبلی → بازصدور لازم است.
- `nginx-golddesk.conf` را اصلاح کردم (ماسک token در لاگ /ws) — ولی اگر توکن را از
  query به `Sec-WebSocket-Protocol` منتقل کنید، آن ماسک لازم نیست. انتخاب با شماست.

## ۶) C10 — کادنس WebSocket (فقط سمت سرور)

- `src/gold_desk/ws_hub.py:71-87`: `ws_endpoint` بعد از accept فقط `receive_text()`
  می‌خواند و به `ping` پاسخ `pong` می‌دهد. **حلقهٔ push وجود ندارد**؛ تنها چیزی که
  client می‌گیرد یک snapshot کش‌شده در `register` (`:31-33`) و فریم‌های `signal`
  از `live_signals.py:188` است.
- docstring ها (`ws_hub.py:3`, `api.py:693`) «هر ۵ ثانیه» می‌گویند — با کد نمی‌خواند.
- **مطلوب (C10)**: وقتی `hub.client_count() > 0`، هر **۱۰ ثانیه**
  `{"type": "hot", "data": …}` و هر **۳۰۰ ثانیه** `{"type": "snapshot", "data": …}`.
- **سمت من (انجام‌شده)**: فرانت هر سه نوع (`hot`, `snapshot`, `signal`) را می‌فهمد،
  زمانِ آخرین پیام را نگه می‌دارد، و کهنگی > ۲× بازهٔ hot را اعلام می‌کند.
  تا وقتی push ندارید، UI «Polling» نشان می‌دهد و polling ۱۰ ثانیه‌ای فعال است —
  یعنی بعد از تغییر شما بدون هیچ تغییر دیگری به Live سوئیچ می‌شود.

## ۷) out-of-sample در `/backtest/real` (F7)

- `backtest_runner.py:77-81` شش فیلد `oos_*` را محاسبه می‌کند ولی
  `api.py:568-600` هیچ‌کدام را در پاسخ **نمی‌گذارد**.
- **مطلوب**: افزودن `oos` به هر استراتژی در پاسخ.
- **سمت من**: صفحهٔ `/gold/backtest` فعلاً صراحتاً می‌گوید این متریک در پاسخ نیست؛
  به‌محض اضافه شدنش، رندر جداگانه‌اش را اضافه می‌کنم (نخواهم شد روی عدد حدسی).

## ۸) دو چیز که «گزارش گفته، کد نکرده» بودند و فقط ثبت می‌شوند

- `api.py:963-989` (DELETE holding با soft-delete + `?force=true`) و
  `models.py:154` (`deleted_at`) و migration `0043_gold_holding_soft_delete`
  **از قبل پیاده شده‌اند**؛ برخلاف فرض گزارش که C7 را «کاری که باید بشود» می‌دانست.
- `/health` امروز ۵۰۳ می‌دهد (`api.py` `def health`) — C8 تا حد زیادی برقرار است؛
  فقط بررسی `brsapi_ok` واقعی بودنش را باقی می‌گذارم (در گزارش ۰2 آمده، من در
  کد تأیید نکردم چون Python نمی‌خوانم مگر برای مستندسازی).

## ۹) سؤال باز برای صاحب محصول

`docs/golddesk_backup.md §۵`: دو متغیر `<REDACTED>` و
`<REDACTED>` حالا در compose **اجباری** اند، ولی `.env.example` آن‌ها را
ندارد (فایل در محدودهٔ مالکیت هیچ‌کدام از سه دستیار نیست). تا قبل از افزودن،
`docker compose up` با پیام `must be set in .env` می‌ایستد. درخواست جدا:
`docs/fixes/handoff_frontend_to_ops_env.md`.
