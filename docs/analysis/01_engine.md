**گزارش حسابرسی موتور GoldDesk (`src/gold_desk/`)**

> **دامنه:** `constants.py`, `pricer.py`, `bubbler.py`, `parity.py`, `signal_engine.py`, `nav_checker.py`, `scorer.py`, `dca_planner.py`, `hard_stops.py`, `black76.py`, `backtest.py`, `backtest_runner.py`, `pattern_detector.py`, `live_signals.py`, `macro_news.py` و منطق P&L در `portfolio.py` — به‌همراه `tests/gold_desk/`.
>
> **روش:** خواندن کامل کد ۱۶ ماژول + اجرای `pytest tests/gold_desk -q` (نتیجه: **۱۷۰ تست پاس**) + اجرای محاسبات عددی مستقل برای تأیید ادعاها (خروجی‌ها در متن نقل شده‌اند).
>
> **قاعده برچسب‌گذاری:** `[کد]` = واقعیت خوانده‌شده از کد با مسیر و شماره خط · `[استنباط]` = استنتاج من از کد، بدون اثبات مستقیم · `[پیشنهاد]` = اصلاح پیشنهادی.
>
> **هیچ فایلی جز همین گزارش تغییر نکرد.** ماژول‌های خارج از دامنه (`models.py`, `schemas.py`, `api.py`, `snapshot_service.py`, `alert_engine.py`, `telegram_bot.py`, `api_token.py`, `ws_hub.py`, `hotpath.py`, `metrics.py`, `chat.py`, `secondary_source.py`, jobها، Docker/nginx، `frontend/`) فقط برای فهم ورودی/خروجی خوانده شده‌اند و در بخش ۹/۱۰ با برچسب «وابستگی بیرونی» فهرست شده‌اند.

---

# ۱. خلاصه اجرایی

موتور GoldDesk مجموعه‌ای از توابع تقریباً pure برای «ارزش ذاتی → حباب → امتیاز → سیگنال/پلن» است. کیفیت کد در لایهٔ **قیمت‌گذاری و امتیازدهی تک‌جزئی** خوب است (توابع کوچک، dataclassهای frozen، تست واحد برای هر شاخه). اما در لایهٔ **بک‌تست، تشخیص الگو و P&L** چند نقص ساختاری وجود دارد که خروجی محصول را بی‌معنا یا گمراه‌کننده می‌کند و هیچ‌کدام توسط ۱۷۰ تست فعلی گرفته نمی‌شود.

**یافته‌های اصلی (همه با اجرای واقعی تأیید شده‌اند):**

| # | یافته | شدت | تأیید |
|---|---|---|---|
| ۱ | `backtest_runner` واحد پول را گم می‌کند: `units` از سرمایهٔ نرمال‌شدهٔ `1.0` ساخته می‌شود اما `total_return` بر `initial_capital=100_000_000` تقسیم می‌شود ⇒ `total_return_pct = -100.0` و `alpha_pct = -119.46` در یک سری صعودی. (`backtest_runner.py:100,121,168,170`) | Critical | اجرای `_compute_metrics` روی fixture خودِ تست: `final_value 0.5475`, `total_return_pct -100.0`, `buy_hold 19.46` |
| ۲ | `backtest.py` از `np.convolve(..., mode="same")` برای SMA30 استفاده می‌کند که ۱۵ قیمت **آینده** را در میانگین می‌آورد ⇒ look-ahead bias. (`backtest.py:54`) | Critical | `sma30[40] = 139.5` در حالی که میانگین trailing واقعی `125.5` است |
| ۳ | `pattern_detector._fetch_closes` cutoff میلادی می‌سازد و با ستون تاریخ شمسی مقایسه می‌کند ⇒ همیشه ۰ ردیف؛ `/patterns` عملاً همیشه «داده کافی نیست». (`pattern_detector.py:54`) | Critical | `'1405-08-02' >= '2026-09-24'` → `False` |
| ۴ | `fifo_realized` لات‌ها را بین نمادها مشترک نگه می‌دارد ⇒ سود تحقق‌یافتهٔ یک نماد با بهای نماد دیگر محاسبه می‌شود. (`portfolio.py:230`) | Critical | خرید ۱۰ گرم طلای ۱۸ (۱۰۰) + فروش ۵ سکه (۱۰۰۰) → `realized_pnl_irt = 4500` |
| ۵ | نرمال‌سازی امتیاز بر «وزن موجود» ⇒ با یک کامپوننت از شش کامپوننت، امتیاز **۱۰۰ و GREEN** می‌شود. (`scorer.py:208-209`) | Critical | `bubble=7.9` تنها → `total=100`, `decision=GREEN` |
| ۶ | `signal_engine` ده روز **جدیدتر** را دور می‌ریزد (`reversed(closes[-days:])`) ⇒ RSI/EMA و «تغییر روزانهٔ دلار» برای hard stop کهنه‌اند. (`signal_engine.py:29,48`) | High | بازسازی لیست: `40..1` با `days=30` → `[1..30]`؛ ۴۰ و ۳۹ حذف می‌شوند |
| ۷ | `max_drawdown` در `backtest_runner` همیشه صفر است (`cumsum` صعودی × قیمت پایانی). (`backtest_runner.py:182-184`) | High | خروجی اجرا: `maxdd 0.0` |
| ۸ | `theta` در Black-76 علامت جملهٔ نرخ بهره را اشتباه دارد (~۳۶٪ خطا در ATM با r=0.30). (`black76.py:117-122`) | High | finite-difference: `-0.021412/day` vs کد `-0.029101/day` |

**جمع‌بندی:** `pricer.py` / `bubbler.py` / `parity.py` / `hard_stops.py` / `dca_planner.py` را می‌توان با اطمینان به‌عنوان «محاسبهٔ درست با آستانه‌های بدون منبع» پذیرفت. `scorer.py` نیازمند سیاست پوشش داده است. `backtest*.py` و `pattern_detector.py` از نظر اعتبار آماری/کارکردی **قابل استفاده نیستند** تا اصلاح شوند. `portfolio.py` در مسیرهای ساده (P&L یک نماد) درست است ولی FIFO و XIRR آن چند فرض ناگفته دارد.

---

# ۲. نقشه ماژول‌ها

## ۲.۰ جریان داده

```
BrsApi tables (brsapi_*)                          جدول‌های تاریخچه
  brsapi_gold_coin_history (date: شمسی, close)
  brsapi_gold_currency_pro_daily_history (XAUUSD/USD/DXY)
  brsapi_nav_records (nav_issue, nav_redemption)
  brsapi_historical_real_legal (buy_real/sell_real value)
  brsapi_index_values (شاخص کل)
        │
        ▼
snapshot_service.build_snapshot()  ← وابستگی بیرونی (خارج از دامنه)
        ├─ parity.aed_parity_usd / aed_gap_pct
        ├─ pricer.fair_value ──► bubbler.calc_bubble      (طلا و سکه)
        ├─ nav_checker.get_all_funds_status               (صندوق‌ها)
        ├─ signal_engine.get_xau_indicators               (RSI/EMA/SMA/BB/MACD)
        ├─ hard_stops.check_hard_stops                    (TSE/DXY/USD)
        └─ scorer.compute_score ──► ScoreResult (0-100 + band)
        │
        ▼
SnapshotResponse → Redis/DB → api.py → frontend        (وابستگی بیرونی)

مسیرهای مستقل:
  backtest.run_backtest        ◄── brsapi_gold_coin_history (مستقیم)
  backtest_runner.run_strategy_backtest ◄── همان جدول (مستقیم)
  pattern_detector.detect_patterns      ◄── همان جدول (مستقیم، buggy)
  live_signals.detect_and_broadcast     ◄── snapshot قبلی/فعلی + Redis
  portfolio.*                           ◄── GoldHolding/GoldTrade + snapshot
```

`[کد]` مبادی فراخوانی در `snapshot_service.py:210-211, 229-230, 250-251, 266, 285, 305, 312` و در jobها `brsapi/jobs/gold_desk_jobs.py:76, 87-89, 146, 195, 261`.

نکتهٔ ساختاری مهم: **هیچ‌کدام از ماژول‌های تحلیل (scorer/backtest/pattern/macro) از یکدیگر یا از یک «موتور رویدادمحور» تغذیه نمی‌شوند.** هر کدام مستقل روی DB می‌خوانند؛ نتیجه این است که منطق‌های تکراری (SMA30، حباب تکنیکال، آستانه‌ها) در سه جا با سه پیاده‌سازی متفاوت تکرار شده‌اند (`backtest.py:54`, `backtest_runner.py:108`, `pattern_detector.py:73`).

---

## ۲.۱ `constants.py` — «تک‌منبع حقیقت» اسمی، عملاً دو منبع

**هدف و جایگاه:** ثابت‌های متالورژی، وزن سکه، کارمزد ابزار، آستانه‌های امتیازدهی، رجیستری نمادها، آستانه‌های ری‌بالانس.

**توابع/کلاس‌ها:** هیچ تابع یا کلاسی ندارد. فقط داده در سطح ماژول + دو `assert` در زمان import:
- `[کد]` `constants.py:60` — `assert sum(SCORE_WEIGHTS.values()) == 100`
- `[کد]` `constants.py:173` — `assert abs(sum(PORTFOLIO_TARGET_WEIGHTS.values()) - 100.0) < 1e-9`

**عوارض جانبی:** import این ماژول، `services.gold.constants` را import می‌کند (`constants.py:35-36`) و در صورت خطا کل GoldDesk بالا نمی‌آید. همچنین دو assert می‌تواند در محیط production باعث `AssertionError` در startup شود (مطلوب است، ولی باید آگاهانه باشد).

**دوگانگی منبع:** `[کد]` `constants.py:38` مقدار `MINTING_COST_TOMAN = 50_000.0` را به‌عنوان fallback تعریف می‌کند و در همان بلوک، جدول واقعی را از `services.gold.constants.COIN_MINTING_COSTS` می‌گیرد (`:35,39`). یعنی «تک‌منبع» در عمل «دو فایل با ارجاع یک‌طرفه» است؛ تغییر در `services/gold/constants.py` بی‌سروصدا روی pricer اثر می‌گذارد.

---

## ۲.۲ `pricer.py` — ارزش ذاتی طلای وزنی و سکه

**هدف و جایگاه:** تبدیل (اونس جهانی، دلار تهران) به تومانِ هر واحد کالا. ورودی آن از snapshot می‌آید (`snapshot_service.py:229,250`) و خروجی‌اش مستقیماً به `bubbler.calc_bubble` می‌رود.

| تابع | امضا | ورودی (نوع/واحد/بازه) | خروجی | عوارض جانبی |
|---|---|---|---|---|
| `base_24k_per_gram` | `(xau_usd: float, usd_irt: float) -> float` | `xau_usd`: دلار/اونس، `(0, ∞)` عملاً ۱۰۰۰–۱۰۰۰۰ (`VALID_XAU_RANGE`); `usd_irt`: تومان/دلار، ۱۰k–۱۰M | تومان بر گرم طلای ۲۴ عیار | `ValueError` اگر هر ورودی `<= 0` (`:38-39`) |
| `fair_gold_18k` | `(xau_usd, usd_irt) -> float` | همان | تومان/گرم ۱۸ عیار | هیچ |
| `fair_gold_24k` | `(xau_usd, usd_irt) -> float` | همان | تومان/گرم ۲۴ عیار | هیچ |
| `fair_coin` | `(symbol: str, xau_usd, usd_irt) -> float` | `symbol ∈ COIN_WEIGHTS` (۶ نماد) | تومان/سکه (شامل ضرب) | `ValueError` برای نماد ناشناس (`:55-56`) |
| `fair_coin_breakdown` | `(symbol, xau_usd, usd_irt) -> dict[str,float]` | همان | `{gold_value, minting_cost, fair_value}` | همان `ValueError` |
| `fair_value` | `(symbol: str, xau_usd, usd_irt) -> float` | نمادهای رجیستری + `IR_GOLD_1G` | تومان/واحد | `ValueError` (`:95`) |
| `fair_gram_weight` | `(symbol: str) -> float` | همان | گرم طلای خالص هر واحد | `ValueError`; **بدون مصرف‌کننده** (بخش ۷، L1) |

---

## ۲.۳ `bubbler.py` — حباب و دلار ضمنی

**هدف و جایگاه:** مصرف‌کنندهٔ `pricer.fair_value` و قیمت بازار؛ خروجی `BubbleResult` داخل `AssetBlock` snapshot می‌نشیند (`snapshot_service.py:230-243`).

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `BubbleResult` (dataclass frozen) | `symbol, market, fair, bubble_abs, bubble_pct, implied_usd` | — | — | — |
| `_purity_for_symbol` | `(symbol: str) -> float` | نماد | کسر عیار (۰.۷۵ / ۰.۹۹۹۹ / ۰.۹) | `ValueError` (`:43`) |
| `_pure_gold_weight` | `(symbol: str) -> float` | نماد | گرم خالص هر واحد | — |
| `calc_bubble` | `(symbol, market: float, fair: float, xau_usd: float) -> BubbleResult` | `market`: تومان؛ `fair`: تومان؛ `xau_usd > 0` | `BubbleResult` | هیچ؛ برای `fair<=0` یا `xau_usd<=0` مقدار ۰ برمی‌گرداند (سکوت، بخش ۷) |

---

## ۲.۴ `parity.py` — شکاف درهم/دلار

**هدف و جایگاه:** یک تابع دو خطی که در snapshot برای ساخت `ReferenceBlock` و ورودی کامپوننت `parity` امتیاز استفاده می‌شود (`snapshot_service.py:210-211`).

| تابع | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `aed_parity_usd` | `(aed_irt: float) -> float` | تومان/درهم، `> 0` | تومان/دلار تعادلی | `ValueError` (`:14-15`) |
| `aed_gap_pct` | `(usd_irt: float, aed_irt: float) -> float` | تومان/دلار، تومان/درهم | درصد شکاف (مثبت = دلار گران‌تر) | `aed_parity_usd` را صدا می‌زند ⇒ `ValueError` غیرمستقیم |

---

## ۲.۵ `signal_engine.py` — اندیکاتورهای XAU

