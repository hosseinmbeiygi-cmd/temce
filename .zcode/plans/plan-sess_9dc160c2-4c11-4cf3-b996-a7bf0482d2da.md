# Temce GoldDesk v2 — پلن نهایی ارتقا یافته (با ۱۰ اصلاح + تست + سند کامل)

## خلاصه ۱۰ اصلاح نسبت به v1

| # | ایراد v1 | اصلاح v2 |
|---|---|---|
| 1 | Macro score = placeholder ثابت ۷ | حذف. فقط ۶ کامپوننت واقعی (جمع ۱۰۰) |
| 2 | Fund_flow score = placeholder | جایگزین با مقایسه NAV ۷روزه صندوق با میانگین (15→12 weight) |
| 3 | بدون backtest | اضافه شد: `backtest.py` با اجرای ۹۰ روز + گزارش hit rate |
| 4 | تک منبع (BrsApi) | اضافه fallback: `secondary_source.py` (TGJU scraper) + health check |
| 5 | بدون hard-stop | اضافه شد: `hard_stops.py` (جنگ/تحریم/سقوط بورس >5% = RED مطلق) |
| 6 | Alert spam risk | Rate limit per-rule: max 1 پیام/ساعت + batch digest |
| 7 | Telegram chat_id hardcode | Per-rule chat_id در DB |
| 8 | DCA بدون مالیات/کارمزد | محاسبه دقیق fee در ۵ ابزار (ETF/شمش/آب‌شده/سکه/زینتی) |
| 9 | timezone شمسی edge cases | استفاده کامل از `jdatetime` + helper برای تعطیلی رسمی |
| 10 | Score بدون explanation | breakdown کاملاً قابل خواندن با دلیل هر امتیاز |

## ساختار فایل‌ها (۳۱ فایل جدید/تغییر)

### Backend (Python) — `src/gold_desk/` (۱۸ فایل)
```
constants.py              # ثابت‌ها + thresholds
models.py                 # 5 جدول SQLAlchemy
schemas.py                # Pydantic models
pricer.py                 # fair_value هر asset
bubbler.py                # حباب + implied USD
parity.py                 # AED gap
nav_checker.py            # P/NAV صندوق‌ها
signal_engine.py          # RSI/EMA (extend forecasting)
scorer.py                 # 6-component scoring
dca_planner.py            # 3 risk profile + fee
hard_stops.py             # event-based hard stop
snapshot_service.py       # orchestration + self-check
secondary_source.py       # TGJU fallback (scraper)
alert_engine.py           # rules + dedup + batch
telegram_bot.py           # httpx مستقیم
backtest.py               # 90-day walk-forward
api.py                    # FastAPI router
__init__.py
```

### BrsApi Integration (۱ فایل جدید)
```
brsapi/jobs/gold_desk_jobs.py    # 4 scheduler job
```

### Migration (۱ فایل)
```
alembic/versions/xxxx_gold_desk.py
```

### Frontend (TypeScript) — ۱۲ فایل
```
app/gold/layout.tsx
app/gold/dashboard/page.tsx
app/gold/coins/page.tsx
app/gold/funds/page.tsx
app/gold/technical/page.tsx
app/gold/alerts/page.tsx
app/gold/dca/page.tsx
app/gold/settings/page.tsx
components/gold/{GoldKPICard,BubbleGauge,ScoreGauge,CoinBubbleTable,FundNAVTable,TimeSeriesChart,AlertRuleForm,AlertEventList,DCACalculator,ParityBadge,RSIIndicator,ScoreBreakdown}.tsx (12 component)
lib/goldApi.ts
types/gold.ts
```

### Config (۲ فایل)
```
.env.example (GOLD_TELEGRAM_* + GOLD_DESK_*)
frontend/src/components/layout/AppLayout.tsx (modify: add Gold nav)
```

### Tests (۴ فایل — یاد نره!)
```
tests/gold_desk/test_constants.py
tests/gold_desk/test_scorer.py
tests/gold_desk/test_pricer_bubbler.py
tests/gold_desk/test_dca_planner.py
```

