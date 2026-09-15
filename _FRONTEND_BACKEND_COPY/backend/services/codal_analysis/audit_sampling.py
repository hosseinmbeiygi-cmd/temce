from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StratifiedSampleResult:
    stratum_name: str
    stratum_value: float
    stratum_size: int
    sample_size: int
    selected_items: list[Any] = field(default_factory=list)
    misstatement_found: float = 0
    projected_misstatement: float = 0


@dataclass
class StratifiedSamplingOutput:
    strata: list[StratifiedSampleResult] = field(default_factory=list)
    total_population_value: float = 0
    total_population_items: int = 0
    total_sample_size: int = 0
    total_projected_misstatement: float = 0
    sampling_error: float = 0
    confidence_level: float = 0.95


@dataclass
class AttributeSamplingInput:
    population_size: int = 0
    expected_deviation_rate: float = 0.01
    tolerable_deviation_rate: float = 0.05
    risk_of_overreliance: float = 0.05


@dataclass
class AttributeSamplingResult:
    sample_size: int
    expected_deviation_rate: float
    tolerable_deviation_rate: float
    risk_of_overreliance: float
    deviations_found: int
    deviation_rate: float
    upper_deviation_limit: float
    is_acceptable: bool
    conclusion: str = ""


@dataclass
class ClassicalVariablesSamplingInput:
    population_size: int = 0
    population_value: float = 0
    tolerable_misstatement: float = 0
    expected_misstatement: float = 0
    confidence_level: float = 0.95
    estimated_std_dev: float | None = None


@dataclass
class ClassicalVariablesSamplingResult:
    sample_size: int
    tolerable_misstatement: float
    expected_misstatement: float
    confidence_level: float
    sample_mean: float | None = None
    sample_std_dev: float | None = None
    precision: float = 0
    lower_bound: float = 0
    upper_bound: float = 0
    is_acceptable: bool = False
    method: str = ""


@dataclass
class PPSUnit:
    item_id: str
    value: float
    cumulative_value: float = 0


def _z_score(confidence_level: float) -> float:
    return {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence_level, 1.96)


class StratifiedSampler:
    """Stratified Sampling for Substantive Testing"""

    def __init__(self, random_seed: int | None = None):
        self.rng = random.Random(random_seed)

    def stratify(
        self,
        items: list[dict[str, Any]],
        value_key: str = "value",
        strata_count: int = 3,
    ) -> list[list[dict[str, Any]]]:
        sorted_items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)
        strata: list[list[dict[str, Any]]] = [[] for _ in range(strata_count)]

        # Top stratum: highest value items covering ~50% of total value
        total_value = sum(item.get(value_key, 0) for item in sorted_items)
        cum_value = 0
        threshold_50 = total_value * 0.5
        threshold_80 = total_value * 0.8

        for item in sorted_items:
            val = item.get(value_key, 0)
            if cum_value < threshold_50:
                strata[0].append(item)
            elif cum_value < threshold_80:
                strata[1].append(item)
            else:
                strata[2].append(item)
            cum_value += val

        return strata

    def sample_stratum(
        self,
        stratum: list[dict[str, Any]],
        stratum_name: str,
        confidence_level: float = 0.95,
        sample_fraction: float | None = None,
    ) -> StratifiedSampleResult:
        n = len(stratum)
        if n == 0:
            return StratifiedSampleResult(stratum_name, 0, 0, 0)

        total_value = sum(item.get("value", 0) for item in stratum)

        if n <= 5:
            sample_size = n
        elif sample_fraction:
            sample_size = max(5, min(n, int(n * sample_fraction)))
        else:
            z = _z_score(confidence_level)
            sample_size = max(5, min(n, int(z**2 * 0.5 * 0.5 / 0.03**2)))
            sample_size = min(sample_size, n)

        selected = self.rng.sample(stratum, sample_size) if sample_size < n else list(stratum)

        return StratifiedSampleResult(
            stratum_name=stratum_name,
            stratum_value=total_value,
            stratum_size=n,
            sample_size=sample_size,
            selected_items=[item.get("id", f"{stratum_name}_{i}") for i, item in enumerate(selected)],
        )

    def sample_all(
        self,
        items: list[dict[str, Any]],
        value_key: str = "value",
        strata_count: int = 3,
        confidence_level: float = 0.95,
    ) -> StratifiedSamplingOutput:
        if not items:
            return StratifiedSamplingOutput()

        strata = self.stratify(items, value_key, strata_count)
        total_value = sum(item.get(value_key, 0) for item in items)
        names = ["high_value", "medium_value", "low_value"]

        results = []
        total_sample = 0

        for i, stratum in enumerate(strata):
            if i == 0:
                fraction = 1.0  # 100% of high-value stratum
            elif i == 1:
                fraction = 0.5
            else:
                fraction = 0.2

            result = self.sample_stratum(stratum, names[i], confidence_level, fraction)
            results.append(result)
            total_sample += result.sample_size

        return StratifiedSamplingOutput(
            strata=results,
            total_population_value=total_value,
            total_population_items=len(items),
            total_sample_size=total_sample,
            confidence_level=confidence_level,
        )