**هدف و جایگاه:** خواندن close روزانه از دو جدول BrsApi و محاسبهٔ RSI/EMA/SMA/Bollinger/MACD. خروجی `get_xau_indicators` در snapshot (`:285`) و `fetch_closes` هم در snapshot برای «تغییر روزانهٔ USD/DXY» (`:146,177`) استفاده می‌شود.

| تابع | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `_fetch_gold_coin_closes` | `(session, symbol: str, days: int) -> list[float]` | `days` تعداد سشن | close صعودی (قدیم→جدید) — **عملاً بدون ۱۰ روز آخر** | SELECT روی DB |
| `_fetch_pro_daily_closes` | همان | همان | همان (منبع دوم) | SELECT |
| `fetch_closes` | همان | همان | بهترین منبع بر اساس تعداد ردیف | ۲ کوئری بالقوه؛ استثناها را log و خفه می‌کند (`:58,63`) |
| `calc_rsi` | `(closes: list[float], period: int = 14) -> float \| None` | حداقل `period+1` مقدار | RSI ویلدر ۰–۱۰۰ | هیچ |
| `calc_ema` | `(closes, period=14) -> float \| None` | حداقل `period` | EMA آخرین نقطه | هیچ |
| `calc_sma` | `(closes, period=20) -> float \| None` | حداقل `period` | SMA | هیچ |
| `calc_bollinger` | `(closes, period=20, k=2.0) -> dict \| None` | حداقل `period` | `{middle, upper, lower, width_pct}` | هیچ |
| `calc_macd` | `(closes, fast=12, slow=26, signal=9) -> dict \| None` | حداقل `slow+signal` | `{macd, signal, histogram, bullish}` | هیچ |
| `calc_ema_bubble` | `(closes, period=20) -> float \| None` | حداقل `period` | درصد فاصله از EMA | هیچ |
| `get_xau_rsi` | `(session, days=30) -> float \| None` | — | RSI | SELECT؛ **بدون مصرف‌کننده** |
| `get_xau_ema` | `(session, days=30) -> float \| None` | — | EMA | SELECT؛ **بدون مصرف‌کننده** |
| `get_xau_indicators` | `(session, days=40) -> dict` | — | دیکشنری همهٔ اندیکاتورها + `closes` خام | SELECT |

---

## ۲.۶ `nav_checker.py` — P/NAV صندوق‌ها

**هدف و جایگاه:** تنهاترین ماژول «کثیف» دامنه (DB + import داخل تابع + fallbackهای زنجیره‌ای). خروجی `FundNAVStatus` هم در snapshot و هم ورودی چهار کامپوننت امتیاز است.

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `MAX_MARKET_DATA_AGE_DAYS` | `int = 7` | — | آستانهٔ کهنگی real/legal | — |
| `FundNAVStatus` | dataclass: `symbol, fund_name, nav_per_unit, market_price\|None, bubble_abs\|None, bubble_pct\|None, bpr, real_buy_value, real_sell_value, net_inflow, nav_7d_pct\|None` | — | — | — |
| `_pick_nav` | `(row: Any) -> float \| None` | ردیف `(nav_issue, nav_redemption)` | اولین مقدار truthy | هیچ |
| `_latest_nav` | `(session, symbol) -> float \| None` | — | NAV آخر | SELECT |
| `_nav_7d_ago` | `(session, symbol) -> float \| None` | — | NAV با `date <= jalali_days_ago(7)` | SELECT |
| `_fund_market_data` | `(session, symbol) -> dict \| None` | — | `{buy_value, sell_value, bpr, net_inflow}` | SELECT؛ همهٔ استثناها خفه (`:122-123`) |
| `get_fund_status` | `(session, symbol, market_price_override: float \| None = None) -> FundNAVStatus \| None` | قیمت بازار تومان | وضعیت کامل | ۴ کوئری + حداقل یک import پویا؛ در نبود NAV `None` |
| `get_all_funds_status` | `(session, symbols: list[str], market_prices: dict[str,float] \| None) -> list[FundNAVStatus]` | ۱۰ نماد `FUND_SYMBOLS` | لیست وضعیت | N×`get_fund_status` (بدون batch) |

---

## ۲.۷ `scorer.py` — امتیاز ۶ کامپوننت

**هدف و جایگاه:** قلب تصمیم‌گیری؛ خروجی آن `ScoreBlock` snapshot و مبنای رنگ داشبورد و آلارم‌هاست.

| مورد | امضا | ورودی (واحد) | خروجی | عوارض |
|---|---|---|---|---|
| `ScoreComponent` | frozen dataclass `(value:int, max_value:int, reason:str)` | — | — | — |
| `ScoreResult` | frozen dataclass `(total, decision, components, hard_stop_active, hard_stop_reason, raw_total, available_weight, data_coverage_pct)` | — | — | — |
| `_clip` | `(x:int, lo:int, hi:int) -> int` | — | clamp | — |
| `score_bubble` | `(bubble_pct: float\|None) -> ScoreComponent` | درصد حباب سکه امامی | `0..20` | — |
| `score_nav` | `(nav_bubble_pct: float\|None)` | درصد P/NAV | `0..18` | — |
| `score_tsetmc` | `(bpr: float\|None, net_inflow: float\|None)` | نسبت خرید/فروش، تومان | `0..18` | — |
| `score_technical` | `(rsi: float\|None)` | RSI ۰–۱۰۰ | `0..15` | — |
| `score_parity` | `(aed_gap_pct: float\|None)` | درصد | `0..15` | — |
| `score_fund_flow` | `(nav_7d_pct: float\|None)` | درصد ۷ روزه | `0..14` | — |
| `compute_score` | keyword-only: `bubble_pct, nav_bubble_pct, bpr, net_inflow, xau_rsi, aed_gap_pct, nav_7d_pct, hard_stop_active=False, hard_stop_reason=None` | همه `float\|None` | `ScoreResult` | هیچ |

---

## ۲.۸ `hard_stops.py` — قطع‌کنندهٔ تصمیم

**هدف و جایگاه:** سه شرط بحرانی که امتیاز را باطل و تصمیم را RED می‌کند؛ در `snapshot_service.py:305` با تغییرات روزانهٔ محاسبه‌شده صدا زده می‌شود.

| مورد | امضا | ورودی (درصد تغییر روزانه) | خروجی | عوارض |
|---|---|---|---|---|
| `HardStopResult` | frozen dataclass `(active:bool, reason:str\|None, inputs_missing:bool=False)` | — | — | — |
| `check_hard_stops` | `(tse_daily_change_pct=None, dxy_daily_change_pct=None, usd_irt_daily_change_pct=None) -> HardStopResult` | هر کدام `float\|None` | اولین شرط برنده | هیچ؛ `None` = «نادیده بگیر» و اگر هر سه `None` → `inputs_missing=True` |

---

## ۲.۹ `dca_planner.py` — پلن پله‌ای

**هدف و جایگاه:** تولید پلن ۳ پله‌ای بر اساس پروفایل ریسک و امتیاز. مصرف: `POST /dca/plan` (`api.py:201`) و `POST /portfolio/dca` (`api.py:987`).

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `Tranche` | frozen: `tranche:int, pct:float, amount_irt:float, trigger:str, vehicle:str, estimated_fee_irt:float` | — | — | — |
| `DCAPlan` | frozen: `total_capital_irt, ladder, recommended_vehicle, total_fee_irt, net_investable_irt, stop_loss_pct, take_profit_pct` | — | — | — |
| `_recommend_vehicle` | `(score:int) -> str` | ۰–۱۰۰ | `etf`/`cert`/`melted` | — |
| `_calc_fee` | `(amount_irt: float, vehicle: str) -> float` | تومان، کلید `VEHICLE_FEES` | تومان (فقط خرید) | برای vehicle ناشناس بی‌صدا `etf` می‌گیرد (`:75`) |
| `plan_dca` | `(total_capital_irt: float, risk_profile: str = "balanced", current_score: int = 60, preferred_vehicle: str \| None = None) -> DCAPlan` | `capital > 0`، `score ∈ [0,100]`، `profile ∈ LADDER_PATTERNS` | `DCAPlan` | ۳ `ValueError` (`:96-100`) |

---

## ۲.۱۰ `black76.py` — قیمت‌گذاری اختیار

**هدف و جایگاه:** مستقل از snapshot؛ فقط از API با پارامترهای کاربر صدا زده می‌شود (`api.py:628, 673`).

| مورد | امضا | ورودی (واحد) | خروجی | عوارض |
|---|---|---|---|---|
| `OptionGreeks` | frozen: `delta, gamma, vega, theta, rho` | — | — | — |
| `OptionPrice` | frozen: `call, put, forward, strike, time_to_expiry_years, iv, rate, d1, d2, greeks` | — | — | — |
| `years_to_expiry` | `(expiry: date) -> float` | تاریخ میلادی | سال (حداقل `1e-6`) | `date.today()` (زمان محلی) |
| `black76_price` | `(forward, strike, time_years, iv=0.25, rate=0.30) -> tuple[call, put, d1, d2]` | `F,K,T,iv > 0` | ۴ عدد | ۳ `ValueError` (`:79-84`) |
| `black76_greeks` | `(forward, strike, time_years, iv=0.25, rate=0.30) -> OptionGreeks` | همان، **بدون اعتبارسنجی** | یونانی‌ها | تقسیم بر صفر برای `iv=0`/`T=0` |
| `price_option` | `(forward, strike, expiry: date, iv=0.25, rate=0.30) -> OptionPrice` | — | بستهٔ کامل | — |
| `CollarResult` | frozen: `cost, floor, cap, put_premium, call_premium, spot, put_strike, call_strike, time_years` | — | — | — |
| `protective_collar` | `(spot, put_strike, call_strike, expiry, iv=0.25, rate=0.30) -> CollarResult` | تومان | کالر | فرض `F ≈ spot` (`:189`) |

---

## ۲.۱۱ `backtest.py` — بک‌تست سیگنال حباب

**هدف و جایگاه:** پاسخ به «آیا وقتی حباب بالای آستانه بود، ۳۰ روز بعد بازدهی مثبت بود؟». مصرف: `GET /backtest` (`api.py:496`).

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `BacktestResult` | frozen: `total_days, score_above_threshold_days, forward_return_30d_avg, forward_return_30d_positive, forward_return_30d_negative, hit_rate, sample_warning` | — | — | — |
| `_daily_bubble_pct` | `(session, symbol, days) -> list[tuple[str, float, float]]` | `days` روز تقویمی (cutoff = `days+60` شمسی) | `(date, bubble_vs_SMA30, fwd30)` | SELECT؛ همهٔ استثناها → `[]` (`:64-66`) |
| `run_backtest` | `(session, symbol="IR_COIN_EMAMI", days=90, bubble_threshold=8.0) -> BacktestResult` | آستانه درصد | نتیجه | — |

---

## ۲.۱۲ `backtest_runner.py` — شبیه‌سازی DCA

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `BacktestTrade` | frozen: `date, tranche, price, amount_irt, units, trigger_met` | — | — | — |
| `BacktestMetrics` | frozen: `period_start, period_end, initial_capital, final_value, total_return_pct, buy_hold_return_pct, alpha_pct, hit_rate_pct, n_trades, n_successful, max_drawdown_pct, sharpe_ratio, trades, warning` | — | — | — |
| `_fetch_daily_closes` | `(session, symbol, days) -> list[tuple[date,float]]` | cutoff شمسی | سری صعودی | SELECT؛ استثنا → `[]` |
| `_simulate_dca` | `(closes, tranches_pct: list[float], bubble_trigger: float) -> list[BacktestTrade]` | حداقل ۱۰ کندل | معاملات | هیچ (اما اقتصاد آن خراب است، بخش ۵) |
| `_compute_metrics` | `(closes, trades, initial_capital: float) -> BacktestMetrics` | تومان | متریک‌ها | هیچ |
| `run_strategy_backtest` | `(session, symbol="IR_COIN_EMAMI", days=90, tranches_pct=(0.30,0.40,0.30), bubble_trigger=5.0, initial_capital=100_000_000.0)` | — | `BacktestMetrics` | SELECT |

---

## ۲.۱۳ `pattern_detector.py` — تشخیص الگو

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `DetectedPattern` | frozen: `pattern_type, confidence, description, expected_direction, expected_magnitude_pct, historical_hit_rate, sample_size` | — | — | — |
| `PatternReport` | frozen: `symbol, period_start, period_end, patterns, summary, recommendation` | — | — | — |
| `_fetch_closes` | `(session, symbol, days) -> list[tuple[str,float]]` | cutoff **میلادی** (باگ) | سری | SELECT؛ استثنا → `[]` |
| `_detect_mean_reversion` | `(prices: list[float]) -> DetectedPattern \| None` | ≥۶۰ قیمت | الگو یا `None` | هیچ |
| `_detect_trend` | `(prices) -> DetectedPattern \| None` | ≥۵ | الگو | — |
| `_detect_spike` | `(prices) -> DetectedPattern \| None` | ≥۴ | الگو | — |
| `_detect_vol_regime` | `(prices) -> DetectedPattern \| None` | ≥۲۰ | الگو | — |
| `pd_rolling_mean` | `(arr: np.ndarray, window: int) -> np.ndarray` | — | میانگین متحرک با backfill | — |
| `detect_patterns` | `(session, symbol="IR_COIN_EMAMI", days=90) -> PatternReport` | — | گزارش | SELECT؛ هر detector در `try` جدا |

---

## ۲.۱۴ `live_signals.py` — سیگنال real-time

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `Signal` | frozen: `symbol, signal_type, severity, title, description, current_value, threshold, change_pct, ts` + `to_dict()` | — | دیکشنری | `ts or time.time()` |
| `detect_spike` | `(prev: float, curr: float, threshold: float = 1.0) -> str \| None` | تومان/درصد | `spike_up`/`spike_down`/`None` | — |
| `detect_signals` | `(prev_snap: dict \| None, curr_snap: dict) -> list[Signal]` | ساختار snapshot | لیست سیگنال | — |
| `detect_and_broadcast` | `(curr_snap: dict) -> list[Signal]` | snapshot | سیگنال‌های یکتا | Redis read/write (`:155,163,166,179`) + broadcast WS (`:184-188`)؛ همهٔ خطاها → `[]` (`:192-194`) |

