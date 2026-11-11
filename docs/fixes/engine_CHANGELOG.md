# CHANGELOG — دستیار «engine» (branch `fix/engine`)

محدودهٔ مالکیت: `src/gold_desk/{constants,pricer,bubbler,parity,signal_engine,nav_checker,scorer,dca_planner,hard_stops,black76,backtest,backtest_runner,pattern_detector,live_signals,macro_news}.py`،
فایل جدید `src/gold_desk/indicators.py` و تست‌های `tests/gold_desk/`.

**نتیجهٔ نهایی اجرای تست‌ها**

| دستور | نتیجه |
|---|---|
| `pytest tests/gold_desk` (بدون `test_fifo_realized.py`) | **۲۵۵ passed** |
| `pytest tests/unit/test_gold_silver_funds_critical_regressions.py tests/unit/test_gold_silver_funds_fixes.py tests/unit/test_audit_fixes_batch2.py tests/unit/test_audit_stages_2_3_5.py` | **۶۱ passed** |
| `git diff --stat 4e9e289a..HEAD` | فقط فایل‌های محدودهٔ من (۲۹ فایل) |

`tests/gold_desk/test_fifo_realized.py` مال دستیار دیگری است (روی `portfolio.py` کار
می‌کند، در همان worktree مشترک) و در حال حاضر به‌دلیل رفع‌نشدن C4 قرمز است؛ در اجرای
من حذف شده و به محدودهٔ من ربطی ندارد.

---

## ۱. جدول وضعیت

