# گزارش آدیت کامل — مخزن temce

**تاریخ:** ۱۴۰۳/۰۷/۰۴  
**بررسی‌شده توسط:** Software Factory Agent  
**شاخه:** main  
**تعداد کل یافته‌ها:** ۱۳۰ (۱۴ بحرانی، ۶۴ بالا، ۵۲ متوسط/پایین)

---

## خلاصه اجرایی

| زیرسیستم | بحرانی | بالا | متوسط/پایین | جمع |
|---|:---:|:---:|:---:|---:|
| Backtesting (PnL، FIFO، fees، slippage) | ۴ | ۱۰ | ۸ | **۲۲** |
| Services / Queue / ML pipeline | ۳ | ۸ | ۴ | **۱۵** |
| Risk / Optimization | ۲ | ۶ | ۴ | **۱۲** |
| Data Pipeline / TSETMC / CODAL | ۲ | ۱۰ | ۷ | **۱۹** |
| Smart Money / Quantitative | ۰ | ۶ | ۴ | **۱۰** |
| API / Auth / WebSocket / Frontend | ۱ | ۵ | ۷ | **۱۳** |
| Security (.env، CORS، secrets) | ۲ | ۳ | ۲ | **۷** |
| Repositories / Domain / Schemas | ۰ | ۲ | ۱۰ | **۱۲** |
| Tests / CI-CD / Docker / Dependencies | ۰ | ۱۴ | ۶ | **۲۰** |
| **جمع کل** | **۱۴** | **۶۴** | **۵۲** | **۱۳۰** |

---

## فاز ۰: معماری و فهرست فایل‌ها

### ساختار اصلی مخزن

```
temce/
├── .agents/skills/security-audit/
├── .github/workflows/ (ci.yml, ci-pr.yml, decision-engine.yml, release.yml, secrets-scan.yml)
├── BrsApi_Forecasting/ (FastAPI مستقل پیش‌بینی)
│   ├── api/ (routers, websocket, models)
│   ├── contracts/
│   ├── core/ (config, redis_client)
│   └── services/ (forecasting, query, symbol_registry)
├── backtesting/ (موتور بک‌تست چندبازاری)
│   ├── engine/ (backtest_engine, clock, position_manager, event_loop)
│   ├── execution/ (execution_policy, fill_simulator, queue_simulation)
│   ├── market/ (rule_engine, policies)
│   ├── metrics/ (performance, trade_metrics, return_metrics)
│   ├── risk/, portfolio/, capital/, optimization/
│   └── commission.py, costs.py, corporate_actions.py
├── services/ (منطق تجاری اصلی)
│   ├── accuracy_outcome_queue.py
│   ├── signal_accuracy_tracker.py
│   ├── auto_retrain_pipeline.py
│   ├── backtest_service.py
│   ├── ml_signal_connector.py
│   └── backtest/, broker/, ml/, quantitative/, smart_money/
├── ml/ (مدل‌های یادگیری ماشین)
├── iran_market_data/ (TSETMC، CODAL)
├── providers/ (HTTP client، rate policy، parsers)
├── jobs/ (dispatcher، locking، retry)
├── orchestration/ (runners، recovery، checkpoints)
├── apps/api/endpoints/ (market, trades, forecast)
├── repositories/, domain/, schemas/
├── core/ (database, session)
├── frontend/ (Next.js)
└── migrations/versions/ (Alembic 0001-0018)
```

### نقشه زیرسیستم‌ها

| زیرسیستم | پوشه‌ها | سطح ریسک |
|---|---|---|
| بک‌تست | backtesting/ | **بحرانی** |
| منطق مالی | backtesting/costs/, engine/commission.py | **بحرانی** |
| سیگنال و دقت | services/signal_*.py, accuracy_outcome_queue.py | **بالا** |
| ML | ml/, services/ml/, auto_retrain_pipeline.py | **بالا** |
| DB | core/database.py, migrations/ | **بالا** |
| API | apps/api/, BrsApi_Forecasting/api/ | **بالا** |
| داده ایران | iran_market_data/, providers/, codal_* | **بالا** |
| قوانین بازار | backtesting/market/ | **متوسط** |
| Frontend | frontend/ | **متوسط** |

---

## فاز ۱: Red Flags (اسکن سطحی)

| یافته | فایل | چرا ریسک‌زا | شدت |
|---|---|---|---|
| `SECRET_KEY=change-me-in-production` | `.env.example` | جعل JWT، دسترسی غیرمجاز | **بحرانی** |
| `ENCRYPTION_KEY=change-me-in-production` | `.env.example` | رمزگشایی داده‌های حساس | **بحرانی** |
| `DEBUG=true` | `.env.example` | افشای اطلاعات داخلی | **بالا** |
| `CORS_ORIGINS=["*"]` + `allow_credentials=True` | `.env.example` | سطح حمله CSRF | **بالا** |
| `DB_PASSWORD=password` | `.env.example` | دسترسی به دیتابیس | **بالا** |

---

## فاز ۲A: آدیت Backtesting

### Issue Register