---

## ۲.۱۵ `macro_news.py` — رویدادهای کلان

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `MacroEvent` | frozen: `title, source, category, impact_score(-3..3), confidence(0..1), explanation, published_at` + `to_dict()` | — | — | — |
| `_score_rate_event` | `(title: str) -> int` | عنوان فارسی/انگلیسی | `-2/+2/0` | — |
| `_score_inflation_event` | `(title) -> int` | — | `+2/-1/0` | — |
| `_score_fx_event` | `(title) -> int` | — | `-2/+2/0` | — |
| `_score_demand_event` | `(title) -> int` | — | `+2/-1/0` | — |
| `estimate_impact` | `(title: str, category: str) -> tuple[int, float]` | — | `(score, 0.6)` | — |
| `get_sample_events` | `() -> list[MacroEvent]` | — | ۴ رویداد **دستی/دمو** | هیچ؛ طبق مستند خودش (`:109-113`) هرگز از مسیر واقعی صدا زده نمی‌شود |
| `compute_macro_multiplier` | `(events: list[MacroEvent]) -> float` | رویدادهای ۳۰ روز | `[-1, +1]` | هیچ |
| `fetch_macro_events` | `() -> list[MacroEvent]` | — | از Redis یا `[]` | Redis read؛ خطا → `[]` |
| `scrape_cbi_news` | `() -> list[MacroEvent]` | — | رویدادهای استخراج‌شده | HTTP به `cbi.ir` |

---

## ۲.۱۶ `portfolio.py` — P&L، XIRR، FIFO، DCA status

**هدف و جایگاه:** خواندن `GoldHoldingModel` / `GoldTradeModel` / `GoldDCAPlanModel` + قیمت‌های snapshot و تولید P&L و بازده. بیشترین سطح تماس با API (`api.py:891-919, 1046, 1107`).

| مورد | امضا | ورودی | خروجی | عوارض |
|---|---|---|---|---|
| `HoldingPnL` | frozen: `symbol, display_name, quantity, avg_buy_price, current_price\|None, cost_basis, current_value\|None, pnl_irt\|None, pnl_pct\|None, n_purchases` | — | — | — |
| `PortfolioSummary` | frozen: `total_cost, total_value, total_pnl, total_pnl_pct, holdings, by_symbol, unpriced_holdings=0` | — | — | — |
| `_add_prices` | `(target: dict[str,float], assets) -> None` | dict یا list از asset dict | — | mutates `target` |
| `get_current_prices` | `(snap: dict \| None) -> dict[str,float]` | snapshot | `symbol → market_price` | — |
| `_flow_date` | `(value: object) -> date` | datetime/date | date | `TypeError` (`:93`) |
| `cash_flows_from_trades` | `(trades: Iterable[object]) -> list[Flow]` | آبجکت‌های trade | `[(date, ±amount_irt)]` | — |
| `build_cash_flows` | `(*, holdings=None, trades=None) -> list[Flow]` | — | جریان‌ها | — |
| `PortfolioReturns` | frozen: `nominal_pnl_irt, nominal_pnl_pct\|None, nominal_xirr\|None, real_xirr\|None, usd_xirr\|None, cpi_basis, usd_basis, unavailable: dict` | — | — | — |
| `_xirr_or_none` | `(flows, unavailable: dict, key: str) -> float \| None` | — | XIRR یا `None` | mutates `unavailable` |
| `compute_returns` | `(flows, *, ending_value: float, asof: date, fx=None, cpi=None, cpi_basis=None, usd_basis=None) -> PortfolioReturns` | تومان | بازده اسمی/واقعی/دلاری | — |
| `fifo_realized` | `(trades: Iterable[object]) -> dict` | معاملات (همهٔ نمادها) | `{realized_pnl_irt, sold_quantity, open_lots, open_quantity, open_cost_basis_irt}` | — |
| `trades_to_csv` | `(trades) -> str` | — | CSV | — |
| `build_tax_summary` | `(session) -> dict` | — | خروجی FIFO | ۲ SELECT |
| `build_trades_csv` | `(session) -> str` | — | CSV | ۲ SELECT |
| `_live_prices_from_snapshot` | `(snap) -> dict[str,float]` | — | قیمت‌ها | — |
| `load_holdings_and_trades` | `(session) -> tuple[list, list]` | — | holdings, trades | ۲ SELECT |
| `_load_fx_series` | `(session) -> dict[date,float]` | — | سری دلار (شمسی→میلادی) | SQL خام؛ خطا → `{}` |
| `build_portfolio_returns` | `(session, *, snapshot=None, asof=None, fx=None, cpi=None, cpi_basis=None, usd_basis=None)` | — | `PortfolioReturns` | ۳ SELECT + `get_holdings_grouped` |
| `get_holdings_grouped` | `(session, current_prices: dict[str,float]) -> PortfolioSummary` | — | خلاصه | SELECT |
| `DCAPlanStatus` | frozen: `plan_id, name, total_capital, executed, remaining, next_tranche_pct, next_tranche_amount, next_trigger, current_score, stop_loss_pct, take_profit_pct` | — | — | — |
| `get_plan_status` | `(plan: GoldDCAPlanModel, current_score: int) -> DCAPlanStatus` | مدل DB | وضعیت | JSON parse خفه (`:477-480`) |
| `record_trade` | `(session, *, symbol, action, quantity, price, amount_irt, fee_pct=0.0, holding_id=None, plan_id=None, note=None) -> GoldTradeModel` | تومان/واحد | رکورد | **`session.add` + `commit` + `refresh`** (`:545-547`) |

---

# ۳. دیکشنری فرمول‌ها و ثابت‌ها

## ۳.۱ قیمت پایه و ارزش ذاتی (`pricer.py`)

`[کد]` `pricer.py:36-40`:

```
base_24k_per_gram = (xau_usd × usd_irt) / 31.1034768          # تومان بر گرم ۲۴ عیار
fair_gold_18k     = base_24k_per_gram × (750.0 / 999.9)
fair_gold_24k     = base_24k_per_gram
pure_gram_coin    = weight × (900.0 / 999.9)
fair_coin         = pure_gram_coin × base_24k_per_gram + minting_cost(symbol)
```

`[کد]` `pricer.py:86-93` — dispatch:
- `IR_GOLD_MELTED` → `MESGHAL_GRAMS × fair_gold_18k` (یعنی ۴.۶۰۸۳ گرم ۱۸ عیار) — دلیل در docstring: «بازار آب‌شده را مثقالی قیمت می‌زند» (GS-05).
- `IR_GOLD_18K` → گرم ۱۸ عیار؛ `IR_GOLD_24K` و `IR_GOLD_1G` → گرم ۲۴ عیار؛ سکه‌ها → فرمول سکه.

**مفروضات عددی (تأییدشده با اجرا):** با `XAU = 2750` و `USD = 68,000`:

| کمیت | مقدار |
|---|---|
| `base_24k_per_gram` | `6,012,189.61` تومان/گرم |
| `fair_gold_18k` | `4,509,593.17` تومان/گرم |
| `IR_GOLD_MELTED` | `20,781,558.18` تومان/مثقال |
| `IR_COIN_EMAMI` | `44,091,825.46` = `44,011,825.46` طلا + `80,000` ضرب |
| `IR_COIN_HALF` / `QUARTER` / `1G` | `22,053,206.97` / `11,036,603.49` / `5,480,626.92` |

**ناسازگاری عیار بین دو ماژول:** `[کد]` pricer از نسبت `750/999.9 = 0.750075` استفاده می‌کند، اما `bubbler.py:34-38` برای ۱۸ عیار `750/1000 = 0.750` و برای ۲۴ عیار `999.9/1000` می‌گیرد. اختلاف ~۰.۰۱٪ است (کم‌اثر ولی دو تعریف از یک کمیت).

## ۳.۲ حباب و دلار ضمنی (`bubbler.py`)

`[کد]` `bubbler.py:57-71`:

```
bubble_abs   = market − fair
bubble_pct   = bubble_abs / fair × 100                (اگر fair > 0، وگرنه 0)
pure_w       = weight × purity   (سکه) | 1 × purity (طلای وزنی) | 4.6083 × purity (آب‌شده)
implied_usd  = market × 31.1034768 / (pure_w × xau_usd)   (اگر pure_w > 0)
```

`[استنباط]` ساده‌سازی جبری: چون `fair − mint = pure_w × (xau_usd × usd_irt / 31.1034768)`:

```
implied_usd = usd_irt × market / (fair − mint) = usd_irt × (1 + bubble_pct/100) × fair/(fair − mint)
```

یعنی **implied_usd اطلاعات مستقلی نیست**؛ یک تبدیل یکنواخت از همان `bubble_pct` است (برای طلای بدون ضرب دقیقاً `usd_irt × (1+bubble)`). برای سکه، هزینهٔ ضرب آن را ~`mint/fair` بالا می‌برد (در مثال بالا `+0.18%`).

مثال تأییدشده: `market = 53,000,000`, `fair = 44,091,825.46` → `bubble_pct = 20.20`, `bubble_abs = 8,908,175`, `implied_usd = 81,895` (در برابر دلار بازار ۶۸,۰۰۰).

## ۳.۳ شکاف درهم (`parity.py`)

`[کد]` `parity.py:12-26`:

```
aed_parity_usd = aed_irt × 3.6725
aed_gap_pct    = (usd_irt − aed_parity_usd) / aed_parity_usd × 100
```

مثال: `aed = 18,520`, `usd = 68,000` → parity `68,014.70` → gap `−0.022%`.

## ۳.۴ اندیکاتورها (`signal_engine.py`)

- RSI ویلدر `[کد] :69-85`: میانگین سادهٔ `period` تغییر اول، سپس `avg = (avg×(n−1) + x)/n`. اگر `avg_loss == 0` → `100.0` (`:82-83`).
- EMA `[کد] :88-97`: `alpha = 2/(period+1)`، شروع از `arr[0]` (نه SMA) ⇒ همگرایی کندتر و وابسته به طول سری.
- SMA `[کد] :100-104`: `mean(closes[-period:])`.
- Bollinger `[کد] :107-114`: `std` با `ddof=0` (جامعه)، `width_pct = 2k·σ/SMA×100`.
- MACD `[کد] :117-141`: `EMA12 − EMA26`, سیگنال `EMA9` روی خط MACD؛ `bullish = hist > 0`.
- EMA bubble `[کد] :144-151`: `(last − EMA20)/EMA20 × 100`.

## ۳.۵ NAV، BPR، جریان (`nav_checker.py`)

`[کد]`:

```
nav                = اولین مقدار truthy از (nav_issue, nav_redemption)      # :46-58
nav_7d_pct         = (nav − nav_{7d}) / nav_{7d} × 100   اگر nav_{7d} > 0   # :186-188
bpr                = buy_real_value / sell_real_value    اگر sell > 0، وگرنه 0  # :114-116
net_inflow         = buy_real_value − sell_real_value                      # :118
bubble_abs/pct     = market_price − nav ؛ bubble_abs/nav×100               # :190-195
```

`[کد]` در snapshot، BPR و inflow کل صندوق‌ها **تجمیعی** محاسبه می‌شوند: `bpr = Σbuy / Σsell`, `net_inflow = Σ(buy − sell)` (`snapshot_service.py:298-303`).

## ۳.۶ Black-76 (خلاصهٔ فرمول؛ تحلیل در بخش ۶)

`[کد]` `black76.py:87-92`:

```
d1 = (ln(F/K) + 0.5σ²T) / (σ√T)
d2 = d1 − σ√T
C  = e^{−rT} [F·N(d1) − K·N(d2)]
P  = e^{−rT} [K·N(−d2) − F·N(−d1)]
```

## ۳.۷ جدول کامل ثابت‌ها و آستانه‌ها

