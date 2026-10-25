**گزارش حسابرسی لایهٔ API و Snapshot — GoldDesk (`src/gold_desk/api.py`, `snapshot_service.py`)**

> **دامنه:** `api.py` (۱۵۵۳ خط، ۶۳ عملیات)، `snapshot_service.py` (۳۷۷ خط)، `schemas.py`، `hotpath.py`، `api_token.py`، `ws_hub.py`، `metrics.py`، `freshness.py`، و آنچه رفتار آنها را تعیین می‌کند: `apps/api/router.py` (مونتاژ و گیت)، `apps/api/middleware.py` (گیت نوشتن)، `apps/api/dependencies.py`، `src/gold_desk/models.py`، و قرارداد مصرف‌کننده در `frontend/src/lib/goldApi.ts`.
>
> **روش:** خواندن کامل فایل‌های بالا + شمارش واقعی مسیرها با import ماژول + اجرای ۶ پروب رفتاری (HTTP shape، health، token lifecycle، DCA tranche، پارامترها) + اجرای تست‌های مرتبط (**۷۲ تست پاس**). هیچ فایل کد، تست یا تنظیمی تغییر نکرد؛ تنها فایل جدید همین گزارش است.
>
> **قاعده برچسب‌گذاری:** `[کد]` = واقعیت خوانده‌شده با مسیر و شماره خط · `[اجرا]` = خروجی واقعی یک اجرا (نقل‌شده در متن) · `[استنباط]` = استنتاج من بدون اثبات مستقیم · `[پیشنهاد]` = اصلاح پیشنهادی.

---

# ۱. خلاصه اجرایی

لایهٔ API از نظر «کدِ خوانا» وضعیت خوبی دارد: هر endpoint کوچک، نام‌گذاری یکدست، envelope واحد در ۵۶ عملیات، و گیت احراز هویت در لایهٔ مونتاژ (نه در بدنهٔ handler). اما سه دستهٔ نقص ساختاری وجود دارد که محصول را از «کار می‌کند» به «قابل اتکا نیست» می‌برد:

1. **مدل داده تک‌کاربره با گیت چندکاربره.** هیچ‌یک از ۹ جدول GoldDesk ستون `user_id`/tenant ندارد `[کد: models.py]`، ولی مسیرها با `_require_user` محافظت شده‌اند `[کد: apps/api/router.py:291-296]`. نتیجه: هر کاربر احراز‌شدهٔ پلتفرم، پرتفوی، معاملات، قوانین هشدار و فایل مالیاتیِ همان یک ردیف مشترک را می‌بیند. گیت، «ناشناس» را می‌بندد ولی «کاربر دیگر» را نه.
2. **زیرساخت توکن API کار نمی‌کند.** `verify_token` هیچ‌جا صدا زده نمی‌شود، `revoke_token` عملاً بی‌اثر است و `list_tokens` همیشه خالی است `[اجرا]`. یعنی `/gold/tokens` یک سطح امنیتی نمایشی است.
3. **خطاها به موفقیت تبدیل می‌شوند.** `/snapshot` و `/score` هر استثنا را می‌گیرند و با **HTTP 200** و `success: false` برمی‌گردانند و متن خطای داخلی را به کلاینت می‌دهند `[اجرا]`. مانیتورینگ، HEALTHCHECK و SPA هیچ‌کدام خطا نمی‌بینند.

**یافته‌های اصلی (تأیید‌شده):**

| # | یافته | شدت | تأیید |
|---|---|---|---|
| ۱ | هیچ‌یک از ۹ جدول ستون مالک ندارد، ولی همهٔ مسیرها با «یک کاربر واقعی» باز می‌شوند (`models.py`، `router.py:291-296`) | Critical | `grep user_id` در `models.py` → صفر؛ تست فقط ۴۰۱/۲۰۰ را می‌سنجد |
| ۲ | چرخهٔ عمر توکن شکسته: `verify_token` بدون مصرف‌کننده، `revoke_token` بی‌اثر، `list_tokens` همیشه `[]` (`api_token.py:84,116,138`) | Critical | `[اجرا]` `verify-after-revoke: True` · `list_tokens length: 0` |
| ۳ | `delete_holding` با `ondelete="CASCADE"` معاملاتِ همان دارایی را پاک می‌کند ⇒ بهای تمام‌شده و گزارش مالیاتی از بین می‌رود (`api.py:964`، `models.py:181`) | Critical | `[کد]` FK + حذف بدون هشدار/بکاپ |
| ۴ | خطای snapshot/score ⇒ HTTP 200 + `str(exc)` (`api.py:96-108,110-117`) | High | `[اجرا]` `status: 200` با `success: False` |
| ۵ | `WS /gold/ws` با کادنس واقعی ۳۰۰ ثانیه push می‌کند نه «هر ۵ ثانیه» (`ws_hub.py:3`، `api.py:692-706`، `gold_desk_jobs.py:311`) | High | برداشت از تنها فراخوان `broadcast` در job ۵دقیقه‌ای |
| ۶ | `/score` و `/snapshot` هر درخواست، snapshot کامل را از صفر می‌سازند: ~۳۷ رفت‌وبرگشت DB + ۱۳ فراخوانی بیرونی، بدون cache/single-flight (`api.py:96,110`، `snapshot_service.py:196`) | High | شمارش فراخوانی‌ها در مسیر build |
| ۷ | ۵۴ مسیر به‌صورت `dict` بی‌فیلد و ۵ مسیر بدون هیچ schema پاسخ می‌دهند (فقط ۴ مسیر مدل واقعی دارند)؛ `ScoreBlock` سه فیلد پوشش دادهٔ موتور را دور می‌ریزد (`schemas.py:96-101`) | High | `[اجرا]` پیمایش `response_model` روی ۶۳ مسیر |
| ۸ | `/docs/endpoints` `base_url` را `/api/gold` می‌گوید (واقعی: `/api/v1/gold`) و ~۴۰ عملیات را جا انداخته (`api.py:1300-1343`) | High | `[کد]` + `core/config` → `api_prefix = "/api/v1"` |
| ۹ | `/telegram/test` پارامتر `chat_id` را **query** می‌خواند ولی فرانت آن را در **body** می‌فرستد (`api.py:379`، `goldApi.ts:testTelegram`) | High | `[اجرا]` `query=['chat_id'] body=[]` |
| ۱۰ | `health()` مقدار `brsapi_ok=db_ok` می‌گذارد و هرگز BrsApi را نمی‌سنجد (`api.py:459`)؛ Redis خاموش ⇒ ۲۰۰ (خلاف docstring) | High | `[اجرا]` `{"brsapi_ok": true, "redis_ok": false}` با status 200 |

**جمع‌بندی:** `snapshot_service.build_snapshot` منطق درستی دارد ولی به‌عنوان «یک تابع گران» در سه مسیر تکرار می‌شود و خروجی‌اش توسط schema ناقص بریده می‌شود. `hotpath`/`freshness` ساده و صادق‌اند. `api_token` و `ws_hub` را می‌توان «پیاده‌سازی نیمه‌کاره» نامید. `metrics` شمارنده‌هایی دارد که هرگز افزایش نمی‌یابند. مسیرهای مالی (portfolio/tax) از نظر شکل پاسخ درست‌اند اما از نظر مالکیت داده و دو باگ دامنه‌ای (FIFO و XIRR، گزارش `01_engine.md`) هنوز قابل اتکا نیستند.

---

# ۲. نقشه ماژول‌ها و مسیرها

## ۲.۰ چرخهٔ یک درخواست

```
RequestContextMiddleware (trace_id)  →  TimingMiddleware  →  SecurityMiddleware
   →  RateLimitMiddleware
   →  APIRouter(prefix="/api/v1")            [apps/api/router.py]
        ├─ include_router(gold_core_router,  prefix="/gold",      deps=_require_user)   ← endpoints/gold.py (۱۳ op)
        ├─ include_router(anonymous_router,  خودش /gold,          بدون گیت)             ← health / assistant-rules / ws
        ├─ include_router(router,            خودش /gold,          deps=_require_user)  ← همان ماژول، ۶۰ op
        └─ include_router(gold_analytics,    prefix="/gold/analytics", …)
   →  handler → Depends(get_db_session) → AsyncSession
             → Redis (get_cache)  ·  BrsApi QueryService  ·  TGJU (فالبک)
```

`[کد]` ترتیب مهم است: `gold_core_router` **پیش از** روتِر GoldDesk مونتاژ می‌شود، پس اگر روزی مسیری با همان path در هر دو تعریف شود، نسخهٔ `endpoints/gold.py` برنده می‌شود و مسیر GoldDesk بی‌صدا ۴۰۴/سایه می‌شود. امروز تداخلی وجود ندارد (بررسی شد: ۱۳ مسیر core، ۶۳ مسیر GoldDesk، اشتراک صفر) — ولی هیچ تست یا assert‌ای این را قفل نکرده است `[استنباط: ریسک آینده]`.