## ۶ Component امتیازدهی (100 امتیاز)
| Component | Max | منبع داده |
|---|---|---|
| bubble (سکه امامی) | 20 | pricer + bubbler |
| nav (P/NAV صندوق عیار) | 18 | nav_checker |
| tsetmc (BPR + inflow) | 18 | brsapi_historical_real_legal |
| technical (XAU RSI) | 15 | signal_engine + brsapi_gold_coin_history |
| parity (AED gap) | 15 | brsapi_currency_prices |
| fund_flow (NAV 7d) | 14 | brsapi_ime_funds historical |

## ۴ Scheduler Job
- `gold_snapshot` — هر 5 دقیقه
- `gold_score_persist` — هر 5 دقیقه  
- `gold_alert_evaluate` — هر 2 دقیقه
- `gold_daily_history` — هر شب 21:00

## ۸ گروه API Endpoint
1. `GET /api/gold/snapshot` — KPIs + score (FE polls هر 60s)
2. `GET /api/gold/history/{bubble|price|score}?symbol=&days=` — time-series
3. `GET /api/gold/score` — فقط امتیاز
4. `POST /api/gold/dca/plan` — محاسبه پله‌ای + fee
5. `GET/POST/PUT/DELETE /api/gold/alerts/rules` — CRUD قوانین
6. `GET /api/gold/alerts/events?days=&unread=` — تاریخچه
7. `POST /api/gold/alerts/{id}/ack` — mark read
8. `GET /api/gold/health` + `POST /api/gold/telegram/test` + `GET/PUT /api/gold/watchlist`

## Frontend — ۷ صفحه + ۱۲ کامپوننت
- `/gold/dashboard` — ScoreGauge + CoinBubbleTable + FundNAVTable + ParityBadge
- `/gold/coins` — TimeSeriesChart (bubble %)
- `/gold/funds` — FundNAVTable با sparkline
- `/gold/technical` — TimeSeriesChart (price) + RSIIndicator
- `/gold/alerts` — AlertRuleForm + AlertEventList
- `/gold/dca` — DCACalculator
- `/gold/settings` — Telegram chat_id + watchlist

## Self-check در snapshot_service
```python
assert xau_usd > 100
assert 1000 < usd_irt < 5_000_000
assert -10 < aed_gap_pct < 10
assert all(-50 < c["bubble_pct"] < 100 for c in {**gold, **coins}.values())
assert 0 <= score["total"] <= 100
assert sum(score["components"].values()) == score["total"]
```

## Test Coverage
- test_constants: thresholds، ثابت‌های متالورژی، وزن سکه‌ها
- test_scorer: 8 سناریو (سبز، زرد، قرمز، edge cases، 6 component isolated)
- test_pricer_bubbler: 9 symbol (gold_18k/24k/1g/melted + 5 coin) با داده fixture
- test_dca_planner: 3 risk profile + fee calculation

## وابستگی — هیچ پکیج جدید
- httpx (Telegram) ✓ موجود
- sqlalchemy[asyncio] ✓
- redis ✓
- apscheduler ✓
- jdatetime ✓
- pandas/numpy ✓
- React Query, Tailwind, lucide-react ✓
- recharts (اگر نبود → SVG inline)

## مراحل اجرا
1. Migration + constants + config (نیم روز)
2. pricer + bubbler + parity + self-check (1 روز)
3. nav_checker + signal_engine + scorer (1 روز)
4. snapshot_service + scheduler job (نیم روز)
5. API endpoints (نیم روز)
6. **Tests** (نیم روز — اول با scorer شروع)
7. Frontend pages 1-3 (2 روز)
8. Frontend pages 4-7 + components باقی (2 روز)
9. Alert engine + Telegram (1 روز)
10. DCA + backtest (1 روز)
11. Polish + manual E2E (1 روز)

**جمع: ~10-12 روز کاری**

## اولویت تست
تست‌ها قبل از UI نوشته می‌شن (TDD برای scorer و pricer). UI با داده واقعی (snapshot endpoint) تست می‌شه، نه mock.

## تأیید نهایی
این پلن جایگزین v1 می‌شه. شروع به کدنویسی.