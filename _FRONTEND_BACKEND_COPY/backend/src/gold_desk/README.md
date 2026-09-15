# GoldDesk — تحلیل و پایش شخصی طلای ایران

ابزار شخصی برای تحلیل و تصمیم‌گیری داده‌محور در بازار طلا، سکه، ارز و صندوق‌های طلا.

## معماری

```
Backend (FastAPI)
├── src/gold_desk/
│   ├── constants.py        # ثابت‌ها (عیار، وزن، آستانه‌ها، fee)
│   ├── models.py           # 5 جدول SQLAlchemy
│   ├── schemas.py          # Pydantic models
│   ├── pricer.py           # fair_value (طلا + سکه)
│   ├── bubbler.py          # حباب + implied USD
│   ├── parity.py           # شکاف درهم
│   ├── signal_engine.py    # RSI/EMA (numpy)
│   ├── nav_checker.py      # P/NAV صندوق‌ها
│   ├── scorer.py           # امتیازدهی 6 کامپوننت
│   ├── dca_planner.py      # DCA با fee
│   ├── hard_stops.py       # شرایط بحران
│   ├── secondary_source.py # TGJU fallback
│   ├── snapshot_service.py # ارکستراسیون + self-check
│   ├── alert_engine.py     # قوانین + dedup
│   ├── telegram_bot.py     # httpx مستقیم
│   ├── backtest.py         # 90-day walk-forward
│   └── api.py              # FastAPI router
├── brsapi/jobs/gold_desk_jobs.py   # 4 scheduler job
└── tests/gold_desk/                # 51 unit test

Frontend (Next.js 15 + TypeScript)
├── app/gold/
│   ├── layout.tsx
│   ├── dashboard/page.tsx          # KPI + Score
│   ├── coins/page.tsx              # حباب + نمودار
│   ├── funds/page.tsx              # P/NAV table
│   ├── technical/page.tsx          # RSI + قیمت
│   ├── dca/page.tsx                # Calculator
│   ├── alerts/page.tsx             # قوانین + رویدادها
│   └── settings/page.tsx           # Health + Telegram + Watchlist
├── components/gold/                # 12 component
├── lib/goldApi.ts                  # Typed client
└── types/gold.ts                   # Types
```

## نصب و راه‌اندازی

### 1. Migration
```bash
alembic upgrade head
```

### 2. متغیرهای محیطی
```bash
# اختیاری - برای اعلان تلگرام
GOLD_TELEGRAM_ENABLED=true
GOLD_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
GOLD_TELEGRAM_CHAT_ID=123456789
```

### 3. Backend
```bash
uvicorn apps.api.main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend && pnpm dev
```

### 5. تست‌ها
```bash
pytest tests/gold_desk/ -v
# 51 passed
```

## API Endpoints (prefix: /api/gold)

| Method | Path | توضیح |
|---|---|---|
| GET | `/snapshot` | snapshot کامل + score |
| GET | `/score` | فقط امتیاز فعلی |
| GET | `/history/score?days=7` | تاریخچه امتیاز |
| GET | `/history/snapshot?symbol=&days=` | تاریخچه snapshot |
| POST | `/dca/plan` | محاسبه DCA |
| GET | `/alerts/rules` | لیست قوانین |
| POST | `/alerts/rules` | ساخت قانون |
| PUT | `/alerts/rules/{id}` | ویرایش |
| DELETE | `/alerts/rules/{id}` | حذف |
| GET | `/alerts/events?days=&unread_only=` | رویدادها |
| POST | `/alerts/{id}/ack` | خوانده‌شده |
| POST | `/alerts/seed` | درج قوانین پیش‌فرض |
| GET | `/watchlist` | لیست شخصی |
| PUT | `/watchlist` | جایگزینی |
| POST | `/telegram/test` | تست ارسال |
| GET | `/telegram/status` | وضعیت |
| GET | `/health` | سلامت |
| GET | `/backtest?days=90` | بک‌تست |

## Scoring Matrix (6 کامپوننت، جمع ۱۰۰)

| Component | Max | منبع |
|---|---|---|
| bubble (حباب سکه) | 20 | bubbler |
| nav (P/NAV صندوق) | 18 | nav_checker |
| tsetmc (BPR + Inflow) | 18 | HistoricalRealLegalModel |
| technical (XAU RSI) | 15 | signal_engine |
| parity (AED gap) | 15 | brsapi_currency_prices |
| fund_flow (NAV 7d) | 14 | brsapi_ime_funds historical |

**Decision Bands:** GREEN ≥ 80 | YELLOW ≥ 55 | RED < 55

**Hard Stop:** اگر فعال → RED مطلق (بدون توجه به امتیاز)

## Scheduler Jobs

| نام | فرکانس | عملکرد |
|---|---|---|
| `gold_snapshot` | 5 min | snapshot + persist + cache |
| `gold_score_persist` | 5 min | ذخیره امتیاز |
| `gold_alert_evaluate` | 2 min | بررسی قوانین + dispatch |
| `gold_daily_history` | 21:00 daily | backfill |

## Self-Check

در `snapshot_service.build_snapshot`:
```python
assert 1000 < xau_usd < 10000
assert 10_000 < usd_irt < 10_000_000
assert -10 < aed_gap_pct < 10
assert -50 < bubble_pct < 100
assert 0 <= score.total <= 100
assert sum(components) == score.total
```

## Fallback

اگر BrsApi قطع → TGJU scraper به‌عنوان منبع ثانویه (`secondary_source.py`).
`quality_flag = "fallback"` در snapshot.

## منابع

- اونس جهانی: BrsApi `/Market/Gold_Currency_Pro.php`
- دلار/درهم: BrsApi `/Market/Gold_Currency.php`
- طلا/سکه: BrsApi `/Market/Gold_Currency.php`
- NAV صندوق: BrsApi `/Market/NAV.php`
- BPR/Inflow: BrsApi `/Market/HistoryRealLegal.php`

## هشدار

این ابزار صرفاً تحلیل شخصی است. سیگنال خرید/فروش مالی محسوب نمی‌شود.
تصمیم سرمایه‌گذاری با مشاور مالی تأیید شود.