| نام | مقدار | واحد | محل استفاده | قابل پیکربندی؟ |
|---|---|---|---|---|
| `TROY_OUNCE_GRAMS` | `31.1034768` (`constants.py:10`) | گرم | `pricer.base_24k`, `bubbler.implied_usd` | خیر (ثابت فیزیکی) |
| `GOLD_PURITY_24K` | `999.9` (`:11`) | در هزار | مخرج نسبت عیار | خیر |
| `GOLD_PURITY_18K` | `750.0` (`:12`) | در هزار | طلای ۱۸ عیار و آب‌شده | خیر |
| `GOLD_PURITY_COIN` | `900.0` (`:14`) | در هزار | وزن خالص سکه | خیر |
| `MESGHAL_GRAMS` | `4.6083` (`:15`) | گرم | `fair_value(IR_GOLD_MELTED)` | خیر |
| `AED_PEG` | `3.6725` (`:16`) | درهم/دلار | `parity` | خیر (پگ رسمی) |
| `COIN_WEIGHTS` | ۸.۱۳۳ / ۴.۰۶۶ / ۲.۰۳۳ / ۱.۰۱۰ (`:19-26`) | گرم | `pricer`, `bubbler` | خیر |
| `MINTING_COST_TOMAN` | `50_000.0` (`:38`) | **تومان (نام) / IRR (کامنت `services`)** | fallback ضرب | خیر |
| `COIN_MINTING_COSTS` | ۸۰k / ۸۰k / ۵۰k / ۳۵k / ۱۵k / ۱۵k (`:39` ← `services/gold/constants.py:102-109`) | **واحد مبهم** | `fair_coin` | فقط با ویرایش `services/gold/constants.py` |
| `VEHICLE_FEES.etf` | buy/sell `0.15%` (`:42-48`) | درصد | `_calc_fee` فقط خرید | ویرایش فایل |
| `VEHICLE_FEES.cert` | `0.24%` | درصد | همان | ویرایش فایل |
| `VEHICLE_FEES.melted` | buy `0.30%`, sell `0.50%` | درصد | همان (sell استفاده نمی‌شود) | ویرایش فایل |
| `VEHICLE_FEES.coin` | `1.50%` | درصد | همان | ویرایش فایل |
| `VEHICLE_FEES.jewelry` | buy `18%`, sell `25%`, VAT `9%` | درصد | همان (VAT استفاده نمی‌شود) | ویرایش فایل |
| `SCORE_WEIGHTS` | bubble 20, nav 18, tsetmc 18, technical 15, parity 15, fund_flow 14 (`:52-59`) | امتیاز | `scorer` | فقط با حفظ `assert` جمع=۱۰۰ |
| `BUBBLE_GREEN_MAX` | `8.0` (`:63`) | درصد | `score_bubble` | ویرایش فایل |
| `BUBBLE_YELLOW_MAX` | `15.0` (`:64`) | درصد | `score_bubble` | ویرایش فایل |
| `BUBBLE_ORANGE_MAX` | `22.0` (`:65`) | درصد | `score_bubble` | ویرایش فایل |
| `NAV_GREEN_MAX` | `0.5` (`:69`) | درصد P/NAV | `score_nav` | ویرایش فایل |
| `NAV_YELLOW_MAX` | `1.5` (`:70`) | درصد | `score_nav` | ویرایش فایل |
| `NAV_RED_MAX` | `3.0` (`:71`) | درصد | `score_nav` | ویرایش فایل |
| `NAV_PREMIUM_BUY_BELOW` | `−2.0` (`:79`) | درصد | `antigravity/calculations.py`, `services/fund_scoring.py` — **نه scorer** | ویرایش فایل |
| `NAV_PREMIUM_SELL_ABOVE` | `+3.0` (`:80`) | درصد | همان | ویرایش فایل |
| `TSETMC_BPR_GREEN/YELLOW/ORANGE` | `2.0 / 1.5 / 1.0` (`:83-85`) | نسبت | `score_tsetmc` | ویرایش فایل |
| `TSETMC_INFLOW_GREEN/YELLOW` | `5e9 / 1e9` (`:86-87`) | تومان | `score_tsetmc` | ویرایش فایل |
| `RSI_GREEN_MIN/GREEN_MAX/YELLOW_MAX/DANGER` | `30 / 45 / 60 / 70` (`:90-93`) | RSI | `score_technical` | ویرایش فایل |
| `PARITY_GREEN/YELLOW/RED_MAX` | `0.5 / 1.5 / 3.0` (`:96-98`) | درصد | `score_parity` | ویرایش فایل |
| `FUND_FLOW_GREEN_MIN/YELLOW_MIN` | `1.0 / 0.0` (`:101-102`) | درصد ۷ روزه | `score_fund_flow` | ویرایش فایل |
| `SCORE_GREEN_MIN/YELLOW_MIN` | `80 / 55` (`:106-107`) | امتیاز | `compute_score` | ویرایش فایل |
| `HARDSTOP_TSE_CRASH_PCT` | `−5.0` (`:111`) | درصد روزانه | `check_hard_stops` | ویرایش فایل |
| `HARDSTOP_DXY_SPIKE_PCT` | `3.0` (`:112`) | درصد | همان | ویرایش فایل |
| `HARDSTOP_USD_SPIKE_PCT` | `5.0` (`:113`) | درصد | همان | ویرایش فایل |
| `PORTFOLIO_TARGET_WEIGHTS` | etf 40 / melted 40 / coin 20 (`:168-172`) | درصد | `portfolio_history` (بیرون دامنه) | ویرایش فایل |
| `PORTFOLIO_DRIFT_TOLERANCE_PCT` | `10.0` (`:176`) | درصد | `alert_engine` | ویرایش فایل |
| `PORTFOLIO_CONCENTRATION_WARN_PCT` | `60.0` (`:178`) | درصد | `alert_engine` | ویرایش فایل |
| `PORTFOLIO_DRAWDOWN_WARN_PCT` | `15.0` (`:180`) | درصد | `alert_engine` | ویرایش فایل |
| `PORTFOLIO_PERFORMANCE_WINDOW_DAYS` | `90` (`:182`) | روز | `api.PORTFOLIO_PERFORMANCE_WINDOW_DAYS` | ویرایش فایل |
| `VALID_XAU_RANGE` | `(1000, 10000)` (`:212`) | دلار/اونس | `snapshot_service._soft_check` (هشدار فقط) | ویرایش فایل |
| `VALID_USD_RANGE` | `(10_000, 10_000_000)` (`:213`) | تومان | همان | ویرایش فایل |
| `VALID_BUBBLE_PCT_RANGE` | `(−50, 100)` (`:214`) | درصد | همان | ویرایش فایل |
| `VALID_PARITY_GAP_RANGE` | `(−10, 10)` (`:215`) | درصد | همان | ویرایش فایل |
| `MAX_MARKET_DATA_AGE_DAYS` | `7` (`nav_checker.py:25`) | روز | `_fund_market_data` | ویرایش فایل |
| `SIGNAL_COOLDOWN_SEC` | `600` (`live_signals.py:21`) | ثانیه | `detect_and_broadcast` | ویرایش فایل |
| `IRAN_RISK_FREE_RATE` | `0.30` (`black76.py:28`) | سالانه | `black76_price/greeks` | فقط با پارامتر `rate` |
| `DEFAULT_IV` | `0.25` (`black76.py:31`) | سالانه | همان | فقط با پارامتر `iv` |
| مقاومت/جهش در `live_signals` | `1.5% / 2% / 3% / 25` (`:72,83,109,131`) | درصد | spike قیمت، USD، AED، حباب | **خیر — hardcode و خارج از `constants.py`** |
| باند ماهانه impacy (macro) | `30` روز (`macro_news.py:167`) | روز | `compute_macro_multiplier` | خیر |
| `LADDER_PATTERNS` | 20/40/40, 30/40/30, 50/30/20 (`dca_planner.py:43-60`) | کسر سرمایه | `plan_dca` | ویرایش فایل |
| Stop/Take DCA | 5/20, 8/25, 12/35 (`dca_planner.py:124-128`) | درصد | `DCAPlan` | ویرایش فایل |
| آستانه‌های `pattern_detector` | `60`, `20%`, `10%`, `7`, `5%`, `2%` (`:68,75,100,120,139`) | ترکیبی | detectors | خیر |
| آستانه‌های `backtest` | `35`, `30`, `5` (`backtest.py:49,57,110`) | تعداد روز | backtest | خیر |

## ۳.۸ منبع / استدلال هر فرمول

| فرمول | منبع در کد | ارزیابی |
|---|---|---|
| `base_24k_per_gram` (تبدیل اونس×دلار/۳۱.۱۰۳۵) | `pricer.py:1-9` (docstring) | `[کد]` ریاضی صحیح و استاندارد؛ **بدون منبع مکتوب**. |
| وزن/عیار سکه | `services/gold/constants.py:36-52` با کامنت «Source/assumption: Standard Iranian coin specs» | `[کد]` صریحاً «assumption»؛ **بدون منبع**. |
| `MESGHAL_GRAMS = 4.6083` | `services/gold/constants.py:14` («Iranian market convention») | **بدون منبع** (عدد رایج بازار، بدون ارجاع). |
| حباب = (market−fair)/fair | `bubbler.py:1-8` | تعریف قراردادی؛ **بدون منبع**. |
| `implied_usd` | `bubbler.py:63-68` با اشتقاق سه‌خطی | ریاضی سازگار، ولی نامش مستقلازحباب را القا می‌کند (`[استنباط]`). |
| `aed_parity_usd = aed×3.6725` | `parity.py:1-6` | پگ رسمی درهم؛ **بدون منبع در کد** (پگ شناخته‌شده است). |
| RSI/EMA/MACD/Bollinger | `signal_engine.py` بدون docstring منبع | فرمول‌های استاندارد TA؛ **بدون منبع**. |
| BPR / net inflow | `nav_checker.py:112-119` | تعریف ساده؛ **بدون منبع**. |
| وزن‌های ۲۰/۱۸/۱۸/۱۵/۱۵/۱۴ | `constants.py:54-59` | **بدون منبع**. هیچ سند یا بک‌تستی برای توجیه انتخاب وزن‌ها در ریپو نیست. |
| آستانه‌های ۸/۱۵/۲۲ و ۸۰/۵۵ و … | `constants.py:63-107` | **بدون منبع**. عددهای «گرد و باورپذیر». |
| Black-76 | `black76.py:1-19` + `PLAN_GOLD.md` (بخش «منابع بیشتر») → ارجاع کلی به «GapGPT Gold Analysis» | فرمول استاندارد (Hull) است؛ ولی «سند مرجع» یک لینک کلی است، نه اشتقاق. تست `test_black76.py` به Hull Example 17.1 ارجاع می‌دهد (اگرچه اعداد مثال با پارامترهای تست یکی نیست). |
| DCA ladder و stop/take | `dca_planner.py:43-60, 124-128` | **بدون منبع**. |
| `historical_hit_rate = 62.0/58.0` | `pattern_detector.py:114,133` | **بدون منبع و بدون محاسبه** — عدد ثابت در کد. |
| آستانه‌های hard stop | `hard_stops.py:1-13` (docstring با مثال) | **بدون منبع**؛ فقط توضیح کیفی. |

---

# ۴. تحلیل امتیازدهی و hard stop

## ۴.۱ وزن‌ها و جدول کامل باندها

`[کد]` `constants.py:52-59` و `scorer.py:66-169`:

| کامپوننت | وزن | شرط | امتیاز | خط |
|---|---|---|---|---|
| **bubble** (حباب سکه امامی) | ۲۰ | `bubble < 8` | ۲۰ | `:71` |
| | | `8 ≤ bubble < 15` | `int(20×0.75)=15` | `:74` |
| | | `15 ≤ bubble < 22` | `int(20×0.4)=8` | `:77` |
| | | `bubble ≥ 22` | ۰ | `:79` |
| | | `None` | ۰ («داده موجود نیست») | `:68-69` |
| **nav** (P/NAV صندوق عیار) | ۱۸ | `nav ≤ 0.5` | ۱۸ | `:86` |
| | | `≤ 1.5` | `int(18×0.75)=13` | `:89` |
| | | `≤ 3.0` | `int(18×0.3)=5` | `:92` |
| | | `> 3.0` | ۰ | `:94` |
| **tsetmc** (BPR + inflow) | ۱۸ | BPR `≥2.0` / `≥1.5` / `≥1.0` / `<1` | ۱۱ / ۸ / ۴ / ۰ | `:105-113` |
| | | inflow `>5e9` / `>1e9` / else | ۷ / ۴ / ۰ | `:115-119` |
| | | `bpr is None` | ۰ (کل کامپوننت) | `:101` |
| **technical** (RSI ۱۴ XAU) | ۱۵ | `30 ≤ rsi ≤ 45` | ۱۵ | `:131` |
| | | `rsi < 30` | `int(15×0.6)=9` | `:134` |
| | | `45 < rsi ≤ 60` | `int(15×0.7)=10` | `:137` |
| | | `60 < rsi ≤ 70` | `int(15×0.3)=4` | `:139` |
| | | `rsi > 70` | ۰ | `:140` |
| **parity** (\|gap\| درهم) | ۱۵ | `< 0.5` | ۱۵ | `:147` |
| | | `< 1.5` | `int(15×0.7)=10` | `:149` |
| | | `< 3.0` | `int(15×0.3)=4` | `:151` |
| | | `≥ 3.0` | ۰ | `:152` |
| **fund_flow** (NAV ۷ روزه) | ۱۴ | `≥ 1` | ۱۴ | `:162` |
| | | `≥ 0` | `int(14×0.6)=8` | `:164` |
| | | `≥ −1` (عدد جادویی، خارج از constants) | `int(14×0.3)=4` | `:166` |
| | | `< −1` | ۰ | `:167` |

**باندهای تصمیم** `[کد]` `scorer.py:211-219` + `constants.py:106-107`:
- hard stop فعال → `RED` (بی‌توجه به امتیاز)
- `total ≥ 80` → `GREEN`
- `55 ≤ total < 80` → `YELLOW`
- `total < 55` → `RED`

## ۴.۲ فرمول نرمال‌سازی — ریشهٔ خطای «GREEN کاذب»

`[کد]` `scorer.py:203-209`:

```
available_weight = Σ وزن کامپوننت‌هایی که ورودی‌شان is not None
total            = round(raw_total × 100 / available_weight)
data_coverage_pct = float(available_weight)          # در واقع «وزن پوشش‌داده‌شده»، نه درصد پوشش
```

مثال عددی گام‌به‌گام (اجرا شده):

| ورودی | مقدار | امتیاز کامپوننت |
|---|---|---|
| `bubble_pct` | `7.9` | ۲۰ |
| `nav_bubble_pct` | `None` | — |
| `bpr`, `net_inflow` | `None`, `None` | — |
| `xau_rsi` | `None` | — |
| `aed_gap_pct` | `None` | — |
| `nav_7d_pct` | `None` | — |

`raw_total = 20`، `available_weight = 20`، `total = round(20×100/20) = 100`، `decision = GREEN`.
یعنی یک منبع داده از شش منبع، **امتیاز کامل و چراغ سبز خرید** می‌دهد. `[کد]` `data_coverage_pct = 20.0` در `ScoreResult` هست، ولی نه در `ScoreBlock`/schemas منتشر می‌شود و نه بر تصمیم اثر دارد؛ تنها مصرف آن یک self-check داخلی است (`snapshot_service.py:361`) که فقط وقتی پوشش ۱۰۰٪ است اجرا می‌شود.

`[استنباط]` ریشهٔ مشکل: نرمال‌سازی GS-02 برای این ساخته شد که «نبودِ NAV امتیاز را زیر آستانه نکشاند»، ولی شرط لازم (حداقل پوشش داده) اضافه نشد. راه‌حل `[پیشنهاد]`: امتیاز مطلق + قاعدهٔ صریح `if available_weight < 60: decision = "NO_DATA"` یا نمایش `total*coverage` به‌عنوان معیار تصمیم.

## ۴.۳ مثال عددی امتیاز (سناریوی زرد — هر شش جزء موجود)

ورودی‌ها (مطابق `tests/gold_desk/test_scorer.py:150-165`):

