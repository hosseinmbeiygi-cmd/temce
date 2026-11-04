# 🥇 GoldDesk — تحلیل و پایش شخصی طلای ایران

ابزار شخصی برای تحلیل داده‌محور بازار طلا، سکه، ارز و صندوق‌های طلا. شامل scoring ۶ کامپوننت، DCA، options (Black-76)، portfolio tracker، chatbot، real-time signals و PWA.

> ### ⚠️ دقت اسناد (D1 — بازمحاسبه از کد، ۲۰۲۶-۱۰-۲۴)
>
> این بخش از سند قبلاً با کد نمی‌خواند. اعداد زیر **از خودِ repo شمرده شده‌اند**،
> نه از ادعای نسخهٔ قبلی:
>
> | مورد | ادعای قبلی | واقعیت کد |
> |---|---|---|
> | پایهٔ URL | `/api/gold` | **`/api/v1/gold`** (`api.py:67,79` prefix `/gold` + mount زیر v1؛ فرانت هم `frontend/src/lib/api.ts:1` را همین می‌داند) |
> | عملیات سطح شخصی GoldDesk | «28+» | **۶۳** = ۶۲ HTTP + ۱ WebSocket (`src/gold_desk/api.py`: ۵۵+۱، `src/gold_desk/antigravity/api.py`: ۷) |
> | سطح‌های دیگر (جدا شمرده می‌شوند) | — | `apps/api/endpoints/gold.py` ۱۳ · `gold_analytics.py` ۲۶ · `golddesk.py` (SaaS) ۳ |
> | جدول‌های GoldDesk | «5 جدول» | **۹** (`src/gold_desk/models.py`) |
> | فایل‌های `src/gold_desk/` | «37 فایل» | **۴۷** فایل `.py` |
> | صفحات فرانت طلا | «8 صفحه» | **۲۰** route زیر `/gold` — که فقط **۱۵** تایشان در `TABS` ناوبری هستند؛ ۵ route بدون لینک: `/gold/coins`, `/gold/dashboard`, `/gold/dca`, `/gold/funds`, `/gold/technical` |
> | کامپوننت‌های طلا | «15 component» | **۲۱** فایل در `components/gold/` که **۱۰** تای آن‌ها بیرون از تست‌ها هیچ import ندارند (فهرست در `docs/fixes/frontend_infra_CHANGELOG.md`) |
> | فایل‌های طلای فرانت | «21 فایل» | **۵۸** (۳۱ در `app/gold/**` + ۲۱ در `components/gold/**` + ۶ فایل lib/types/hook/public) |
> | jobهای زمان‌بندی طلا | «4 job» | **۶** job در `brsapi/jobs/gold_desk_jobs.py` (`job_gold_snapshot`, `_score_persist`, `_alert_evaluate`, `_fund_nav`, `_portfolio_value`, `_daily_history`) + jobهای macro جدا (CFTC، tokenized gold) |
> | Next.js | «Next.js 15» | **۱۶.۲.۹** (`frontend/package.json`) |
> | تست‌های `tests/gold_desk` | «117 passed in 2.45s» | **۲۵۸ passed, 1 deselected in ~35s** (اجرای واقعی ۲۰۲۶-۱۰-۲۴ با `./venv/Scripts/python.exe -m pytest tests/gold_desk -q`) |
> | تست فرانت | ذکر نشده بود | **۴۸ فایل / ۵۲۷ تست vitest** پاس (`cd frontend && npx vitest run`) |
> | مجوز | «شخصی — استفاده داخلی» | **MIT** — فایل `LICENSE` موجود است و README هم MIT می‌گوید؛ تناقض با این سند رفع شد (تأیید نهایی صاحب محصول باقی می‌ماند) |

---

## 🚀 شروع سریع

### پیش‌نیازها
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (یا TimescaleDB)
- Redis 7+
- (اختیاری) Telegram Bot Token

### نصب
```bash
# Backend
pip install -r requirements.txt
alembic upgrade head

# Frontend
cd frontend && pnpm install
```