| شناسه | دسته | فایل/تابع | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| BT-001 | PnL | engine/position_manager.py | **بحرانی** | میانگین موزون به‌جای FIFO. سود/زیان نادرست محاسبه می‌شود | پیاده‌سازی lot-based FIFO با deque |
| BT-004 | مالیات | backtesting/costs/iran_costs.py | **بحرانی** | مالیات فروش ۰.۵٪ است؛ باید ۱.۵٪ باشد | خواندن نرخ از تنظیمات بازار |
| BT-009 | Look-ahead | engine/backtest_engine.py | **بحرانی** | سیگنال و اجرا روی همان کندل. بک‌تست نادرست است | اجرای سفارش از کندل بعدی |
| BT-013 | Timezone | engine/clock.py | **بحرانی** | datetime naive در بخش‌های اصلی | timezone-aware با ZoneInfo("Asia/Tehran") |
| BT-002 | PnL | metrics/trade_metrics.py | **بالا** | ناسازگاری FIFO در metrics با میانگین موزون در portfolio | یک موتور lot accounting مشترک |
| BT-003 | کارمزد | backtesting/costs.py | **بالا** | نرخ ۰.۳۵٪ یکسان برای خرید و فروش | IranTradingCostSchedule سمت‌محور |
| BT-005 | کارمزد | engine/commission.py | **بالا** | نرخ مشترک خرید/فروش. VAT مدل نشده | buy_commission_pct + sell_commission_pct + vat_pct + sell_tax_pct |
| BT-007 | لغزش | execution_simulator_wrapper.py | **بالا** | لغزش ثابت ۱۰bps. برای بازار کم‌نقدشونده ایران غیرواقعی است | مدل پویا بر اساس حجم، spread و نقدشوندگی |
| BT-008 | Look-ahead | execution/execution_policy.py | **بالا** | fill روی قیمت close همان کندل | استفاده از next open یا ask/bid مشاهده‌شده |
| BT-010 | Look-ahead | execution_policy.py | **بالا** | market order با قیمت close | next open یا قیمت tick بعدی |
| BT-011 | Corporate Action | corporate_actions.py | **بالا** | adjustment بدون تاریخ مؤثر و as-of | اعمال فقط از تاریخ مؤثر |
| BT-014 | Timezone | engine/data_layer.py | **بالا** | فیلتر datetime بدون normalize timezone | normalize با ZoneInfo |
| BT-015 | Corporate Action | engine/portfolio.py | **بالا** | lotهای تاریخی بعد از corporate action قابل بازسازی نیستند | نگهداری lot history |
| BT-016 | Cash | engine/portfolio.py | **بالا** | breakdown هزینه در FillEvent ناقص است | FillEvent با commission، vat، clearing، tax، total |
| BT-017 | نقدشوندگی | execution/partial_fill.py | **بالا** | fill با قیمت ثابت برای سفارش بزرگ | تقسیم به چند fill در سطوح مختلف قیمت |
| BT-006 | مالیات | engine/commission.py | **بالا** | نرخ مالیات legacy با canonical متفاوت است | یک منبع حقیقت برای نرخ‌ها |
| BT-012 | Off-by-one | engine/event_loop.py | **متوسط** | clock یک روز قبل از پردازش bar پیش می‌رود | timestamp bar مستقیم به clock |
| BT-018 | تصادفی | execution/fill_simulator.py | **متوسط** | random بدون seed | random.Random(seed) یا RNG تزریق‌شده |
| BT-019 | صف سفارش | execution/queue_simulation.py | **بالا** | مدل صف ساده‌شده | استفاده از tick trade و اولویت قیمتی-زمانی |
| BT-020 | Hardcoded | backtesting/market/policies.py | **متوسط** | ساعت‌ها و tick size در کد ثابت | MarketRuleSet نسخه‌دار از فایل/DB |
| BT-021 | Metrics | metrics/performance.py | **متوسط** | سالانه‌سازی با عدد ثابت ۲۵۲ | از تقویم بازار و timeframe ورودی |
| BT-022 | PnL | metrics/trade_metrics.py | **متوسط** | معاملات باز وارد round-trip metrics می‌شوند | جداسازی معاملات باز از بسته |

### پچ نمونه: BT-001 (FIFO)

```python
# قبل
pnl = (fill.price - pos.avg_price) * fill.quantity

# بعد
@dataclass
class Lot:
    quantity: int
    price: float

def apply_sell(self, instrument_id: str, quantity: int, price: float) -> float:
    lots = self._lots_for(instrument_id)  # deque[Lot]
    remaining, pnl = quantity, 0.0
    while remaining > 0:
        lot = lots[0]  # FIFO
        matched = min(remaining, lot.quantity)
        pnl += (price - lot.price) * matched
        lot.quantity -= matched
        remaining -= matched
        if lot.quantity == 0:
            lots.popleft()
    return pnl
```

### پچ نمونه: BT-003/004/005 (IranTradingCostSchedule)

