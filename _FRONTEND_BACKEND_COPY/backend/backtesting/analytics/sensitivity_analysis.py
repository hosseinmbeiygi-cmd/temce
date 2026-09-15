from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class SensitivityParameter:
    name: str
    base_value: float
    min_value: float
    max_value: float
    steps: int = 10
    description: str = ""


@dataclass
class SensitivityResult:
    parameter_name: str
    base_value: float
    values: list[float]
    metric_values: list[dict[str, float]]
    elasticity: float = 0.0
    impact_pct: float = 0.0
    is_linear: bool = False


@dataclass
class SensitivityReport:
    parameters: list[SensitivityResult] = field(default_factory=list)
    tornado_data: dict[str, tuple[float, float]] = field(default_factory=dict)
    top_parameters: list[str] = field(default_factory=list)


class SensitivityAnalysis:
    def __init__(self) -> None:
        self._results: dict[str, SensitivityResult] = {}

    def analyze_parameter(
        self,
        param: SensitivityParameter,
        metric_function: Callable[[float], dict[str, float]],
        primary_metric: str = "total_return_pct",
    ) -> SensitivityResult:
        values = []
        metric_values = []
        step_size = (param.max_value - param.min_value) / max(param.steps - 1, 1)
        for i in range(param.steps):
            val = param.min_value + i * step_size
            metrics = metric_function(val)
            values.append(val)
            metric_values.append(metrics)

        base_metrics = metric_function(param.base_value)
        base_metric_val = base_metrics.get(primary_metric, 0.0)
        if base_metric_val != 0:
            pct_changes = []
            for mv in metric_values:
                mv_val = mv.get(primary_metric, 0.0)
                if mv_val != 0:
                    pct_changes.append(abs((mv_val - base_metric_val) / base_metric_val * 100))
            impact_pct = sum(pct_changes) / len(pct_changes) if pct_changes else 0.0
        else:
            impact_pct = 0.0

        first_val = metric_values[0].get(primary_metric, 0.0) if metric_values else 0.0
        last_val = metric_values[-1].get(primary_metric, 0.0) if metric_values else 0.0
        param_range = param.max_value - param.min_value
        metric_range = last_val - first_val
        elasticity = (
            (metric_range / base_metric_val) / (param_range / param.base_value)
            if base_metric_val != 0 and param.base_value != 0
            else 0.0
        )

        mid = len(values) // 2
        if mid > 0 and mid < len(values):
            linear_check = abs(metric_values[mid].get(primary_metric, 0.0) - (first_val + last_val) / 2)
            is_linear = linear_check < abs(metric_range) * 0.1 if metric_range != 0 else True
        else:
            is_linear = True

        result = SensitivityResult(
            parameter_name=param.name,
            base_value=param.base_value,
            values=values,
            metric_values=metric_values,
            elasticity=elasticity,
            impact_pct=impact_pct,
            is_linear=is_linear,
        )
        self._results[param.name] = result
        return result

    def analyze_multiple(
        self,
        parameters: list[SensitivityParameter],
        metric_function: Callable[[dict[str, float]], dict[str, float]],
        primary_metric: str = "total_return_pct",
    ) -> SensitivityReport:
        results: list[SensitivityResult] = []
        tornado_data: dict[str, tuple[float, float]] = {}

        for param in parameters:

            def make_single_func(p: SensitivityParameter) -> Callable[[float], dict[str, float]]:
                return lambda val, p=p: metric_function({p.name: val})

            result = self.analyze_parameter(param, make_single_func(param), primary_metric)
            results.append(result)
            low_metric = result.metric_values[0].get(primary_metric, 0.0) if result.metric_values else 0.0
            high_metric = result.metric_values[-1].get(primary_metric, 0.0) if result.metric_values else 0.0
            tornado_data[param.name] = (low_metric, high_metric)

        sorted_params = sorted(tornado_data.items(), key=lambda x: abs(x[1][1] - x[1][0]), reverse=True)
        top_parameters = [p[0] for p in sorted_params[:5]]

        return SensitivityReport(
            parameters=results,
            tornado_data=tornado_data,
            top_parameters=top_parameters,
        )

    def get_tornado_data(self) -> dict[str, tuple[float, float]]:
        tornado: dict[str, tuple[float, float]] = {}
        for name, result in self._results.items():
            if result.metric_values:
                first = result.metric_values[0]
                last = result.metric_values[-1]
                metric_key = list(first.keys())[0] if first else "value"
                tornado[name] = (first.get(metric_key, 0.0), last.get(metric_key, 0.0))
        return tornado

    def get_most_sensitive(self, top_n: int = 5) -> list[str]:
        sorted_results = sorted(
            self._results.values(),
            key=lambda r: r.impact_pct,
            reverse=True,
        )
        return [r.parameter_name for r in sorted_results[:top_n]]

    def clear(self) -> None:
        self._results.clear()


class DefaultSensitivityParameters:
    @staticmethod
    def commission_rate() -> SensitivityParameter:
        return SensitivityParameter(
            name="commission_pct",
            base_value=0.0035,
            min_value=0.001,
            max_value=0.01,
            steps=10,
            description="کارمزد معاملات (درصد)",
        )

    @staticmethod
    def slippage() -> SensitivityParameter:
        return SensitivityParameter(
            name="slippage_bps",
            base_value=10,
            min_value=0,
            max_value=50,
            steps=11,
            description="لغزش قیمت (bps)",
        )

    @staticmethod
    def tick_size() -> SensitivityParameter:
        return SensitivityParameter(
            name="tick_size",
            base_value=1,
            min_value=0.1,
            max_value=10,
            steps=10,
            description="اندازه تیک",
        )

    @staticmethod
    def price_limit() -> SensitivityParameter:
        return SensitivityParameter(
            name="price_limit_pct",
            base_value=5.0,
            min_value=1.0,
            max_value=10.0,
            steps=10,
            description="دامنه نوسان (درصد)",
        )

    @staticmethod
    def initial_capital() -> SensitivityParameter:
        return SensitivityParameter(
            name="initial_capital",
            base_value=1_000_000_000,
            min_value=100_000_000,
            max_value=10_000_000_000,
            steps=10,
            description="سرمایه اولیه",
        )

    @classmethod
    def get_defaults(cls) -> list[SensitivityParameter]:
        return [
            cls.commission_rate(),
            cls.slippage(),
            cls.tick_size(),
            cls.price_limit(),
            cls.initial_capital(),
        ]