> ⚠️ **اولین راه‌اندازی؟** `docker compose up` بدون چهار مقدار secret عمداً
> می‌ایستد (I3). ساخت مقدار، پرکردن `.env`، و بررسی سلامت:
> **`docs/golddesk_first_run.md`**. بازگردانی نسخه: `docs/golddesk_backup.md`.

### اجرا
```bash
# Terminal 1: Backend
uvicorn apps.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && pnpm dev

# Terminal 3: Scheduler (jobs)
python -m apps.scheduler.app
```

سپس باز کنید: **http://localhost:3000/gold**

### با Docker
```bash
docker-compose -f docker-compose.production.yml up -d
```

---

## ✨ Features

### داشبورد (`/gold`)
- **Score 0-100** با ۶ کامپوننت: bubble, NAV, TSETMC, technical, parity, fund_flow
- **تصمیم**: سبز (≥۸۰)، زرد (۵۵-۷۹)، قرمز (<۵۵) — و از این نسخه **`NO_DATA`** وقتی
  وزنِ داده‌دارِ موجود زیر آستانه باشد (قرارداد C1). در `NO_DATA` عدد `total` همچنان
  رسم می‌شود ولی رنگ سبز/قرمز **نمی‌گیرد** و UI «داده ناکافی» + `data_coverage_pct`
  را نشان می‌دهد.
- **Hard stop** خودکار (TSE crash > 5%، DXY spike > 3%، USD spike > 5%)
- **طلا و سکه**: bubble % + دلار ضمنی — `bubble_pct` و `implied_usd` nullable هستند
  (C2): نبود داده «—» است، نه صفر.
- **صندوق‌های طلا**: P/NAV + BPR + Inflow
- **تکنیکال اونس**: نمودار SVG با تغییر بازه
- **اختیار Black-76**: ATM + Protective Collar
- **DCA inline**: calculator ۳ risk profile
- **هشدار ثابت** روی صفحه: «ابزار تحلیلی، نه توصیهٔ مالی» (F3 — دیگر هیچ حالتی
  «خرید قطعی» خوانده نمی‌شود)

### تحلیل تاریخی (`/gold/analytics`)
- نمودار امتیاز در زمان با band رنگی
- مقایسه همزمان چند symbol
- Heatmap صندوق‌ها (داغ/گرم/سرد)

### DCA Plans (`/gold/portfolio` → DCA)
- ساخت پلن با ۳ پله (conservative/balanced/aggressive)
- علامت‌گذاری پله اجرا شده
- Trigger شرطی هر پله

### Portfolio Tracker (`/gold/portfolio`)
- ثبت خرید (symbol, quantity, buy_price)
- **P&L خودکار** بر اساس قیمت فعلی از snapshot
- تاریخچه معاملات
- P&L تجمعی

### Alerts (`/gold/alerts`)
- قوانین: bubble > 25%، score > 80، شکاف درهم > 3%، حباب NAV > 3%
- ۵ قانون پیش‌فرض (seed)
- اعلان In-app + Telegram
- cooldown قابل تنظیم

### Live Signals (`/gold`)
- **Real-time banner** با beep
- تشخیص spike قیمت (سکه، دلار، درهم)
- تغییر امتیاز ≥ 10
- حباب شدید (≥ 25%)
- cooldown ۱۰ دقیقه

### Chatbot AI (`/gold/chat`)
- System prompt با snapshot + portfolio + patterns
- ترکیب ChatEngine temce + fallback heuristic
- پیشنهاد سریع

### Patterns Detection (`/api/v1/gold/patterns`)
- `mean_reversion` (bubble > 20% → بازگشت؟)
- `trend_continuation` (7+ روز مثبت)
- `spike_crash` (جهش > 5% → اصلاح؟)
- `vol_regime` (نوسان بالا = ریسک)

### Hot Path (`/api/v1/gold/hot`)
- snapshot کم‌حجم (latency < 50ms)
- برای polling هر ۱۰ ثانیه
- شامل: refs + score + signal coin_emami + ۳ صندوق برتر

### API Tokens (`/gold/tokens`)
- scopes: read / write / admin (همین سه؛ scope چهارمی مثل `metrics` هنوز در کد نیست —
  `src/gold_desk/api_token.py:32`)
- OpenAPI docs در `/api/v1/gold/docs/endpoints`
- امکان اتصال Google Sheets، ربات تلگرام، اپ موبایل