## ۲.۱ `api.py` — ۶۳ عملیات در ۲ روتِر

شمارش واقعی با import ماژول (نه از docstring):

| گروه | تعداد | مسیرها | گیت |
|---|---|---|---|
| snapshot / score | ۲ | `/snapshot`, `/score` | JWT |
| تاریخچه | ۲ | `/history/score`, `/history/snapshot` | JWT |
| DCA (محاسبه) | ۱ | `POST /dca/plan` | JWT |
| هشدارها | ۷ | rules CRUD (۴)، events، ack، seed | JWT |
| واچ‌لیست | ۲ | GET/PUT `/watchlist` | JWT |
| تلگرام | ۲ | `/telegram/test`, `/telegram/status` | JWT |
| سلامت / تازگی / قواعد | ۳ | `/health` و `/assistant-rules` (anonymous)، `/freshness` | ۲ آزاد |
| بک‌تست | ۳ | `/backtest`, `/backtest/strategy`, `/backtest/real` | JWT |
| اختیار | ۲ | `/options/price`, `/options/collar` | JWT |
| WebSocket | ۱ | `/ws` | توکن در query |
| توکن API | ۳ | POST/GET/DELETE `/tokens` | JWT |
| پرتفوی | ۱۵ | portfolio، history، performance، snapshot، returns، tax، export.csv، holdings(۲)، dca(۴)، trades(۲) | JWT |
| سیگنال زنده | ۲ | `/signals/recent`, `/signals/detect` | JWT |
| چت | ۱ | `POST /chat` | JWT |
| hot / patterns / docs / metrics | ۴ | `/hot`, `/patterns`, `/docs/endpoints`, `/metrics` | JWT |
| کلان / کریپتو / FX | ۴ | `/macro`, `/macro/scrape`, `/crypto`, `/fx` | JWT |
| پیش‌بینی | ۲ | `/forecast`, `/forecast/all` | JWT |
| Antigravity (زیرروتِر) | ۷ | `signal`, `assets`, `quick-signal`, `kill-switch/check`, `arbitrage/scan`, `dollar-return`, `coin-bubble` | JWT |
| **جمع** | **۶۳** | ۶۰ روی `router` + ۳ روی `anonymous_router` | |

نکته: docstring تست `tests/unit/api/test_gold_personal_surface_auth.py:6` عدد «۶۲ operations» را می‌گوید؛ عدد امروز **۶۳** است. `[کد]`

**سه مسیر عمداً ناشناس** `[کد: api.py:66-79]`:
- `GET /gold/health` — HEALTHCHECK داکر توکن ندارد.
- `GET /gold/assistant-rules` — کارت قواعدی که صفحات *قبل از لاگین* `/markets/gold` و `/markets/silver` می‌خوانند.
- `WS /gold/ws` — سوکت؛ توکن را خودش از `?token=` می‌خواند و پیش از `accept()` با کد ۱۰۰۸ می‌بندد.

**الگوی تکرارشونده در همهٔ handlerها** `[استنباط]`: پارامترهای کوئری با `Query(default, ge, le)` مهار شده‌اند (خوب)، اما بدنه‌ها فقط در ۶ نقطه Pydantic دارند (`DCARequest`, `HoldingCreate`, `DCAPlanCreate`, `TradeCreate`, `ChatRequest`, `WatchlistResponse`) و بقیه dict خام می‌پذیرند/می‌دهند.

## ۲.۲ `snapshot_service.py` — تابع‌ها و عوارض جانبی

| تابع | امضا | کار | عوارض جانبی |
|---|---|---|---|
| `_read_brsapi_prices` | `() -> dict[str, float]` | ۳ کوئری دسته‌ای BrsApi (gold/currency/commodity) + ۱۰ فراخوانی `get_symbol_snapshot` برای صندوق‌ها | **یک session مستقل** از `async_session_factory` باز می‌کند (`:50-54`)، خطاها را لاگ و بلع می‌کند |
| `_read_references` | `(prices=None) -> (dict, str)` | xau_usd/usd_irt/aed_irt + فالبک TGJU | شبکه (TGJU) در صورت نقص؛ برچسب `source` |
| `_calc_daily_changes` | `(session, prices) -> dict[str, float\|None]` | تغییر روزانه USD (DB)، TSE (شاخص کل)، DXY (DB) | ۳ کوئری؛ هر خطا جدا لاگ می‌شود (GS-07) |
| `_soft_check` | `(value, (lo,hi), name) -> bool` | محدودهٔ معقول | فقط لاگ |
| `build_snapshot` | `(session) -> SnapshotResponse` | ارکستراسیون کامل | ≥۳۷ کوئری DB + ۱۳ فراخوانی بیرونی + یک session اضافی |
| `snapshot_to_dict` | `(snap) -> dict` | `model_dump(mode="json")` | ندارد |

**ورودی‌ها از `constants.py`:** `GOLD_SYMBOLS` (۶ نماد وزنی)، `COIN_SYMBOLS`، `FUND_SYMBOLS` (**۱۰ صندوق**: عیار، طلا، کهربا، زر، زرفام، گوهر، تابش، نفیس، آلتون، ناب)، چهار بازهٔ `VALID_*_RANGE`. `[کد: constants.py:123-140]`

## ۲.۳ `schemas.py` — کدام مدل واقعاً به سیم وصل است؟

| مدل | مصرف | نکته |
|---|---|---|
| `SnapshotResponse` / `ReferenceBlock` / `AssetBlock` / `FundBlock` / `ScoreBlock` / `ScoreComponents` | `snapshot_service.build_snapshot` | تنها جایی که schema واقعاً Zod-وار عمل می‌کند |
| `HealthResponse` | `api.health` (response_model + پاسخ خام) | مدل واقعی، بدون envelope |
| `WatchlistResponse` | GET/PUT watchlist | پاسخ **بدون** envelope |
| `DCAResponse` / `DCATranche` | `POST /dca/plan` (response_model) | تنها POST با مدل و بدون envelope |
| `DCARequest` | `POST /dca/plan` | `preferred_vehicle` شامل `jewelry` است ولی `DCAPlanCreate.vehicle` فقط ۴ مقدار → ناسازگاری دو schema |
| `AlertRuleCreate/Update/Out`, `AlertEventOut` | فقط Create/Update مصرف می‌شوند | `*Out` هیچ‌جا به‌عنوان `response_model` نیست ⇒ پاسخ‌ها dict دستی |
| `ScoreHistoryPoint` | `history/score` | `total=int(total_score)` ⇒ بریدن اعشار |
| `BubbleHistoryPoint` | **بدون مصرف‌کننده** | کد مرده |

`[اجرا]` پیمایش `response_model` روی همهٔ ۶۳ مسیر:

- **۵۴ مسیر** ← `response_model` از نوع `dict` (FastAPI آن را از `-> dict` استنتاج می‌کند) ⇒ در `openapi.json` یک «object» بدون هیچ property.
- **۵ مسیر** ← `response_model=None` (`/snapshot`, `/portfolio/export.csv`, `/metrics`, `/assistant-rules`, `/ws`).
- **۴ مسیر** ← مدل واقعی (`/dca/plan`=DCAResponse، `/watchlist`×۲=WatchlistResponse، `/health`=HealthResponse).

پس docstring ماژول («اکیداً typed. هیچ dict آزاد») با ۵۹ مسیر از ۶۳ در تناقض است — تنها ۴ مسیر قرارداد ماشین‌خوان دارند.

## ۲.۴ `hotpath.py`

`compute_quick_signal(bubble)` آستانه‌های ۰/۵/۱۲/۲۲ درصد را به `buy|hold|sell|wait` نگاشت می‌کند؛ `get_hot_snapshot()` فقط `REDIS_KEY_SNAPSHOT = "golddesk:snapshot:latest"` را می‌خواند (TTL نوشتن: ۶۰۰ ثانیه در job)؛ `build_hotpath_response` یک payload ~۱۵ فیلدی می‌سازد. `[کد]`

نکتهٔ قراردادی: `quick_signal` دو منبع حقیقت دارد — آستانه‌های `bubble_pct < 5` **هاردکد** در تابع و `BUBBLE_GREEN_MAX/YELLOW/ORANGE` از constants در ادامه. با تغییر constants، مرز ۵٪ سر جایش می‌ماند `[کد: hotpath.py:44-56]`.

## ۲.۵ `api_token.py`

`generate_token` → `secrets.token_urlsafe(32)`؛ `token_id = plain[:8]`؛ ذخیرهٔ `sha256(token+SALT)` در Redis زیر `golddesk:api_tokens:hash:*` و `:meta:*`؛ `SALT` از env با پیش‌فرض `"temce-golddesk-default-salt"`. `[کد]`

سه نقص قطعی که در §۶ با اجرا اثبات شده‌اند: بدون مصرف‌کننده، بدون revoke مؤثر، بدون index.

## ۲.۶ `ws_hub.py`

