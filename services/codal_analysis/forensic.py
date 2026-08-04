from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)

BENFORD_EXPECTED: dict[int, float] = {
    1: 30.1, 2: 17.6, 3: 12.5, 4: 9.7,
    5: 7.9, 6: 6.7, 7: 5.8, 8: 5.1, 9: 4.6,
}


@dataclass
class BenfordResult:
    passing: bool
    chi_square_stat: float
    chi_square_critical: float
    observed: dict[int, float]
    expected: dict[int, float]
    mad: float
    sample_size: int


@dataclass
class FraudRiskScore:
    overall_risk: float
    benford_risk: float = 0
    related_party_risk: float = 0
    ratio_anomaly_risk: float = 0
    warnings: list[str] = field(default_factory=list)


def benford_analysis(values: list[float], significance: float = 0.05) -> BenfordResult:
    first_digits = []
    for v in values:
        if v == 0:
            continue
        abs_v = abs(v)
        first_digit = int(str(abs_v)[0])
        if 1 <= first_digit <= 9:
            first_digits.append(first_digit)

    if len(first_digits) < 50:
        observed_counts: dict[int, int] = Counter(first_digits)
        observed_pct = {d: c / len(first_digits) * 100 for d, c in observed_counts.items()}
        return BenfordResult(
            passing=True,
            chi_square_stat=0,
            chi_square_critical=0,
            observed=observed_pct,
            expected=BENFORD_EXPECTED,
            mad=0,
            sample_size=len(first_digits),
        )

    n = len(first_digits)
    observed_counts = Counter(first_digits)
    observed_pct = {d: c / n * 100 for d, c in observed_counts.items()}

    chi_sq = sum(
        (observed_counts.get(d, 0) - n * (BENFORD_EXPECTED[d] / 100)) ** 2 / (n * (BENFORD_EXPECTED[d] / 100))
        for d in range(1, 10)
    )

    critical = 15.507  # chi^2 critical for df=8, alpha=0.05

    mad = sum(abs(observed_pct.get(d, 0) - BENFORD_EXPECTED[d]) for d in range(1, 10)) / 9

    passing = mad < 0.015 and chi_sq < critical

    return BenfordResult(
        passing=passing,
        chi_square_stat=round(chi_sq, 4),
        chi_square_critical=critical,
        observed={d: round(observed_pct.get(d, 0), 2) for d in range(1, 10)},
        expected=BENFORD_EXPECTED,
        mad=round(mad, 6),
        sample_size=n,
    )


def assess_fraud_risk(
    values: list[float],
    ratios: dict[str, float | None] | None = None,
) -> FraudRiskScore:
    risk = FraudRiskScore(overall_risk=0)

    benford_res = benford_analysis(values)
    risk.benford_risk = 0.8 if not benford_res.passing else 0.1
    if not benford_res.passing:
        risk.warnings.append(f"توزیع ارقام غیرعادی (MAD={benford_res.mad:.4f}) - احتمال دستکاری داده‌ها")

    if ratios:
        roe = ratios.get("roe")
        roa = ratios.get("roa")
        if roe and roa and roe > 0.5 and roa < 0.05:
            risk.ratio_anomaly_risk += 0.4
            risk.warnings.append("ROE بسیار بالا با ROA پایین - احتمال استفاده از اهرم مالی بیش از حد")
        debt_eq = ratios.get("debt_to_equity")
        if debt_eq and debt_eq > 3:
            risk.ratio_anomaly_risk += 0.3
            risk.warnings.append("نسبت بدهی به حقوق صاحبان سهام بسیار بالا")
        current_r = ratios.get("current_ratio")
        if current_r and current_r < 0.5:
            risk.ratio_anomaly_risk += 0.3
            risk.warnings.append("نسبت جاری بسیار پایین - ریسک نقدینگی بالا")

    risk.overall_risk = min(1.0, risk.benford_risk * 0.3 + risk.ratio_anomaly_risk * 0.4 + risk.related_party_risk * 0.3)
    return risk


@dataclass
class MonetaryUnitSamplingResult:
    sample_size: int
    confidence_level: float
    allowable_error: float
    population_value: float


def calculate_mus_sample_size(
    population_value: float,
    confidence_level: float = 0.95,
    allowable_error: float = 0.05,
) -> MonetaryUnitSamplingResult:
    if population_value <= 0:
        return MonetaryUnitSamplingResult(0, confidence_level, allowable_error, 0)

    z_score = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence_level, 1.96)
    sample_size = max(1, int((z_score / allowable_error) ** 2))
    return MonetaryUnitSamplingResult(
        sample_size=sample_size,
        confidence_level=confidence_level,
        allowable_error=allowable_error,
        population_value=population_value,
    )