| شناسه | وضعیت | فایل‌ها | تست |
|---|---|---|---|
| E-C5 | fixed | `constants.py`, `scorer.py` | `test_scorer.py::test_low_coverage_gives_no_data`, `::test_compute_score_bounds`, `::test_full_coverage_still_decides` |
| E-H1 | fixed | `signal_engine.py` | `test_signal_engine.py::test_fetch_returns_newest_window_in_chronological_order`, `::test_fetch_closes_keeps_row_order_through_fallback`, `::test_rsi_uses_latest_value_not_stale_window` |
| E-L5 | fixed | `signal_engine.py` | `test_signal_engine.py::test_rsi_flat_series_is_neutral` |
| E-M16 | fixed | `bubbler.py` | `test_pricer_bubbler.py::test_bubble_pct_none_when_fair_invalid`, `::test_implied_usd_none_when_xau_invalid` |
| E-M4 | fixed (+وابستگی schema) | `nav_checker.py` | `test_nav_checker.py::test_bpr_none_when_no_sell_value`, `::test_bpr_computed_when_both_sides_exist` |
| E-M3 | fixed | `nav_checker.py` | `test_nav_checker.py::test_pick_nav_prefers_nav_issue`, `::test_pick_nav_reports_issue_redemption_divergence`, `::test_pick_nav_falls_back_to_redemption` |
| E-M5 | fixed | `nav_checker.py` | `test_nav_checker.py::test_stale_data_detected_for_non_padded_jalali_date`, `::test_fresh_data_accepted`, `::test_unparsable_date_rejected_with_warning` |
| E-L7 | fixed | `nav_checker.py` | `test_nav_checker.py::test_market_data_exception_is_logged` |
| E-L8 | fixed | `nav_checker.py` | `test_nav_checker.py::test_all_funds_status_uses_batch_queries`, `::test_all_funds_status_maps_batched_nav_rows_to_symbols` |
| indicators.py | fixed (ماژول جدید) | `indicators.py`, `constants.py` | `test_indicators.py` (۱۱ تست) |
| E-C2 | fixed | `backtest.py` | `test_backtest.py::test_daily_bubble_is_trailing_not_centered`, `test_indicators.py::test_sma30_is_trailing_mean`, `::test_sma30_matches_audit_number` |
| E-H6 | fixed | `pattern_detector.py` | `test_pattern_detector.py::test_rolling_mean_has_no_backfill`, `::test_rolling_mean_short` |
| E-C3 | fixed | `pattern_detector.py` | `test_pattern_detector.py::test_fetch_closes_uses_jalali_cutoff` |
| E-M12 | fixed | `pattern_detector.py` | `test_pattern_detector.py::test_period_dates_are_parsed_from_jalali` |
| E-M13 | fixed | `pattern_detector.py` | `test_pattern_detector.py::test_trend_hit_rate_is_computed_not_hardcoded`, `::test_spike_hit_rate_is_computed_not_hardcoded` |
| E-M14 | fixed | `pattern_detector.py` | `test_pattern_detector.py::test_recommendations_enum_matches_emitted_values` |
| E-C1 | fixed | `backtest_runner.py` | `test_backtest_runner.py::test_total_return_has_realistic_magnitude`, `::test_units_use_real_capital`, `::test_fee_is_deducted_from_units` |
| E-H2 | fixed | `backtest_runner.py` | `test_backtest_runner.py::test_max_drawdown_positive_on_falling_series` |
| E-H3 | fixed | `backtest_runner.py` | `test_backtest_runner.py::test_tranches_are_chained_and_event_driven`, `::test_pullback_tranche_runs_after_pullback`, `::test_simulate_dca_high_bubble` |
| E-H4 | fixed | `backtest_runner.py` | `test_backtest_runner.py::test_sharpe_uses_strategy_nav`, `::test_metrics_alpha_calculation`, `::test_out_of_sample_metrics_present` |
| E-H5 | fixed | `black76.py` | `test_black76.py::test_theta_matches_finite_difference` |
| E-L6 | fixed | `black76.py` | `test_black76.py::test_years_to_expiry_past_raises`, `::test_years_to_expiry_uses_tehran_today` |
| E-M6 | fixed | `live_signals.py`, `constants.py` | `test_live_signals.py::test_price_spike_threshold_is_configurable`, `::test_bubble_extreme_threshold_is_configurable` |
| E-M7 | fixed | `live_signals.py`, `constants.py` | `test_live_signals.py::test_stale_prev_snapshot_is_discarded`, `::test_fresh_prev_snapshot_is_unwrapped`, `::test_legacy_prev_snapshot_still_readable` |
| E-M8 | fixed | `live_signals.py` | `test_live_signals.py::test_missing_prev_score_skips_score_signal`, `::test_missing_curr_score_skips_score_signal` |
| E-M9 | fixed | `macro_news.py` | `test_macro_news.py::test_neutral_title_with_dash_scores_zero`, `::test_numeric_sign_drives_the_score`, `::test_confidence_is_not_a_constant` |
| E-M10 | fixed (+وابستگی api.py) | `macro_news.py` | `test_macro_news.py::test_scorer_does_not_consume_macro_news`, `::test_macro_module_is_documented_as_informational` |
| E-M11 | **partial** — تاریخ انتشار از متن خبر پارس می‌شود؛ اگر صفحه تاریخ نداشته باشد fallback «زمان واکشی» است (نمی‌توان عددی ساخت که وجود ندارد) | `macro_news.py` | `test_macro_news.py::test_extract_published_at_parses_jalali_date`, `::test_extract_published_at_falls_back_without_date`, `::test_dedupe_key_is_stable_and_source_scoped`, `::test_dedupe_removes_repeated_events` |
| E-M15 | fixed | `dca_planner.py` | `test_dca_planner.py::test_ladder_is_internally_consistent`, `::test_plan_fee_calculation`, `::test_plan_fee_jewelry` |
| E-M17 | fixed | `pricer.py`, `bubbler.py` | `test_pricer_bubbler.py::test_pricer_and_bubbler_share_one_purity_definition` |
| E-M18 | fixed (مستندسازی + assert) | `constants.py` | `test_pricer_bubbler.py::test_minting_costs_are_in_toman_scale` |
| E-L2 | fixed | `scorer.py`, `constants.py` | `test_scorer.py::test_tsetmc_point_split_matches_component_weight` |
| E-L3 | fixed | `scorer.py`, `constants.py` | `test_scorer.py::test_fund_flow_minor_drop_band_is_named` |
| E-L4 | fixed | `scorer.py`, `constants.py` | `test_scorer.py::test_threshold_boundaries_are_inclusive` |
| E-L1 | fixed جز یک مورد (پایین را ببینید) | `pricer.py`, `signal_engine.py` | `test_signal_engine.py::test_dead_helpers_stay_removed` |
| parity tests | fixed (پوشش جدید) | `tests/gold_desk/test_parity.py` | ۶ تست |

