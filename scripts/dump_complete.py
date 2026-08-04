"""
یک فایل تکست کامل از تمام کدهای برنامه
خروجی: COMPLETE_CODE.txt
"""
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT / "COMPLETE_CODE.txt"

# تمام فایل‌های مهم برنامه
ALL_FILES = [
    # ── سیگنال ──
    "services/multi_market_signal_engine.py",
    "services/quant_signal_orchestrator.py",
    "services/signal_decision_engine.py",
    "services/confidence_scorer.py",
    "services/probability_calibrator.py",
    "services/signal_voting_system.py",
    "services/ml_signal_connector.py",
    "services/signal_feature_pipeline.py",
    "services/signal_accuracy_tracker.py",
    "services/auto_retrain_pipeline.py",
    # ── API ──
    "apps/api/endpoints/multi_market_signals.py",
    "apps/api/endpoints/brsapi.py",
    "apps/api/router.py",
    "apps/api/app.py",
    "apps/api/dependencies.py",
    # ── کانفیگ ──
    "config/signal_policy.yaml",
    ".env",
    # ── فرانت‌اند ──
    "frontend/src/app/multi-market-signals/page.tsx",
    "frontend/src/app/multi-market-signals/MarketBiasRadar.tsx",
    "frontend/src/app/brsapi/page.tsx",
    "frontend/src/lib/api.ts",
    "frontend/src/components/layout/AppLayout.tsx",
    # ── دیتابیس ──
    "core/database.py",
    "brsapi/models/codal.py",
    "brsapi/models/commodity.py",
    "brsapi/models/crypto.py",
    "brsapi/models/tsetmc.py",
    "brsapi/models/base.py",
    "brsapi/parsers/codal.py",
    "brsapi/parsers/commodity.py",
    "brsapi/parsers/tsetmc.py",
    "brsapi/services/history_fetch_service.py",
    # ── ML ──
    "ml/models/registry.py",
    "ml/evaluation/metrics.py",
    # ── مدل‌های ORM ──
    "models/historical_daily.py",
    "models/symbol_snapshots.py",
    "models/codal_reports.py",
    # ── اسکریپت‌ها ──
    "scripts/fetch_all_history.py",
    "scripts/fetch_codal_all.py",
    "scripts/import_history_data.py",
    "scripts/train_all_symbols.py",
    # ── اپلیکیشن اصلی ──
    "main.py",
]

with open(OUTPUT, "w", encoding="utf-8") as out:
    out.write("=" * 80 + "\n")
    out.write("  Iran Market Platform — COMPLETE CODE DUMP\n")
    out.write("  تمام کدهای برنامه در یک فایل\n")
    out.write(f"  تعداد فایل‌ها: {len(ALL_FILES)}\n")
    out.write("=" * 80 + "\n\n")

    # فهرست
    out.write("TABLE OF CONTENTS\n")
    out.write("-" * 40 + "\n")
    total = 0
    for i, f in enumerate(ALL_FILES, 1):
        full = PROJECT / f
        if full.exists():
            lines = full.read_text(encoding="utf-8", errors="replace").count("\n") + 1
            total += lines
            out.write(f"  {i:2d}. {f} ({lines} lines)\n")
        else:
            out.write(f"  {i:2d}. {f} [NOT FOUND]\n")
    out.write(f"\n  Total: {total} lines\n")
    out.write("\n" + "=" * 80 + "\n\n")

    for f in ALL_FILES:
        full = PROJECT / f
        out.write("\n" + "#" * 80 + "\n")
        out.write(f"# FILE: {f}\n")
        out.write("#" * 80 + "\n\n")

        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            out.write(content)
        else:
            out.write("[FILE NOT FOUND]\n")

        out.write("\n")

    out.write("\n" + "=" * 80 + "\n")
    out.write("END OF COMPLETE CODE DUMP\n")
    out.write("=" * 80 + "\n")

size = OUTPUT.stat().st_size
print("Done!")
print(f"  File: {OUTPUT}")
print(f"  Size: {size / 1024:.0f} KB ({size / (1024*1024):.1f} MB)")
print(f"  Lines: {total}")
print(f"  Files: {len(ALL_FILES)}")