### Backtest (`/api/v1/gold/backtest`)
- سیگنال ساده: bubble threshold → forward 30d return
- استراتژی DCA: alpha, Sharpe, max drawdown
- تازگی (D1): `hit_rate_pct` همچنان در پاسخ API هست، اما به‌عنوان **ادعای کیفیت**
  در این سند مطرح نمی‌شود — روی نمونهٔ کوچک و با تعریف «پیروزی» که خودِ موتور
 تنظیم می‌کند، شاخص قابل اتکایی نیست. تا راستی‌آزمایی نشده، در UI هم فقط یک عدد
  خام است نه امتیاز عملکرد.
- متریک out-of-sample در `backtest_runner.py` (`oos_*`) محاسبه می‌شود ولی
  `/backtest/real` آن را در پاسخ **نمی‌گذارد** → درخواست به بک‌اند ثبت شده.

### کلان (`/gold/macro`) — فقط اطلاعاتی
- تحلیل کلان (TIPS/DXY/روند) به امتیاز **وصل نمی‌شود**؛ قرارداد C6: پاسخ
  `/macro` فیلد `affects_score: false` دارد و UI برچسب «اطلاعاتی — بدون اثر بر
  امتیاز» را نشان می‌دهد.

### Options (Black-76)
- Call/Put pricing با Greeks (Δ, Γ, Vega, Θ, Ρ)
- Protective Collar (floor/cap با هزینه نزدیک صفر)

### تم‌ها
- 🌙 **Dark** (پیش‌فرض)
- ☀️ **Light**
- ✨ **Gold** premium

### PWA
- قابل نصب روی موبایل (Add to Home Screen)
- Service Worker با offline mode
- Push notification ready

---

## 📊 معماری

```
┌─────────────────────────────────────────────────────────────┐
│              Frontend (Next.js 16 + TypeScript)              │
│ • 20 route  • 15 در ناوبری  • 21 component (10 بدون import) │
│  • 3 theme  • mobile responsive • PWA (manifest + SW + TTL) │
└────────────────────┬────────────────────────────────────────┘
                     │ /api/v1/gold/* (FastAPI)
┌────────────────────▼────────────────────────────────────────┐
│                  Backend (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  GoldDesk Analytics Engine                            │  │
│  │  pricer | bubbler | scorer | dca | pattern | signals │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Infra: alerts | telegram | chat | portfolio | hot   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /metrics (Prometheus) + /health (Docker healthcheck) │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
       ┌─────────────┼─────────────┬──────────────┐
       ▼             ▼             ▼              ▼
   TimescaleDB    Redis        BrsApi.ir     TSETMC (via BrsApi)
   (snapshots,    (live rate,  (HTTP)         (HTTP)
    history)      EMA cache,
                  alerts queue)
```

> **Time-series در TimescaleDB:** جدول‌های ۹‌گانهٔ `src/gold_desk/models.py`
> (gold_snapshots، gold_score_history، gold_portfolio_values و…) **hypertable
> نیستند** — در migration های `0041/0042/0043` به‌صورت جدول معمولی ساخته شده‌اند.
> تنها جدولِ با پیشوند طلا که hypertable است `gold_currency_prices` است
> (`migrations/versions/0001_initial_schema.py:330`) که متعلق به این ماژول نیست.
> وضعیت تبدیل شدن یا نشدنشان کار دستیار ۲ است (`docs/analysis/02_backend_infra.md`).