```python
@dataclass(frozen=True)
class IranTradingCostSchedule:
    buy_commission_pct: float = 0.00462   # ۰.۴۶۲٪
    sell_commission_pct: float = 0.00553  # ۰.۵۵۳٪
    vat_pct: float = 0.0
    sell_tax_pct: float = 0.015           # ۱.۵٪ مالیات فروش
    clearing_fee_pct: float = 0.0

    def compute(self, side: str, price: float, quantity: int) -> dict[str, float]:
        principal = price * quantity
        is_sell = side.lower() == "sell"
        commission_pct = self.sell_commission_pct if is_sell else self.buy_commission_pct
        commission = principal * commission_pct
        vat = commission * self.vat_pct
        clearing = principal * self.clearing_fee_pct
        tax = principal * self.sell_tax_pct if is_sell else 0.0
        return {
            "commission": commission, "vat": vat,
            "clearing": clearing, "tax": tax,
            "total": commission + vat + clearing + tax,
        }
```

---

## فاز ۲C-E: Services، DB و ML

### Issue Register

| شناسه | دسته | فایل/تابع | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| SRV-001 | صف | accuracy_outcome_queue.py | **بحرانی** | صف فقط in-memory. با restart outcomeها از بین می‌روند | Redis Streams یا outbox با ACK و DLQ |
| ML-004 | ML | auto_retrain_pipeline.py | **بحرانی** | new_accuracy = min(current+0.03, 0.75). ارزیابی واقعی نیست | holdout زمانی و ارزیابی واقعی |
| ML-001 | Data Leakage | ml/dataset_builder.py | **بحرانی** | normalize روی کل dataset قبل از split | scaler فقط روی train fit شود |
| SRV-007 | Fail-open | ml_signal_connector.py | **بالا** | در نبود مدل، heuristic سیگنال معاملاتی صادر می‌کند | fail-closed در production |
| SRV-009 | Backtest | backtest_service.py | **بالا** | metric با contextlib.suppress پوشانده شده. نتیجه ناقص = completed | وضعیت partial و ممنوع از promotion |
| ML-002 | Cross-validation | ml/evaluation/cross_validation.py | **بالا** | K-Fold عادی برای داده زمانی | TimeSeriesSplit با gap/embargo |
| ML-007 | Artifact | ml/model_loader.py | **بالا** | pickle.load. اجرای کد دلخواه در صورت artifact مخرب | ONNX یا safetensors با امضا |
| ML-006 | Cache | ml/model_loader.py | **بالا** | cache بدون version. worker مدل قدیمی سرو می‌کند | cache key با model_version + artifact_hash |
| DB-002 | Isolation | core/database.py | **بالا** | isolation level صریح نیست | تعیین صریح برای PostgreSQL |
| DB-005 | Index | migration 0007 | **بالا** | composite index برای accuracy queries مشخص نیست | (market, outcome_set_at, direction) |
| ML-005 | Bootstrap | auto_retrain_pipeline.py | **بالا** | آموزش روی داده bootstrap مصنوعی در production | fail در نبود داده کافی |
| SRV-002 | Drop | accuracy_outcome_queue.py | **بالا** | حذف خاموش قدیمی‌ترین outcome | backpressure یا DLQ |
| SRV-005 | Idempotency | signal_accuracy_tracker.py | **بالا** | ثبت تکراری outcome در retry | unique constraint روی signal_id |
| ML-003 | Reproducibility | services/adaptive_engine.py | **بالا** | seed مرکزی ثبت نمی‌شود | seed از run_id، ثبت برای Python+NumPy+framework |
| DB-001 | Session | core/database.py | **متوسط** | commit برای read-only session | session جداگانه برای read/write |
| DB-003 | Transaction | get_session | **متوسط** | پردازش سنگین داخل session | داده در short read-only transaction، پردازش خارج |
| DB-004 | Migration | migrations/versions | **متوسط** | زنجیره revision بدون بررسی خودکار در CI | alembic upgrade head در CI |
| ML-008 | Point-in-time | signal_feature_pipeline.py | **متوسط** | داده‌های خارجی بدون کنترل as-of | available_at و as_of اجباری |
| ML-009 | Ensemble | ml_signal_connector.py | **متوسط** | وزن‌های ثابت مدل. مدل خراب همچنان اثر دارد | وزن‌ها version شوند، مدل نامعتبر حذف شود |
| SRV-003 | Queue | AccuracyOutcomeQueue | **بالا** | بدون coordination بین workerها | Redis Streams با consumer group |
| SRV-004 | DLQ | AccuracyOutcomeQueue.flush | **متوسط** | خطای دائمی = retry loop | سقف retry + DLQ |
| SRV-006 | Outcome | SignalAccuracyTracker | **بالا** | outcome قبل از پایان horizon ثبت می‌شود | prediction_at و evaluation_due_at |
| SRV-008 | Calibration | calibration_loop.py | **متوسط** | calibration بدون فیلتر نسخه مدل | فیلتر model_version، تاریخ، horizon و sample size |
| SRV-010 | Concurrency | BacktestService | **متوسط** | cache و lock in-memory. در چند process | وضعیت run در DB با idempotency key |

---

## فاز ۲F-G: API، قوانین بازار و Frontend