`GoldWebSocketHub` با یک `set[WebSocket]`، `asyncio.Lock`، آخرین snapshot در حافظه، و `broadcast` که کلاینت‌های خطادار را حذف می‌کند. `ws_endpoint` فقط `ping→pong` و ثبت/حذف مشتری؛ **هیچ حلقهٔ تولید snapshot ندارد**. `[کد]` تنها فراخوان `cache_snapshot`/`broadcast` در `brsapi/jobs/gold_desk_jobs.py:107-111` است (job با `cron=300`).

## ۲.۷ `metrics.py`

پنج شمارنده (`snapshot_total`, `signal_total`, `alert_fired_total`, `chat_total`, `api_errors_total`)، سه histogram، یک gauge برای WS، `_percentile` با درون‌یابی خطی (اصلاح GS-27). `[کد]`

**مشکل ساختاری:** `incr()` و `measure_*()` هیچ فراخوانی‌ای در کل ریپو ندارند (grep: فقط تعریف) ⇒ `/metrics` همیشه صفر و بدون histogram منتشر می‌شود. `[کد]`

## ۲.۸ `freshness.py`

۱۳ منبع، هرکدام `MAX(column)` + `COUNT(*)` داخل `session.begin_nested()`، تبدیل تهران→UTC برای ستون‌های naive، وضعیت `ok|stale|empty|missing` و آستانهٔ کلی بدبینانه. `[کد]` طراحی صادق است (خطا → `missing`، نه «تازه»)، ولی ۲۶ کوئری سریال در هر درخواست دارد.

## ۲.۹ مونتاژ و گیت

```python
# apps/api/router.py
_public_read  = [Depends(require_user_for_writes)]           # :15
_require_user = [Depends(require_any_role("user","analyst","admin"))]  # :20
router.include_router(gold_core_router, prefix="/gold", dependencies=_require_user)   # :277-283
router.include_router(gold_desk_public_router)                                        # :291
router.include_router(gold_desk_personal_router, dependencies=_require_user)          # :296
```

`[کد]` علاوه بر این، `SecurityMiddleware` هر **نوشتن** زیر `/api/v1/gold/` را مستقل از روتِر مستلزم Bearer می‌داند (`apps/api/middleware.py:47-52`). یعنی دو گیت موازی برای POST/PUT/DELETE و یک گیت برای GET.

---

# ۳. دیکشنری قراردادها و پاکت پاسخ

## ۳.۱ سه شکل پاسخ (نه یکی)

| شکل | نمونه | مسیرها |
|---|---|---|
| `{"success": true, "data": …}` | اکثریت | ۵۶ عملیات |
| بدنهٔ خام مدل | `{"symbols": [], "updated_at": null}` · `{"brsapi_ok": …}` · `{"total_capital_irt": …}` | `GET/PUT /watchlist`, `GET /health`, `POST /dca/plan` |
| غیر-JSON | CSV · متن Prometheus · فریم WS | `/portfolio/export.csv`, `/metrics`, `/ws` |

`[اجرا]` تفاوت شکل خطا هم واقعی است:

```
[snapshot-error] status: 200 body: {"success": false, "data": null, "error": {...}}
[score-error]    status: 200 body: {"success": false,               "error": {...}}
```

یعنی کلاینتی که `resp.data` را بدون بررسی `success` می‌خواند، در `/score` کلید `data` را **نمی‌یابد** `[کد: api.py:114]`. فرانت این را با کامنت‌های «tolerate both shapes» جبران کرده (`goldApi.ts:getHealth`, `getWatchlist`) — نشانهٔ اینکه ناسازگاری واقعاً به مصرف‌کننده رسیده است.

## ۳.۲ `SnapshotResponse` — قرارداد سیم

| فیلد | نوع | واحد / معنا | منبع |
|---|---|---|---|
| `snapshot_at` | datetime (UTC, ISO) | زمان **ساخت** پاسخ، نه زمان قیمت | `datetime.now(UTC)` |
| `references.xau_usd` | float | دلار بر اونس | BrsApi/TGJU |
| `references.usd_irt` | float | قیمت دلار؛ واحد (ریال/تومان) در کد تثبیت نشده | BrsApi/TGJU |
| `references.aed_irt` | float | درهم | BrsApi/TGJU |
| `references.aed_parity_usd` | float | درهم→دلار | `parity.aed_parity_usd` |
| `references.aed_gap_pct` | float (%) | شکاف آربیتراژ | `parity.aed_gap_pct` |
| `references.source` | Literal `brsapi\|tgju\|cache` | منبع؛ `mixed` هرگز تولید نمی‌شود (شاخهٔ مرده) | `:121` |
| `references.age_seconds` | float | **همیشه 0.0** — هیچ‌جا set نمی‌شود | `schemas.py:27` |
| `gold{} / coins{}` | dict[str, AssetBlock] | کلید = `coin_emami`, `gold_18k`, … | `GOLD_SYMBOLS/COIN_SYMBOLS` |
| `AssetBlock.market_price` | float | تومان (اسم فیلد واحد را نمی‌گوید) | BrsApi |
| `AssetBlock.fair_value` | float\|None | تومان | `pricer.fair_value` |
| `AssetBlock.bubble_pct` | float\|None (%) | (market−fair)/fair | `bubbler.calc_bubble` |
| `AssetBlock.quality_flag` | str | **همیشه "clean"** برای هر دارایی | `:250-262` |
| `funds[]` | FundBlock | NAV/بازار/حباب/BPR/ورود پول/NAV7d | `nav_checker` |
| `score.total/decision/components` | int / GREEN\|YELLOW\|RED / ۶ جزء | ۰-۱۰۰ | `scorer.compute_score` |
| `score.hard_stop_active/reason` | bool / str\|None | قطع‌کننده | `hard_stops` |
| `quality_flag` | str | `clean` اگر `source=="brsapi"` وگرنه `fallback` | `:371` |

**فیلدهای مرده در قرارداد:** `age_seconds` (همیشه ۰)، `AssetBlock.quality_flag` (همیشه `clean`). **فیلدهای گم‌شده:** `raw_total`, `available_weight`, `data_coverage_pct` که موتور از GS-02 محاسبه می‌کند ولی `ScoreBlock` ندارد ⇒ API نمی‌تواند بگوید «این امتیاز با ۳ جزء از ۶ ساخته شده».

## ۳.۳ پارامترهای کوئری (بازه‌ها همان‌طور که در کد است)

| مسیر | پارامتر | پیش‌فرض | بازه |
|---|---|---|---|
| `/history/score`, `/history/snapshot`, `/alerts/events` | `days` | ۷ | ۱..۹۰ |
| `/history/snapshot` | `symbol` | `IR_COIN_EMAMI` | آزاد |
| `/backtest` | `days` / `bubble_threshold` | ۹۰ / ۸.۰ | ۳۰..۳۶۵ / ≥۰ |
| `/backtest/strategy` | `days` / `bubble_trigger` / `initial_capital` | ۹۰ / ۵.۰ / ۱۰۰M | ۳۰..۳۶۵ / ≥۰ / ≥۱M |
| `/backtest/real` | `days` | ۱۸۰ | ۶۰..۷۳۰ |
| `/options/price` | `iv` / `rate` | ۰.۲۵ / ۰.۳۰ | ۰.۰۱..۲.۰ / ۰..۱.۰ |
| `/tokens` POST | `name` / `scopes` | — / `read` | ۱..۶۴ کاراکتر |
| `/portfolio/history` | `days` | ۹۰ | ۲..۷۳۰ |
| `/portfolio/performance` | `days` | ۹۰ (`PORTFOLIO_PERFORMANCE_WINDOW_DAYS`) | ۲..۷۳۰ |
| `/portfolio/trades` | `limit` | ۵۰ | ۱..۵۰۰ |
| `/portfolio/dca` GET | `current_score` | **۶۰** | ۰..۱۰۰ |
| `/portfolio/dca/{id}/execute` | `tranche` | — | ۱..۱۰ |
| `/signals/recent` | `limit` | ۲۰ | ۱..۱۰۰ |
| `/patterns` | `days` | ۹۰ | ۳۰..۳۶۵ |
| `/macro` | `limit` | ۲۰ | ۱..۱۰۰ |
| `/forecast` | `days` | ۶۰ | ۲۰..۳۶۵ |
| `/alerts/events` | `unread_only` | `false` | — |

`[کد]` دو پارامتر «پنهان» که رفتار محصول را عوض می‌کنند: `current_score` در `/portfolio/dca` (پیش‌فرض ۶۰ ⇒ وضعیت پله‌ها همیشه با عدد فرضی ۶۰ محاسبه می‌شود مگر کلاینت عدد واقعی را بفرستد) و `initial_capital` در بک‌تست‌ها (پیش‌فرض ۱۰۰M تومان).

## ۳.۴ کدهای وضعیت واقعی