| ورودی | مقدار | کامپوننت | محاسبه | امتیاز |
|---|---|---|---|---|
| bubble | ۱۰.۰٪ | bubble | `8 ≤ 10 < 15` | `int(20×0.75)=15` |
| NAV | ۱.۰٪ | nav | `0.5 < 1.0 ≤ 1.5` | `int(18×0.75)=13` |
| BPR / inflow | ۱.۷ / `2e9` | tsetmc | `≥1.5`→۸ ؛ `>1e9`→۴ | ۱۲ |
| RSI | ۵۵ | technical | `45<55≤60` | `int(15×0.7)=10` |
| \|gap\| | ۱.۰٪ | parity | `<1.5` | `int(15×0.7)=10` |
| NAV 7d | ۰.۵٪ | fund_flow | `≥0` | `int(14×0.6)=8` |

`raw_total = 15+13+12+10+10+8 = 68`؛ `available_weight = 100` ⇒ `total = 68` ⇒ **YELLOW**.

در همین مثال توجه کنید: `int(10.5)` و `int(8.4)` رفتار truncation دارند (نه round)، بنابراین مرزها یک‌طرفه به نفع امتیاز کمتر کج می‌شوند؛ و در `total = round(...)` پایتون از banker's rounding استفاده می‌کند (`round(79.5)=80` ولی `round(78.5)=78`) — یعنی رفتار در مرز باند GREEN ناپیوسته است `[کد]` `:209`.

## ۴.۴ منطق hard stop

`[کد]` `hard_stops.py:28-61`، به‌ترتیب اولویت:

| # | شرط | آستانه | نتیجه | خط |
|---|---|---|---|---|
| ۱ | هر سه ورودی `None` | — | `active=False`, `inputs_missing=True` | `:40-46` |
| ۲ | `tse_daily_change_pct <= −5.0` | `HARDSTOP_TSE_CRASH_PCT` | فعال، دلیل «سقوط شاخص کل» | `:47-51` |
| ۳ | `dxy_daily_change_pct >= +3.0` | `HARDSTOP_DXY_SPIKE_PCT` | فعال، «شوک ارزی جهانی» | `:52-56` |
| ۴ | `usd_irt_daily_change_pct >= +5.0` | `HARDSTOP_USD_SPIKE_PCT` | فعال، «تقاضای سفته‌بازانه» | `:57-61` |

مثال گام‌به‌گام: فرض `TSE = −5.0`، `DXY = +3.5`، `USD = +6.0`. خروجی: شرط ۲ اول برنده می‌شود (`<=` شامل مرز) و **دلیل بقیه گزارش نمی‌شود**؛ سپس `compute_score` با `hard_stop_active=True` حتی اگر `total=100` باشد `decision="RED"` می‌دهد (`scorer.py:212-213`) و `total` دست‌نخورده در پاسخ می‌ماند (این رفتار مستند و تست‌شده است: `test_compute_hard_stop_overrides`).

نکات مهم:
- `[کد]` نابرابری TSE `<=` و DXY/USD `>=` است ⇒ مرز دقیقاً فعال می‌شود؛ اما در آستانه‌های scorer مرزها ترکیبی از `<` و `<=` است (`:71` vs `:86`) — ناسازگاری سبک.
- `[کد]` DXY در `snapshot_service.py:174-184` از `fetch_closes(session,"DXY",2)` می‌آید؛ کامنت خودِ کد می‌گوید منبع تاریخی DXY در DB نیست ⇒ عملاً همیشه `None`. پس شرط ۳ در عمل ارزیابی نمی‌شود.
- `[کد]` تغییر روزانهٔ USD/DXY از همان `fetch_closes` معیوب (بخش ۷، H1) می‌آید ⇒ حتی وقتی داده هست، دو ردیف **قدیمی‌تر** مقایسه می‌شوند.

---

# ۵. Backtest و اعتبار آماری

## ۵.۱ `backtest.py` — بک‌تست سیگنال

**آنچه کد ادعا می‌کند:** «آیا وقتی score>80 بوده، ۳۰ روز بعد بازدهی مثبت بوده؟» (`backtest.py:1-4`).
**آنچه کد انجام می‌دهد:** فیلتر `bubble > bubble_threshold` نسبت به SMA30، سپس بازده ۳۰ ردیف بعدی (`:92-93, 61`). `[کد]` ناسازگاری doc با پیاده‌سازی: هیچ امتیازی محاسبه نمی‌شود؛ دلیلش هم در `:73-75` اعتراف شده («score نیاز به همه componentها دارد»).

### باگ look-ahead

`[کد]` `backtest.py:54`:

```python
sma30 = np.convolve(prices, np.ones(30) / 30, mode="same")
```

با کرنل زوج (`30`) و `mode="same"`، خروجی در ایندکس `i` میانگین پنجرهٔ `[i−14, i+15]` است، نه `[i−29, i]`. سطرهای `i < 30` رد می‌شوند (`:57-58`) ولی برای تمام `i ≥ 30` هنوز ۱۵ قیمت آینده داخل میانگین است.

**تأیید عددی (اجرا شده):** برای سری `100, 101, …, 159` و `i=40`:
- `sma30[40]` با convolve = **۱۳۹.۵**
- میانگین trailing واقعی = **۱۲۵.۵**
- پنجرهٔ واقعی: ایندکس ۲۶ تا ۵۵ (شامل ۱۵ قیمت آینده)

اثر: `bubble = (p − sma)/sma×100` سیستماتیک **کم‌برآورد** می‌شود در روند صعودی (چون SMA آینده بالاتر است) ⇒ روزهای سیگنال کم شمرده می‌شوند و «hit rate» روی نمونهٔ گزینش‌شدهٔ متفاوتی محاسبه می‌شود. این کل نتیجهٔ بک‌تست را بی‌اعتبار می‌کند.

### ایرادهای آماری

`[کد]`:
1. **بازده‌های همپوشان:** هر روز یک پنجرهٔ ۳۰ ردیفی دارد؛ نمونه‌های متوالی ۲۹ روز مشترک دارند ⇒ فرض استقلال نقض می‌شود. تعداد نمونهٔ مؤثر ≈ `n/30`، بنابراین خطای معیار hit rate دست‌کم `√30 ≈ 5.5` برابر بزرگ‌تر از محاسبهٔ ساده است.
2. **بدون بازهٔ اطمینان / بدون آزمون معنا‌داری:** فقط `hit_rate` و یک هشدار برای `n < 5` (`:110-112`).
3. **بدون baseline:** نرخ پایهٔ «بازده ۳۰ روزهٔ مثبت» در کل نمونه گزارش نمی‌شود؛ بدون آن، hit rate ۶۰٪ ممکن است بی‌معنا باشد. `[پیشنهاد]` گزارش هم‌زمان `P(fwd>0 | no signal)` و آزمون دو نسبت.
4. **افق زمانی:** «۳۰ روز» در واقع ۳۰ **ردیف** است (سشن معاملاتی)، نه ۳۰ روز تقویمی — در docstring «۳۰ روز» نوشته شده (`:3`).
5. **هزینه‌ها:** هیچ کارمزد/اسپرد/مالیات در بازده اعمال نمی‌شود (`:61`)، در حالی که `VEHICLE_FEES` وجود دارد و برای سکه ۱.۵٪ رفت‌وبرگشت است.
6. **آستانه روی دادهٔ in-sample انتخاب شده:** `bubble_threshold` پیش‌فرض ۸.۰ دقیقاً همان `BUBBLE_GREEN_MAX` است؛ یعنی آستانهٔ امتیازدهی به‌عنوان آستانهٔ بک‌تست استفاده شده و بعد «توان پیش‌بینی» گزارش می‌شود ⇒ circular / overfit پنهان.

## ۵.۲ `backtest_runner.py` — شبیه‌سازی DCA

### اقتصاد شبیه‌سازی خراب است (Critical)

سه خط، سه اشکال به‌هم‌پیوسته:

```
:100  capital_remaining = 1.0                       # سرمایهٔ نرمال‌شده
:121  amount  = capital_remaining * pct             # کسرِ سرمایهٔ باقی‌مانده
:168  final_value = Σunits × end_price              # بدون بعد (≈ 0.5)
:170  total_return = (final_value / initial_capital − 1) × 100   # تقسیم بر 100,000,000
```

**خروجی واقعی اجرا** روی fixture خودِ تست (`make_closes(90, trend=0.002)`, سرمایه ۱۰۰ میلیون):

```
trades: [(tranche=1, amount=0.3, units=5.7e-09, price=53,088,646),
         (tranche=3, amount=0.21, units=3.5e-09, price=59,730,647)]
final_value      = 0.5475
total_return_pct = -100.0
buy_hold_pct     =  19.46
alpha_pct        = -119.46
max_drawdown_pct =   0.0
```

یعنی محصول در یک بازار صعودی، «۱۰۰٪ ضرر» و «آلفای منفی ۱۱۹٪» نشان می‌دهد. تست `test_metrics_alpha_calculation` فقط رابطهٔ `alpha = total − buy_hold` را چک می‌کند (`test_backtest_runner.py:79-82`) و هرگز بزرگی `total_return` را assert نمی‌کند؛ به همین دلیل ۱۷۰ تست سبز است.

**اشکال تخصیص سرمایه (High):** `amount = capital_remaining × pct` باعث می‌شود سهم‌ها روی «باقی‌مانده» اعمال شوند نه کل سرمایه: ۰.۳۰ + ۰.۷۰×۰.۴۰ + ۰.۴۲×۰.۳۰ = ۰.۷۰۶ از سرمایه، و اگر پله‌ای trigger نشود، بخش بیشتری خاک می‌خورد؛ پول نقد بلااستفاده هم در `final_value` نیست.

**اشکال trigger (High):** `[کد]` `:105-118`
- سه تاریخ خرید **ثابت** `[n/3, 2n/3, n−1]` است (`:103`)؛ استراتژی در واقع «DCA تقویمی» است نه رویدادمحور، و شرط‌ها فقط تعیین می‌کنند «آیا همان روز خرید شود».
- اگر پلهٔ ۱ trigger نشود، `last_buy_price = None` می‌ماند و شرط `tranche_idx == 1 and last_buy_price` نادرست می‌شود ⇒ به شاخهٔ `else` می‌رود و **پلهٔ ۲ بی‌قید و شرط خرید می‌کند** (`:111-118`). در اجرای بالا نیز دقیقاً همین اتفاق افتاد: پله‌های ۱ و ۳ اجرا شدند و پلهٔ ۲ با شرط اصلاح ۳–۵٪ رد شد (بدون آنکه کسی متوجه شود).

### متریک‌های نامعتبر (High)

- **max drawdown همیشه صفر:** `[کد]` `:182-184`:

  ```python
  values = np.array([t.units for t in trades])
  portfolio = np.cumsum(values) * end_price      # صعودی یکنوا
  peak = np.maximum.accumulate(portfolio)
  drawdown = (peak − portfolio)/peak × 100       # = 0 همیشه
  ```

  `units` (مثبت) با `cumsum` جمع می‌شود و در قیمت پایانی ضرب می‌شود؛ مسیر ارزش پرتفوی در طول زمان محاسبه نشده است. اجرا: `maxdd = 0.0`.
- **Sharpe، شارپ استراتژی نیست:** `[کد]` `:189-197` از بازده‌های روزانهٔ **دارایی پایه** محاسبه می‌شود، نه از NAV استراتژی (که فقط ۳ نقطه دارد). `rf = 0` فرض شده و `252` برای داده‌ای که ممکن است سشن‌های گسسته داشته باشد نامعتبر است.
- **hit rate سطحی:** `[کد]` `:175` `successful = تعداد معاملاتی که price < end_price` — این «سودآوری» نیست، فقط «قیمت خرید زیر قیمت پایانی» است؛ با کارمزد و وزن‌های متفاوت پله‌ها هم‌ارز نیست.
- **`n_successful`/`alpha` بدون معنا:** `alpha` اختلاف دو عدد با فرض سرمایه‌گذاری کامل است، در حالی که در عمل ~۳۰–۵۰٪ سرمایه نقد مانده.
- **تاریخ‌ها:** `[کد]` `:69-77` رشتهٔ تاریخ شمسی را با `%Y-%m-%d` پارس می‌کند ⇒ `date(1405, …)`; ثم `period_start/period_end` در API به‌صورت ISO نمایش داده می‌شود (`api.py:536-539`) و سال ۱۴۰۵ را به کاربر نشان می‌دهد (اگر مدل، `str` برگرداند؛ `GoldCoinHistoryModel.date` از نوع `String(20)` است — `brsapi/models/commodity.py:54`).

## ۵.۳ اعتبار آماری کلی

| موضوع | وضعیت | توضیح |
|---|---|---|
| طول نمونه | ضعیف | پیش‌فرض ۹۰ ردیف؛ بسته به تعداد ردیف‌های واقعی ~۳۰–۹۰ روز سیگنال با همپوشانی ⇒ نمونهٔ مؤثر ~۱–۳ |
| out-of-sample | ندارد | هیچ split یا walk-forward وجود ندارد |
| آزمون معنا‌داری | ندارد | هیچ p-value/CI |
| هزینهٔ معامله | ندارد | کارمزد، اسپرد، مالیات صفر |
| سوگیری انتخاب | دارد | آستانه از همان `constants` امتیازدهی گرفته شده |
| look-ahead | دارد | `backtest.py:54` |
| داده‌های گمشده | خفه می‌شود | `except Exception → []` و سپس `sample_warning` عمومی |
| تکرار منطق | دارد | سه پیاده‌سازی مستقل از SMA30/حباب |

`[پیشنهاد]` حداقل: (۱) SMA trailing با `prices[i−29:i+1].mean()` یا `pandas.rolling(30)`، (۲) بازده‌های غیرهمپوشان یا Newey–West، (۳) گزارش baseline، (۴) mark-to-market روزانه برای drawdown و Sharpe، (۵) اعمال `VEHICLE_FEES`، (۶) تفکیک صریح in-sample/out-of-sample.

---

# ۶. Black-76 و DCA

## ۶.۱ درستی ریاضی Black-76

**قیمت‌گذاری:** `[کد]` `black76.py:87-92` فرمول استاندارد است و **درست** پیاده شده. تست‌ها این را تأیید می‌کنند:
- `test_put_call_parity` (`tests/gold_desk/test_black76.py:39-46`): `C − P = e^{−rT}(F − K)` با خطای `< 0.01` — این قوی‌ترین شاهد صحت است.
- `test_black76_atm` فقط بازهٔ `5.0 < call < 6.0` را چک می‌کند (assert ضعیف، ولی عدد درست است).