### Issue Register

| شناسه | دسته | فایل/تابع | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| API-002 | Idempotency | precompute_router.py | **بحرانی** | check/start غیراتمی. دو job موازی ممکن است | Redis SET NX EX |
| API-001 | CORS | BrsApi_Forecasting/main.py | **بالا** | allow_origins=["*"] + allow_credentials=True | originهای مجاز از config |
| API-003 | WebSocket | precompute_router.py | **بالا** | WebSocket بدون احراز هویت | token در handshake |
| API-008 | Auth bypass | apps/api/auth.py | **بالا** | احراز هویت فقط در production | حذف bypass، fail-closed همیشه |
| MKT-001 | Timezone | backtesting/market/rule_engine.py | **بالا** | session بدون تبدیل به Asia/Tehran | ZoneInfo("Asia/Tehran") |
| MKT-002 | Halted | rule_engine.py | **بالا** | سفارش روی نماد متوقف validate می‌شود | بررسی instrument status |
| API-007 | قرارداد | frontend/src/lib/api.ts | **متوسط** | پاسخ API بدون validation schema | Zod یا validator زمان اجرا |
| API-005 | Pagination | apps/api/endpoints/market.py | **متوسط** | فقط limit. در رشد registry، پاسخ سنگین | pagination واقعی در query |
| API-006 | Pagination | apps/api/endpoints/trades.py | **متوسط** | total از slice است نه count واقعی | count جداگانه |
| API-010 | Timeout | BrsApi_Forecasting | **متوسط** | timeout جامع برای DB، service و endpoint ندارد | timeout لایه‌ای |
| API-011 | Error handling | BrsApi_Forecasting/main.py | **متوسط** | str(exc) در response | error code عمومی، جزئیات فقط در log |
| MKT-003 | Tick size | rule_engine.py | **متوسط** | گردکردن float به‌جای Decimal | Decimal با tier مشخص |
| MKT-004 | Auction | backtesting/market/policies.py | **متوسط** | نوع auction اثر عملی ندارد | session phase جداگانه |
| MKT-005 | Market policy | policies.py | **متوسط** | instrument-specific exceptions مدل نشده | policy از instrument metadata |
| MKT-006 | Stale data | precompute_router.py | **متوسط** | freshness فقط UTC | calculated_at و market session جدا |
| FE-001 | WebSocket | frontend/src/hooks/useWebSocket.ts | **متوسط** | پیام‌ها بدون schema validator | validate payload |
| FE-002 | API prefix | frontend/src/lib/api.ts | **پایین** | prefix ناسازگار بین سرویس‌ها | یک configuration source |
| API-004 | WebSocket input | precompute_router.py | **متوسط** | payload JSON بدون Pydantic | مدل Pydantic و محدودیت اندازه |
| API-009 | Access token | frontend/src/lib/api.ts | **پایین** | token در JavaScript memory | session مبتنی بر cookie امن |

---

## آدیت Risk، Optimization، Broker، Smart Money

### Issue Register