| کد | کجا | یادداشت |
|---|---|---|
| ۲۰۰ | همه‌چیز، **حتی شکست** | `/snapshot`, `/score`, `/signals/recent`, `/tokens` DELETE |
| ۴۰۰ | تاریخ نامعتبر، `call<=put`، scope نامعتبر، ترتیب پله | `HTTPException` |
| ۴۰۱ | گیت JWT (روتِر) | در تست قفل شده |
| ۴۰۴ | rule/event/holding/plan یافت نشد | — |
| ۴۲۲ | نقض `Query(ge/le)` یا بدنهٔ ناقص | FastAPI |
| ۵۰۰ | `IntegrityError` احتمالی در `update_alert_rule` با `null` | §۷ H9 |
| ۵۰۳ | فقط `health` وقتی DB قطع است | Redis قطع ⇒ ۲۰۰ |
| ۱۰۰۸ | بستن WS بدون توکن | پیش از `accept()` |

## ۳.۵ واحد پول و دقت عدد

همهٔ مبالغ `float` هستند (`total_capital_irt`, `amount_irt`, `fee_irt`, `buy_amount_irt`, `total_value_irt`, `net_flow_irt`). هیچ‌جا `Decimal` نیست و هیچ schema‌ای واحد (ریال/تومان) را در نام یا docstring تثبیت نمی‌کند به‌جز پسوند `_irt`. `[کد]` — این همان ابهام واحد است که در `01_engine.md` (M18) و در دادهٔ BrsApi باز مانده و اینجا به سطح قرارداد عمومی API می‌رسد.

---

# ۴. تحلیل مسیر snapshot

## ۴.۱ هزینهٔ یک build

`build_snapshot(session)` `[کد: snapshot_service.py:196-377]`:

| مرحله | تعداد رفت‌وبرگشت |
|---|---|
| `_read_brsapi_prices()` — ۳ کوئری دسته‌ای + ۱۰ `get_symbol_snapshot` (به‌ازای `FUND_SYMBOLS`) | ۱۳ فراخوانی بیرونی، روی **session دوم** |
| `nav_checker.get_all_funds_status` — ۳ کوئری به‌ازای هر صندوق (`_latest_nav`, `_fund_market_data`, `_nav_7d_ago`) | ۱۰ × ۳ = ۳۰ |
| `signal_engine.get_xau_indicators(days=40)` | ۱-۲ |
| `_calc_daily_changes` — USD closes، شاخص کل، DXY closes | ۳ |
| **جمع** | **~۳۷ کوئری DB + ۱۳ فراخوانی بیرونی، همه سریال** |

`[استنباط از کد]` هیچ `asyncio.gather`، هیچ batch، هیچ کش و هیچ single-flight وجود ندارد. `[پیشنهاد]` ساخت snapshot در job با TTL کوتاه کش شود و `/snapshot`/`/score` همان کش را سرو کنند (مثل کاری که `/hot` با `REDIS_KEY_SNAPSHOT` می‌کند).

## ۴.۲ چه کسی build را صدا می‌زند؟

| فراخوان | کادنس | نتیجه |
|---|---|---|
| `GET /gold/snapshot` | هر درخواست | build کامل |
| `GET /gold/score` | هر درخواست | **build کامل برای ۶ عدد** |
| `job_gold_snapshot` | ۳۰۰ ثانیه | build + persist + cache + broadcast |
| `job_gold_score_persist` | ۳۰۰ ثانیه | build دوباره، فقط برای یک ردیف score |
| `job_gold_alert_evaluate` | ۱۲۰ ثانیه | build دوباره، برای ارزیابی قواعد |

`[کد: gold_desk_jobs.py:64,146,195,309-334]` ⇒ در حالت عادی **~۴٫۵ build در هر ۵ دقیقه فقط از سمت jobها** (~۱۷۰ کوئری DB + ۶۰ فراخوانی بیرونی) و هر بازدید صفحه روی آن اضافه می‌شود. این بزرگ‌ترین هزینهٔ زیرساختی GoldDesk است و در `/doc/endpoints` یا PLAN_GOLD ذکر نشده.

## ۴.۳ نردبان فالبک

1. BrsApi (bulk) → اگر ناقص: TGJU برای **فقط** سه مرجع (`XAUUSD`, `USD`, `AED`).
2. اگر هر سه موجود نشد ⇒ `RuntimeError("no price source available …")` ⇒ در API به ۲۰۰ + `success:false` تبدیل می‌شود.
3. برچسب `source`:

```python
source = "tgju" if not all(prices.get(k) for k in ("XAUUSD","USD","AED")) else "mixed"
```

`[کد: :121]` شاخهٔ `"mixed"` **دست‌نیافتنی** است: برای ورود به این بلوک باید حداقل یکی از سه مرجع در `prices` خالی باشد، پس شرط همیشه `"tgju"` می‌دهد. نتیجهٔ عملی: اگر ۲ مرجع از BrsApi و ۱ از TGJU بیاید، کل snapshot «tgju» برچسب می‌خورد و `quality_flag` هم `fallback` می‌شود. `[پیشنهاد]` سه‌حالته کردن (`brsapi|mixed|tgju`) به‌همراه Literal.

## ۴.۴ self-check: چه چیزی را واقعاً متوقف می‌کند؟

`_soft_check` فقط `logger.warning` می‌دهد `[کد: :188-194]`؛ خروجی‌های خارج از محدوده (`VALID_XAU_RANGE`, `VALID_USD_RANGE`, `VALID_PARITY_GAP_RANGE`, `VALID_BUBBLE_PCT_RANGE`) **حذف یا null نمی‌شوند**. یعنی قیمت ۱۰× اشتباه، با یک خط لاگ، وارد score و در نتیجه وارد تصمیم خرید می‌شود. تنها self-check سخت در `build_snapshot` این است که جمع اجزا با `total` بخواند و آن هم فقط وقتی `data_coverage_pct >= 100` است `[کد: :341-352]`.

## ۴.۵ تازگی داده

- `snapshot_at` = زمان ساخت پاسخ ⇒ کلاینت نمی‌تواند سن **قیمت** را بفهمد.
- `ReferenceBlock.age_seconds` همیشه ۰ ⇒ فیلدی که برای همین کار ساخته شده، هرگز پر نمی‌شود.
- `/hot` از کش می‌خواند (TTL ۶۰۰ ثانیه) و `timestamp` همان `snapshot_at` قدیمی را می‌دهد — این تنها مسیری است که سن واقعی را افشا می‌کند (با مقایسهٔ سمت کلاینت).
- `/portfolio`, `/portfolio/returns`, `/portfolio/performance` قیمت‌ها را از `get_hot_snapshot()` می‌گیرند؛ اگر scheduler خوابیده باشد، `snap=None` ⇒ قیمت‌ها صفر/`None` و P&L بی‌معنا، **بدون هیچ هشداری در پاسخ** `[کد: api.py:914-917]`. `[پیشنهاد]` افزودن `snapshot_at` + `stale: bool` به پاسخ پرتفوی.

---

# ۵. اعتبار خروجی و مصرف‌کننده‌ها

## ۵.۱ تطابق فرانت با بک (بررسی مسیر‌به‌مسیر `goldApi.ts`)

| تابع فرانت | مسیر | وضعیت |
|---|---|---|
| `getSnapshot` | `GET /gold/snapshot` | ✅ مسیر/شکل درست |
| `getScoreHistory` / `getSnapshotHistory` | `/history/*` | ✅ |
| `getHealth` | `GET /gold/health` | ⚠️ فرانت هر دو شکل (پاکت/خام) را تحمل می‌کند — بدهی فنی مستندشده |
| `getFreshness` | `GET /gold/freshness` | ✅ |
| `testTelegram` | `POST /gold/telegram/test` با body | ❌ **body نادیده گرفته می‌شود** (پارامتر query است) `[اجرا]` |
| `getWatchlist` / `putWatchlist` | `/gold/watchlist` | ⚠️ پاسخ خام، بدون پاکت |
| `getAlertRules`/`getAlertEvents`/`createAlertRule`/… | `/alerts/*` | ✅ |
| `planDCA` | `POST /gold/dca/plan` | ❌ پاسخ **بدنهٔ خام** `DCAResponse` است ولی فرانت `return r.data` می‌کند ⇒ `undefined` `[کد: goldApi.ts planDCA]` |
| `getStrategyBacktest`/`getBacktest` | `/backtest*` | ✅ (شکل درست، **اعداد** غلط — `01_engine.md` C1/C2) |
| `getPortfolioPerformance` | `/portfolio/performance` | ✅ |
| `subscribeGoldWS` | `ws://…/gold/ws?token=` | ⚠️ کادنس ۵ دقیقه، کامنت فرانت «every few seconds» |
| `getGoldLivePrices`, `getFutures*`, `getKillSwitch`, `getArbitrage`, … | `endpoints/gold.py` | خارج از دامنهٔ این گزارش |