### E-L1 — گزارش با کد نمی‌خواند

گزارش سه محل «کد مرده» داده بود. با grep در کل ریپو (شامل تست‌ها، `app/`, `services/`, `jobs/`, `api/`):

- `pricer.fair_gram_weight` — واقعاً بدون مصرف‌کننده ⇒ حذف شد.
- `signal_engine.get_xau_rsi` / `get_xau_ema` — واقعاً بدون مصرف‌کننده ⇒ حذف شد.
- `constants.py:161` (= `REDIS_KEY_WATCHLIST`) — **مصرف‌کننده دارد**: `api.py`.
  گزارش در این مورد اشتباه است؛ کد دست‌نخورده ماند (قاعدهٔ ۶).

### تذکر روش‌شناسی

در سه ماژول (`pattern_detector`, `backtest_runner`, `macro_news`) چند شناسه در یک
بازنویسی هم‌زمان رفع شدند، پس یک commit چند شناسه را پوشش می‌دهد (به‌جای یک commit
به‌ازای هر شناسه):

- `9294cfa1` ⇒ E-H6, E-C3, E-M12, E-M13, E-M14
- `4fd05334` ⇒ E-C1, E-H2, E-H3, E-H4
- `9a383d3b` ⇒ E-H5, E-L6
- `fd0a0665` ⇒ E-M6, E-M7, E-M8
- `dd0b5ec9` ⇒ E-M9, E-M10, E-M11
- `2ca2c2c3` ⇒ E-M17, E-M18
- `d354fbff` ⇒ E-L2, E-L3, E-L4
- `48c78f99` ⇒ ماژول `indicators.py` (زیرساخت E-C2/H6، شناسهٔ مستقل ندارد)

بقیه (E-C5, E-H1, E-L5, E-M16, E-M4, E-M3, E-M5, E-L7, E-L8, E-C2, E-M15, E-L1) هر کدام
commit جدا با پیام `fix(<ID>)` دارند.

`.editorconfig`-مانندی برای CRLF وجود ندارد؛ گیت روی این مخزن LF→CRLF هشدار می‌دهد
ولی diff فقط محتوای واقعی را نشان می‌دهد.

---

## ۲. تغییرهای رفتاری که مصرف‌کننده باید بداند

1. **`ScoreResult.decision` می‌تواند `"NO_DATA"` باشد** (C1). `total` همچنان عددی است.
   `hard_stop_active=True` بر `NO_DATA` اولویت دارد (RED).
2. **`BubbleResult.bubble_pct` / `implied_usd` می‌توانند `None` باشند** (C2).
   `bubble_abs` عددی ماند (تفریق با fair≤0 تعریف‌شده است).
3. **`FundNAVStatus.bpr` می‌تواند `None` باشد** (E-M4).
4. **`PatternReport.period_start/end` حالا تاریخ میلادی واقعی‌اند** (قبلاً «سال ۱۴۰۵»).
5. **`BacktestMetrics` فیلدهای جدید دارد**: `cash_remaining`, `total_fee_paid`,
   `oos_start`, `oos_total_return_pct`, `oos_buy_hold_return_pct`, `oos_alpha_pct`,
   `oos_max_drawdown_pct` (افزایشی). `BacktestTrade.fee_irt` هم اضافه شد (پیش‌فرض ۰).
6. **`years_to_expiry` برای سررسید گذشته `ValueError` می‌دهد** (E-L6).
7. **`DCAPlan.net_investable_irt` دیگر `total − fee` نیست**؛ مبلغ خالصی است که مجموع
   پله‌ها با آن برابر است و `net + fee = total` (E-M15).
8. **`estimate_impact` برای تیتر بی‌نشانه `(0, 0.0)` می‌دهد** (قبلاً `(0, 0.6)`).
9. **`live_signals` پیلود Redis را در قالب `{"ts", "snapshot"}` می‌نویسد** (خواندن قالب
   قدیمی حفظ شده است).

---

## ۳. درخواست‌های فرامحدوده (handoff)

فایل کامل: `docs/fixes/handoff_engine_to_backend.md` — خلاصه:

1. `schemas.py`: `ScoreBlock.decision` باید `"NO_DATA"` را بپذیرد. **بدون این تغییر،
   `/snapshot` در محیطی که پوشش داده کمتر از ۶۰ است `ValidationError` می‌دهد.**
2. `snapshot_service.py`: `_soft_check` باید `None` را بپذیرد (`bubble_pct` می‌تواند
   None شود).
3. `schemas.py`: `FundBlock.bpr` باید `float | None` شود.
4. `api.py`: `GET /macro` باید `"affects_score": false` بدهد (C6).
5. `api.py`: `ValueError` مسیر `/options/price` و `/options/collar` باید 400 شود.

---

## ۴. تست‌های بخش ۸ گزارش که انجام نشدند

| # | تست | دلیل |
|---|---|---|
| ۴ | `fifo_realized` با دو نماد | `portfolio.py` خارج از محدودهٔ من است (دستیار دیگری روی C4 کار می‌کند؛ `tests/gold_desk/test_fifo_realized.py` را هم او اضافه کرده). |
| ۹ | `compute_returns` با trade + holding | همان دلیل (H8 در `portfolio.py`). |

بقیهٔ ۹ مورد پیشنهادی گزارش (۱، ۲، ۳، ۵، ۶، ۷، ۸) نوشته شدند؛ مورد ۸
(`live_signals.detect_and_broadcast` با prev کهنه) در سطح تابع خالصِ
`_unwrap_prev_snapshot` تست شد، چون مسیر `detect_and_broadcast` به Redis و WS وابسته
است و در تست واحد قابل کنترل نیست.

---

## ۵. سؤالات باز

1. **`NO_DATA` در UI چه معنایی دارد؟** من تصمیم گرفتم `hard_stop` بر `NO_DATA` اولویت
   داشته باشد (ایمنی > کفایت داده). اگر محصول می‌خواهد «دادهٔ ناکافی» همیشه برنده باشد،
   باید در `scorer.compute_score` جای دو شرط عوض شود.
2. **در حالت `NO_DATA`، `total` عددی می‌ماند** (طبق C1 و برای نمودار) ولی کاربر ممکن است
   «۱۰۰» ببیند و GREEN فرض کند. نمایش پوشش داده در فرانت لازم است.
3. **واحد پول BrsApi (تومان یا ریال؟)** — گزارش ۰۱ هم آن را سؤال باز گذاشته بود؛ من در
   محدودهٔ خودم هیچ تبدیل واحدی اضافه نکردم.
4. **واحد `COIN_MINTING_COSTS`**: `services/gold/constants.py` کامنت `IRR` دارد،
   `constants.py` نام `..._TOMAN`. من فقط assert بازهٔ تومانی گذاشتم تا خطای ۱۰× لو برود؛
   منبع حقیقت باید یکی شود.
5. **سری DXY** در `brsapi_gold_currency_pro_daily_history` وجود دارد یا نه؟ اگر نه، سومین
   hard stop عملاً مرده است (باگ نیست، نبود داده است).
6. **منبع نرخ بدون ریسک و IV**: هر دو پارامتر ورودی/ثابت‌اند و از DB خوانده نمی‌شوند.
   خارج از فهرست رفع من بود، ولی `theta` اصلاح‌شده حالا حساسیت درست را نشان می‌دهد.
7. **تاریخ انتشار خبر CBI**: صفحهٔ `cbi.ir` تاریخ هر تیتر را در HTML نمی‌دهد؛ اگر جایی در
   متن تاریخ باشد پارس می‌شود، وگرنه زمان واکشی می‌نشیند. تصمیم محصول لازم است: یا
   `published_at` nullable شود، یا منبع خبری با تاریخ انتشار استفاده شود.
8. **آستانه‌های `TRANCHE2_PULLBACK_*` و افق‌های بک‌تست** (۳–۵٪ اصلاح، ۵ روز رویداد، ۳۰٪
   out-of-sample) از متن گزارش گرفته شده‌اند، منبع بیرونی ندارند.
9. **`live_signals`**: بازهٔ snapshot روی ۳۰۰ ثانیه فرض شده
   (`LIVE_SNAPSHOT_INTERVAL_SEC`). اگر job با بازهٔ دیگری اجرا می‌شود، این ثابت باید از
   تنظیمات خوانده شود.