| شناسه | دسته | فایل/تابع | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| RISK-001 | VaR | backtesting/risk/var.py | **بحرانی** | VaR علامت اشتباه. مقدار مثبت برمی‌گردد اما زیان نیست | max(0, -(mu + zσ) * sqrt(horizon)) |
| RISK-002 | CVaR | backtesting/risk/cvar.py | **بحرانی** | CVaR میانگین بازده، نه Expected Shortfall | تبدیل به زیان مثبت |
| RISK-005 | Kill Switch | risk/pre_trade_risk.py | **بالا** | کنترل زیان روزانه غیراتمی | قفل یا ذخیره اتمیک |
| RISK-008 | Kill Switch | PreTradeRiskEngine | **بالا** | kill switch فقط in-instance. restart آن را پاک می‌کند | storage مشترک durable |
| OPT-001 | Sharpe | optimization/objective_functions.py | **بالا** | ddof=0. Sharpe خوش‌بینانه در نمونه کوچک | ddof=1 و حداقل نمونه |
| OPT-006 | Portfolio | portfolio/constraints.py | **بالا** | محدودیت sector ذخیره ولی اعمال نمی‌شود | check_sector_weights در هر allocation |
| OPT-008 | Capital | capital/dynamic_allocator.py | **بالا** | فرمول penalty drawdown اشتباه | استاندارد کردن convention drawdown |
| BROKER-001 | Timeout | services/broker/paper_broker.py | **بالا** | asyncio.sleep(0.05) timeout واقعی نیست | asyncio.wait_for |
| SMART-001 | Smart Money | smart_money/layer1_price_volume.py | **بالا** | داده ناقص با مقدار 1 جایگزین. score قابل معامله | insufficient_data status |
| SMART-002 | Smart Money | smart_money/layer2_absorption.py | **بالا** | یک tick = absorption کاذب | حداقل sample size و minimum volume |
| SMART-003 | Smart Money | smart_money/layer8_microstructure.py | **بالا** | حرکت کوچک = جذب شدید کاذب | epsilon بر اساس tick size |
| QUANT-001 | MACD | smart_money/advanced_analytics.py | **بالا** | signal line = macd_line * 0.8 برای داده کوتاه | حداقل ۳۵ داده یا خروجی None |
| RISK-003 | Position sizing | risk/position_sizing.py | **بالا** | واحد volatility تعریف نشده | واحد صریح + تبدیل سالانه به روزانه |
| RISK-004 | Kelly | position_sizing.py | **بالا** | نام fractional Kelly اما Full Kelly برمی‌گرداند | پارامتر fraction: float = 0.25 |
| OPT-002 | Calmar | objective_functions.py | **بالا** | annual return و drawdown واحد ناسازگار | هر دو از NAV محاسبه شوند |
| OPT-003 | Bayesian | bayesian_optimization.py | **بالا** | نام Bayesian اما GP ندارد | نام‌گذاری صادقانه یا GP واقعی |
| BROKER-004 | Live broker | services/broker/ | **بالا** | فقط paper_broker. live adapter ممیزی نشده | contract مشترک timeout/auth/retry |
| RISK-006 | Daily reset | pre_trade_risk.py | **بالا** | reset PnL زمان‌محور نیست | reset بر اساس timezone بازار |
| RISK-007 | Drawdown | risk/drawdown_control.py | **متوسط** | peak از صفر. NAV منفی مدیریت خاص ندارد | baseline از اولین NAV معتبر |
| OPT-004 | Genetic | optimization/genetic_optimization.py | **متوسط** | seed، elitism و history ندارد | seed، elitism و ثبت history |
| OPT-005 | Walk-forward | optimization/walk_forward.py | **متوسط** | constraints در optimizer enforce نمی‌شوند | constraints داخل simulator |
| OPT-007 | Portfolio | portfolio/allocator.py | **متوسط** | وزن‌ها normalize می‌شوند ولی constraints اعمال نمی‌شوند | solver یا projection constrained |
| SMART-004 | Data quality | smart_money/data_quality.py | **متوسط** | is_valid=True برای partial | is_tradable جدا از is_valid |
| SMART-005 | Config | smart_money/config_loader.py | **متوسط** | خطای config = ادامه با default | fail-closed برای config عملیاتی |
| SMART-006 | Timestamp | لایه‌های Smart Money | **متوسط** | freshness timestamp بررسی نمی‌شود | timestamp حداکثر عمر اجباری |
| QUANT-002 | RSI | advanced_analytics.py | **متوسط** | RSI=100 در نبود زیان | insufficient_variation status |
| QUANT-003 | ATR | advanced_analytics.py | **متوسط** | ATR ناقص با period کوتاه | حداقل period اجباری |
| QUANT-004 | Duplicate | services/quantitative/ | **پایین** | RSI، MACD، ATR در Smart Money و Quantitative تکرار شده | یک implementation مرجع |
| QUANT-005 | Timing | advanced_analytics.py | **متوسط** | candle بسته نشده ممکن است وارد محاسبه شود | as_of و candle close status |
| BROKER-002 | Idempotency | paper_broker.py | **متوسط** | تغییر کوچک price = duplicate order | کلید idempotency پایدار |
| BROKER-003 | State | cancel_order | **متوسط** | لغو از mapping محلی. پس از restart نادرست | order state durable |

---

## آدیت Data Pipeline و Ingestion

### Issue Register