### Backend (۴۷ فایل `.py` در `src/gold_desk/`)
```
src/gold_desk/
├── constants.py            # ثابت‌ها (عیار، وزن سکه، thresholds, fees)
├── models.py               # 9 جدول SQLAlchemy
├── schemas.py              # Pydantic models
├── pricer.py               # fair_value (طلا + سکه)
├── bubbler.py              # حباب + implied USD
├── parity.py               # شکاف درهم
├── signal_engine.py        # RSI/EMA
├── nav_checker.py          # P/NAV صندوق
├── scorer.py               # 6-component scoring
├── dca_planner.py          # 3 risk profile + fee
├── hard_stops.py           # event-based hard stop
├── snapshot_service.py     # orchestration + self-check
├── secondary_source.py     # TGJU fallback
├── alert_engine.py         # rules + dedup
├── telegram_bot.py         # httpx مستقیم
├── backtest.py             # signal backtest
├── backtest_runner.py      # DCA strategy simulation
├── black76.py              # Options pricing + Greeks + Collar
├── live_signals.py         # Real-time signal detector
├── pattern_detector.py     # AI pattern recognition
├── portfolio.py            # P&L + DCA tracker
├── hotpath.py              # Lightweight fast endpoint
├── api_token.py            # Personal API tokens
├── chat.py                 # AI assistant with system prompt
├── ws_hub.py               # WebSocket broadcast hub
├── macro_news.py           # CBI/MarkazAmar/WGC events
├── metrics.py              # Prometheus exporter
├── snapshot_service.py
├── alert_engine.py
├── api.py                  # 55 HTTP + 1 WebSocket (سطح شخصی)
└── __init__.py

brsapi/jobs/gold_desk_jobs.py    # 6 scheduler job
```

### Frontend (۵۸ فایل طلایی: ۳۱ در `app/gold/**`، ۲۱ در `components/gold/**`، ۶ lib/types/hook/public)
```
frontend/src/
├── app/gold/
│   ├── layout.tsx              # 3 theme + drawer + bottom nav + PWA + LiveSignalBanner
│   ├── page.tsx                # Unified dashboard
│   ├── chat/page.tsx           # AI assistant
│   ├── portfolio/page.tsx      # 4 tab (overview/add/dca/trades)
│   ├── analytics/page.tsx      # score chart + compare + heatmap
│   ├── alerts/page.tsx         # rules + events
│   ├── backtest/page.tsx       # strategy backtest
│   ├── tokens/page.tsx         # API token management
│   └── settings/page.tsx       # health + telegram + watchlist
├── components/gold/            # 15 components
│   ├── ThemeProvider.tsx
│   ├── PWAProvider.tsx
│   ├── LiveSignalBanner.tsx
│   ├── GoldKPICard.tsx
│   ├── ScoreGauge.tsx
│   ├── ScoreBreakdown.tsx
│   ├── CoinBubbleTable.tsx
│   ├── FundNAVTable.tsx
│   ├── ParityBadge.tsx
│   ├── RSIIndicator.tsx
│   ├── TimeSeriesChart.tsx
│   ├── BubbleGauge.tsx
│   ├── AlertRuleForm.tsx
│   ├── AlertEventList.tsx
│   └── DCACalculator.tsx
├── lib/goldApi.ts              # Typed API client + WS manager
├── types/gold.ts               # TypeScript types
└── public/
    ├── golddesk-manifest.json  # PWA manifest
    └── golddesk-sw.js          # Service worker
```

---

## 🔌 API Endpoints

پایهٔ همه: **`/api/v1/gold`** (در نسخهٔ قبل این سند `/api/gold` نوشته بود؛ آن
مسیر در کد وجود ندارد). شمارش از خودِ کد: ۵۵ HTTP + ۱ WebSocket در
`src/gold_desk/api.py` و ۷ HTTP در `src/gold_desk/antigravity/api.py` → **۶۳
عملیات** در سطح شخصی. سطح‌های محاسبگر عمومی (`apps/api/endpoints/gold.py` ۱۳،
`gold_analytics.py` ۲۶، `golddesk.py` SaaS ۳) جدا شمرده می‌شوند.

