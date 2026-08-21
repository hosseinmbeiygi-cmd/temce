# 🛠️ scripts/ — اسکریپت‌های جانبی و ابزارهای عملیاتی

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۲ — فاز ۱۱ (پاک‌سازی ۵۴ اسکریپت مرده)

ابزارهای خط فرمان برای مدیریت، همگام‌سازی، ایمپورت داده، آموزش مدل‌های ML، بک‌تست و نگهداری دیتابیس. این اسکریپت‌ها معمولاً **به‌صورت دستی یا توسط scheduler** اجرا می‌شوند (نه از طریق API).

---

## 🧹 پاک‌سازی انجام‌شده (فاز ۱۱)

**۵۴ فایل مرده حذف شدند** (با تأیید کاربر، محدوده «متوسط» + ۴ کاندید تکمیلی):

| دسته | تعداد | نمونه |
|------|-------|-------|
| `debug_*` (یکبارمصرف دیباگ) | ۱۳ | `debug_gates2/3`, `debug_db_check`, `debug_subprocess*` |
| `check_*` (بازرسی دستی DB) | ۲۷ | `check_codal*`, `check_db_*`, `check_tables` |
| `dump_*` (خروجی کد) | ۳ | `dump_all_code`, `dump_complete`, `dump_signal_code` |
| آشغال / منسوخ | ۷ | `gen.py`, `decoder.py`, `_add_pythonpath.py`, `drop_all_tables.py`, `import_csv.py` (stub), `test_train_results.json`, `train_results.json` |
| یکبارمصرف هم‌خانواده (تکمیلی) | ۴ | `codal_check2.py`, `codal_check3.py`, `codal_deep.py`, `codal_audit.py` |

### 🔴 باگ بحرانی رفع‌شده
**`scripts/__init__.py` خراب بود** — تابع `bootstrap_environment` را import می‌کرد در حالی که نام واقعی تابع در `bootstrap_env.py` برابر `bootstrap` است → کل پکیج `scripts` با `ImportError` شکست می‌خورد و `services/sync_master_service.py` (که از `scripts.full_populate_profiles` و `scripts.update_free_float` استفاده می‌کند) آسیب می‌دید. با alias رفع شد:
```python
from scripts.bootstrap_env import bootstrap as bootstrap_environment
```

### 🟡 حذف تکمیلی کاندیدهای هم‌خانواده
هر ۴ فایل بدون هیچ ارجاعی در کد بودند و حذف شدند. (توجه: جدول دیتابیس `codal_audit_summary` که در API استفاده می‌شود دست‌نخورده است — فقط اسکریپت‌ها حذف شدند.)

---

## 🗂️ دسته‌بندی اسکریپت‌های باقی‌مانده (~۱۲۸ فایل)

### 📥 ایمپورت داده
| اسکریپت | کاربرد |
|---------|--------|
| `import_data.py` | ایمپورت نمادها از CSV/JSON/Excel (جایگزین `import_csv.py` حذف‌شده) — توسط API هم استفاده می‌شود |
| `import_quotes.py` | ایمپورت فایل‌های روزانه قیمت (با `--dry-run`, `--only`, `--source`) |
| `import_history_data.py` / `import_history_to_db.py` | ایمپورت تاریخچه قیمت |
| `import_codal.py` | ایمپورت فایل‌های کدال (CSV/JSON/Excel) |
| `import_codal_excel.py` / `import_codal_json.py` | ایمپورت سریع صورت‌های مالی کدال |
| `import_codal_to_profiles.py` | انتقال داده بنیادی به `screener_profiles` |
| `import_shareholders.py` / `import_real_legal.py` | سهامداران حقیقی/حقوقی |
| `import_transactions.py` / `import_transaction_top43.py` | تراکنش‌ها |
| `import_gold_currency_history.py` | تاریخچه طلا و ارز |
| `import_backtest_data.py` / `import_analysis_data.py` | داده بک‌تست و تحلیل |
| `import_initial_symbols.py` | نمادهای اولیه |