**یونانی‌ها:**

| یونانی | فرمول کد | ارزیابی |
|---|---|---|
| `delta` | `e^{−rT}N(d1)` (`:112`) | `[کد]` صحیح برای call در Black-76 (با تنزیل) — تست `0 < delta < 1` |
| `gamma` | `e^{−rT}φ(d1)/(Fσ√T)` (`:113`) | صحیح |
| `vega` | `e^{−rT}Fφ(d1)√T/100` (`:115`) | صحیح (به ازای ۱٪) |
| `theta` | `[−Fφσe^{−rT}/(2√T) − rFe^{−rT}N(d1) + rKe^{−rT}N(d2)]/365` (`:117-122`) | **علامت جملهٔ نرخ اشتباه** |
| `rho` | `−T(FN(d1)−KN(d2))e^{−rT}/100` (`:123`) | صحیح |

**اثبات خطای theta:** `C = e^{−rT}(F N(d1) − K N(d2))` و با اتحاد `Fφ(d1) = Kφ(d2)`:

```
∂C/∂T = e^{−rT}[Fφ(d1)σ/(2√T) − r(FN(d1) − KN(d2))]
θ_day  = −∂C/∂T/365 = [−Fφσe^{−rT}/(2√T) + r e^{−rT}(FN(d1) − KN(d2))]/365
```

کد ترم آخر را با علامت منفی دارد. **تأیید عددی** (`F=K=100, T=0.25, iv=0.25, r=0.30`):

| روش | theta روزانه |
|---|---|
| کد | `−0.029101` |
| finite difference (`−(C(T+1d) − C(T))`) | `−0.021412` |
| فرمول اصلاح‌شده | `−0.021501` |

یعنی کد قدر مطلق theta را ~۳۶٪ بیش‌برآورد می‌کند (اختلاف = `2 × r·C/D`). تست `test_greeks_theta_negative` فقط علامت را چک می‌کند، پس این خطا پنهان مانده است.

**سایر ایرادها:**
- `[کد]` `black76_greeks` هیچ اعتبارسنجی ورودی ندارد (`:97-108`)؛ `iv=0` یا `T=0` → `ZeroDivisionError`، `F<=0` → `math domain error`. مسیر عمومی `price_option` از `black76_price` اعتبارسنجی می‌گیرد، اما هر مصرف‌کنندهٔ مستقیم `greeks` محافظت ندارد.
- `[کد]` `years_to_expiry` تاریخ گذشته را با `max(..., 1e-6)` به «۱ روز» تبدیل می‌کند (`:65`) ⇒ قیمت‌گذاری یک آپشن منقضی به‌جای خطا، عدد تقریباً صفر برمی‌گرداند. `[پیشنهاد]` `ValueError` برای `expiry < today`.
- `[کد]` زمان با `date.today()` (منطقهٔ زمانی سیستم) محاسبه می‌شود، در حالی که بقیهٔ کد از `core.time.now_tehran/utc_now_naive` استفاده می‌کند ⇒ در سرور UTC، در ساعات ۲۰:۳۰–۲۴ تهران، `T` یک روز اختلاف می‌گیرد.
- `[کد]` در `protective_collar` فرض `F ≈ spot` است (`:189`) و `cost = put − call` بدون تنزیل جداگانه (هر دو قبلاً تنزیل شده‌اند) — از نظر علامت درست است، اما «هزینهٔ نزدیک صفر» یک ادعای تبلیغاتی است، نه خاصیت فرمول.

## ۶.۲ ورودی‌ها از کجا می‌آیند؟

`[کد]` تنها مسیر production: `POST /options/price` و `POST /options/collar` (`api.py:606-680`):

| پارامتر | منبع | مقدار پیش‌فرض | ارزیابی |
|---|---|---|---|
| `forward` | query param کاربر | اجباری | هیچ‌جا از NAV/spot/فیوچرز بازار ساخته نمی‌شود؛ مصرف‌کننده باید دستی بدهد (`[کد]`) |
| `strike` | query param | اجباری | — |
| `expiry` | query param `YYYY-MM-DD` | اجباری | تاریخ **میلادی**؛ در بازار ایران سررسیدها شمسی/تقویمی هستند `[استنباط]` |
| `iv` | query param | `0.25` (`api.py:614`, `black76.py:31`) | **IV بازار خوانده نمی‌شود**؛ هیچ سطح نوسان، هیچ سری تاریخی IV در دامنه وجود ندارد (جدول IV در jobها ذکر شده اما خارج از دامنه) |
| `rate` | query param | `0.30` (`api.py:615`, `black76.py:28`) | «نرخ اخزا ~۳۰٪» فقط در docstring؛ بدون منبع و بدون خواندن از DB |

**محدودیت‌های بازار ایران** `[استنباط]` (با برچسب استنباط، چون منبع در کد نیست):
1. Black-76 نیاز به `F` قابل‌مشاهده و قرض‌پذیری/فروش استقراضی برای آربیتراژ دارد؛ در نبود بازار عمیق اختیار روی صندوق طلا، `F` تنها یک **فرض** است.
2. نرخ بدون ریسک ۳۰٪ ثابت، در شرایط تغییر نرخ بهره، قیمت put/call را به‌شدت جابه‌جا می‌کند: با `r` از ۰.۳۰ به ۰.۴۰، `e^{−rT}` برای ۹۰ روز از ۰.۹۲۸ به ۰.۹۰۶ می‌رود (≈۲.۴٪ روی قیمت) و `rho` نیز اثر می‌گذارد.
3. `iv = 25%` برای صندوق طلای ایران با نوسان روزانهٔ چند درصد و شکاف‌های ارزی، بسیار کم است `[استنباط]`. بدون کالیبراسیون روی قیمت‌های واقعی، اعداد «دقیق‌نما» ولی بی‌مبنا هستند.
4. مالیات، کارمزد و محدودیت نقدشوندگی در مدل نیست؛ collar برای سرمایه‌گذار ایرانی با هزینهٔ فرصت و ریسک پایه (basis) قابل پوشش کامل نیست.

## ۶.۳ DCA planner

`[کد]` `dca_planner.py`:

```
ladder(conservative) = 20/40/40 ; balanced = 30/40/30 ; aggressive = 50/30/20      # :43-60
amount_i   = total_capital × pct_i           (جمع = ۱۰۰٪ سرمایه)                  # :107-108
fee_i      = amount_i × buy_pct(vehicle)     (فقط خرید)                           # :71-75, :109
total_fee  = Σ fee_i                                                              # :110
net_investable = total_capital − total_fee                                        # :135
```

**ایرادها:**
1. `[کد]` جمع `amount_irt`ها = کل سرمایه، اما `net_investable` = سرمایه − کارمزد ⇒ **پلن با پول موجود سازگار نیست**: اگر کاربر ۱۰۰ میلیون داشته باشد، پله‌ها ۱۰۰ میلیون می‌خواهند + ۱۵۰ هزار کارمزد.
2. `[کد]` کارمزد **فقط خرید** است؛ `sell_pct` و `vat_pct` در `VEHICLE_FEES` هرگز استفاده نمی‌شوند. برای `jewelry` با VAT ۹٪، برآورد به‌شدت کم است.
3. `[کد]` `_recommend_vehicle` وابسته به امتیاز است (`≥75 → etf`, `≥60 → cert`, else `melted`) و **`risk_profile` را نادیده می‌گیرد**؛ یک کاربر محافظه‌کار با امتیاز ۸۰ همان ETF می‌گیرد که کاربر تهاجمی.
4. `[کد]` `stop_loss_pct`/`take_profit_pct` ثابت‌های پروفایل هستند (`5/20`, `8/25`, `12/35`) و به نوسان بازار، افق سرمایه‌گذاری یا کارمزد ربطی ندارند.
5. `[کد]` `trigger` فقط یک **رشتهٔ فارسی** است (`:44-59`)؛ هیچ اجرای ماشینی ندارد، در حالی که `get_plan_status` آن را به‌عنوان «شرط پلهٔ بعدی» به UI می‌دهد (`portfolio.py:497-510`) ⇒ کاربر باید دستی قضاوت کند.
6. `[کد]` `_calc_fee` برای vehicle ناشناس بی‌صدا `etf` را جایگزین می‌کند (`:75`)، در حالی که `plan_dca` برای `risk_profile` ناشناس خطا می‌دهد — ناسازگاری سیاست اعتبارسنجی.
7. `[پیشنهاد]` پیشنهاد می‌شود `amount_i = (total_capital − total_fee) × pct_i` و کارمزد فروش/مالیات در پیش‌بینی بازده لحاظ شود.

---

# ۷. باگ‌ها و ریسک‌ها (جدول با اولویت Critical/High/Medium/Low)

