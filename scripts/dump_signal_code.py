"""
تمام کدهای مرتبط با تولید سیگنال چندبازاره را به یک فایل متنی تبدیل می‌کند.
اجرا: python scripts/dump_signal_code.py
خروجی: signal_code_dump.txt
"""
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# فایل‌های مرتبط با تولید سیگنال
FILES = [
    # Backend — موتور تولید سیگنال
    "services/multi_market_signal_engine.py",
    # Backend — ارکستراتور ( pipeline کامل )
    "services/quant_signal_orchestrator.py",
    # Backend — موتور تصمیم‌گیری (10 دروازه)
    "services/signal_decision_engine.py",
    # Backend — امتیازدهی اطمینان
    "services/confidence_scorer.py",
    # Backend — کالیبراسیون احتمال
    "services/probability_calibrator.py",
    # Backend — سیستم رأی‌گیری
    "services/signal_voting_system.py",
    # Backend — کانکتور ML
    "services/ml_signal_connector.py",
    # Backend — پایپلاین ویژگی
    "services/signal_feature_pipeline.py",
    # Backend — دقت سیگنال
    "services/signal_accuracy_tracker.py",
    # Backend — بازآموزی خودکار
    "services/auto_retrain_pipeline.py",
    # Backend — همبستگی بین‌بازاری (بخشی از orchestrator)
    # Backend — API endpoint
    "apps/api/endpoints/multi_market_signals.py",
    # Backend — کانفیگ سیاست
    "config/signal_policy.yaml",
    # Frontend — صفحه سیگنال
    "frontend/src/app/multi-market-signals/page.tsx",
    # Frontend — رادار
    "frontend/src/app/multi-market-signals/MarketBiasRadar.tsx",
]

OUTPUT = PROJECT / "signal_code_dump.txt"

with open(OUTPUT, "w", encoding="utf-8") as out:
    out.write("=" * 80 + "\n")
    out.write("  Iran Market Platform — Multi-Market Signal Generation Code Dump\n")
    out.write("  Generated: 2026-07-23\n")
    out.write("=" * 80 + "\n\n")

    # فهرست
    out.write("TABLE OF CONTENTS\n")
    out.write("-" * 40 + "\n")
    for i, f in enumerate(FILES, 1):
        full = PROJECT / f
        exists = "OK" if full.exists() else "MISSING"
        out.write(f"  {i:2d}. [{exists}] {f}\n")
    out.write("\n" + "=" * 80 + "\n\n")

    for f in FILES:
        full = PROJECT / f
        out.write("=" * 80 + "\n")
        out.write(f"FILE: {f}\n")
        out.write("=" * 80 + "\n\n")

        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            out.write(content)
        else:
            out.write(f"[FILE NOT FOUND: {full}]\n")

        out.write("\n\n")

    # خلاصه معماری
    out.write("=" * 80 + "\n")
    out.write("ARCHITECTURE SUMMARY\n")
    out.write("=" * 80 + "\n")
    out.write("""
Signal Generation Pipeline:

  1. MultiMarketSignalEngine.generate_all()
     ├── _signals_stocks()     → SMA/RSI/MACD/ATR + Smart Money
     ├── _signals_gold()       → Momentum + Volume
     ├── _signals_currency()   → Trend + Rate-of-change
     ├── _signals_crypto()     → RSI + MACD + Volume
     ├── _signals_options()    → PCR + OI + IV
     ├── _signals_commodities()→ Trend + Seasonal
     └── _signals_ime()        → Futures basis

  2. QuantSignalOrchestrator.generate()
     ├── Stage 1: Rule-based signals (above)
     ├── Stage 2: ML predictions (MLSignalConnector)
     ├── Stage 3: Voting (SignalVotingSystem)
     ├── Stage 3.5: Probability calibration
     ├── Stage 4: Confidence calibration (ConfidenceScorer)
     ├── Stage 4.5: Decision engine (10-gate pipeline)
     │   ├── Gate 1: Data Quality
     │   ├── Gate 2: Model Health
     │   ├── Gate 3: Probability threshold
     │   ├── Gate 4: Market regime
     │   ├── Gate 5: Ensemble consensus
     │   ├── Gate 6: Liquidity
     │   ├── Gate 7: Risk/Reward ratio
     │   ├── Gate 8: Net expectancy
     │   ├── Gate 9: Portfolio risk
     │   └── Gate 10: Execution feasibility
     ├── Stage 5: Cross-market correlation
     ├── Stage 6: Confidence filter + diversity quota
     └── Stage 7: Outcome recording + auto-retrain

  3. SignalPolicy (config/signal_policy.yaml)
     ├── Per-market thresholds (stock, gold, crypto, currency, commodity, option)
     ├── Grade definitions (A+, A, B, WATCHLIST, REJECT)
     └── Gate-specific configs (probability, expectancy, risk_reward, etc.)

  4. Frontend: /multi-market-signals
     ├── Market filter (all/stock/gold/currency/crypto/option/commodity/ime)
     ├── Timeframe filter (daily/2day/3day/weekly/monthly/quarterly)
     ├── Signal filter (buy/sell/hold)
     ├── Confidence slider
     └── Signal detail modal (11 columns per user spec)
""")

    out.write("=" * 80 + "\n")
    out.write("END OF DUMP\n")
    out.write("=" * 80 + "\n")

print(f"Done! Output: {OUTPUT}")
print(f"Total size: {OUTPUT.stat().st_size / 1024:.1f} KB")