### 🔄 همگام‌سازی و دریافت داده
| اسکریپت | کاربرد |
|---------|--------|
| `brsapi_full_update.py` | بروزرسانی کامل BrsApi (توسط scheduler ویندوز صدا زده می‌شود) |
| `sync_live_data.py` | همگام‌سازی داده زنده (توسط scheduler ویندوز) |
| `sync_historical_batch.py` | بک‌فیل تاریخچه به‌صورت دسته‌ای |
| `sync_all_tables.py` / `sync_all_brsapi.py` | همگام‌سازی همه جداول |
| `sync_codal_with_ins_id.py` | اتصال کدال به instrument_id |
| `sync_symbol_details_all.py` | جزئیات همه نمادها |
| `sync_master_run.py` | اجرای همگام‌سازی جامع |
| `fetch_news.py` | دریافت اخبار از همه منابع (بسیار قابل‌تنظیم) |
| `fetch_codal_all.py` / `fetch_all_history.py` / `fetch_crypto_history.py` / `fetch_quote_direct.py` | دریافت داده از منابع مختلف |
| `smart_fetch.py` | دریافت هوشمند |

### 🤖 آموزش مدل‌های ML
| اسکریپت | کاربرد |
|---------|--------|
| `train.py` | **لانچر واحد آموزش** — حالت‌های `quick`/`full`/`legacy` |
| `train_all_symbols.py` | آموزش همه نمادها (موازی با `--workers`) |
| `train_all_models.py` | همه مدل‌ها روی همه نمادها (با resume) |
| `train_baseline_models.py` / `train_model_direct.py` | مدل پایه / آموزش مستقیم |
| `train_now.py` | آموزش سریع از `brsapi_historical_daily` |
| `run_ml_all_symbols.py` / `run_ml_dual.py` / `run_train_all_symbols.py` | اجرای آموزش ML |

### 📊 بک‌تست
| اسکریپت | کاربرد |
|---------|--------|
| `run_full_backtest.py` | بک‌تست کامل |
| `backtest_all_symbols.py` / `run_all_backtests.py` | بک‌تست همه نمادها |
| `run_sample_backtest.py` / `run_ml_all_symbols.py` | نمونه/ML |
| `batch_backtest_ml.py` / `batch_final.py` | اجرای دسته‌ای |

### 🌱 Seed و Bootstrap
| اسکریپت | کاربرد |
|---------|--------|
| `bootstrap_env.py` | ساخت پوشه‌های داده و `.env` (الزامی قبل از اجرا) |
| `seed_architecture.py` / `seed_decisions.py` / `seed_funds.py` | داده اولیه معماری/تصمیم/صندوق |
| `full_populate_profiles.py` / `populate_profiles.py` | پر کردن پروفایل‌ها (توسط sync_master_service استفاده می‌شود) |
| `update_free_float.py` | بروزرسانی درصد شناوری (توسط sync_master_service) |
| `install_timescaledb.py` | نصب TimescaleDB |
| `create_missing_partitions.py` / `merge_year_tables.py` | مدیریت پارتیشن |
| `populate_24h_tables.py` / `create_symbol_kpi_view.py` | جدول‌های ۲۴ ساعته و KPI |

### 🚀 اجرای محلی
| اسکریپت | کاربرد |
|---------|--------|
| `start_scheduler.py` | اجرای Scheduler (با `--daemon`) — توسط launcherها صدا زده می‌شود |
| `run_local_api.py` / `run_local_admin.py` / `run_local_workers.py` | اجرای محلی API/ادمین/workerها |
| `run_brsapi_sync.py` / `run_codal_import.py` | همگام‌سازی/ایمپورت پس‌زمینه |