`[کد]` فرانت حدود **۲۲** عملیات را صدا می‌زند. هیچ فراخوانی برای `/gold/score`, `/gold/hot`, `/gold/patterns`, `/gold/chat`, `/gold/tokens`, `/gold/forecast*`, `/gold/macro*`, `/gold/crypto`, `/gold/fx`, `/gold/signals/*`, `/gold/docs/endpoints`, `/gold/metrics` و **۱۳ مسیر از ۱۵ مسیر پرتفوی** وجود ندارد. یعنی ~۴۰ عملیات (از ۶۳) مصرف‌کنندهٔ فرانت ندارند — یا برای ابزارهای بیرونی‌اند (که `/docs/endpoints` باید معرفی کند) یا مرده‌اند.

## ۵.۲ `/docs/endpoints` دروغ می‌گوید

`[کد: api.py:1300-1343]`

| ادعا | واقعیت |
|---|---|
| `"base_url": "/api/gold"` | `/api/v1/gold` |
| `"auth": "Bearer token … (for write endpoints)"` | همهٔ مسیرها JWT می‌خواهند؛ توکن GoldDesk (`/tokens`) هیچ‌جا پذیرفته نمی‌شود |
| ۱۸ عملیات فهرست شده | ۶۳ عملیات وجود دارد؛ portfolio (۱۵)، chat، patterns، forecast، macro، crypto/fx، hot، metrics، signals غایب‌اند |
| `"scope": "read"` برای `POST /dca/plan` | scope مفهومی است که در اجرا وجود ندارد |

این endpoint برای «ابزارهای خارجی» طراحی شده و همان‌ها را گمراه می‌کند. `[پیشنهاد]` تولید فهرست از `router.routes` به‌جای لیست دستی، یا حذف endpoint.

## ۵.۳ چیزهایی که API عمداً یا سهواً پنهان می‌کند

| پنهان‌شده | اثر |
|---|---|
| `data_coverage_pct` / `available_weight` / `raw_total` | کاربر نمی‌فهمد امتیاز با چند جزء ساخته شده (ریشهٔ GREEN کاذب، `01_engine.md` C5) |
| `AssetBlock.quality_flag` همیشه `clean` | قیمت فالبک‌شده مثل قیمت سالم نمایش داده می‌شود |
| `age_seconds` همیشه ۰ | صفحه نمی‌تواند «داده کهنه» را نشان دهد |
| `historical_hit_rate` ثابت ۶۲/۵۸ در `/patterns` | عدد آماری جعلی با ظاهر واقعی (`01_engine.md` M13) |
| `macro_multiplier` در `/macro` ولی نه در `/score` | ادعای «تحلیل کلان در تصمیم» محقق نشده (`01_engine.md` M10) |
| خطای واقعی در `/signals/recent` | `success: true` + `error: "Expecting property name…"` `[اجرا]` |

---

# ۶. احراز هویت، توکن و چندمستأجری

## ۶.۱ آنچه درست است

- گیت در لایهٔ مونتاژ است، نه در handler ⇒ مسیر جدید به‌طور پیش‌فرض بسته است `[کد: router.py:296]`.
- سه مسیر آزاد مستند و در تست قفل شده‌اند (`test_gold_personal_surface_auth.py`): ۴۰۱ برای بقیه، ۲۰۰/۵۰۳ برای health، ۲۰۰ برای assistant-rules، ۱۰۰۸ برای WS بدون توکن. `[اجرا: ۶۸ تست پاس]`
- docstring ماژول (`api.py:1-3`: «بدون auth چون شخصی است») **کهنه** است و با واقعیت نمی‌خواند — منبع سردرگمی برای ممیزی بعدی. `[کد]`

## ۶.۲ آنچه کار نمی‌کند: چرخهٔ عمر توکن

اجرای واقعی با Redis درون‌حافظه‌ای `[اجرا]`:

```
[tokens] verify-before: True
[tokens] revoke returned: True
[tokens] verify-after-revoke: True        ← revoke عملاً بی‌اثر است
[tokens] list_tokens length: 0            ← index هرگز نوشته نمی‌شود
[tokens] token_id == plain[:8]: True      ← ۸ کاراکتر از خودِ راز در پاسخ GET /tokens
[tokens] redis keys:
  golddesk:api_tokens:hash:7bbe85e2…   ← verify_token این را می‌خواند
  golddesk:api_tokens:meta:gqs8JhYu    ← revoke_token این را False می‌کند
```

علت ریشه‌ای `[کد]`:
- `verify_token` (`:84`) کلید `hash:*` را می‌خواند و `info.enabled` **همان رکورد** را چک می‌کند؛ `revoke_token` (`:116`) رکورد `meta:*` را `enabled=False` می‌کند ⇒ هیچ‌وقت دیده نمی‌شود.
- `save_token` (`:60`) هیچ‌گاه `golddesk:api_tokens:index` را نمی‌نویسد ⇒ `list_tokens` (`:138`) همیشه خالی.
- `verify_token` در کل ریپو **صفر** فراخوان دارد (grep) ⇒ حتی اگر درست بود، هیچ درخواستی با آن احراز نمی‌شد.
- `SALT` پیش‌فرض هاردکد `temce-golddesk-default-salt` ⇒ در دیپلوی بدون env، هش قابل پیش‌بینی است (توکن‌ها همچنان تصادفی‌اند، ولی salt دیگر «راز» نیست).

## ۶.۳ چندمستأجری: گیت هست، مالکیت نیست

`[کد]` هیچ‌یک از این جدول‌ها ستون مالک ندارد:

`gold_snapshots`, `gold_fund_nav`, `gold_alert_rules`, `gold_alert_events`, `gold_score_history`, `gold_holdings`, `gold_dca_plans`, `gold_trades`, `gold_portfolio_values`.

نتیجهٔ مستقیم: با دو کاربر احراز‌شده،
`GET /gold/portfolio` برای هر دو **همان** دارایی‌ها را برمی‌گرداند؛
`DELETE /gold/portfolio/holdings/{id}` کاربر B می‌تواند سطر کاربر A را پاک کند (شناسه عددی متوالی است)؛
`GET /gold/portfolio/tax` و `export.csv` همان گزارش مالیاتی مشترک را می‌دهند؛
`GET /gold/alerts/events` و `tokens` و `watchlist` هم مشترک‌اند.

`[استنباط]` طراحی اولیه «شخصی/تک‌کاربره» بوده و بعداً گیت `_require_user` به آن اضافه شده بدون مهاجرت مدل داده. تا وقتی tenant اضافه نشود، بهتر است سطح GoldDesk روی یک instance اختصاصی (یا یک کاربر) بماند و این محدودیت در مستندات صریح باشد؛ در غیر این صورت باید `user_id` به ۹ جدول + filter در همهٔ کوئری‌ها اضافه شود.

## ۶.۴ گیت نوشتن در middleware

`SecurityMiddleware` هر `POST/PUT/DELETE` زیر `/gold/` را بیرون از dependency مستلزم Bearer می‌کند `[کد: middleware.py:47-52]`. عوارض جانبی:
- `POST /gold/options/price` (یک ماشین‌حساب خالص بدون دادهٔ شخصی) از هر تماس‌گیرندهٔ ناشناس ۴۰۱ می‌گیرد؛ در حالی که `GET /gold/analytics/options/*` عمومی است ⇒ ناسازگاری سیاست بین دو سطح طلا.
- `/gold/metrics` پشت JWT است ⇒ Prometheus استاندارد نمی‌تواند scrape کند (مگر با توکن استاتیک در config).

---

# ۷. باگ‌ها و ریسک‌ها