class AttributeSampler:
    """Attribute Sampling for Tests of Controls (ISA 530)"""

    def __init__(self):
        pass

    def calculate_sample_size(self, inp: AttributeSamplingInput) -> AttributeSamplingResult:
        population = inp.population_size
        edr = inp.expected_deviation_rate
        tdr = inp.tolerable_deviation_rate
        roo = inp.risk_of_overreliance

        if tdr <= edr:
            return AttributeSamplingResult(
                sample_size=0,
                expected_deviation_rate=edr,
                tolerable_deviation_rate=tdr,
                risk_of_overreliance=roo,
                deviations_found=0,
                deviation_rate=0,
                upper_deviation_limit=0,
                is_acceptable=False,
                conclusion="Tolerable rate must exceed expected rate",
            )

        z = _z_score(1 - roo)
        numerator = z**2 * (1 - edr) * (1 + 1 / max(population, 1)) if population > 0 else z**2 * (1 - edr)
        denominator = (tdr - edr) ** 2
        if denominator <= 0:
            return AttributeSamplingResult(
                sample_size=100,
                expected_deviation_rate=edr,
                tolerable_deviation_rate=tdr,
                risk_of_overreliance=roo,
                deviations_found=0,
                deviation_rate=0,
                upper_deviation_limit=0,
                is_acceptable=True,
                conclusion="Using default sample size",
            )

        sample_size = max(25, min(200, int(numerator / denominator)))
        if population > 0:
            sample_size = min(sample_size, population)

        return AttributeSamplingResult(
            sample_size=sample_size,
            expected_deviation_rate=edr,
            tolerable_deviation_rate=tdr,
            risk_of_overreliance=roo,
            deviations_found=0,
            deviation_rate=0,
            upper_deviation_limit=0,
            is_acceptable=True,
            conclusion=f"Sample size calculated: {sample_size} items",
        )

    def evaluate_results(
        self,
        sample_size: int,
        deviations_found: int,
        tolerance_rate: float,
        risk_of_overreliance: float = 0.05,
    ) -> AttributeSamplingResult:
        if sample_size <= 0:
            return AttributeSamplingResult(
                sample_size=0,
                expected_deviation_rate=0,
                tolerable_deviation_rate=tolerance_rate,
                risk_of_overreliance=risk_of_overreliance,
                deviations_found=deviations_found,
                deviation_rate=0,
                upper_deviation_limit=0,
                is_acceptable=False,
            )

        deviation_rate = deviations_found / sample_size

        # Upper deviation limit using Poisson distribution approximation
        if deviations_found == 0:
            upper_limit = 1 - (risk_of_overreliance) ** (1 / sample_size)
        else:
            upper_limit = deviations_found / sample_size + _z_score(1 - risk_of_overreliance) * math.sqrt(
                (deviations_found / sample_size) * (1 - deviations_found / sample_size) / sample_size
            )

        upper_limit = min(1.0, upper_limit)
        is_acceptable = upper_limit <= tolerance_rate

        if is_acceptable:
            conclusion = f"Controls effective: UDL {upper_limit:.2%} <= tolerable rate {tolerance_rate:.2%}"
        else:
            conclusion = f"Controls NOT effective: UDL {upper_limit:.2%} > tolerable rate {tolerance_rate:.2%}"

        return AttributeSamplingResult(
            sample_size=sample_size,
            expected_deviation_rate=0,
            tolerable_deviation_rate=tolerance_rate,
            risk_of_overreliance=risk_of_overreliance,
            deviations_found=deviations_found,
            deviation_rate=round(deviation_rate, 4),
            upper_deviation_limit=round(upper_limit, 4),
            is_acceptable=is_acceptable,
            conclusion=conclusion,
        )