### 🧹 نگهداری و تعمیر
| اسکریپت | کاربرد |
|---------|--------|
| `backup_postgres.py` | پشتیبان‌گیری PostgreSQL |
| `cleanup_duplicate_symbols.py` / `remove_duplicate_symbols.py` / `find_duplicate_symbols.py` | حذف/یافتن نمادهای تکراری |
| `cleanup_storage.py` / `migrate_raw_payloads.py` | پاک‌سازی/مهاجرت ذخیره‌سازی |
| `migrate_symbols_to_instruments.py` | مهاجرت به جدول instruments |
| `fix_categories.py` / `fix_news_categories.py` / `fix_remaining_categories.py` | اصلاح دسته‌بندی اخبار |
| `fix_eps.py` / `fix_codal.py` / `fix_historical_id*` / `fix_null_market_field.py` / `fix_save.py` | اصلاح‌های داده |
| `rebuild_features.py` / `rebuild_indicators.py` | بازسازی ویژگی‌ها/اندیکاتورها |
| `check_*` بقیه / `verify_tables.py` / `list_tables*.py` / `show_brsapi_tables.py` / `audit_data_access.py` / `add_constraints.py` | بازرسی و اعتبارسنجی |
| `create_sqlserver_schema.py` / `export_clean_symbols.py` / `export_symbols.py` | صادرات/اسکیما |
| `extract_codal_financials.py` / `analyze_patterns.py` / `analyze_shareholders.py` | تحلیل |
| `stamp_migration.py` | علامت‌گذاری ریویژن‌های alembic |
| `batch_audit_all_symbols.py` / `audit_data_access.py` | ممیزی |

### 🧪 تست دستی (غیر pytest)
> این فایل‌ها با پیشوند `test_*` **تست‌های واحد نیستند** — اسکریپت‌های smoke-test دستی‌اند و در `pytest` اجرا نمی‌شوند. تست‌های واقعی در `tests/unit/` هستند.
`test_single_symbol.py`, `test_ml_*.py`, `test_train_*.py`, `test_excel_parser*.py`, `test_backtest_runs.py`, `test_codal_api.py`, `test_worker.py`, `test_real_legal_insert.py`, `test_service_direct.py`, `test_strategy_generator.py`, `test_alpha_direct.py`

### ⚙️ اسکریپت‌های ویندوز/لینوکس
| فایل | کاربرد |
|------|--------|
| `setup_windows_scheduler.ps1` / `.bat` | نصب jobهای قدیمی زمان‌بندی BrsApi (live/comprehensive/APScheduler) |
| `setup_brsapi_auto_sync.ps1` / `.bat` | نصب/حذف/بررسی Task اختصاصی سینک شبانه `sync_all_tables_auto.py` در ساعت ۰۰:۱۰ |
| `sync_all_tables_auto.bat` | wrapper دارای لاگ برای اجرای Task Scheduler؛ لاگ در `logs/brsapi_sync_YYYYMMDD.log` |
| `install_brsapi_tasks_silent.ps1` | نصب بی‌صدا taskهای BrsApi |
| `fetch_news_daily.ps1` / `.bat` | اجرای روزانه `fetch_news.py` |
| `ci_simulate_local.sh` | شبیه‌سازی CI به‌صورت محلی |
| `setup_secrets.sh` | تنظیم secrets در لینوکس |

---

## 🚀 شروع سریع

```bash
# ۱. آماده‌سازی محیط
python scripts/bootstrap_env.py

# ۲. ایمپورت داده
python scripts/import_data.py path/to/symbols.csv
python scripts/import_quotes.py path/to/daily/files/ --dry-run

# ۳. همگام‌سازی
python scripts/sync_historical_batch.py
python scripts/fetch_news.py --top 20

# ۴. آموزش ML
python scripts/train.py --mode quick --symbols فولاد,فملی

# ۵. بک‌تست
python scripts/run_sample_backtest.py

# ۶. اجرای زمان‌بندی قدیمی (در صورت نیاز)
python scripts/start_scheduler.py

# ۷. نصب سینک خودکار شبانه در Windows Task Scheduler
scripts\\setup_brsapi_auto_sync.bat

# بررسی Task ثبت‌شده
scripts\\setup_brsapi_auto_sync.bat -Status

# حذف Task
scripts\\setup_brsapi_auto_sync.bat -Uninstall
```

> **نکته:** همه اسکریپت‌ها با `python scripts/<name>.py` از ریشه پروژه اجرا می‌شوند. `bootstrap_env.py` مسیر پروژه را خودکار به `sys.path` اضافه می‌کند.

---

## ✅ اعتبارسنجی
- **py_compile** روی همه اسکریپت‌های باقی‌مانده ✅
- **ruff** روی اسکریپت‌های کلیدی ✅
- **import پکیج** (`from scripts import bootstrap`) ✅
- **import سرویس‌ها** (`scripts.full_populate_profiles`, `scripts.update_free_float`) ✅