| ID | اولویت | محل | نوع | توضیح | اثر | پیشنهاد |
|---|---|---|---|---|---|---|
| C1 | Critical | `models.py` (۹ جدول) + `router.py:291-296` | مالکیت داده | گیت «یک کاربر واقعی» بدون ستون مالک | هر کاربر، دارایی/مالیات/هشدار/توکن کاربر دیگر را می‌بیند و می‌تواند حذف کند | افزودن `user_id` + filter اجباری، یا مستندسازی صریح «تک‌کاربره» و جلوگیری از ثبت‌نام چندکاربره |
| C2 | Critical | `api_token.py:60,84,116,138` | چرخهٔ توکن | `verify_token` بدون مصرف‌کننده؛ revoke روی کلید اشتباه؛ index نوشته نمی‌شود | توکن صادر می‌شود، هرگز باطل نمی‌شود، فهرست خالی | یک منبع واحد (`hash:*`)، revoke با حذف همان کلید، نوشتن index، و اتصال به یک dependency واقعی یا حذف `/tokens` |
| C3 | Critical | `api.py:964-976` + `models.py:181` | از دست رفتن داده | `delete_holding` سطر را پاک می‌کند و FK `gold_trades.holding_id` با `CASCADE` معاملات را می‌برد | یک کلیک در UI، تاریخچهٔ معاملات و مبنای مالیاتی را نابود می‌کند؛ `/portfolio/tax` و `export.csv` دیگر آن را ندارند | `ondelete="SET NULL"` یا soft-delete؛ هشدار + تأیید صریح در API (`?force=true`) |
| H1 | High | `api.py:96-117,1168-1187` | پوشاندن خطا | استثنا → ۲۰۰ + `success:false` + `str(exc)`؛ `/signals/recent` حتی `success:true` با متن خطا | مانیتورینگ/uptime/SPA خطا نمی‌بیند؛ پیام داخلی DB به کلاینت نشت می‌کند | `HTTPException(503)` یا `Response(status_code=503)` با پیام عمومی و `logger.exception` |
| H2 | High | `ws_hub.py:3,74` + `api.py:692-706` + `gold_desk_jobs.py:311` | قرارداد نادرست | تنها broadcast از job ۳۰۰ثانیه‌ای است؛ docstring «هر ۵ ثانیه» | «پخش زنده» عملاً هر ۵ دقیقه؛ فرانت با ping ۳۰ ثانیه‌ای زنده به‌نظر می‌رسد | یا حلقهٔ تولید سبک (پاسخ `/hot` هر ۵-۱۰ ثانیه) یا اصلاح مستندات و برچسب «۵ دقیقه» |
| H3 | High | `api.py:96,110` + `snapshot_service.py:45-54,196` | کارایی/معماری | `/score` و `/snapshot` build کامل؛ `_read_brsapi_prices` session مستقل باز می‌کند (ورودی `session` را نادیده می‌گیرد) | ~۳۷ کوئری + ۱۳ فراخوانی بیرونی برای ۶ عدد؛ checkout دوم از pool؛ `dependency_overrides` در تست روی قیمت‌ها اثر ندارد | کش کوتاه‌مدت یک snapshot در Redis + `single-flight`؛ `_read_brsapi_prices(session)` |
| H4 | High | ۵۹ از ۶۳ مسیر (۵۴ `dict` + ۵ `None`) | قرارداد | OpenAPI هیچ فیلدی برای پاسخ‌ها ندارد؛ ۳ شکل پاکت | تغییر فیلد بی‌صدا مصرف‌کننده را می‌شکند؛ کدجن/کلاینت تایپ‌دار ممکن نیست | `response_model=` روی همه + حذف dict‌های دستی |
| H5 | High | `api.py:379` vs `goldApi.ts:testTelegram` | پارامتر | `chat_id` کوئری است، فرانت body می‌فرستد | تست تلگرام همیشه به chat پیش‌فرض می‌رود (یا نمی‌رود) و کاربر نمی‌فهمد چرا | `chat_id: str \| None = Query(None)` → مدل بدنه، یا اصلاح فرانت |
| H6 | High | `api.py:1300-1343` | مستندات اجرایی | `base_url` غلط، auth غلط، ۱۸ از ۶۳ مسیر | ابزار خارجی مسیر/auth را اشتباه می‌گیرد | تولید از `router.routes` |
| H7 | High | `api.py:409-476` | سلامت | `brsapi_ok=db_ok`؛ Redis خاموش ⇒ ۲۰۰؛ یک کوئری بی‌مصرف؛ ۵ کوئری در probe | HEALTHCHECK BrsApi را هرگز نمی‌سنجد و Redis را نادیده می‌گیرد | `brsapi_ok` واقعی (آخرین `quality_flag`/`/freshness`) + ۵۰۳ برای Redis + حذف کوئری مرده |
| H8 | High | `api.py:979-1010,1033-1060` | منبع امتیاز | `current_score` از بدنهٔ کلاینت ذخیره و از query (پیش‌فرض ۶۰) خوانده می‌شود | «پلهٔ بعدی» و آستانه‌های پلن هیچ‌گاه امتیاز واقعی موتور را نمی‌بینند | محاسبه از snapshot/سرور، حذف پارامتر کلاینت |
| H9 | High | `api.py:266-277` + `schemas.py:150-157` | یکپارچگی | `AlertRuleUpdate` فیلدهای `NOT NULL` را `None`-پذیر می‌کند؛ `channel` آزاد در update، Literal در create | `{"name": null}` ⇒ `IntegrityError` ⇒ ۵۰۰؛ کانال نامعتبر ذخیره می‌شود و dispatch را می‌شکند | `exclude_unset` + اعتبارسنجی غیر-None + `Literal` یکسان |
| H10 | High | `api.py:482-487` + `freshness.py:158-181` | کارایی | ۱۳ منبع × ۲ کوئری، سریال، بدون کش | هر بار باز کردن صفحهٔ سلامت = ۲۶ کوئری | `asyncio.gather` + کش ۶۰ثانیه‌ای |
| H11 | High | `api.py:200-225` vs `goldApi.ts planDCA` | قرارداد شکسته | روت `POST /dca/plan` بدنهٔ خام `DCAResponse` می‌دهد (بدون `data`) ولی فرانت `r.data` را برمی‌گرداند | صفحهٔ DCA مقدار `undefined` می‌گیرد؛ پلن ساخته‌شده نمایش داده نمی‌شود | یا پاکت `{success,data}` (هم‌راستا با ۵۶ مسیر دیگر) یا اصلاح `return r` در فرانت |
| M1 | Medium | `api.py:1068-1086` | ماشین حالت | `if tranche > executed+1` فقط جلوگیری از **پرش** می‌کند؛ مقدار قبلی می‌تواند عقب برود | `[اجرا]` executed=5 + tranche=2 ⇒ `executed_tranches=2` | `if tranche != executed+1: 400` + `UPDATE … WHERE executed_tranches = :old` |
| M2 | Medium | `api.py:323-334` | مالکیت | `ack_alert` هر رویدادی را با id می‌بندد | (زیرمجموعهٔ C1) بستن هشدار دیگران | filter مالک پس از C1 |
| M3 | Medium | `api.py:342-377` | وضعیت مشترک | واچ‌لیست یک کلید Redis سراسری، `set_persistent`، بدون اعتبارسنجی نماد | همه یک لیست؛ نماد نامعتبر ذخیره می‌شود | کلید per-user + اعتبارسنجی در برابر `DISPLAY_LABELS` |
| M4 | Medium | `api.py:1168-1187` | خواندن/خطا | کل لیست خوانده و در حافظه sort می‌شود؛ خطای parse به `success:true` تبدیل می‌شود | با رشد سیگنال‌ها کند و بی‌صدا خراب | `lrange` + `count` + خطای واقعی |
| M5 | Medium | `api.py:1441` | مقدار جادویی | `usd_irt = … or 70000` وقتی snapshot نیست | قیمت ریالی کریپتو با نرخ فرضی و ۳۰۰ ثانیه کش می‌شود | خطای «نرخ دلار ناموجود» یا `dataAvailable:false` |
| M6 | Medium | `api.py:1413-1420` | عملیات | `POST /macro/scrape` اسکرپ همگام، بدون rate-limit/قفل | هر کاربر می‌تواند منبع را تحت فشار بگذارد | job + صف، یا محدودیت نرخ |
| M7 | Medium | `api.py:490-598` | خروجی | سه بک‌تست همگام تا ۷۳۰ روز، بدون کش؛ اعداد از موتور باگ‌دار C1/C2 می‌آید | پاسخ کند و **گمراه‌کننده** (بازده −۱۰۰٪) | رفع موتور، سپس کش/صف + هشدار `warning` برجسته |
| M8 | Medium | `api.py:1483-1553` | کارایی | آموزش ۳ مدل در هر درخواست `/forecast` | latency بالا و تکرار محاسبه | کش per (symbol, days) با TTL |
| M9 | Medium | `schemas.py:27` + `api.py:914-950` | فیلد مرده | `age_seconds=0`, `AssetBlock.quality_flag="clean"` | کلاینت به «تازگی» و «کیفیت» اعتماد می‌کند در حالی که مقداری ندارد | پر کردن واقعی یا حذف از schema |
| M10 | Medium | `snapshot_service.py:121,371` | برچسب | `mixed` دست‌نیافتنی؛ `quality_flag` دوحالته | منبع ترکیبی «tgju» برچسب می‌خورد؛ «پاک/فالبک» بدون درجه | سه‌حالته + درجه‌بندی |
| M11 | Medium | `schemas.py:96-106` vs `scorer.py` | پوشش | `raw_total`, `available_weight`, `data_coverage_pct` در پاسخ نیست | تصمیم GREEN با ۱ جزء، در API غیرقابل تشخیص | افزودن سه فیلد به `ScoreBlock` |
| M12 | Medium | `api.py:1264-1295` | وابستگی معیوب | `/patterns` از `pattern_detector` با cutoff میلادی می‌خواند (`01_engine.md` C3) | همیشه خالی + `historical_hit_rate` ثابت | رفع C3 موتور، سپس حذف اعداد ثابت |
| M13 | Medium | `metrics.py:39-86` + `api.py:1345` | مشاهده‌پذیری | `incr`/`measure_*` صفر فراخوان؛ `/metrics` پشت JWT؛ quantile روی نوع histogram | داشبورد همیشه صفر و scrape ناموفق | اتصال به handlerها (middleware) + مسیر عمومی محدود به شبکهٔ داخلی |
| M14 | Medium | `api.py:1208-1246` | پوشاندن خطا | `contextlib.suppress` روی portfolio و patterns | چت با context ناقص پاسخ می‌دهد و کاربر نمی‌داند | لاگ + پرچم `context_complete` در پاسخ |
| M15 | Medium | `api.py:257-263` | اعتبارسنجی | `rule_type` رشتهٔ آزاد | قانون نامعتبر ذخیره می‌شود و هرگز fire نمی‌کند | `Literal` از انواع پشتیبانی‌شدهٔ `alert_engine` |
| M16 | Medium | `api.py:146-169` | دقت | `int(r.total_score)` | نمودار با بریدن اعشار پله‌ای می‌شود | `round` + حفظ نوع |
| M17 | Medium | `api.py:603-648` | ورودی | `forward`/`strike` منفی و تاریخ گذشته پذیرفته می‌شود | قیمت اختیار بی‌معنا با ۲۰۰ | `gt=0` + `expiry > today` (تهران) |
| M18 | Medium | `api.py:81-88` | راه‌اندازی | import زیرروتِر Antigravity داخل `try/except` | اگر import بشکند، ۷ مسیر بی‌صدا ۴۰۴ می‌شوند و کسی نمی‌فهمد | fail-fast در محیط غیرتولیدی یا `/health` پرچم `antigravity_mounted` |
| L1 | Low | `api.py:1-3` | مستندات | «بدون auth چون شخصی است» | ممیزی بعدی را گمراه می‌کند | به‌روزرسانی docstring |
| L2 | Low | `api_token.py:46` | افشای جزئی | `token_id = plain[:8]` و همان در `GET /tokens` | ۴۸ بیت از راز در پاسخ فهرست | `token_id` مستقل تصادفی + `preview = plain[:4]+"…"` |
| L3 | Low | `api_token.py:24` | راز پیش‌فرض | salt هاردکد | در نبود env، salt عمومی است | الزام env در تولید (`raise` اگر unset) |
| L4 | Low | `api.py:114` | شکل | `/score` در خطا کلید `data` ندارد | پارس سمت کلاینت می‌شکند | یکسان‌سازی با `/snapshot` |
| L5 | Low | `api.py:466-472` | سازگاری | `from fastapi import Response` تکراری داخل تابع (بالا هم import شده) | سایه‌انداختن/سردرگمی | حذف import محلی |
| L6 | Low | `api.py:478-480` | ثابت کهنه | fallback `return 4` در حالی که رجیستری **۶** job دارد `[اجرا]` | `/health` عدد غلط می‌دهد اگر import شکند | از همان رجیستری یا صفر |
| L7 | Low | `api.py:928` | تدافعی | `getattr(summary, "unpriced_holdings", 0)` | نشانهٔ drift قرارداد داخلی | صریح‌سازی فیلد |
| L8 | Low | `metrics.py:139-147` | فرمت Prometheus | `quantile` روی `# TYPE histogram` | برخی scraperها آن را نامعتبر می‌دانند | `summary` یا bucket واقعی |
| L9 | Low | `api.py:128-131` | تکرار | `"IR_COIN_EMAMI"` در ۶ پیش‌فرض تکرار شده | تغییر نماد پیش‌فرض = ۶ ویرایش | ثابت در `constants.py` |
| L10 | Low | `hotpath.py:44-56` | دو منبع حقیقت | مرز `5` هاردکد در کنار `BUBBLE_GREEN_MAX` | تغییر constants، سیگنال سریع را نیمه‌به‌روز می‌کند | استفادهٔ کامل از constants |
| L11 | Low | `api.py:770-775` | کد وضعیت | حذف توکن ناموجود ⇒ ۲۰۰ `{"success": false}` | کلاینت نمی‌تواند ۴۰۴ را تشخیص دهد | ۴۰۴ |
| L12 | Low | `api.py:1103-1128` | تراکنش | `record_trade` خودش commit می‌کند (`portfolio.py:545`) | نوشتن غیراتمی در سطح API | commit در لایهٔ endpoint/UnitOfWork |

