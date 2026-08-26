# الزامات استخراج‌شده — سند معماری ارشد v5.0 (موتور تصمیم‌یار و کارخانه سیگنال)

> منبع: `سند معماری ارشد - موتور تصمیم_یار و کارخانه سیگنال (نسخه ۵.۰).docx` — ۶۱۰ خط، ۱۶ جدول
> استخراج: ۱۴۰۴/۰۶/۰۵ | این فایل، چک‌لیست پیاده‌سازی کامل است

## ۱. هدف و Non-Goals

- **هدف:** Quant Decision-Support System (نه OMS/اجرای خودکار)، پشتیبانی تصمیم با Expected Value، مدیریت ریسک و Out-of-Sample، Paper Trading
- **Design Target:** Win Rate 55-60% و Sharpe >1.5 در Paper (غیر از این، ML فعال نمی‌شود)
- **Non-Goals:** اجرای خودکار (Auto-Trading)، HFT، توصیه سرمایه‌گذاری مجوزدار

## ۲. محدودیت‌ها و فرض‌ها

- BrsApi بدون SLA — نیاز به Heartbeat، DATA_SOURCE_DOWN، DATA_DEGRADED، Rate Limiting با Exponential Backoff + Jitter، همگام‌سازی NTP
- مقیاس: Python polling (asyncio) + Redis Streams کافی است؛ Kafka/Ray فقط در صورت نیاز HFT

## ۳. Data Plane

- **Raw_Tick:** `instrument_key, market_time, receive_time, best_bid, best_ask, volume_visible, open_interest, source, data_quality, checksum, schema_version`
- **Instrument_Key:** `Symbol_ID + Underlying_Asset + Contract_Type + Strike + Expiry + Contract_Size + Delivery_Location`
- **Guard:** اگر Best_Bid/Ask نامعتبر → Mid_Price نامعتبر → downstream با Guard Clause رد شود

## ۴. Research Plane — Tiered Model Approach

### ۴.۱ قیمت‌گذاری آپشن
- **Tier1 (پیش‌فرض):** Black-76: `C = e^-rT [F N(d1) - K N(d2)]`, `d1=[ln(F/K)+0.5σ²T]/(σ√T)`, `d2=d1-σ√T`
- **Tier2 (اختیاری):** Displaced Diffusion: `dS = r S dt + σ(S+α) dW`, `C = e^-rT [(F+α)N(d1)-(K+α)N(d2)]`
- **IV:** Newton-Raphson `σ1=σ0 - (C_model - C_market)/Vega`, fallback به Brent

### ۴.۲ سطح نوسان (Vol Surface)
- **Tier1:** Cubic Spline بین Strikeها
- **Tier2:** SABR — فعال‌سازی فقط اگر: ≥5 Strike/Maturity، ≥2 Maturity فعال، RMSE <0.02، پایداری 20 روز

### ۴.۳ محاسبه Carry
- **Tier1:** `F* = S e^((r+c-y)T)`, `Mispricing% = (F_market - F*)/F*`
- **Tier2:** Cointegration Johansen — Z-score `Z=(Spread-μ)/σ`, سیگنال |Z|>2

## ۵. Trading Plane

### ۵.۱ چرخه عمر Signal
`Data Alert → Analytical Opportunity → Actionable Trade Card` (3 سطح Maturity)

### ۵.۲ Hard Blocks (6)
`REJECTED_DATA_STALE`, `REJECTED_DELIVERY_RISK`, `REJECTED_LOW_LIQUIDITY`, `REJECTED_TICK_MISMATCH`, `REJECTED_COST_NOT_COVERED`, `REJECTED_MODEL_LOW_CONFIDENCE`

### ۵.۳ NetEdge
`NetEdge = GrossEdge - Commission - Slippage - MarketImpact - LatencyBuffer`
`MarketImpact` با Almgren-Chriss: `Impact = η σ √(Q/V) + γ (Q/V)`

### ۵.۴ سیگنال‌های ساختاری
- IV Mean-Reversion: `IV_Rank >80% AND IV/RV(20d) >1.3`
- Calendar Arb: `(F_near - C_carry)/(F_far - C_carry) <0.95`
- Gamma Scalp: نیاز به نوسان واقعی

### ۵.۵ Signal Score
`Score = 0.30*Data_Quality + 0.25*Liquidity + 0.25*Execution_Ease + 0.20*Model_Confidence` (0.5-1.0)

## ۶. Risk — Position Sizing

- **Fixed Fractional:** `Size = (Risk_Budget * Tier) / Stop_Distance` (0.5% تا 2% بسته به Score)
- **Half-Kelly (آزمایشی):** `f*=(pb-q)/b`, `Size=0.5*f*Capital` — فقط با p معتبر
- **Drawdown Control:** -5% توقف احتیاط، -10% توقف کامل، -15% کاهش 50% سایز

## ۷. Validation

- **In-Sample / Validation / Out-of-Sample** + Walk-Forward + Event-Driven با Bid/Ask و Partial Fill
- **Metrics:** Win Rate >55%, Sharpe/Sortino, Max Drawdown, Profit Factor
- **Statistical Acceptance Gate:** 6 شرط (Win Rate، Sharpe، OOS، etc.) — همه باید پاس شود
- **Drift Monitoring:** Data Freshness، Liquidity، IV convergence، Slippage — Grafana

## ۸. Control Plane

- **RACI:** 4 نقش اصلی + On-Call Runbook برای DATA_SOURCE_DOWN، Threshold Breach، Kill Switch
- **Data Contract:** Raw_Tick, Signal_Candidate, Trade_Card, Execution_Feedback با schema_version
- **سایر:** Vault, Prometheus, Risk Register, 3 مثال عددی (Mid, Cost-of-Carry, NetEdge, Signal Score, Position Size)

## ۹. چک‌لیست پیاده‌سازی (اقتباس سند)

| فاز | محتوا | وضعیت |
|-----|-------|--------|
| فاز 0 | Data Foundation (Raw_Tick + Quality) | در حال پیاده‌سازی |
| فاز 1 | Tier1 Pricing (Black-76, IV, Greeks, Spline) | در حال پیاده‌سازی |
| فاز 2 | Signal Engine (NetEdge, Hard Blocks, Score) | در حال پیاده‌سازی |
| فاز 3 | Risk (Fixed Fractional, Drawdown) | در حال پیاده‌سازی |
| فاز 4 | Validation Gate + Observability | در حال پیاده‌سازی |
| فاز 5 | Tier2 (SABR, Cointegration, Half-Kelly) — اختیاری | پس از Tier1 |