class ClassicalVariablesSampler:
    """Classical Variables Sampling for Substantive Testing (ISA 530)"""

    def __init__(self):
        pass

    def calculate_sample_size(self, inp: ClassicalVariablesSamplingInput) -> ClassicalVariablesSamplingResult:
        n = inp.population_size
        tm = inp.tolerable_misstatement
        em = inp.expected_misstatement
        cl = inp.confidence_level
        std_dev = inp.estimated_std_dev

        if tm <= 0 or n <= 0:
            return ClassicalVariablesSamplingResult(
                sample_size=0,
                tolerable_misstatement=tm,
                expected_misstatement=em,
                confidence_level=cl,
            )

        z = _z_score(cl)
        if std_dev is None:
            std_dev = tm * 0.5 / z  # crude estimate

        allowance_for_sampling_risk = tm - em
        if allowance_for_sampling_risk <= 0:
            allowance_for_sampling_risk = tm * 0.3

        sample_size = max(10, int((z * std_dev * n / allowance_for_sampling_risk) ** 2))
        sample_size = min(sample_size, n)

        return ClassicalVariablesSamplingResult(
            sample_size=sample_size,
            tolerable_misstatement=tm,
            expected_misstatement=em,
            confidence_level=cl,
            method=f"Mean-per-unit with estimated std dev {std_dev:.2f}",
            precision=allowance_for_sampling_risk,
        )

    def evaluate_results(
        self,
        sample_values: list[float],
        sample_book_values: list[float],
        population_size: int,
        population_value: float,
        tolerable_misstatement: float,
        confidence_level: float = 0.95,
    ) -> ClassicalVariablesSamplingResult:
        n = len(sample_values)
        if n == 0:
            return ClassicalVariablesSamplingResult(
                sample_size=0,
                tolerable_misstatement=tolerable_misstatement,
                expected_misstatement=0,
                confidence_level=confidence_level,
            )

        differences = [sample_values[i] - sample_book_values[i] for i in range(n)]
        mean_diff = sum(differences) / n
        variance = sum((d - mean_diff) ** 2 for d in differences) / (n - 1) if n > 1 else 0
        std_dev = math.sqrt(variance)

        z = _z_score(confidence_level)
        precision = z * std_dev / math.sqrt(n) * population_size

        projected_misstatement = mean_diff * population_size
        lower_bound = projected_misstatement - precision
        upper_bound = projected_misstatement + precision

        is_acceptable = abs(lower_bound) <= tolerable_misstatement and abs(upper_bound) <= tolerable_misstatement

        return ClassicalVariablesSamplingResult(
            sample_size=n,
            tolerable_misstatement=tolerable_misstatement,
            expected_misstatement=0,
            confidence_level=confidence_level,
            sample_mean=mean_diff,
            sample_std_dev=std_dev,
            precision=round(precision),
            lower_bound=round(lower_bound),
            upper_bound=round(upper_bound),
            is_acceptable=is_acceptable,
            method="Difference estimation",
        )


class PPSampler:
    """Probability Proportional to Size (PPS) / Monetary Unit Sampling"""

    def __init__(self, random_seed: int | None = None):
        self.rng = random.Random(random_seed)

    def calculate_sample_size(
        self,
        population_value: float,
        materiality: float,
        expected_error_rate: float = 0.05,
        confidence_level: float = 0.95,
    ) -> int:
        if population_value <= 0 or materiality <= 0:
            return 0

        z = _z_score(confidence_level)
        sample_size = max(1, int((z * population_value / materiality) ** 2 * expected_error_rate))
        return min(sample_size, 5000)

    def select_sample(
        self,
        items: list[dict[str, Any]],
        value_key: str = "value",
        id_key: str = "id",
        materiality: float = 0,
        confidence_level: float = 0.95,
    ) -> list[dict[str, Any]]:
        if not items:
            return []

        total = sum(item.get(value_key, 0) for item in items)
        sample_size = self.calculate_sample_size(total, materiality, 0.05, confidence_level)

        if sample_size <= 0 or total <= 0:
            return []

        interval = total / sample_size

        start = self.rng.uniform(0, interval)
        cumulative = 0.0
        selected: set[str] = set()
        selected_items: list[dict[str, Any]] = []
        monetary_unit = start

        for item in sorted(items, key=lambda x: x.get(id_key, "")):
            item_value = item.get(value_key, 0)
            cumulative += item_value

            while monetary_unit <= cumulative and len(selected) < sample_size:
                item_id = str(item.get(id_key, ""))
                if item_id not in selected:
                    selected.add(item_id)
                    selected_items.append(item)
                monetary_unit += interval

            if len(selected) >= sample_size:
                break

        return selected_items


def format_sampling_for_response(result: Any) -> dict[str, Any]:
    if isinstance(result, StratifiedSamplingOutput):
        return {
            "type": "stratified_sampling",
            "strata": [
                {
                    "stratum_name": s.stratum_name,
                    "stratum_value": s.stratum_value,
                    "stratum_size": s.stratum_size,
                    "sample_size": s.sample_size,
                    "projected_misstatement": s.projected_misstatement,
                }
                for s in result.strata
            ],
            "total_population_value": result.total_population_value,
            "total_population_items": result.total_population_items,
            "total_sample_size": result.total_sample_size,
            "total_projected_misstatement": result.total_projected_misstatement,
            "confidence_level": result.confidence_level,
        }
    elif isinstance(result, AttributeSamplingResult):
        return {
            "type": "attribute_sampling",
            "sample_size": result.sample_size,
            "expected_deviation_rate": result.expected_deviation_rate,
            "tolerable_deviation_rate": result.tolerable_deviation_rate,
            "deviations_found": result.deviations_found,
            "deviation_rate": result.deviation_rate,
            "upper_deviation_limit": result.upper_deviation_limit,
            "is_acceptable": result.is_acceptable,
            "conclusion": result.conclusion,
        }
    elif isinstance(result, ClassicalVariablesSamplingResult):
        return {
            "type": "classical_variables_sampling",
            "sample_size": result.sample_size,
            "tolerable_misstatement": result.tolerable_misstatement,
            "confidence_level": result.confidence_level,
            "sample_mean": result.sample_mean,
            "precision": result.precision,
            "lower_bound": result.lower_bound,
            "upper_bound": result.upper_bound,
            "is_acceptable": result.is_acceptable,
            "method": result.method,
        }
    return {"type": "unknown", "data": str(result)}