---

# ۸. پوشش تست

**اجرا:** `pytest tests/unit/api/test_gold_personal_surface_auth.py tests/unit/api/test_golddesk_portfolio_returns.py tests/unit/api/test_golddesk_portfolio_performance.py tests/unit/test_gold_freshness.py tests/unit/test_gold_desk_job_registry.py -q` ⇒ **۶۸ passed** در ۶۶ ثانیه. به‌علاوه `tests/unit/services/test_gold_snapshot_fund_prices.py` = **۴ تست** (مسیر قیمت صندوق در `_read_brsapi_prices`). جمع دامنه: **۷۲ تست سبز**.

| ماژول | تست موجود | چه چیزی پوشش دارد | چه چیزی ندارد |
|---|---|---|---|
| `api.py` (۶۳ op) | `test_gold_personal_surface_auth.py` (**۴۶ تست** جمع‌آوری‌شده) | ۴۰۱ برای مسیرهای شخصی، ۲۰۰/۵۰۳ برای health، assistant-rules آزاد، WS ۱۰۰۸، تفکیک `/analytics` | **شکل پاسخ هیچ مسیری**؛ خطاها؛ `/tokens`؛ `/alerts` CRUD؛ `/portfolio/trades`؛ `/docs/endpoints` |
| `api.py` (پرتفوی) | `test_golddesk_portfolio_returns.py`, `…_performance.py` | سیمینگ و shape دو مسیر با stub | سایر ۱۳ مسیر پرتفوی؛ مسیر خطا |
| `snapshot_service.py` | `test_gold_snapshot_fund_prices.py` (۴) | قیمت صندوق از provider، fallback به close، غیبت بدون صفر | `build_snapshot`، `_read_references` (فالبک TGJU)، برچسب `source`، `_calc_daily_changes`، `ScoreBlock` ناقص، `quality_flag` |
| `hotpath.py` | **هیچ** | — | آستانه‌ها، `build_hotpath_response` با snapshot ناقص/`None` |
| `ws_hub.py` | فقط تست ۱۰۰۸ | توکن‌نداشتن | register/unregister، broadcast، snapshot اولیه |
| `api_token.py` | **هیچ** | — | revoke (باگی که `[اجرا]` نشان داد)، list، verify |
| `metrics.py` | **هیچ** | — | رندر، شمارنده‌ها، فرمت Prometheus |
| `freshness.py` | `test_gold_freshness.py` | وضعیت‌ها و تبدیل زمان | پوشش خوب است؛ فقط هزینه/کش ندارد |
| job registry | `test_gold_desk_job_registry.py` | نگاشت نام→تابع، job ناشناس | کادنس واقعی (۳۰۰ ثانیه vs ادعای ۵ ثانیه) |

**تست‌های لازم (پیشنهاد، به ترتیب ارزش):**
1. `test_tokens_revoke_is_effective` — یک توکن بساز، revoke کن، `verify_token` باید `None` بدهد (امروز fail می‌شود).
2. `test_snapshot_error_is_503` — `build_snapshot` را raise کن، انتظار `status_code == 503` و نبود `str(exc)` در بدنه.
3. `test_score_block_exposes_data_coverage` — پاسخ `/snapshot` باید `data_coverage_pct` داشته باشد.
4. `test_delete_holding_keeps_trades` — حذف دارایی نباید ردیف‌های `gold_trades` را پاک کند.
5. `test_dca_execute_rejects_a_rewind` — `executed=5` + `tranche=2` ⇒ ۴۰۰.
6. `test_telegram_test_reads_chat_id_from_body` — همان قراردادی که فرانت استفاده می‌کند.
7. `test_health_reports_brsapi_separately` — `brsapi_ok` نباید از `db_ok` کپی شود.
8. `test_every_route_has_a_response_model_or_is_documented_exempt` — گارد علیه بازگشت dict خام.
9. `test_docs_endpoints_lists_every_route` — فهرست باید با `router.routes` برابر باشد (الگوی `test_analytics_route_split_is_exhaustive` را دارد).
10. `test_watchlist_is_per_user` — پس از C1.
11. `test_personal_data_is_scoped_to_owner` — دو کاربر، دو پرتفوی (پس از C1).
12. `test_ws_broadcasts_at_the_documented_cadence` — یا کادنس را قفل کند یا مستندات را.

---

# ۹. وابستگی‌های بیرونی و سؤالات باز

## ۹.۱ وابستگی‌ها (فقط خوانده و گزارش شده)

