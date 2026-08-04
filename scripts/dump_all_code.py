"""
تمام کدهای برنامه را بخش به بخش به فایل‌های تکست تبدیل می‌کند.
خروجی: code_dump/ directory
"""
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT / "code_dump"
OUTPUT_DIR.mkdir(exist_ok=True)

SECTIONS = {
    "01_signal_engine": {
        "desc": "موتور تولید سیگنال چندبازاره",
        "files": [
            "services/multi_market_signal_engine.py",
        ]
    },
    "02_orchestrator": {
        "desc": "ارکستراتور سیگنال (Pipeline کامل)",
        "files": [
            "services/quant_signal_orchestrator.py",
        ]
    },
    "03_decision_engine": {
        "desc": "موتور تصمیم‌گیری 10 دروازه‌ای",
        "files": [
            "services/signal_decision_engine.py",
        ]
    },
    "04_confidence_scorer": {
        "desc": "امتیازدهی اطمینان",
        "files": [
            "services/confidence_scorer.py",
        ]
    },
    "05_probability_calibrator": {
        "desc": "کالیبراسیون احتمال",
        "files": [
            "services/probability_calibrator.py",
        ]
    },
    "06_voting_system": {
        "desc": "سیستم رأی‌گیری",
        "files": [
            "services/signal_voting_system.py",
        ]
    },
    "07_ml_connector": {
        "desc": "کانکتور ML",
        "files": [
            "services/ml_signal_connector.py",
        ]
    },
    "08_feature_pipeline": {
        "desc": "پایپلاین ویژگی",
        "files": [
            "services/signal_feature_pipeline.py",
        ]
    },
    "09_accuracy_tracker": {
        "desc": "ردیابی دقت سیگنال",
        "files": [
            "services/signal_accuracy_tracker.py",
        ]
    },
    "10_auto_retrain": {
        "desc": "بازآموزی خودکار",
        "files": [
            "services/auto_retrain_pipeline.py",
        ]
    },
    "11_api_endpoint": {
        "desc": "API Endpoint سیگنال",
        "files": [
            "apps/api/endpoints/multi_market_signals.py",
        ]
    },
    "12_signal_policy": {
        "desc": "کانفیگ سیاست سیگنال",
        "files": [
            "config/signal_policy.yaml",
        ]
    },
    "13_frontend_page": {
        "desc": "صفحه فرانت‌اند سیگنال",
        "files": [
            "frontend/src/app/multi-market-signals/page.tsx",
            "frontend/src/app/multi-market-signals/MarketBiasRadar.tsx",
        ]
    },
    "14_brsapi_service": {
        "desc": "سرویس دریافت تاریخچه BrsApi",
        "files": [
            "brsapi/services/history_fetch_service.py",
            "brsapi/models/codal.py",
            "brsapi/parsers/codal.py",
        ]
    },
    "15_brsapi_endpoints": {
        "desc": "API Endpoint‌های BrsApi",
        "files": [
            "apps/api/endpoints/brsapi.py",
        ]
    },
    "16_brsapi_frontend": {
        "desc": "صفحه فرانت‌اند BrsApi",
        "files": [
            "frontend/src/app/brsapi/page.tsx",
        ]
    },
    "17_ml_models": {
        "desc": "مدل‌های ML",
        "files": [
            "ml/models/registry.py",
            "ml/evaluation/metrics.py",
        ]
    },
    "18_database": {
        "desc": "دیتابیس و مدل‌ها",
        "files": [
            "core/database.py",
            "brsapi/models/commodity.py",
            "brsapi/models/crypto.py",
            "brsapi/models/tsetmc.py",
        ]
    },
    "19_main_app": {
        "desc": "应用程序 اصلی",
        "files": [
            "main.py",
            "apps/api/router.py",
            "apps/api/app.py",
        ]
    },
    "20_scripts": {
        "desc": "اسکریپت‌ها",
        "files": [
            "scripts/fetch_all_history.py",
            "scripts/fetch_codal_all.py",
            "scripts/import_history_data.py",
        ]
    },
}

total_lines = 0
total_files = 0

for section_key, section_info in SECTIONS.items():
    section_dir = OUTPUT_DIR / section_key
    section_dir.mkdir(exist_ok=True)

    # Section index file
    index_content = f"{'=' * 70}\n"
    index_content += f"  {section_info['desc']}\n"
    index_content += f"{'=' * 70}\n\n"

    for f in section_info["files"]:
        full = PROJECT / f
        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            lines = content.count("\n") + 1
            total_lines += lines
            total_files += 1

            # Save individual file
            out_file = section_dir / Path(f).name
            out_file.write_text(content, encoding="utf-8")

            index_content += f"--- {f} ({lines} lines) ---\n\n"
            index_content += content
            index_content += "\n\n"
        else:
            index_content += f"--- {f} [NOT FOUND] ---\n\n"

    # Save section index
    (section_dir / "_INDEX.txt").write_text(index_content, encoding="utf-8")

    print(f"  {section_key}: {section_info['desc']}")

print(f"\nDone! {total_files} files, {total_lines} total lines")
print(f"Output: {OUTPUT_DIR}")

# Also create a master file
master = OUTPUT_DIR / "00_ALL_CODE.txt"
master_content = f"{'=' * 70}\n"
master_content += "  Iran Market Platform — Complete Code Dump\n"
master_content += f"  Total: {total_files} files, {total_lines} lines\n"
master_content += f"{'=' * 70}\n\n"

for section_key, section_info in SECTIONS.items():
    master_content += f"\n{'#' * 70}\n"
    master_content += f"# {section_key}: {section_info['desc']}\n"
    master_content += f"{'#' * 70}\n\n"

    for f in section_info["files"]:
        full = PROJECT / f
        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            master_content += f"\n{'=' * 50}\n"
            master_content += f"FILE: {f}\n"
            master_content += f"{'=' * 50}\n\n"
            master_content += content
            master_content += "\n"

master.write_text(master_content, encoding="utf-8")
print(f"Master file: {master} ({master.stat().st_size / 1024:.0f} KB)")
