"""
📊 Signal Quality Benchmark — زنجیره کامل کیفیت سیگنال‌ها

این بنچمارک زنجیره کامل سیگنال را اجرا کرده و معیارهای کیفی
avg_confidence, signal distribution, calibration quality, decision distribution
را اندازه‌گیری و گزارش می‌دهد.

Usage:
    python tests/benchmark_signal_quality.py              # با دیتابیس واقعی
    python tests/benchmark_signal_quality.py --mock        # با داده مصنوعی
    python tests/benchmark_signal_quality.py --quick       # فقط mock — سریع
    python tests/benchmark_signal_quality.py --json        # خروجی JSON
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Ensure project root is on sys.path so ``services`` etc. can be imported
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ── ANSI Colors (ASCII-safe, no emoji for Windows cp1252) ───────────────────

class _C:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


# ASCII replacements for emoji (cp1252-safe)
_ROCKET = "[==>"
_CHART = "[CHART]"
_TARGET = "[TARGET]"
_SHIELD = "[SHIELD]"
_GLOBE = "[GLOBE]"
_COMPASS = "[COMPASS]"
_CHECK = "[OK]"
_CROSS = "[X]"
_WARN = "[!]"


def _p(label: str, value: Any, unit: str = "", color: str = "") -> str:
    """Pretty-print a metric."""
    c = color or _C.OKCYAN
    return f"  {c}{label}: {_C.BOLD}{value}{_C.ENDC}{c} {unit}{_C.ENDC}"


# ── Quality Metrics ──────────────────────────────────────────────────────────


@dataclass
class SignalQualityMetrics:
    """Comprehensive signal quality metrics from a benchmark run."""

    # ── Signal volume ──
    total_signals: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0

    # ── Confidence ──
    avg_confidence: float = 0.0
    median_confidence: float = 0.0
    min_confidence: float = 1.0
    max_confidence: float = 0.0
    confidence_std: float = 0.0
    confidence_histogram: dict[str, int] = field(default_factory=lambda: {
        "0.00-0.20": 0, "0.20-0.40": 0, "0.40-0.60": 0,
        "0.60-0.80": 0, "0.80-1.00": 0,
    })

    # ── Calibration ──
    calibration_counts: dict[str, int] = field(default_factory=lambda: {
        "very_high": 0, "high": 0, "medium": 0, "low": 0,
    })

    # ── Decision ──
    decision_counts: dict[str, int] = field(default_factory=lambda: {
        "release": 0, "watchlist": 0, "reject": 0, "ungated": 0,
    })
    grade_distribution: dict[str, int] = field(default_factory=dict)

    # ── Score ──
    avg_rule_score: float = 0.0
    avg_boosted_score: float = 0.0
    avg_ml_influence_pct: float = 0.0
    avg_ml_score: float = 0.0

    # ── Market breakdown ──
    markets: dict[str, dict[str, int]] = field(default_factory=dict)

    # ── Calibrated probability ──
    avg_calibrated_probability: float = 0.0
    avg_effective_threshold: float = 0.0
    avg_net_expectancy_r: float = 0.0

    # ── Cross-market ──
    cross_market_signals_count: int = 0
    cross_market_types: list[str] = field(default_factory=list)

    # ── Performance ──
    generation_duration_ms: float = 0.0
    signal_count: int = 0
    use_real_data: bool = False

    # ── Summary ──
    quality_score: float = 0.0  # 0-100 composite score

    def compute(self, signals: list[Any]) -> SignalQualityMetrics:
        """Compute all metrics from a list of signals."""
        self.total_signals = len(signals)

        if not signals:
            return self

        # ── Direction counts ──
        self.buy_count = sum(1 for s in signals if s.direction == "buy")
        self.sell_count = sum(1 for s in signals if s.direction == "sell")
        self.hold_count = sum(1 for s in signals if s.direction in ("hold", "wait"))

        # ── Confidence ──
        confidences = [s.confidence for s in signals]
        self.avg_confidence = sum(confidences) / len(confidences)
        sorted_conf = sorted(confidences)
        self.median_confidence = sorted_conf[len(sorted_conf) // 2]
        self.min_confidence = min(confidences)
        self.max_confidence = max(confidences)
        variance = sum((c - self.avg_confidence) ** 2 for c in confidences) / len(confidences)
        self.confidence_std = math.sqrt(max(0.0, variance))

        # Confidence histogram
        for c in confidences:
            for lo, hi, key in [
                (0.0, 0.20, "0.00-0.20"), (0.20, 0.40, "0.20-0.40"),
                (0.40, 0.60, "0.40-0.60"), (0.60, 0.80, "0.60-0.80"),
                (0.80, 1.01, "0.80-1.00"),
            ]:
                if lo <= c < hi:
                    self.confidence_histogram[key] += 1
                    break

        # ── Calibration ──
        cal_levels = [s.calibration_level for s in signals]
        for cl in cal_levels:
            self.calibration_counts[cl] = self.calibration_counts.get(cl, 0) + 1

        # ── Decision ──
        for s in signals:
            verdict = getattr(s, "decision_verdict", "") or "ungated"
            self.decision_counts[verdict] = self.decision_counts.get(verdict, 0) + 1

            grade = getattr(s, "decision_grade", "") or "UNGRADED"
            self.grade_distribution[grade] = self.grade_distribution.get(grade, 0) + 1

        # ── Scores ──
        rule_scores = [s.rule_score for s in signals]
        boosted_scores = [s.boosted_score for s in signals]
        ml_influences = [s.ml_influence_pct for s in signals]
        ml_scores = [s.ml_score for s in signals]

        self.avg_rule_score = sum(rule_scores) / len(rule_scores)
        self.avg_boosted_score = sum(boosted_scores) / len(boosted_scores)
        self.avg_ml_influence_pct = sum(ml_influences) / len(ml_influences)
        self.avg_ml_score = sum(ml_scores) / len(ml_scores)

        # ── Market breakdown ──
        for s in signals:
            m = s.market
            if m not in self.markets:
                self.markets[m] = {"buy": 0, "sell": 0, "hold": 0}
            if s.direction == "buy":
                self.markets[m]["buy"] += 1
            elif s.direction == "sell":
                self.markets[m]["sell"] += 1
            else:
                self.markets[m]["hold"] += 1

        # ── Probability / Threshold / Expectancy ──
        cal_probs = [getattr(s, "calibrated_probability", s.confidence) for s in signals]
        thresholds = [getattr(s, "effective_threshold", 0.55) for s in signals]
        expectancies = [getattr(s, "net_expectancy_r", 0.0) for s in signals]

        self.avg_calibrated_probability = sum(cal_probs) / len(cal_probs)
        self.avg_effective_threshold = sum(thresholds) / len(thresholds)
        self.avg_net_expectancy_r = sum(expectancies) / len(expectancies)

        # ── Composite Quality Score (0-100) ──
        # Formula: weighted combination of key metrics
        confidence_score = min(100, self.avg_confidence * 125)  # 0.8 → 100
        calibration_score = (
            (self.calibration_counts.get("very_high", 0) * 100 +
             self.calibration_counts.get("high", 0) * 75 +
             self.calibration_counts.get("medium", 0) * 50 +
             self.calibration_counts.get("low", 0) * 25) /
            max(self.total_signals, 1)
        )
        decision_score = (
            self.decision_counts.get("release", 0) * 100 +
            self.decision_counts.get("watchlist", 0) * 50
        ) / max(self.total_signals, 1)
        diversity_score = min(100, len(self.markets) * 15)  # up to 7 markets → 105
        signal_score = min(100, self.avg_boosted_score)

        self.quality_score = (
            confidence_score * 0.25 +
            calibration_score * 0.25 +
            decision_score * 0.20 +
            diversity_score * 0.10 +
            signal_score * 0.20
        )

        return self

    def report(self) -> str:
        """Generate a formatted report string."""
        lines: list[str] = []
        lines.append(f"\n{_C.HEADER}{'='*60}{_C.ENDC}")
        lines.append(f"{_C.HEADER}{_C.BOLD}  {_CHART} SIGNAL QUALITY BENCHMARK REPORT{_C.ENDC}")
        lines.append(f"{_C.HEADER}{'='*60}{_C.ENDC}")

        # Quality score
        qs = self.quality_score
        if qs >= 75:
            qc = _C.OKGREEN
        elif qs >= 50:
            qc = _C.WARNING
        else:
            qc = _C.FAIL
        lines.append(f"  {qc}{_C.BOLD}  Quality Score: {qs:.1f}/100{_C.ENDC}")
        lines.append(f"  {'[GOOD]' if qs >= 60 else '[WARN]'}  Target: >70% accuracy | Current composite: {qs:.1f}")
        lines.append("")

        # Overview
        lines.append(f"  {_C.BOLD}  Overview{_C.ENDC}")
        lines.append(_p("Data Source", "REAL" if self.use_real_data else "MOCKED",
                        color=_C.OKGREEN if self.use_real_data else _C.WARNING))
        lines.append(_p("Total Signals", self.total_signals))
        lines.append(_p("Markets Covered", len(self.markets)))
        lines.append(_p("Generation Time", f"{self.generation_duration_ms:.1f}", "ms"))
        lines.append("")

        # Confidence
        lines.append(f"  {_C.BOLD}  Confidence{_C.ENDC}")
        conf_color = _C.OKGREEN if self.avg_confidence >= 0.55 else _C.WARNING if self.avg_confidence >= 0.40 else _C.FAIL
        lines.append(_p("Average", f"{self.avg_confidence:.3f}", color=conf_color))
        lines.append(_p("Median", f"{self.median_confidence:.3f}"))
        lines.append(_p("Std Dev", f"{self.confidence_std:.3f}"))
        lines.append(_p("Min -> Max", f"{self.min_confidence:.2f} -> {self.max_confidence:.2f}"))
        lines.append("  Histogram:")
        for key, count in sorted(self.confidence_histogram.items()):
            bar = "#" * min(count, 40)
            pct = count / max(self.total_signals, 1) * 100
            lines.append(f"    {key}: {bar} {count} ({pct:.1f}%)")
        lines.append("")

        # Calibration
        lines.append(f"  {_C.BOLD}  Calibration Levels{_C.ENDC}")
        for level in ["very_high", "high", "medium", "low"]:
            count = self.calibration_counts.get(level, 0)
            pct = count / max(self.total_signals, 1) * 100
            lines.append(f"    {level:12s}: {pct:5.1f}% ({count})")
        lines.append("")

        # Decision
        lines.append(f"  {_C.BOLD}  Decision Distribution{_C.ENDC}")
        for verdict in ["release", "watchlist", "reject", "ungated"]:
            count = self.decision_counts.get(verdict, 0)
            pct = count / max(self.total_signals, 1) * 100
            lines.append(f"    {verdict:10s}: {pct:5.1f}% ({count})")
        lines.append("")

        # Grade distribution
        if self.grade_distribution:
            lines.append(f"  {_C.BOLD}  Grade Distribution{_C.ENDC}")
            for grade in ["A+", "A", "B", "WATCHLIST", "REJECT", "UNGRADED"]:
                count = self.grade_distribution.get(grade, 0)
                if count:
                    pct = count / max(self.total_signals, 1) * 100
                    lines.append(f"    {grade:10s}: {pct:5.1f}% ({count})")
            lines.append("")

        # Scores
        lines.append(f"  {_C.BOLD}  Score Metrics{_C.ENDC}")
        lines.append(_p("Avg Rule Score", f"{self.avg_rule_score:.1f}", "/100"))
        lines.append(_p("Avg Boosted Score", f"{self.avg_boosted_score:.1f}", "/100"))
        lines.append(_p("Avg ML Score", f"{self.avg_ml_score:.3f}", "/1"))
        lines.append(_p("Avg ML Influence", f"{self.avg_ml_influence_pct:.1f}", "%"))
        lines.append("")

        # Market breakdown
        if self.markets:
            lines.append(f"  {_C.BOLD}  Market Breakdown{_C.ENDC}")
            for mkt in sorted(self.markets.keys()):
                data = self.markets[mkt]
                total = sum(data.values())
                buy_pct = data["buy"] / max(total, 1) * 100
                sell_pct = data["sell"] / max(total, 1) * 100
                hold_pct = data["hold"] / max(total, 1) * 100
                bar = "G" * min(data["buy"], 10) + "R" * min(data["sell"], 10) + "W" * min(data["hold"], 10)
                lines.append(f"    {mkt:10s}: {total:3d} signals {bar}")
                lines.append(f"             Buy {buy_pct:5.1f}% | Sell {sell_pct:5.1f}% | Hold {hold_pct:5.1f}%")
            lines.append("")

        # Probability / Threshold / Expectancy
        lines.append(f"  {_C.BOLD}  Advanced Metrics{_C.ENDC}")
        lines.append(_p("Avg Calibrated Prob", f"{self.avg_calibrated_probability:.3f}"))
        lines.append(_p("Avg Effective Threshold", f"{self.avg_effective_threshold:.3f}"))
        lines.append(_p("Avg Net Expectancy (R)", f"{self.avg_net_expectancy_r:.4f}"))
        lines.append("")

        # Cross-market
        if self.cross_market_signals_count > 0:
            lines.append(f"  {_C.BOLD}  Cross-Market Signals ({self.cross_market_signals_count}){_C.ENDC}")
            for cm in self.cross_market_types:
                lines.append(f"    . {cm}")
            lines.append("")

        # Direction breakdown
        buy_pct = self.buy_count / max(self.total_signals, 1) * 100
        sell_pct = self.sell_count / max(self.total_signals, 1) * 100
        hold_pct = self.hold_count / max(self.total_signals, 1) * 100
        lines.append(f"  {_C.BOLD}  Direction Breakdown{_C.ENDC}")
        lines.append(f"    [BUY]  {_C.OKGREEN}{buy_pct:5.1f}%{_C.ENDC} ({self.buy_count})")
        lines.append(f"    [SELL] {_C.FAIL}{sell_pct:5.1f}%{_C.ENDC} ({self.sell_count})")
        lines.append(f"    [HOLD] {_C.WARNING}{hold_pct:5.1f}%{_C.ENDC} ({self.hold_count})")
        lines.append("")

        # Quality assessment
        lines.append(f"  {_C.BOLD}  Quality Assessment{_C.ENDC}")
        issues: list[str] = []
        strengths: list[str] = []

        if self.avg_confidence < 0.40:
            issues.append("[X] avg_confidence < 0.40 - too low")
        elif self.avg_confidence < 0.55:
            issues.append("[!] avg_confidence below 0.55 target")
        else:
            strengths.append(f"[OK] avg_confidence good ({self.avg_confidence:.2f})")

        if self.calibration_counts.get("low", 0) > self.total_signals * 0.4:
            issues.append("[X] Over 40% signals have low confidence")
        elif self.calibration_counts.get("very_high", 0) + self.calibration_counts.get("high", 0) > self.total_signals * 0.5:
            strengths.append(f"[OK] {self.calibration_counts.get('very_high', 0) + self.calibration_counts.get('high', 0)}/{self.total_signals} high-confidence signals")

        decision_release = self.decision_counts.get("release", 0)
        if decision_release < self.total_signals * 0.5:
            issues.append("[X] Less than 50% signals approved for release")
        elif decision_release > self.total_signals * 0.8:
            strengths.append(f"[OK] {decision_release}/{self.total_signals} signals released")

        if self.avg_net_expectancy_r > 0:
            strengths.append(f"[OK] Positive net expectancy ({self.avg_net_expectancy_r:.3f}R)")
        else:
            issues.append("[X] Negative net expectancy - strategy not profitable")

        for issue in issues:
            lines.append(f"  {issue}")
        for strength in strengths:
            lines.append(f"  {strength}")

        lines.append(f"\n{_C.HEADER}{'='*60}{_C.ENDC}\n")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_signals": self.total_signals,
            "avg_confidence": round(self.avg_confidence, 4),
            "median_confidence": round(self.median_confidence, 4),
            "confidence_std": round(self.confidence_std, 4),
            "min_confidence": round(self.min_confidence, 4),
            "max_confidence": round(self.max_confidence, 4),
            "confidence_histogram": self.confidence_histogram,
            "calibration_counts": self.calibration_counts,
            "decision_counts": self.decision_counts,
            "grade_distribution": self.grade_distribution,
            "avg_rule_score": round(self.avg_rule_score, 2),
            "avg_boosted_score": round(self.avg_boosted_score, 2),
            "avg_ml_influence_pct": round(self.avg_ml_influence_pct, 2),
            "avg_ml_score": round(self.avg_ml_score, 4),
            "avg_calibrated_probability": round(self.avg_calibrated_probability, 4),
            "avg_effective_threshold": round(self.avg_effective_threshold, 4),
            "avg_net_expectancy_r": round(self.avg_net_expectancy_r, 4),
            "markets": self.markets,
            "quality_score": round(self.quality_score, 2),
            "cross_market_signals_count": self.cross_market_signals_count,
            "generation_duration_ms": round(self.generation_duration_ms, 2),
            "use_real_data": self.use_real_data,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "hold_count": self.hold_count,
            "signal_count": self.signal_count,
        }


# ── Mock Signal Generator ────────────────────────────────────────────────────

def _generate_mock_signals(count: int = 100) -> list[Any]:
    """Generate mock EnrichedSignal objects for benchmarking without a database."""
    import random

    from services.quant_signal_orchestrator import EnrichedSignal

    random.seed(42)
    markets = ["stock", "gold", "currency", "crypto", "option", "commodity", "ime"]
    directions = ["buy", "sell", "hold"]
    timeframes = ["daily", "weekly", "monthly"]

    signals = []
    for i in range(count):
        market = random.choice(markets)
        direction = random.choices(directions, weights=[0.4, 0.3, 0.3])[0]
        rule_score = random.uniform(30, 95)

        # Simulate ML boost for some signals
        has_ml = random.random() < 0.6
        ml_score = random.uniform(0.3, 0.85) if has_ml else 0.0
        ml_influence = random.uniform(5, 40) if has_ml else 0.0
        boosted = rule_score * (1 - ml_influence / 100) + ml_score * 100 * (ml_influence / 100)

        confidence = random.uniform(0.15, 0.85)
        if confidence >= 0.75:
            cal_level = "very_high"
        elif confidence >= 0.60:
            cal_level = "high"
        elif confidence >= 0.40:
            cal_level = "medium"
        else:
            cal_level = "low"

        # Decision based on confidence
        if confidence >= 0.60 and random.random() < 0.8:
            verdict = "release"
            grade = random.choices(["A+", "A", "B"], weights=[0.1, 0.3, 0.6])[0]
        elif confidence >= 0.40 and random.random() < 0.6:
            verdict = "watchlist"
            grade = "WATCHLIST"
        else:
            verdict = "reject"
            grade = "REJECT"

        cal_prob = confidence * random.uniform(0.85, 1.15)
        cal_prob = max(0.01, min(0.99, cal_prob))

        sig = EnrichedSignal(
            symbol=f"SYM{i:04d}",
            name=f"نماد {i}",
            market=market,
            direction=direction,
            timeframe=random.choice(timeframes),
            entry_zone="100-105",
            stop_loss="95",
            targets="110 | 120",
            risk_reward="1:2",
            position_sizing="3%",
            confirmation_condition="",
            reason="تحلیل بنچمارک",
            invalidation="",
            trailing_stop="",
            price=random.uniform(100, 10000),
            change_pct=random.uniform(-5, 5),
            rule_score=rule_score,
            ml_score=ml_score,
            boosted_score=boosted,
            ml_influence_pct=ml_influence,
            confidence=confidence,
            calibration_level=cal_level,
            confidence_factors={
                "historical_accuracy": random.uniform(0.4, 0.8),
                "model_agreement": random.uniform(0.3, 0.9),
                "trend_strength": random.uniform(0.3, 0.8),
                "volatility_regime": random.uniform(0.2, 0.7),
                "signal_strength": random.uniform(0.3, 0.9),
            },
            confidence_notes=["تست بنچمارک"],
            calibrated_probability=cal_prob,
            calibration_version="1.0.0",
            calibration_method="bucket",
            decision_verdict=verdict,
            decision_grade=grade,
            effective_threshold=0.55,
            net_expectancy_r=random.uniform(-0.2, 1.5),
            vote_strategy=random.choice(["weighted", "ml_weighted", "rule_only"]),
            vote_direction_scores={"buy": 0.6, "sell": 0.2, "hold": 0.2},
            source="benchmark",
            created_at=datetime.now().isoformat(),
        )
        signals.append(sig)

    return signals


# ── Benchmark Runner ─────────────────────────────────────────────────────────

async def run_benchmark(
    use_mock: bool = False,
    quick: bool = False,
    market_filter: str = "all",
    min_confidence: float = 0.35,
    limit: int = 100,
) -> SignalQualityMetrics:
    """Run the signal quality benchmark.

    Args:
        use_mock: If True, generate mock signals instead of querying DB
        quick: If True, skip the orchestrator and just use mock data
        market_filter: Market filter (all, stock, gold, etc.)
        min_confidence: Minimum confidence threshold
        limit: Maximum signals to process

    Returns:
        SignalQualityMetrics with all computed metrics
    """
    print(f"\n  {_C.HEADER}{_ROCKET} Running Signal Quality Benchmark...{_C.ENDC}")
    print(f"  Mode: {'QUICK MOCK' if quick else 'MOCK' if use_mock else 'REAL DB'}")
    print(f"  Market filter: {market_filter} | Min confidence: {min_confidence} | Limit: {limit}")
    print()

    start = time.monotonic()
    metrics = SignalQualityMetrics()
    metrics.use_real_data = not use_mock and not quick

    if quick or use_mock:
        # Quick mode: generate mock enriched signals directly
        print(f"  {_C.WARNING}[!] Generating mock signals...{_C.ENDC}")
        signals = _generate_mock_signals(count=limit)
        metrics.generation_duration_ms = (time.monotonic() - start) * 1000
        metrics.signal_count = len(signals)
        metrics.compute(signals)
        return metrics

    # Real mode: try to use QuantSignalOrchestrator with DB
    try:
        print(f"  {_C.OKBLUE}[DB] Connecting to database...{_C.ENDC}")

        # Check if DB is available
        from core.database import async_session_factory

        if async_session_factory is not None:
            # Test connection
            from sqlalchemy import text
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            print(f"  {_C.OKGREEN}{_CHECK} Database connection OK{_C.ENDC}")
        else:
            print(f"  {_C.WARNING}{_WARN} No DB factory available, initializing...{_C.ENDC}")
            from core.database import init_database
            await init_database()

            if async_session_factory is None:
                print(f"  {_C.FAIL}{_CROSS} Database not available. Falling back to mock mode.{_C.ENDC}")
                signals = _generate_mock_signals(count=limit)
                metrics.generation_duration_ms = (time.monotonic() - start) * 1000
                metrics.use_real_data = False
                metrics.signal_count = len(signals)
                metrics.compute(signals)
                return metrics

        # Run the full QuantSignalOrchestrator
        print(f"  {_C.OKBLUE}[GEAR] Running QuantSignalOrchestrator...{_C.ENDC}")
        from services.quant_signal_orchestrator import QuantSignalOrchestrator

        orchestrator = QuantSignalOrchestrator()
        report = await orchestrator.generate(
            market_filter=market_filter,
            min_confidence=min_confidence,
            limit=limit,
            use_ml=True,
            use_voting=True,
            use_confidence_calibration=True,
            use_probability_calibration=True,
            use_decision_engine=True,
        )

        metrics.generation_duration_ms = (time.monotonic() - start) * 1000
        metrics.signal_count = len(report.signals)

        if not report.signals:
            print(f"  {_C.WARNING}{_WARN} No signals generated from DB. Falling back to mock.{_C.ENDC}")
            signals = _generate_mock_signals(count=limit)
            metrics.use_real_data = False
            metrics.signal_count = len(signals)
            metrics.compute(signals)
            return metrics

        signals = report.signals
        metrics.cross_market_signals_count = len(report.cross_market_signals)
        metrics.cross_market_types = [
            cm.get("name", cm.get("signal", "?"))
            for cm in report.cross_market_signals
            if cm.get("name") != "Market-Regime" and cm.get("name") != "Market-Biases"
        ]

        metrics.compute(signals)
        return metrics

    except Exception as e:
        print(f"  {_C.FAIL}{_CROSS} Benchmark error: {e}{_C.ENDC}")
        print(f"  {_C.WARNING}{_WARN} Falling back to mock mode...{_C.ENDC}")
        signals = _generate_mock_signals(count=limit)
        metrics.generation_duration_ms = (time.monotonic() - start) * 1000
        metrics.use_real_data = False
        metrics.signal_count = len(signals)
        metrics.compute(signals)
        return metrics


# ── Main Entry Point ─────────────────────────────────────────────────────────

async def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Signal Quality Benchmark")
    parser.add_argument("--mock", action="store_true", help="Use mock data instead of DB")
    parser.add_argument("--quick", action="store_true", help="Quick mode (mock signals directly)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--market", default="all", help="Market filter (all, stock, gold, ...)")
    parser.add_argument("--min-confidence", type=float, default=0.35, help="Min confidence threshold")
    parser.add_argument("--limit", type=int, default=100, help="Max signals to process")
    args = parser.parse_args()

    metrics = await run_benchmark(
        use_mock=args.mock,
        quick=args.quick,
        market_filter=args.market,
        min_confidence=args.min_confidence,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(metrics.report())

    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