| ID | اولویت | محل | نوع | توضیح | اثر | پیشنهاد |
|---|---|---|---|---|---|---|
| C1 | Critical | `backtest_runner.py:100,121,168,170` | واحد/اقتصاد | `units` از سرمایهٔ `1.0` ساخته می‌شود، `total_return` بر `initial_capital` تقسیم می‌شود | `total_return_pct` همیشه ≈`−100٪`، `alpha` ≈`−۱۱۹٪` در بازار صعودی؛ خروجی `/backtest/strategy` بی‌معنا | `amount = total_capital × pct` یا `final_value × initial_capital`؛ assert روی بزرگی بازده در تست |
| C2 | Critical | `backtest.py:54` | look-ahead bias | `np.convolve(..., "same")` میانگین ۱۵ قیمت آینده | نتیجهٔ بک‌تست و hit rate بی‌اعتبار | `prices[i−29:i+1].mean()` یا `pandas.rolling` |
| C3 | Critical | `pattern_detector.py:54` | تقویم (GS-03) | cutoff میلادی در برابر ستون شمسی | `/patterns` همیشه خالی؛ `detect_patterns` هیچ الگویی نمی‌بیند | استفاده از `jalali_days_ago` مانند `backtest.py:38` و `backtest_runner.py:58` |
| C4 | Critical | `portfolio.py:226-245` | FIFO | `lots` سراسری، بدون کلید `symbol` | سود تحقق‌یافتهٔ مالیات اشتباه (اثبات: `4500` از لات نماد دیگر) | `lots: dict[str, list]`؛ گروه‌بندی بر `t.symbol` |
| C5 | Critical | `scorer.py:208-209` | منطق تصمیم | نرمال‌سازی روی وزن موجود، بدون حداقل پوشش | با ۱ کامپوننت از ۶ → `100/GREEN` | `if available_weight < threshold: decision="NO_DATA"` یا امتیاز مطلق |
| H1 | High | `signal_engine.py:29,48` | برش لیست | `reversed(closes[-days:])` جدیدترین ۱۰ ردیف را حذف می‌کند | RSI/EMA ۱۰ سشن کهنه؛ «تغییر روزانهٔ USD/DXY» برای hard stop ~۱۰ روز قدیمی (`snapshot_service.py:146,177`) | `list(reversed(closes))[:days]` |
| H2 | High | `backtest_runner.py:182-184` | متریک | `cumsum(units) × end_price` صعودی است | `max_drawdown` همیشه ۰ | ارزش روزانهٔ پرتفوی (mark-to-market) محاسبه شود |
| H3 | High | `backtest_runner.py:103-121` | منطق استراتژی | پله‌ها روی سرمایهٔ باقی‌مانده و تاریخ‌های ثابت؛ پلهٔ ۲ در نبود پلهٔ ۱ بی‌شرط اجرا می‌شود | شبیه‌سازی، استراتژی واقعی را نشان نمی‌دهد؛ ~۳۰–۵۰٪ سرمایه نقد و بی‌اثر | آستانه‌های رویدادمحور + بازبینی پلهٔ قبلی + شمارش نقد |
| H4 | High | `backtest_runner.py:172,189-197` | متریک | `alpha` با فرض سرمایه‌گذاری کامل؛ Sharpe از دارایی پایه نه استراتژی | مقایسهٔ گمراه‌کننده با buy&hold | NAV استراتژی روزانه + Sharpe روی همان |
| H5 | High | `black76.py:117-122` | ریاضی | علامت جملهٔ نرخ در theta معکوس | theta ۳۶٪ بیش‌برآورد (تأیید FD) | `+ r·e^{−rT}(FN(d1)−KN(d2))` |
| H6 | High | `pattern_detector.py:167-170` | look-ahead | `pd_rolling_mean` مقدار `window−1` اول را با میانگین آینده backfill می‌کند | `bubble[i]` برای `i<29` از دادهٔ آینده؛ hit rate بایاس‌دار | `np.nan` نگه داشتن و حذف ردیف‌های نامعتبر در `_detect_mean_reversion` |
| H7 | High | `portfolio.py:420,441-442` | P&L | `pnl_pct=0` وقتی بهای تمام‌شده صفر است؛ `total_cost` شامل دارایی‌های بی‌قیمت ولی `total_value` بدون آن‌ها | درصد سود گمراه‌کننده / جمع‌های ناسازگار در API | `pnl_pct=None` و انتشار `priced_cost` جداگانه؛ یا حذف دارایی بی‌قیمت از `total_cost` |
| H8 | High | `portfolio.py:110-121` | مبنای جریان نقدی | اگر **یک** trade وجود داشته باشد، همهٔ holdings نادیده گرفته می‌شوند؛ `fee_irt` در جریان‌ها نیست | XIRR اسمی/دلاری overstated؛ سرمایه‌گذاری‌های قدیمی بدون trade از بازده حذف می‌شوند | ترکیب دو منبع یا مهاجرت کامل به trades؛ کسر `fee_irt` از جریان خرید |
| M1 | Medium | `portfolio.py:534` | P&L معامله | `pnl = (price − h.buy_price) × qty` برای فروش جزئی؛ بدون کارمزد؛ فقط با `holding_id` | سود تحقق‌یافتهٔ رکورد معامله اشتباه | FIFO روی همان نماد + کسر کارمزد |
| M2 | Medium | `portfolio.py:545-547` | تراکنش | `record_trade` خودش `commit` می‌کند | شکستن اتمی‌بودن تراکنش API؛ تست‌پذیری سخت | commit در لایهٔ API |
| M3 | Medium | `nav_checker.py:46-58` | NAV | `_pick_nav` اولین مقدار truthy از `(issue, redemption)` را می‌گیرد؛ تفاوت دو NAV نادیده می‌شود | P/NAV می‌تواند با NAV ابطال محاسبه شود؛ خطای سیستمی در صندوق‌های با شکاف صدور/ابطال | انتخاب صریح `nav_issue` + گزارش تفاوت |
| M4 | Medium | `nav_checker.py:114-116` | تقسیم | `bpr=0` وقتی `sell_real_value == 0` (نه `None`) | صندوق بدون فروش، BPR=۰ می‌گیرد؛ `available_weight` آن ۱۸ وزن می‌شمارد ⇒ امتیاز ۰ برای «داده ناقص» | بازگرداندن `None` و حذف وزن |
| M5 | Medium | `nav_checker.py:107-113` | کهنگی داده | مقایسهٔ رشته‌ای `str(row.date) < cutoff` (شمسی) | اگر فرمت تاریخ تغییر کند، سقف تازگی بی‌اثر می‌شود | پارس تاریخ + محاسبهٔ اختلاف روز |
| M6 | Medium | `live_signals.py:21,72,83,109,131` | ثابت جادویی | آستانه‌های ۱.۵/۲/۳/۲۵ و cooldown در constants نیستند | تغییر سیاست نیازمند ویرایش کد؛ ناسازگاری با `constants.py` | انتقال به `constants.py` |
| M7 | Medium | `live_signals.py:163` | کهنگی snapshot | `prev` با TTL یک روز ذخیره می‌شود | پس از ری‌استارت/شب، مقایسهٔ «۵ دقیقه‌ای» با snapshot دیروز ⇒ سیگنال کاذب | TTL کوتاه (مثلاً ۲×interval) + بررسی `ts` |
| M8 | Medium | `live_signals.py:90` | داده گمشده | `prev_snap.get("score",{}).get("total",0)` | نبود score در snapshot قبلی → دلتا=امتیاز فعلی → سیگنال کاذب | `None`-safe و skip |
| M9 | Medium | `macro_news.py:51-89` | heuristic | تطبیق زیررشته‌ای شامل `"+"`/`"-"`؛ `confidence` ثابت ۰.۶ | تیتر خنثی با خط‌تیره → `+2`؛ خروجی بی‌اعتبار ولی با ظاهر عددی | regex عددی + مدل/LLM یا حذف از مسیر تصمیم |
| M10 | Medium | `macro_news.py:161-190` | یکپارچگی | `compute_macro_multiplier` **در scorer وارد نمی‌شود**؛ فقط در `/macro` نمایش داده می‌شود (`api.py:1378`) | ادعای «تحلیل کلان مؤثر بر امتیاز» در محصول محقق نشده | یا حذف ادعا یا اتصال با وزن مشخص و تست |
| M11 | Medium | `macro_news.py:227-256` | داده | `published_at = now` برای خبر اسکرپ‌شده؛ بدون dedupe/ذخیره | همهٔ اخبار «امروز» تلقی می‌شوند؛ decay بی‌معنا | استخراج تاریخ انتشار + کلید یکتا |
| M12 | Medium | `pattern_detector.py:216-217` | تقویم | `datetime.fromisoformat` روی رشتهٔ شمسی؛ `period_*` از نوع `datetime` ولی داده `date` | `period_start` سال ۱۴۰۵ و مقایسه‌های زمانی نادرست | تبدیل با `jdatetime` یا نگه‌داشتن `str` |
| M13 | Medium | `pattern_detector.py:114,133` | عدد بی‌منبع | `historical_hit_rate=62.0/58.0` ثابت | ادعای آماری دروغین در خروجی API | حذف یا محاسبهٔ واقعی |
| M14 | Medium | `pattern_detector.py:207-211` | ادعای مرده | `recommendation` هرگز «خرید قوی» نمی‌شود (`:201-211`) | مقدار enum مرده | حذف یا پیاده‌سازی |
| M15 | Medium | `dca_planner.py:107-135` | سازگاری | پله‌ها ۱۰۰٪ سرمایه + کارمزد جدا | پلن قابل اجرا نیست | کسر کارمزد از سبد پله‌ها |
| M16 | Medium | `bubbler.py:59,62,68` | سکوت عددی | `fair<=0` → `bubble_pct=0`، `xau<=0` → `implied_usd=0` | صفر به‌جای «نامعتبر» ⇒ امتیاز کامل برای داده خراب | `None`/خطا |
| M17 | Medium | `pricer.py:36-40` vs `bubbler.py:34-38` | تعریف دوگانه | نسبت عیار `750/999.9` در برابر `0.750` | اختلاف ~۰.۰۱٪ در fair و implied | یک تابع عیار مشترک |
| M18 | Medium | `constants.py:38-39` | واحد | `MINTING_COST_TOMAN=50_000` (تومان) در برابر جدول `services` با کامنت `IRR` | در صورت تغییر مقیاس، خطای ۱۰× | مستندسازی واحد و assert محدوده |
| L1 | Low | `pricer.py:97`, `signal_engine.py:154,160`, `constants.py:161` | کد مرده | بدون مصرف‌کننده در ریپو | سردرگمی نگهداری | حذف یا استفاده |
| L2 | Low | `scorer.py:105-119` | ثابت جادویی | ۱۱/۷ به‌جای `SCORE_WEIGHTS["tsetmc"]` | تغییر وزن، جمع را می‌شکند | `bpr_pts = weight*11/18` یا assert |
| L3 | Low | `scorer.py:166` | ثابت جادویی | `−1.0` برای باند fund_flow در constants نیست | ناسازگاری سیاست | انتقال به `constants.py` |
| L4 | Low | `scorer.py:71,147` vs `:86,89` | مرز | ترکیب `<` و `<=` | در مقدار دقیق آستانه، رفتار غیرقابل پیش‌بینی | یکدست‌سازی مستند |
| L5 | Low | `signal_engine.py:82-83` | حالت حدی | سری بدون تغییر → RSI=۱۰۰ → امتیاز ۰ | «بی‌حرکتی» جریمه می‌شود | `50` یا `None` |
| L6 | Low | `black76.py:61-65` | تاریخ | `date.today()` محلی؛ `max(...,1e-6)` برای انقضا | اختلاف یک‌روزه با تهران؛ قیمت‌گذاری منقضی | `now_tehran().date()` + `ValueError` |
| L7 | Low | `nav_checker.py:122-123, 186-187` | استثنا | `except Exception: return None` بدون لاگ | دیباگ سخت | `logger.warning(..., exc_info=True)` |
| L8 | Low | `global` | تعداد N+۱ کوئری | `get_all_funds_status` حلقه‌ای | کندی snapshot با ۱۰ صندوق | کوئری batch |

---

# ۸. پوشش تست

**وضعیت اجرا:** `pytest tests/gold_desk -q` → **۱۷۰ passed** در ۱۶.۷ ثانیه (بدون خطا). این عدد با ادعای `PLAN_GOLD.md` («117 passed») هم‌خوان نیست — یعنی تست‌ها بعد از مستند اضافه شده‌اند ولی مستند به‌روز نشده.

| ماژول | تست | چه چیزی پوشش دارد | چه چیزی ندارد |
|---|---|---|---|
| `constants.py` | `tests/gold_desk/__init__.py` (۱۴ تست) | مقادیر troy/aed/عیار/وزن، جمع وزن‌ها، ترتیب باندها، ساختار fee | محدودهٔ هر آستانه، واحدها (تومان/ریال)، ارتباط با `services/gold/constants` |
| `pricer.py` | `test_pricer_bubbler.py:22-84` | ۱۸k/۲۴k/سکه/نیم‌سکه، `ValueError` ورودی منفی، dispatch | `MELTED` (مثقالی) فقط در تست‌های `unit` بیرون از `tests/gold_desk`؛ `fair_gram_weight`; `fair_coin_breakdown` |
| `bubbler.py` | `:88-143` | حباب مثبت/صفر/منفی، implied برای ۱۸k و سکه | `fair=0`, `xau<=0`, نماد ناشناس، `IR_COIN_1G` (مسیر عیار) |
| `parity.py` | **هیچ تست اختصاصی** | — | همهٔ حالت‌ها (`aed<=0`، پرچم `parity=0`) |
| `signal_engine.py` | **هیچ تست** در `tests/gold_desk` | — | RSI/EMA/Bollinger/MACD، ترتیب سری، برش `days` (H1) |
| `nav_checker.py` | `tests/unit/test_gold_silver_funds_critical_regressions.py:114` (بیرون دامنهٔ تست) | `_latest_nav` با یک ردیف | `_nav_7d_ago`، `_pick_nav` دو ستون، کهنگی، BPR=0 (M4) |
| `scorer.py` | `test_scorer.py` (۲۱ تست) | همهٔ باندها، None، hard-stop override، سناریوی سبز/زرد/قرمز | **نرمال‌سازی پوشش داده (C5)**، مرزهای دقیق، `int()` truncation، banker's rounding، `available_weight` جزئی |
| `hard_stops.py` | `tests/unit/test_gold_silver_funds_fixes.py:90-102` | `inputs_missing`، فعال‌شدن با یک ورودی | مرزهای دقیق `−5.0/+3.0/+5.0`، اولویت چند شرط هم‌زمان |
| `dca_planner.py` | `test_dca_planner.py` (۱۳ تست) | ۳ پروفایل، fee ETF/jewelry، خطاها | سازگاری `net_investable` با مجموع پله‌ها، sell fee/VAT، vehicle ناشناس |
| `black76.py` | `test_black76.py` (۱۶ تست) | parity، ATM، ITM، delta/gamma/vega/theta علامت، collar، تاریخ گذشته | **صحّت عددی theta (H5)**، `greeks` بدون اعتبارسنجی، `T` منطقهٔ زمانی، `iv` خیلی بزرگ/کوچک |
| `backtest.py` | **هیچ تست** در `tests/gold_desk` | — (فقط یک تست تقویم در `unit` روی `_daily_bubble_pct`) | look-ahead (C2)، hit rate، baseline |
| `backtest_runner.py` | `test_backtest_runner.py` (۸ تست) | `len(trades)>=1`، دوره، `warning`، رابطهٔ alpha | **بزرگی `total_return` (C1)**، maxDD (H2)، تخصیص پله‌ها (H3)، Sharpe |
| `pattern_detector.py` | `test_pattern_detector.py` (۹ تست) | `pd_rolling_mean`, ۴ detector با داده مصنوعی | `_fetch_closes` (C3)، `period_*` (M12)، backfill look-ahead (H6) |
| `live_signals.py` | `test_live_signals.py` (۱۲ تست) | spike، score delta، USD، bubble extreme، `to_dict` | `detect_and_broadcast` (Redis/WS)، کهنگی prev، snapshot ناقص |
| `macro_news.py` | `test_macro_news.py` (۱۳ تست) | heuristic پایه، multiplier bounds/decay، «بدون seed» | تطبیق مثبت/منفی کاذب (M9)، اتصال به scorer (M10)، scrape |
| `portfolio.py` | `test_portfolio.py` (۳)، `test_portfolio_returns.py` (۷)، `unit/..._fixes.py:280-300` | `get_current_prices`، جریان‌ها، XIRR/P&L، FIFO یک‌نمادی، CSV | **FIFO چندنمادی (C4)**، فروش بیش از موجودی، کارمزد در XIRR (H8)، `pnl_pct=0` (H7)، `record_trade` |

**تست‌های لازم (پیشنهاد):**
1. `backtest_runner`: `assert -50 < metrics.total_return_pct < 200` و `assert metrics.final_value` هم‌مرتبه با `initial_capital`.
2. `backtest._daily_bubble_pct`: مقایسهٔ `sma30[i]` با `mean(prices[i-29:i+1])`.
3. `pattern_detector._fetch_closes`: همان تست تقویمی که برای سه fetcher دیگر وجود دارد (افزودن به پارامتری‌زه `unit/test_gold_silver_funds_critical_regressions.py:180-184`).
4. `fifo_realized` با دو نماد و فروش بدون لات.
5. `compute_score` با `available_weight` کوچک → انتظار `NO_DATA`/`RED`.
6. `signal_engine.calc_rsi` روی سری ۴۰ عضوی و بررسی استفاده از آخرین مقدار (نه مقدار ۱۰ روز قبل).
7. `black76_greeks.theta` در برابر finite difference.
8. `live_signals.detect_and_broadcast` با prev کهنه.
9. `portfolio.compute_returns` با trade + holding هم‌زمان.

---

# ۹. وابستگی‌های بیرونی و سؤالات باز

## ۹.۱ وابستگی‌های بیرونی (فقط خوانده و گزارش شده)

| وابستگی | مصرف‌کننده در دامنه | نکته |
|---|---|---|
| `brsapi.models.commodity.GoldCoinHistoryModel` | `signal_engine._fetch_gold_coin_closes`, `backtest._daily_bubble_pct`, `backtest_runner._fetch_daily_closes`, `pattern_detector._fetch_closes` | `date` از نوع `String(20)` و **شمسی** (`brsapi/models/commodity.py:54`). هیچ‌کدام از این چهار مصرف‌کننده واحد تاریخ را نرمال نمی‌کند؛ سه‌تا با `jalali_days_ago` اصلاح شده‌اند، `pattern_detector` نه. |
| `GoldCurrencyProDailyHistoryModel` | `signal_engine._fetch_pro_daily_closes` | منبع XAUUSD/USD/DXY؛ وجود DXY در DB نامشخص است. |
| `NavRecordModel` | `nav_checker` | فقط `nav_issue`/`nav_redemption`؛ ستون `nav` وجود ندارد (`brsapi/models/tsetmc.py:272-273`). |
| `HistoricalRealLegalModel` | `nav_checker._fund_market_data` | `buy_real_value`/`sell_real_value`؛ واحد تومان فرض شده (`[استنباط]`). |
| `IndexValueModel` | `snapshot_service._calc_daily_changes` (بیرون دامنه) | `index_change_pct` شاخص کل — ورودی TSE hard stop. |
| `core.time.now_tehran` / `utc_now_naive` | `dates.py`, `pattern_detector`, `portfolio`, `macro_news` | `[کد]` در `black76` به‌جای این‌ها `date.today()` استفاده شده. |
| `core.cache.get_cache` | `live_signals`, `macro_news` | Redis؛ رفتار TTL در دامنه قابل کنترل نیست. |
| `services.gold.constants` | `constants.py:35-36`, `pricer.py:14-24` | منبع حقیقت وزن/عیار/کارمزد ضرب. |
| `pandas`/`numpy`/`scipy` | backtest, pattern, black76 | scipy فقط در `black76` و `returns`. |