| Method | Path | Scope | توضیح |
|---|---|---|---|
| GET | `/snapshot` | read | Live snapshot |
| GET | `/score` | read | فقط score |
| GET | `/history/score?days=7` | read | Time-series امتیاز |
| GET | `/history/snapshot?symbol=&days=` | read | Time-series asset |
| POST | `/dca/plan` | read | محاسبه DCA |
| GET | `/alerts/rules` | read | لیست قوانین |
| POST | `/alerts/rules` | write | ساخت قانون |
| GET | `/alerts/events?days=&unread_only=` | read | رویدادها |
| POST | `/alerts/{id}/ack` | write | خوانده‌شده |
| POST | `/alerts/seed` | write | درج قوانین پیش‌فرض |
| POST | `/options/price` | read | Black-76 |
| POST | `/options/collar` | read | Protective Collar |
| GET | `/backtest?days=90` | read | Signal backtest |
| GET | `/backtest/strategy?days=90` | read | DCA strategy |
| POST | `/telegram/test` | write | تست Telegram |
| GET | `/health` | read | Health check (503 در خطا) |
| POST | `/tokens` | admin | ساخت API token |
| GET | `/tokens` | admin | لیست tokens |
| DELETE | `/tokens/{id}` | admin | Revoke |
| GET | `/docs/endpoints` | read | OpenAPI-like list |
| GET | `/portfolio` | read | Portfolio P&L |
| POST | `/portfolio/holdings` | write | ثبت خرید |
| POST | `/portfolio/dca` | write | ساخت پلن DCA |
| GET | `/portfolio/dca` | read | لیست با status |
| POST | `/portfolio/dca/{id}/execute` | write | علامت‌گذاری اجرا |
| POST | `/portfolio/trades` | write | ثبت معامله |
| GET | `/portfolio/trades` | read | تاریخچه |
| GET | `/hot` | read | Hot path (latency < 50ms) |
| GET | `/signals/recent` | read | سیگنال‌های اخیر |
| POST | `/signals/detect` | write | تشخیص دستی |
| GET | `/patterns` | read | الگوهای AI |
| POST | `/chat` | read | AI assistant |
| GET | `/watchlist` | read | Watchlist |
| PUT | `/watchlist` | write | جایگزینی |
| GET | `/telegram/status` | read | Telegram config |
| GET | `/metrics` | read | Prometheus |
| GET | `/macro` | read | Macro events (اطلاعاتی — `affects_score: false`، C6) |
| POST | `/macro/scrape` | read | Scrape CBI |
| WS | `/ws` | read | Live WebSocket |

### کادنس WebSocket (C10) — هدف در برابر واقعیت کد

| | هدف قرارداد (C10) | واقعیت کد امروز |
|---|---|---|
| `hot` | هر ۱۰ ثانیه، وقتی ≥۱ کلاینت وصل است | **هیچ push دوره‌ای ندارد** |
| `snapshot` | هر ۳۰۰ ثانیه | فقط **یک** snapshot کش‌شده در لحظهٔ اتصال (`ws_hub.py:31-33`) |
| `signal` | — | تنها چیزی که واقعاً broadcast می‌شود (`live_signals.py:188`) |

`ws_hub.py:71-87` بعد از accept فقط `receive_text()` می‌خواند و به `ping` پاسخ
`pong` می‌دهد؛ حلقهٔ push ندارد. docstring های `ws_hub.py:3` و `api.py:693`
«هر ۵ ثانیه» می‌گویند و با کد نمی‌خوانند. زمان‌بندی سمت سرور کار دستیار ۲ است.
فرانت از این نسخه هر سه نوع پیام را می‌فهمد و کهنگی را خودش اعلام می‌کند.

---

## 🧪 Tests

```bash
# backend — موتور و surface طلا
./venv/Scripts/python.exe -m pytest tests/gold_desk -q
# ۲۵۸ passed, 1 deselected in ~35s   (اجرای واقعی ۲۰۲۶-۱۰-۲۴)

# frontend — لایهٔ API، رندرها، WS و SW
cd frontend && npx vitest run
# ۴۸ فایل / ۵۲۷ تست passed   (اجرای واقعی ۲۰۲۶-۱۰-۲۴)
```

> عدد «117 passed in 2.45s» در نسخهٔ قبل این سند بود و با کد نمی‌خواند. تست‌های
> نیازمند DB واقعی در `tests/gold_desk` خودشان skip می‌شوند؛ برای شمارش دقیق،
> فایل‌ها را هدف بگیرید نه `-k`.

