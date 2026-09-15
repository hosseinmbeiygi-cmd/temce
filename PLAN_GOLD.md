# 🥇 GoldDesk — تحلیل و پایش شخصی طلای ایران

ابزار شخصی برای تحلیل داده‌محور بازار طلا، سکه، ارز و صندوق‌های طلا. شامل scoring ۶ کامپوننت، DCA، options (Black-76)، portfolio tracker، chatbot، real-time signals و PWA.

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
- **تصمیم** در ۳ band: سبز (≥۸۰)، زرد (۵۵-۷۹)، قرمز (<۵۵)
- **Hard stop** خودکار (TSE crash > 5%، DXY spike > 3%، USD spike > 5%)
- **طلا و سکه**: bubble % + دلار ضمنی
- **صندوق‌های طلا**: P/NAV + BPR + Inflow
- **تکنیکال اونس**: نمودار SVG با تغییر بازه
- **اختیار Black-76**: ATM + Protective Collar
- **DCA inline**: calculator ۳ risk profile

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

### Patterns Detection (`api/gold/patterns`)
- `mean_reversion` (bubble > 20% → بازگشت؟)
- `trend_continuation` (7+ روز مثبت)
- `spike_crash` (جهش > 5% → اصلاح؟)
- `vol_regime` (نوسان بالا = ریسک)

### Hot Path (`/api/gold/hot`)
- snapshot کم‌حجم (latency < 50ms)
- برای polling هر ۱۰ ثانیه
- شامل: refs + score + signal coin_emami + ۳ صندوق برتر

### API Tokens (`/gold/tokens`)
- scopes: read / write / admin
- OpenAPI docs در `/api/gold/docs/endpoints`
- امکان اتصال Google Sheets، ربات تلگرام، اپ موبایل

### Backtest (`/api/gold/backtest`)
- سیگنال ساده: bubble threshold → forward 30d return
- استراتژی DCA: hit rate, alpha, Sharpe, max drawdown

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
│              Frontend (Next.js 15 + TypeScript)              │
│  • 8 صفحه  • 15 component  • 3 theme  • mobile responsive │
│  • PWA (manifest + SW + offline + install)                  │
└────────────────────┬────────────────────────────────────────┘
                     │ /api/gold/* (FastAPI)
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

### Backend (37 فایل)
```
src/gold_desk/
├── constants.py            # ثابت‌ها (عیار، وزن سکه، thresholds, fees)
├── models.py               # 5 جدول SQLAlchemy
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
├── api.py                  # 28+ FastAPI endpoints
└── __init__.py

brsapi/jobs/gold_desk_jobs.py    # 4 scheduler jobs
```

### Frontend (21 فایل)
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

## 🔌 API Endpoints (28+)

همه prefix `/api/gold`:

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
| GET | `/macro` | read | Macro events |
| POST | `/macro/scrape` | read | Scrape CBI |
| WS | `/ws` | read | Live WebSocket |

---

## 🧪 Tests

```bash
pytest tests/gold_desk/ -v
# 117 passed in 2.45s
```

پوشش:
- `constants.py` — ثابت‌ها، thresholds
- `pricer.py` + `bubbler.py` — fair_value، حباب، implied USD
- `scorer.py` — 6 کامپوننت + hard stop
- `dca_planner.py` — 3 risk profile + fee
- `black76.py` — pricing + Greeks + parity
- `backtest_runner.py` — DCA simulation
- `portfolio.py` — P&L
- `chat.py` — fallback heuristic
- `live_signals.py` — spike detection
- `pattern_detector.py` — mean_reversion, trend, spike, vol
- `macro_news.py` — impact estimation

---

## 🐳 Deployment

### Docker
```bash
docker build -f Dockerfile.golddesk -t golddesk-worker .
docker run --env-file .env golddesk-worker
```

### Healthcheck
```bash
curl http://localhost:8000/api/gold/health
# 200: سالم
# 503: db/redis قطع
```

### Nginx
snippet در `nginx-golddesk.conf`:
- `/api/gold/*` → backend:8000
- `/api/gold/ws` → upgrade WebSocket
- `/gold/*` → frontend:3000

### Prometheus
scrape config در `monitoring/golddesk-prometheus.yml`:
- `/api/gold/metrics` هر ۳۰s

---

## 📈 Load Testing

```bash
pip install locust
locust -f tests/load/locustfile.py --host http://localhost:8000
```

SLO targets:
- `/snapshot`: p95 < 500ms
- `/hot`: p95 < 100ms
- `/score`: p95 < 200ms
- `/dca/plan`: p95 < 100ms
- Error rate < 1%

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

# API Token Salt
GOLD_API_TOKEN_SALT=change-me-in-prod
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
1. Score فعلی → سبز = خرید قوی، زرد = محتاط، قرمز = صبر
2. حباب سکه → < 8% خوب، 8-22% احتیاط، > 22% حباب شدید
3. DCA plan → پله ۱ در score سبز، پله ۲ در اصلاح
4. Stop-Loss: -8% / Take-Profit: +25%

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

شخصی — استفاده داخلی.