| شناسه | دسته | فایل/تابع | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| DP-001 | Rate Limit | iran_market_data/collectors/tsetmc.py | **بحرانی** | rate_policy در مسیر request مصرف نمی‌شود. بدون rate limit واقعی | limiter سراسری: ۱ req/sec TSETMC |
| DP-019 | Identity | Instrument model | **بحرانی** | TSETMC instrument ID تاریخی نگهداری نمی‌شود. تغییر ID = split تاریخچه | جدول tsetmc_instrument_id با validity |
| DP-021 | Adjusted Price | DailyPrice model | **بالا** | adjusted/unadjusted در مدل مشخص نیست | price_variant، adjustment_factor، corporate_action_id |
| DP-022 | Corporate Action | collectors | **بالا** | ingestion مستقل برای corporate action ندارد | pipeline جدا با reconciliation |
| DP-002 | Retry | providers/base/http_client.py | **بالا** | HTTP client بدون retry. خطای موقت = شکست کامل | retry با backoff نمایی برای 429، 5xx |
| DP-005 | Duplicate | DailyPrice migration | **بالا** | unique constraint وجود ندارد. اجرای مجدد = رکورد تکراری | unique constraint + upsert |
| DP-007 | Freshness | همه collectorها | **بالا** | source_timestamp ثبت نمی‌شود | source_timestamp، ingested_at، freshness_deadline |
| DP-010 | Schema | TsetmcCollector، CodalCollector | **بالا** | خروجی خام بدون schema validation | قرارداد schema نسخه‌دار |
| DP-011 | Missing Data | DailyPrice parsers | **بالا** | None، قیمت صفر، حجم منفی بررسی نمی‌شود | رد رکورد نامعتبر با علت |
| DP-014 | Job Overlap | jobs/locking.py | **بالا** | fallback به in-memory در نبود Redis | غیرفعال کردن fallback در production |
| DP-015 | Alerting | jobs/base_job.py | **بالا** | شکست job فقط log. بدون alert | metric، dead-letter state، alert |
| DP-016 | Dead Job | jobs/base_job.py | **بالا** | بدون heartbeat. worker مرده تشخیص داده نمی‌شود | heartbeat + watchdog |
| DP-020 | CODAL Mapping | CodalAnnouncement | **بالا** | mapping بر اساس symbol. تغییر نام شرکت = جدا شدن اعلان‌ها | codal_company_id پایدار |
| DP-024 | Parallelism | orchestration/runners.py | **بالا** | workflow موازی بدون coordination rate limit TSETMC را دور می‌زند | semaphore سراسری بر اساس provider |
| DP-003 | Validation | collectors | **بالا** | status code بررسی می‌شود اما schema، content type، JSON نه | اعتبارسنجی نوع، ساختار، اندازه |
| DP-004 | Atomicity | FileDownloader.download | **بالا** | دانلود ناقص مستقیم در storage | دانلود به فایل موقت + rename اتمیک |
| DP-006 | Duplicate Raw | RawStorage.save_json | **متوسط** | timestamp ثانیه‌ای بدون idempotency key | hash محتوا به‌عنوان کلید |
| DP-008 | Timezone | RawStorage، DailyPrice | **متوسط** | زمان ذخیره تهران، مدل DB UTC | UTC aware در همه جا |
| DP-012 | Authentication | AuthHandler | **متوسط** | token بدون refresh، expiry، redaction | secret manager + refresh |
| DP-013 | Stale Cache | JobLocking + cache | **متوسط** | freshness cache کنترل نمی‌شود | version، updated_at، منبع cache |
| DP-017 | Resource | collectors | **متوسط** | lifecycle response مدیریت نمی‌شود | close با finally در سطح job |
| DP-018 | Retry Semantics | JobRetryPolicy | **متوسط** | retry در HTTP client و dispatcher مستقل | policy مشترک با دسته‌بندی خطا |
| DP-023 | Daily Boundary | RawStorage | **متوسط** | partition بر اساس زمان دریافت نه trading_date | partition بر اساس trading_date منبع |
| DP-025 | Checkpoint | InMemoryCheckpointStore | **متوسط** | checkpoint پیش‌فرض in-memory | backend پایدار در production |
| DP-026 | Recovery | RecoveryManager | **متوسط** | recovery در ظاهر موفق بدون اجرای واقعی | قرارداد اجرایی صریح |
| DP-009 | Connection | HttpClient | **پایین** | lifecycle connection pool | health check و shutdown مرکزی |

---

## آدیت Repositories، Domain و Schemas

| شناسه | دسته | فایل/تابع | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| SCH-006 | Schema | schemas/api/auth.py | **بالا** | secret، refresh_token بدون SecretStr. در log افشا می‌شوند | SecretStr + schema separation |
| SCH-009 | Schema | MFAStatusResponse | **بالا** | secret و telegram_chat_id در endpoint وضعیت | schema setup از schema status جدا |
| REP-005 | Repository | base_repository.py | **متوسط** | _shared_store class-level. نشت بین تست‌ها | store instance-level |
| REP-006 | Repository | db_base.py | **متوسط** | lifecycle session در repository مبهم | Unit of Work مرکزی |
| REP-007 | Repository | db_base.py | **متوسط** | بدون optimistic locking | ستون version + UPDATE با شرط نسخه |
| REP-008 | Repository | repositories/ | **متوسط** | حذف فیزیکی داده‌های مالی | سیاست soft delete یا lifecycle |
| REP-001 | Repository | market_repository.py | **متوسط** | get_by_type بدون pagination | page + page_size + offset/limit |
| REP-002 | Repository | market_repository.py | **متوسط** | get_by_exchange بدون pagination | PaginatedResult |
| REP-003 | Repository | alert_repository.py | **متوسط** | چند query فهرستی بدون pagination | pagination اجباری |
| REP-004 | Repository | alert_repository.py | **متوسط** | get_history بدون pagination | page + page_size |
| DOM-001 | Domain | domain/markets/entities.py | **متوسط** | open_time رشته آزاد. ترتیب و timezone اعتبارسنجی نمی‌شود | value object زمان بازار |
| DOM-003 | Domain | domain/instruments/instrument.py | **متوسط** | update_eps هر float قبول می‌کند | Decimal با range validation |
| DOM-006 | Domain | domain/common/events.py | **متوسط** | lifecycle events منتشر نمی‌شوند | انتشار event پس از commit |
| DOM-004 | Domain | domain/instruments/instrument.py | **متوسط** | tags و metadata عمومی قابل تغییر | متدهای Domain برای تغییر |
| DOM-002 | Domain | domain/markets/entities.py | **متوسط** | status رشته آزاد | Enum یا value object |
| DOM-005 | Domain | domain/ | **متوسط** | dict[str, Any] برای metadata | value object یا dataclass typed |
| DOM-007 | Domain | domain/common/value_objects.py | **متوسط** | Percentage با float | Decimal با scale و rounding |
| SCH-001 | Schema | schemas/common/filters.py | **متوسط** | extra_filters: dict[str, Any] | whitelist کلیدها و مقادیر |
| SCH-002 | Schema | schemas/reporting/exports.py | **متوسط** | format و compression رشته آزاد | Literal یا Enum |
| SCH-003 | Schema | schemas/common/pagination.py | **متوسط** | items: list بدون نوع | PaginatedResponse[T] |
| SCH-004 | Schema | schemas/api/auth.py | **متوسط** | email رشته آزاد | EmailStr |
| SCH-005 | Schema | schemas/api/auth.py | **متوسط** | roles: list[str] بدون Enum | Enum برای role |
| SCH-007 | Schema | تمام schemas | **متوسط** | بدون schema_version | schema_version یا version در مسیر |
| SCH-008 | Schema | schemas/reporting/exports.py | **متوسط** | string بدون max_length | max_length + HttpUrl + datetime |
| DOM-008 | Domain | value_objects.py | **پایین** | currency رشته آزاد | ISO code + uppercase normalize |
| REP-009 | Repository | repositories/ | **پایین** | N+1 احتمالی در relations | selectinload یا joinedload مشخص |