پوشش:
- `constants.py` — ثابت‌ها، thresholds
- `pricer.py` + `bubbler.py` — fair_value، حباب، implied USD
- `scorer.py` — 6 کامپوننت + hard stop + آستانهٔ پوشش داده (C1)
- `dca_planner.py` — 3 risk profile + fee
- `black76.py` — pricing + Greeks + parity
- `backtest_runner.py` — DCA simulation
- `portfolio.py` — P&L + soft-delete (C7)
- `chat.py` — fallback heuristic
- `live_signals.py` — spike detection
- `pattern_detector.py` — mean_reversion, trend, spike, vol
- `macro_news.py` — impact estimation
- فرانت (افزوده‌شده در این رفع): `GoldThemeTokens` (F1)، `GoldApiLayer`
  (F2/F4/C3/C4/C5)، `GoldNoData` (F3/C1)، `GoldWebSocket` +
  `GoldSnapshotPolling` (F6/C10)، `GoldServiceWorker` (F9)،
  `GoldFrontendSurfaces` (F5/F8/F10)

---

## 🐳 Deployment

### Docker
```bash
docker build -f Dockerfile.golddesk -t golddesk-worker .
docker run --env-file .env golddesk-worker
```

### Healthcheck
```bash
curl http://localhost:8000/api/v1/gold/health
# 200: سالم
# 503: db/redis قطع (C8 — این رفتار در کد پیاده شده: api.py `def health`)
```

⚠️ تصویر `Dockerfile.golddesk` فقط scheduler را اجرا می‌کند و پورت HTTP باز
نمی‌کند؛ probe روی `localhost:8000` همیشه شکست می‌خورد. healthcheck همان فایل
به `http://backend:8000/api/v1/gold/health` تغییر کرده (وابستگی‌های مشترک را
از طریق API می‌سنجد).

### Nginx
snippet در `nginx-golddesk.conf`:
- `/api/v1/gold/*` → backend:8000
- `/api/v1/gold/ws` → upgrade WebSocket + **لاگ با query ماسک‌شده** (توکن در query
  می‌آید؛ در نسخهٔ قبل روی دیسک نوشته می‌شد — I1)
- `/gold/*` → frontend:3000

> نسخهٔ قبل این فایل مسیرهای `/api/gold/*` را داشت که با هیچ درخواست واقعی مچ
> نمی‌شد.

### Prometheus
scrape config در `monitoring/golddesk-prometheus.yml`:
- `/api/v1/gold/metrics` هر ۳۰s، با `authorization.credentials_file` (C9)
- **هنوز کار نمی‌کند**: `api_token.py:32` فقط `read|write|admin` دارد و scope
  «metrics» وجود ندارد → درخواست در `docs/fixes/handoff_frontend_to_backend.md`

---

## 📈 Load Testing

```bash
pip install locust
locust -f tests/load/locustfile.py --host http://localhost:8000
```

SLO — **هدف‌های اعلام‌شده، نه چیزهایی که تأیید شده‌اند** (D1): هیچ اجرای
load test مستندِ تکرارپذیری این اعداد را تأیید نکرده است. تا وقتی `locust` روی
محیط معادل production اجرا و خروجی‌اش بایگانی نشده، اینها فقط آستانهٔ آرزومندانه
هستند و نباید به‌عنوان «SLO تأییدشده» در گزارش یا قرارداد استفاده شوند:
- `/snapshot`: p95 < 500ms (هدف)
- `/hot`: p95 < 100ms (هدف)
- `/score`: p95 < 200ms (هدف)
- `/dca/plan`: p95 < 100ms (هدف)
- Error rate < 1% (هدف)

---

## ⚙️ Environment Variables

```bash
# Backend
GOLD_DESK_ENABLED=true
GOLD_DESK_SNAPSHOT_INTERVAL=300    # seconds
GOLD_DESK_ALERT_INTERVAL=120       # seconds

# Telegram (optional)
GOLD_TELEGRAM_ENABLED=false
GOLD_TELEGRAM_BOT_TOKEN=
GOLD_TELEGRAM_CHAT_ID=

# API Token Salt — اجباری، بدون پیش‌فرض (I3)
# کد هنوز پیش‌فرض commit شده دارد (api_token.py:28)؛ در docker-compose با `:?`
# اجباری شده تا آن پیش‌فرض در مسیر container هرگز استفاده نشود.
# ⚠️ مقدار تازه = token های قبلی باطل می‌شوند (بازصدور از /gold/tokens).
GOLD_API_TOKEN_SALT=
```