## ۹.۲ سؤالات باز

1. **واحد پول BrsApi:** آیا `USD`/`XAUUSD` در DB تومان ذخیره می‌شوند یا ریال؟ `[کد]` `constants.py:213` بازهٔ `VALID_USD_RANGE = 10_000..10_000_000` و تست‌ها `68_000` را تایید می‌کنند (`[استنباط]` تومان)، اما هیچ تبدیل صریحی در دامنه نیست. اگر منبع ریال بدهد، **همهٔ** `fair_value`ها ۱۰× و همهٔ حباب‌ها بی‌معنا می‌شوند.
2. **واحد کارمزد ضرب:** `MINTING_COST_TOMAN` نام «تومان» دارد ولی `services/gold/constants.py:102-109` کامنت `IRR` دارد (۸۰,۰۰۰). کدام درست است؟ اثر آن روی سکهٔ کامل ~۰.۱۸٪ است.
3. **منبع نرخ بهره بدون ریسک:** `IRAN_RISK_FREE_RATE = 0.30` ثابت است. آیا باید از `اخزا`/DB خوانده شود؟ هیچ جدولی در دامنه به آن وصل نیست.
4. **منبع IV:** «سطح نوسان تاریخی» در jobها ذکر شده ولی در دامنهٔ من هیچ‌جا IV از بازار خوانده نمی‌شود. آیا قیمت واقعی آپشن در دسترس است؟
5. **DXY:** آیا سری DXY در `brsapi_gold_currency_pro_daily_history` وجود دارد؟ کامنت `snapshot_service.py:172-174` می‌گوید نه ⇒ hard stop سوم مرده است.
6. **معنای «امتیاز» برای کاربر:** آیا کاربر می‌داند امتیاز ۱۰۰ با `data_coverage=20` ممکن است؟ آیا UI پوشش داده را نشان می‌دهد؟ `[کد]` جست‌وجو در `schemas.py`, `api.py` و `frontend/src` هیچ ارجاعی به `data_coverage`/`available_weight`/`raw_total` نشان نمی‌دهد؛ پس کاربر فقط `total` نرمال‌شده را می‌بیند.
7. **BPR تجمعی:** جمع `buy_value`/`sell_value` در snapshot بر صندوق‌های با مقیاس متفاوت وزن یکسان می‌دهد. آیا این همان «BPR بازار» است که مدنظر طراحی بود؟
8. **NAV صندوق «عیار»:** `snapshot_service.py:292` با `"عیار" in f.symbol` صندوق مرجع را انتخاب می‌کند؛ اگر چند صندوق شامل این رشته باشند اولین برنده می‌شود. آیا سیاست انتخاب مستند است؟
9. **آیا `/patterns` و `/backtest/strategy` در UI نمایش داده می‌شوند؟** اگر بله، C1/C3 مستقیماً به کاربر عدد غلط نشان می‌دهند.
10. **مالیات/کارمزد در XIRR:** آیا `amount_irt` در `GoldTradeModel` شامل کارمزد است یا نه؟ (در دامنه مشخص نیست؛ `record_trade` کارمزد را جدا ذخیره می‌کند.)

---

# ۱۰. رابط (Interface) با دیگر بخش‌ها: لیست دقیق توابعی که API/snapshot/فرانت صدا می‌زنند

جدول زیر **دقیقاً** توابع دامنه را که از بیرون صدا زده می‌شوند، با محل فراخوانی، نشان می‌دهد. مسیرها همه نسبت به ریپو هستند.

## ۱۰.۱ از `snapshot_service.py` (مسیر اصلی snapshot)

| تابع دامنه | محل فراخوانی | دادهٔ ورودی از کجا | خروجی به کجا |
|---|---|---|---|
| `parity.aed_parity_usd` | `snapshot_service.py:210` | `refs["aed_irt"]` از BrsApi/TGJU | `ReferenceBlock.aed_parity_usd` |
| `parity.aed_gap_pct` | `snapshot_service.py:211` | `usd_irt`, `aed_irt` | `ReferenceBlock.aed_gap_pct` + ورودی scorer |
| `pricer.fair_value` | `snapshot_service.py:229, 250` | `xau`, `usd`, نماد | `AssetBlock.fair_value` |
| `bubbler.calc_bubble` | `snapshot_service.py:230, 251` | `market` از BrsApi, `fair`, `xau` | `AssetBlock.bubble_abs/bubble_pct/implied_usd` |
| `nav_checker.get_all_funds_status` | `snapshot_service.py:266` | `FUND_SYMBOLS`, `market_prices=brsapi_prices` | لیست `FundBlock` |
| `signal_engine.get_xau_indicators` | `snapshot_service.py:285` | `days=40` | `xau_rsi` + اندیکاتورها در snapshot |
| `signal_engine.fetch_closes` | `snapshot_service.py:146, 177` | `"USD", 2` و `"DXY", 2` | `_calc_daily_changes` → hard stop |
| `hard_stops.check_hard_stops` | `snapshot_service.py:305` | سه تغییر روزانه | `ScoreBlock.hard_stop_active/reason` |
| `scorer.compute_score` | `snapshot_service.py:312` | ۷ ورودی + hard stop | `ScoreBlock` (total/decision/components) |

## ۱۰.۲ از `api.py` (endpointهای `POST/GET`)

| تابع دامنه | محل فراخوانی | endpoint | پارامترهای ورودی از کاربر |
|---|---|---|---|
| `dca_planner.plan_dca` | `api.py:201` | `POST /api/gold/dca/plan` | `total_capital_irt`, `risk_profile`, `current_score`, `preferred_vehicle` |
| `backtest.run_backtest` | `api.py:496` | `GET /api/gold/backtest` | `days` (30..365), `bubble_threshold` (≥0), `symbol` |
| `backtest_runner.run_strategy_backtest` | `api.py:526` | `GET /api/gold/backtest/strategy` | `days`, `symbol`, `bubble_trigger`, `initial_capital` |
| `black76.price_option` | `api.py:628` | `POST /api/gold/options/price` | `forward`, `strike`, `expiry`, `iv`, `rate` |
| `black76.protective_collar` | `api.py:673` | `POST /api/gold/options/collar` | `spot`, `put_strike`, `call_strike`, `expiry`, `iv`, `rate` |
| `portfolio.build_portfolio_returns` | `api.py:891, 919` | `GET /api/gold/portfolio/returns`, `GET /api/gold/portfolio` | snapshot داغ |
| `portfolio.build_tax_summary` | `api.py:898` | `GET /api/gold/portfolio/tax` | — |
| `portfolio.build_trades_csv` | `api.py:905` | `GET /api/gold/portfolio/export.csv` | — |
| `portfolio.get_current_prices` | `api.py:917, 1216` | `GET /api/gold/portfolio`, `/chat` | snapshot |
| `portfolio.get_holdings_grouped` | `api.py:918, 1217` | `/portfolio`, `/chat` | قیمت‌های snapshot |
| `portfolio.get_plan_status` | `api.py:1046` | `GET /api/gold/portfolio/dca` | مدل پلن + `current_score` |
| `portfolio.record_trade` | `api.py:1107` | `POST /api/gold/portfolio/trades` | symbol/action/quantity/price/amount/fee |
| `dca_planner.plan_dca` | `api.py:987` | `POST /api/gold/portfolio/dca` | همان API DCA |
| `pattern_detector.detect_patterns` | `api.py:1227, 1274` | `/chat` و `GET /api/gold/patterns` | `symbol`, `days` |
| `macro_news.fetch_macro_events` | `api.py:1364` | `GET /api/gold/macro` | — |
| `macro_news.compute_macro_multiplier` | `api.py:1378` | `GET /api/gold/macro` | رویدادها |
| `macro_news.scrape_cbi_news` | `api.py:1415` | `POST /api/gold/macro/scrape` | — |
| `live_signals.detect_and_broadcast` | `api.py:1196` | `POST /api/gold/signals/detect` | snapshot فعلی |
| `live_signals.REDIS_KEY_RECENT_SIGNALS` | `api.py:1173` | `GET /api/gold/signals/recent` | — |

## ۱۰.۳ از jobها و ماژول‌های بیرون دامنه (خوانده‌شده، تغییرنشده)

| مصرف‌کننده | تابع دامنه | محل |
|---|---|---|
| `brsapi/jobs/gold_desk_jobs.py` | `snapshot_service.build_snapshot` | `:76, 146, 195, 261, 278` |
| `brsapi/jobs/gold_desk_jobs.py` | `live_signals.detect_and_broadcast` | `:87-89` |
| `src/gold_desk/auto_trade.py` | `portfolio.get_current_prices`, `portfolio.get_holdings_grouped` | `:28, 145` |
| `src/gold_desk/portfolio_history.py` | `get_holdings_grouped`, `constants.PORTFOLIO_TARGET_WEIGHTS` | `:32-38, 191, 383` |
| `src/gold_desk/forecaster.py` | `signal_engine.fetch_closes` | `:23` |
| `src/gold_desk/hotpath.py` | `constants.BUBBLE_*`, `REDIS_KEY_SNAPSHOT` | `:17` |
| `src/gold_desk/alert_engine.py` | `constants.PORTFOLIO_*` | `:19-22, 252-268` |
| `src/gold_desk/antigravity/calculations.py` | `constants.NAV_PREMIUM_*` | `:12-13, 33-36` |
| `services/fund_scoring.py` | `constants.NAV_PREMIUM_*` | `:29, 643-647` |
| `tests/unit/*` | `backtest._daily_bubble_pct`, `backtest_runner._fetch_daily_closes`, `scorer.compute_score`, `hard_stops.check_hard_stops`, `portfolio.fifo_realized`, `pricer.fair_coin` | `test_gold_silver_funds_critical_regressions.py:29-38`, `test_gold_silver_funds_fixes.py:38-47`, `test_physical_arbitrage.py:307,346` |

## ۱۰.۴ قراردادهای داده‌ای که نباید تغییر کنند (برای هم‌تیمی‌ها)

`[کد]` این‌ها در `schemas.py`/`api.py` مصرف می‌شوند و تغییر امضا یا معنا در دامنهٔ من، آن‌ها را می‌شکند:

1. **`ScoreResult.total: int`** با دامنهٔ ۰–۱۰۰ و `decision ∈ {"GREEN","YELLOW","RED"}` — اگر `NO_DATA` اضافه شود، `schemas.ScoreBlock.decision` و فرانت باید هماهنگ شوند (وابستگی بیرونی).
2. **`BubbleResult`** با شش فیلد ثابت؛ `None` برای `bubble_pct` در `FundNAVStatus` معنای «قیمت بازار ناموجود» دارد و scorer روی آن حساب می‌کند (`nav_checker.py:30-33`, `scorer.py:200`).
3. **`FundNAVStatus.market_price: float | None`** — صفر یا جایگزین‌کردن با NAV، حباب صفر کاذب می‌سازد (کامنت خود کد، `nav_checker.py:30-32`).
4. **`BacktestMetrics`** — فیلدهای `total_return_pct`/`alpha_pct`/`max_drawdown_pct` در `api.py:537-549` و صفحهٔ `/gold/backtest` (فرانت) مصرف می‌شوند؛ اصلاح C1/H2 **عدد نمایش‌داده‌شده را به‌شدت تغییر می‌دهد** (از −۱۰۰٪ به مقدار واقعی) و باید با هماهنگی فرانت انجام شود.
5. **`PortfolioSummary.total_cost/total_value`** — دو معنای متفاوت دارند (اولی شامل دارایی بی‌قیمت، دومی نه). هر اصلاح H7 باید با `api.py:923-926` و `portfolio_history.py` هم‌زمان باشد.
6. **`detect_patterns` خروجی `PatternReport`** — `period_start/period_end` از نوع `datetime`؛ اگر به `date` تغییر کند، `api.py:1279-1280` باید به‌روزرسانی شود.
7. **کلیدهای Redis** — `golddesk:snapshot:prev` و `golddesk:signals:recent` بین `live_signals` و `api.py:1173` مشترک‌اند؛ تغییر نام، endpoint سیگنال‌های اخیر را خالی می‌کند.

---

## پیوست: چگونه ادعاها را بررسی کردم

| ادعا | روش |
|---|---|
| ۱۷۰ تست پاس | `python -m pytest tests/gold_desk -q` (خروجی: `170 passed in 16.75s`) |
| `total_return_pct ≈ −100` | اجرای `_simulate_dca` + `_compute_metrics` روی fixture تست؛ خروجی در بخش ۵.۲ |
| look-ahead در `np.convolve` | مقایسهٔ `sma[40] = 139.5` با `mean(prices[11:41]) = 125.5` (بخش ۵.۱) |
| `reversed(closes[-days:])` | بازسازی لیست `40..1` با `days=30`؛ ۴۰ و ۳۹ حذف می‌شوند |
| cutoff میلادی/شمسی | `'1405-08-02' >= '2026-09-24' → False` |
| FIFO چندنمادی | دو معاملهٔ دو نماد → `realized_pnl_irt = 4500.0` |
| GREEN با یک کامپوننت | `compute_score(bubble_pct=7.9, بقیه None)` → `total=100, decision='GREEN'` |
| theta | finite difference: کد `−0.029101`، FD `−0.021412`، فرمول اصلاح‌شده `−0.021501` |
| اعداد fair/hubble | اجرای `pricer` و `calc_bubble` با `XAU=2750`, `USD=68_000`, `market=53_000_000` |