---

## آدیت Tests، CI/CD، Docker و Dependencies

| شناسه | دسته | فایل | شدت | خلاصه | پیشنهاد اصلاح |
|---|---|---|---|---|---|
| TST-001 | تست | tests/test_backtest.py | **بالا** | اسکریپت print است نه pytest واقعی | تبدیل به test_* با assertion مالی |
| TST-003 | تست | tests/test_backtest_api_integration.py | **بالا** | تست fee فقط HTTP موفق را بررسی می‌کند | assertion روی net_pnl، fees، return |
| TST-006 | تست | چند تست | **بالا** | استفاده از date.today() | تاریخ ثابت timezone-aware |
| TST-007 | تست | backtesting API | **بالا** | edge cases پوشش ندارند | parametrized tests برای هر حالت |
| TST-009 | تست | test_backtest_api_integration.py | **بالا** | repository با mock. محاسبه مالی واقعی نمی‌شود | مسیر integration با engine واقعی |
| TST-011 | CI/CD | همه workflows | **بالا** | actionها با tag هستند نه commit SHA | pin به SHA + comment نسخه |
| TST-012 | CI/CD | ci.yml | **بالا** | mypy ... \|\| true. خطا مسدود نمی‌کند | حذف \|\| true |
| TST-013 | CI/CD | ci-pr.yml | **بالا** | lint frontend با continue-on-error | حذف continue-on-error |
| TST-015 | CI/CD | release.yml | **بالا** | deploy بدون smoke test image | health check + API smoke قبل از deploy |
| TST-017 | CI/CD | ci.yml، decision-engine.yml | **بالا** | image با tag :latest | tag immutable بر اساس commit |
| TST-018 | CI/CD | workflows | **بالا** | مجوزهای workflow حداقل‌سازی نشده | permissions: contents: read |
| TST-021 | Docker | Dockerfile | **بالا** | base image بدون digest | pin digest + به‌روزرسانی کنترل‌شده |
| TST-022 | Docker | Dockerfile | **بالا** | COPY . . | allowlist برای COPY |
| TST-023 | Docker | Dockerfile | **بالا** | container با root اجرا می‌شود | USER app |
| TST-025 | Docker | Dockerfile.api | **بالا** | dependency lock کامل ندارد | requirements.lock با hash |
| TST-026 | Docker | Dockerfile.api، Dockerfile.worker | **بالا** | COPY . . در stage نهایی | multi-stage با allowlist |
| TST-028 | Docker | Dockerfile.worker | **بالا** | image worker با ابزارهای build | stage runtime حداقلی |
| TST-029 | Docker | Dockerfile.frontend | **بالا** | npm ci --no-audit. بررسی dependency غیرفعال | audit جداگانه در CI |
| DEP-001 | Dependency | requirements.txt | **بالا** | بیشتر dependencies با >=. نسخه آسیب‌پذیر وارد می‌شود | lock file با hash |
| DEP-002 | Dependency | pyproject.toml | **بالا** | lock file جدا برای prod و dev | requirements.lock و requirements-dev.lock |
| DEP-004 | Dependency | requirements.txt | **بالا** | pip-audit در CI اجرا نمی‌شود | pip-audit -r requirements.txt در CI |
| TST-014 | CI/CD | ci-pr.yml، ci.yml | **متوسط** | فقط unit tests در PR اجرا می‌شوند | tier: unit، financial integration، API contract |
| TST-016 | CI/CD | release.yml | **بالا** | کنترل تأییدکنندگان release مشخص نیست | required reviewers در GitHub environment |
| TST-020 | CI/CD | Docker workflows | **بالا** | dependency audit blocking نیست | pip-audit و npm audit --audit-level=high |
| TST-004 | تست | backtesting tests | **بالا** | تست PnL، cash، position sizing ناقص | golden dataset با نتیجه مرجع |
| TST-005 | تست | test_backtest.py | **متوسط** | داده synthetic بدون edge case | fixture با سناریوهای edge |
| TST-008 | تست | tests/conftest.py | **متوسط** | _DB_AVAILABLE global. isolation ناقص | DB schema مجزا برای هر run |
| TST-010 | تست | backtest compare tests | **متوسط** | خطای engine با skip پنهان می‌شود | فقط نبود fixture = skip |
| TST-019 | امنیت | secrets-scan.yml | **متوسط** | retention نتیجه Gitleaks نامشخص | retention + baseline + required check |
| TST-024 | Docker | Dockerfile | **متوسط** | healthcheck ندارد | HEALTHCHECK در Dockerfile |
| TST-027 | Docker | Dockerfile.api | **متوسط** | health endpoint باید contract ثابت داشته باشد | endpoint ساده مستقل از dependencies |
| TST-030 | Docker | Dockerfile.frontend | **متوسط** | wget در healthcheck ممکن است موجود نباشد | ابزار موجود قطعی |
| DEP-003 | Dependency | requirements.txt + pyproject.toml | **متوسط** | نسخه Python در دو فایل | یک source of truth |