---

## 🎯 User Guide

### شروع (Onboarding)
1. صفحه `/gold` را باز کنید
2. منتظر اولین snapshot بمانید (۱-۲ دقیقه)
3. Score فعلی + حباب سکه + صندوق‌ها را ببینید

### روزانه
- **صبح**: چک کردن score + Alerts
- **هر ۱ ساعت**: صفحه `/gold` را refresh
- **عصر**: بررسی تغییرات قیمت (Live Signals banner)
- **شب**: Portfolio P&L + معاملات روز

### تصمیم‌گیری خرید
> ⚠️ (F3) این بخش قبلاً «سبز = خرید قوی» می‌گفت. آن ادعا حذف شد: این ابزار توصیهٔ
> مالی نیست و هیچ رنگی دستور خرید نیست.

1. Score فعلی → سبز = شرایط مناسب‌تر، زرد = احتیاط، قرمز = صبر، **`NO_DATA` = داده
   ناکافی** (نه سیگنال خرید، نه فروش)
2. حباب سکه → < 8% خوب، 8-22% احتیاط، > 22% حباب شدید
3. DCA plan → پله ۱ در score سبز، پله ۲ در اصلاح
4. Stop-Loss: -8% / Take-Profit: +25%
5. `data_coverage_pct` را ببینید: پوشش پایین یعنی عدد بالا پایهٔ سستی دارد

### Telegram Setup
1. به @BotFather پیام بدید → `/newbot`
2. Token و chat_id را در `.env` بگذارید
3. `POST /alerts/seed` → قوانین پیش‌فرض فعال می‌شود
4. `POST /telegram/test` → تست ارسال

### PWA Install
1. Chrome/Edge: باز کنید `/gold`
2. آیکون ⊕ در address bar → Install
3. iOS Safari: Share → Add to Home Screen

---

## 🛠️ Troubleshooting

### Snapshot empty
- BrsApi قطع → TGJU fallback فعال می‌شود (quality_flag=fallback)
- `GET /api/gold/health` → چک کنید

### Score همیشه 0
- داده BrsApi نیست → `quality_flag=fallback`
- Hard stop فعال → چک hard_stop_reason

### Telegram کار نمی‌کند
- `GOLD_TELEGRAM_ENABLED=true` و Token معتبر
- `POST /telegram/test` → خطا
- چک chat_id (نه @username)

### PWA نصب نمی‌شود
- HTTPS لازم است (localhost مجازه)
- `manifest.json` در `/` موجود

---

## 📚 منابع بیشتر

- **سند مرجع**: [GapGPT Gold Analysis](https://gapgpt.app) — تمام فرمول‌ها از اینجا
- **Backend module**: `src/gold_desk/README.md`
- **Test coverage**: `tests/gold_desk/`

---

## ⚖️ هشدار

این ابزار صرفاً برای **تحلیل شخصی** است. سیگنال خرید/فروش مالی محسوب نمی‌شود.
تصمیم سرمایه‌گذاری باید با مشاور مالی تأیید شود.
بازار طلا ذاتاً غیرقابل پیش‌بینی است — هیچ الگوریتمی سود تضمینی نمی‌دهد.

---

## 📝 مجوز

**MIT** — مطابق فایل `LICENSE` (که README هم به آن ارجاع می‌دهد). نسخهٔ قبل این
سند «شخصی — استفاده داخلی» می‌گفت و با `LICENSE` در تناقض بود؛ رفع شد.

> ⚠️ این رفعِ تناقض **متنی** است، نه یک تصمیم حقوقی: فایل `LICENSE` از قبل MIT
> بوده. اگر قصد صاحب محصول واقعاً «فقط استفادهٔ داخلی» است، باید `LICENSE`
> عوض شود نه این سند — به‌عنوان سؤال باز در
> `docs/fixes/frontend_infra_CHANGELOG.md` ثبت شده است.

---

## 🔒 محدودیت: تک‌کاربره

این محصول تک‌کاربره است و جدول‌های طلا `user_id` ندارند (تصمیم عمدی). چک‌لیست
«قبل از کاربر دوم» و دیکشنری داده در `docs/golddesk_single_user_limit.md` است.
