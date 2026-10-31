# مرحلهٔ ۱۰ — مالی/بک‌تست: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: FIN-03، FIN-05، و P2های FIFO/کارمزد/لغزش، مارجین، واحد VaR، `contract_size`، حباب منفی.
هیچ DB/شبکهٔ زنده لمس نشد؛ ۶ تست DB-محور این محیط fail می‌شوند (PostgreSQL auth) و جدا شمرده شده‌اند.

## ۱) FIN-03 — predicate مشترک بک‌تست و استراتژی

**قبل:** `backtest.run_backtest` روزهای `bubble > 8` را می‌سنجید، در حالی که استراتژی زندهٔ DCA
روزهای `bubble < trigger` را می‌خرد — بک‌تست جمعیت مقابل را توصیف می‌کرد.

**بعد:** ماژول [`src/gold_desk/entry_rules.py`](file:///C:/Users/Iran/Desktop/temce/src/gold_desk/entry_rules.py)
با `dca_entry_signal(bubble, threshold)` (مقایسهٔ `<`، `None`/NaN = بدون سیگنال). `backtest.py` و
`backtest_runner._simulate_dca` هر دو از آن استفاده می‌کنند.

**تست:** `tests/unit/gold_desk/test_entry_rule_parity.py` — روزهای سیگنال = زیر آستانه، میانگین
بازده فقط روی همان روزها (روز `bubble>threshold` با بازده منفی وارد نمی‌شود).

## ۲) FIN-08 — اجرا در کندل بعد

`_simulate_dca` قبلاً با **همان close روز سیگنال** پر می‌کرد؛ close بعد از پایان سشن معلوم می‌شود.
اکنون سیگنال از close روز i خوانده می‌شود و fill با close روز i+1 انجام می‌شود؛ سیگنال روز آخر
(بدون کندل بعدی) اجرا نمی‌شود. تاریخ معامله هم تاریخ fill است (NAV روزانه با آن هم‌تراز است).
**تست:** `test_dca_fills_on_the_next_bar_not_the_signal_close`،
`test_a_signal_on_the_last_bar_is_not_executed`.

**باقی‌مانده:** منبع فقط close دارد؛ fill در close فردا تقریب است، نه open واقعی.

## ۳) FIN-05 — purge افق برچسب در تقسیم ML

`DataSplitter.time_based/walk_forward` پارامتر `label_horizon` گرفتند:
- train در `boundary − h` تمام می‌شود و val از `boundary` شروع می‌شود ⇒ `h` ردیف purged بین آن‌ها؛
- همان شکاف بین val و test هم اعمال می‌شود؛
- `label_horizon=0` هندسهٔ قبلی را دقیقاً بازتولید می‌کند؛
- `DatasetBuilder.split` افق را از `config["horizon"]` می‌دهد.

**تست:** `tests/unit/ml/test_split_purge.py` (۶) — هندسهٔ پیش‌فرض، شکاف train/val،
`train_last + horizon < val_first`، شکاف walk-forward، رد horizon منفی، wiring builder.

## ۴) FIFO / کارمزد / لغزش — تأیید (کار قبلی، ادعای مالکیت نیست)

`backtesting/engine/position_manager.py::consume_lots_fifo` (FIFO tax lots)،
`commission.py` (کارمزد خرید + مالیات فروش از جدول ۱۴۰۵، بدون double-count)،
`slippage.py` (خرید بالاتر/فروش پایین‌تر، impact حجم/نوسان) و
`execution_simulator.py` (برداشت نقد یک‌بار در `PortfolioAccounting.apply_fill`، timestamp شبیه‌سازی).
مجموعهٔ `tests/unit/backtesting` = **۳۹۵ passed، ۱ skipped**.

## ۵) مارجین — FIN-09 / FIN-10

- `DEFAULT_OPTION_CONTRACT_SIZE = 1000` در
  [entities.py](file:///C:/Users/Iran/Desktop/temce/domain/options/entities.py) و استفاده در
  `Option` و `OptionLeg`؛ پیش‌فرض ۱ حذف شد (مارجین ۱۰۰۰ برابر کم‌محاسبه می‌شد).
- [margin_engine.py](file:///C:/Users/Iran/Desktop/temce/domain/options/margin_engine.py):
  دیاگونال (strike متفاوت **و** expiry متفاوت) با مارجین naked short کامل و نوع
  `diagonal_spread`؛ vertical فقط با expiry یکسان (calendar همچنان قبل از آن تشخیص داده می‌شود).

**تست:** `tests/unit/options/test_margin_contract_and_diagonal.py` (۳).

## ۶) FIN-11 — واحد VaR

قرارداد واحد: ورودی‌ها **اعشار** (`0.02` = ۲٪)، `var_*` مبلغ ارزی، `var_*_pct` درصد واقعی
(`2.5` = ۲.۵٪). ورودی درصدی (median |r| > 0.5 یا mu/sigma خارج از دامنه) با `ValueError` رد
می‌شود؛ NaN/inf هم رد می‌شود. `greeks_based_var` نیز درصد واقعی برمی‌گرداند.
**تست:** `tests/unit/options/test_var_units.py` (۷) + به‌روزرسانی یک assertion قدیمی
(`test_var_calculator.py:32`) که قرارداد اعشاری قبلی را قفل کرده بود.

## ۷) FIN-12 — کف حباب غیرعادی

`BUBBLE_ANOMALY_FLOOR_PCT = -10.0` در `constants.py`:
- `scorer.score_bubble`: حباب زیر کف → ۰ امتیاز با دلیل «غیرعادی/داده مشکوک»؛
- `hotpath.compute_quick_signal`: → `wait` با confidence 0 (نه buy 0.9).
حباب منفی ملایم (−۳٪) مثل قبل خرید/امتیاز کامل می‌گیرد.
**تست:** `tests/unit/gold_desk/test_bubble_anomaly_floor.py` (۴).

## ۸) اجرای تست

| مجموعه | نتیجه |
|---|---|
| ۲۴ تست جدید مرحله (۵ فایل) | ۲۴ passed |
| `tests/unit/options` + `tests/unit/ml` + `tests/unit/gold_desk` + `tests/gold_desk` + `tests/unit/backtesting` | **۱۲۵۰ passed، ۲ skipped، ۶ failed** |
| ۶ شکست | `test_weight_optimizer.py` (۴) و `test_phase0_snapshot_integration.py` (۲) — «Cannot connect to PostgreSQL»؛ محیط، نه رگرسیون |
| ruff روی فایل‌های تغییریافته | پاک |

**محدودیت‌ها:** ML retrain/بک‌تست با دادهٔ واقعی اجرا نشد (DB در دسترس نیست)؛ predicate مشترک
فعلاً فقط برای DCA است؛ شارپ `backtest_real.py` روی بازده هر معامله (تعریف متفاوت، عمداً دست‌نخورده)؛
`src/gold_desk/backtest_runner` فقط کارمزد خرید را در شبیه‌سازی دارد (مالیات فروش در آن مسیر نیست).