| وابستگی | مصرف‌کننده در دامنه | نکته |
|---|---|---|
| `apps/api/dependencies.get_db_session` | ۳۶ handler | generator واحد؛ session مستقل در `_read_brsapi_prices` از آن عبور نمی‌کند |
| `apps/api/router._require_user` | مونتاژ | `require_any_role("user","analyst","admin")` |
| `apps/api/middleware.SecurityMiddleware` | همهٔ نوشتن‌ها زیر `/api/v1/gold/` | گیت دوم مستقل |
| `core.cache.get_cache` | watchlist، snapshot، crypto، signals، tokens، hot | APIهای استفاده‌شده: `get`, `set(ttl=…)`, `set_persistent`, `ping` |
| `brsapi.services.query_service.BrsApiQueryService` | `_read_brsapi_prices` | `get_gold_coin_prices`, `get_currency_prices`, `get_commodity_prices`, `get_symbol_snapshot` |
| `src/gold_desk.secondary_source` (TGJU) | `_read_references` | شبکه؛ `is_available` می‌تواند کاذب باشد |
| `brsapi.jobs.gold_desk_jobs` | تنها نویسندهٔ `REDIS_KEY_SNAPSHOT` و تنها فراخوان `broadcast` | ۶ job؛ `gold_daily_history` **no-op** است |
| `src/gold_desk.portfolio*`, `alert_engine`, `chat`, `forecaster`, `crypto`, `macro_news`, `pattern_detector`, `backtest*` | handlerها | منطق‌شان در `01_engine.md` حسابرسی شده |
| `frontend/src/lib/goldApi.ts` | مصرف‌کنندهٔ سیم | منبع حقیقت قرارداد عملی (نه OpenAPI) |

## ۹.۲ سؤالات باز

1. **واحد پول:** `usd_irt`, `market_price`, `amount_irt` تومان‌اند یا ریال؟ کد در هیچ لایه‌ای تثبیت نکرده و دادهٔ BrsApi هم مستند نیست (همان سؤال باز `01_engine.md`). تا پاسخ نیاید، هر گزارش P&L قابل بحث است.
2. **چند کاربر واقعاً وجود دارد؟** اگر تنها یک اپراتور، C1 به «مستندسازی» تنزل می‌کند؛ اگر پلتفرم ثبت‌نام دارد، C1 مسدودکنندهٔ انتشار است.
3. **`/snapshot` چرا پشت JWT است؟** دادهٔ بازار است، نه دادهٔ شخصی؛ ولی `/health` و `assistant-rules` آزادند. آیا تصمیم محصولی است یا باقی‌ماندهٔ مونتاژ؟
4. **`/gold/metrics` را چه کسی scrape می‌کند؟** اگر Prometheus است، توکن ثابت در config دارد؟ (در کد اثری نبود.)
5. **`/tokens` قرار بود به کجا وصل شود؟** یک سطح SaaS جدا (`/api/v1/golddesk` با `core.security.saas`) وجود دارد که واقعاً توکن اسکوپ‌دار را enforce می‌کند؛ آیا `src/gold_desk/api_token.py` نسخهٔ مردهٔ همان است؟
6. **کادنس مطلوب live stream** ۵ ثانیه است یا ۵ دقیقه؟ (کد: ۳۰۰s؛ docstring: ۵s.)
7. **`REDIS_KEY_SNAPSHOT` TTL=600 با job=300:** اگر یک اجرا شکست بخورد، `/hot` و کل مسیر پرتفوی تا ۱۰ دقیقه دادهٔ کهنه بی‌هشدار می‌دهند. آیا این قابل قبول است؟

---

# ۱۰. رابط (Interface) با دیگر بخش‌ها

## ۱۰.۱ قراردادهایی که مصرف‌کننده‌ها به آن تکیه می‌کنند و **نباید** بی‌خبر تغییر کنند

| قرارداد | مصرف‌کننده | ریسک تغییر |
|---|---|---|
| `GET /api/v1/gold/snapshot` → `{success, data: SnapshotResponse}` | فرانت (`getSnapshot`)، صفحات analytics | حذف/تغییر نام هر فیلد = صفحهٔ سفید |
| `references.source` ∈ `{brsapi, tgju, cache}` | فرانت/تست‌ها | افزودن `mixed` نیازمند به‌روزرسانی Literal و فرانت |
| `score.decision` ∈ `{GREEN, YELLOW, RED}` | فرانت، `alert_engine` | افزودن `NO_DATA` (پیشنهاد `01_engine.md` C5) یک تغییر ناسازگار است و باید از قبل اعلام شود |
| `GET /gold/hot` → `data.status ∈ {ok, no_data}` | polling فرانت | — |
| `GET /gold/health` → **بدنهٔ خام** `HealthResponse` | Docker HEALTHCHECK + `getHealth` | پاکت‌دار کردن، HEALTHCHECK را نمی‌شکند ولی فرانت را |
| `GET/PUT /gold/watchlist` → **بدنهٔ خام** | فرانت | — |
| `POST /gold/dca/plan` → **بدنهٔ خام** `DCAResponse` | فرانت | پاکت‌دار کردنش ناسازگار است تا وقتی `goldApi.ts` `r.data` را می‌خواند (H11) |
| CSV با هدر `traded_at,symbol,action` | گزارش مالیاتی/اکسل | تغییر ستون‌ها = شکستن قالب کاربر |
| `REDIS_KEY_SNAPSHOT = "golddesk:snapshot:latest"` | job → `hotpath` → `/portfolio*` | تغییر کلید = `/portfolio` بدون قیمت |
| WS frame `{"type":"snapshot","data":…}` | `GoldWSManager` | تغییر نام `type` = استریم خاموش |

## ۱۰.۲ ترتیب و سایه‌اندازی مسیرها

- `gold_core_router` پیش از GoldDesk مونتاژ می‌شود؛ تداخل path امروز صفر است ولی هیچ assert‌ای ندارد `[کد: router.py:277-296]`.
- `WS /gold/ws` روی `anonymous_router` است تا dependency HTTP فرصت رد کردن handshake را نداشته باشد؛ حذف آن از روتِر ناشناس = شکستن جریان زنده `[کد: api.py:691-706]`.
- حذف `anonymous_router` از `router.py` = ۴۰۴ برای `/health` (HEALTHCHECK) و `/assistant-rules` (صفحات قبل از لاگین).

## ۱۰.۳ کارهایی که باید در همین لایه انجام شود (به ترتیب وابستگی)

1. **C1** — تصمیم مالکیت داده. تا این تصمیم گرفته نشود، هر کار دیگری روی پرتفوی/هشدار موقتی است.
2. **C2** — یا `/tokens` حذف/مستند شود («بدون مصرف‌کننده») یا به `core.security.saas` وصل شود.
3. **C3** — `SET NULL` + تأیید صریح حذف دارایی.
4. **H1** — ۵۰۳ واقعی + حذف `str(exc)` از پاسخ. این پیش‌نیاز مانیتورینگ درست است.
5. **H3** — کش/single-flight برای snapshot، سپس `/score` سبک.
6. **H4** — `response_model` روی همه؛ این کار `openapi.json` را قابل استفاده می‌کند و H6 را خودکار حل می‌کند.
7. سپس H5/H7/H8/H9 و M‌ها.

---

## پیوست: چگونه هر ادعا را بررسی کردم

| ادعا | روش |
|---|---|
| ۶۳ عملیات و مسیرها | `import src.gold_desk.api` + پیمایش `router.routes`/`anonymous_router.routes` و چاپ `methods`/`path` |
| تداخل با `endpoints/gold.py` | پیمایش همان روتِر (۱۳ مسیر) و مقایسهٔ مجموعهٔ path |
| HTTP 200 در خطا + نشت پیام | `TestClient` با `dependency_overrides[get_db_session]` و `build_snapshot` پچ‌شده به `raise RuntimeError(...)` ⇒ چاپ `status_code` و `json()` |
| `brsapi_ok == db_ok` و Redis خاموش ⇒ ۲۰۰ | `get_cache` پچ‌شده به cache با `ping→False` ⇒ پاسخ کامل health |
| revoke بی‌اثر / list خالی / token_id = plain[:8] | `FakeCache` درون‌حافظه + `save_token`/`verify_token`/`revoke_token`/`list_tokens` ⇒ چاپ کلیدهای Redis |
| `chat_id` در query است | پیمایش `route.dependant.query_params` و `body_params` |
| DCA rewind | فراخوانی مستقیم `execute_dca_tranche(plan_id=1, tranche=2, session=FakeSession(plan with executed=5))` ⇒ `executed_tranches=2` |
| `mixed` دست‌نیافتنی | استدلال روی شرط `:121` + `Literal` در `schemas.py:27` |
| هزینهٔ build | شمارش فراخوانی‌ها در `snapshot_service`/`nav_checker` (۳ کوئری per fund) و `FUND_SYMBOLS` (۱۰ عضو) |
| پوشش تست | اجرای ۵ فایل در دامنه (۶۸ پاس) + شمارش تست‌های `test_gold_snapshot_fund_prices.py` (۴) |
| نبود `user_id` | `code_search` روی `user_id|__tablename__` در `models.py` ⇒ ۹ جدول، صفر ستون مالک |