---

## فاز ۳: برنامه عمل

### مرحله ۱ — مسدودکننده‌ها (قبل از deploy بعدی)

| اولویت | شناسه‌ها | اقدام | زمان |
|:---:|---|---|---|
| 1 | BT-009، BT-010 | اصلاح Look-ahead: اجرای سفارش از کندل بعدی | ۱ روز |
| 2 | BT-001، BT-002 | FIFO lot accounting | ۲ روز |
| 3 | BT-004، BT-003، BT-005 | کارمزد: خرید ۰.۴۶۲٪، فروش ۰.۵۵۳٪، مالیات ۱.۵٪ | ۱ روز |
| 4 | ML-004 | ارزیابی واقعی مدل پس از retrain | ۱ روز |
| 5 | ML-001 | scaler فقط روی train | نیم روز |
| 6 | SRV-001 | مهاجرت صف accuracy به Redis Streams | ۲ روز |
| 7 | API-002 | atomic lock برای precompute | نیم روز |
| 8 | API-001، API-003 | محدودکردن CORS + احراز هویت WebSocket | ۱ روز |
| 9 | ML-007 | جایگزینی pickle با ONNX/safetensors | ۱ روز |
| 10 | BT-013، MKT-001 | timezone-aware در تمام datetime‌های بازار | ۱ روز |
| 11 | RISK-001، RISK-002 | اصلاح convention VaR و CVaR | نیم روز |
| 12 | DP-001 | rate limit واقعی برای TSETMC | ۱ روز |
| 13 | DP-019 | جدول identity نماد با validity | ۲ روز |
| 14 | TST-011 | pin کردن GitHub Actions به SHA | نیم روز |

### مرحله ۲ — سخت‌افزاری و Performance

| شناسه‌ها | اقدام |
|---|---|
| DB-002، DB-005 | isolation level صریح + composite index |
| ML-002 | TimeSeriesSplit با gap |
| ML-006 | cache key با artifact_hash |
| BT-007 | مدل لغزش پویا |
| BT-011 | corporate action از تاریخ مؤثر |
| DP-002، DP-003 | retry HTTP + schema validation |
| DP-005 | unique constraint + upsert |
| DP-014، DP-015، DP-016 | lock توزیع‌شده + alert + heartbeat |
| TST-001، TST-003، TST-004 | assertion مالی واقعی در تست‌ها |
| TST-021، TST-022، TST-023 | Docker: digest + allowlist + USER app |
| DEP-001، DEP-004 | lock file + pip-audit در CI |
| RISK-005، RISK-008 | kill switch durable + اتمیک |
| OPT-001، OPT-006 | ddof=1 + sector constraints |
| SMART-001 تا SMART-003 | insufficient_data به‌جای مقدار جایگزین |

### مرحله ۳ — بدهی فنی و پوشش تست

| اقدام | هدف |
|---|---|
| IranTradingCostSchedule versioned با تاریخ مؤثر | تغییر مقررات بدون تغییر کد |
| MarketRuleSet از DB با تاریخ مؤثر | تاریخچه مقررات |
| تست round-trip کامل (خرید/فروش/هزینه/PnL) | جلوگیری از regression مالی |
| contract test frontend/backend با Zod | تشخیص تغییر schema |
| seed قابل‌تنظیم در همه اجزای تصادفی | بازتولید دقیق بک‌تست |
| CI tier: unit + financial + API + nightly | پوشش کامل |
| پوشش تست >70٪ برای backtesting/، services/signal_*، ml/ | هدف‌گذاری coverage |
| SCH-003: PaginatedResponse[T] | type safety |
| DOM-006: domain events | audit و notification |
| DP-021، DP-022: adjusted price + corporate action pipeline | داده معتبر برای backtest |

---

*این گزارش توسط Software Factory Agent تولید شده است.*  
*تاریخ تولید: ۱۴۰۳/۰۷/۰۴*