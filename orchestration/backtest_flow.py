from __future__ import annotations

from typing import Any

from core.ids import new_id
from core.logging import get_logger
from orchestration.contracts import Step, Workflow
from orchestration.steps import (
    FetchDataStep,
    PersistDataStep,
    TransformDataStep,
    ValidateDataStep,
)

logger = get_logger("orchestration.backtest_flow")


class BacktestFlow:
    def __init__(self) -> None:
        self._custom_steps: list[Step] = []

    def add_custom_step(self, step: Step) -> None:
        self._custom_steps.append(step)

    def create_flow(
        self,
        strategy: Any,
        config: dict[str, Any],
        data_provider: Any = None,
        metrics_calculator: Any = None,
        report_repository: Any = None,
    ) -> Workflow:
        workflow_id = new_id()
        steps: list[Step] = []

        load_step = FetchDataStep(
            name="load_history",
            provider=data_provider,
            params={
                "symbols": config.get("symbols", []),
                "start_date": config.get("start_date", ""),
                "end_date": config.get("end_date", ""),
                "interval": config.get("interval", "1d"),
                "source": config.get("data_source", "default"),
            },
        )
        steps.append(load_step)

        def run_backtest_fn(data: Any) -> Any:
            initial_capital = config.get("initial_capital", 100000)
            positions = []
            equity_curve = [initial_capital]
            current_capital = initial_capital
            market_data = data.get("market_data", data) if isinstance(data, dict) else data
            signals = strategy.generate_signals(market_data) if hasattr(strategy, "generate_signals") else {}
            if isinstance(market_data, list):
                for i, _bar in enumerate(market_data):
                    signal = signals.get(i, "HOLD") if isinstance(signals, dict) else "HOLD"
                    if signal == "BUY":
                        positions.append({"bar": i, "action": "BUY"})
                        current_capital *= 1.01
                    elif signal == "SELL":
                        positions.append({"bar": i, "action": "SELL"})
                        current_capital *= 0.99
                    equity_curve.append(current_capital)
            return {
                "strategy": type(strategy).__name__ if strategy else "unknown",
                "initial_capital": initial_capital,
                "final_capital": current_capital,
                "positions": positions,
                "equity_curve": equity_curve,
                "num_bars": len(market_data) if isinstance(market_data, list) else 0,
                "config": config,
            }

        backtest_step = TransformDataStep(
            name="run_backtest",
            transform_fn=run_backtest_fn,
            input_key="load_history_result",
        )
        steps.append(backtest_step)

        def calculate_metrics_fn(data: Any) -> Any:
            equity_curve = data.get("equity_curve", [100000])
            initial = data.get("initial_capital", 100000)
            final = data.get("final_capital", initial)
            total_return = (final - initial) / initial if initial > 0 else 0
            max_drawdown = 0.0
            peak = equity_curve[0] if equity_curve else initial
            for val in equity_curve:
                if val > peak:
                    peak = val
                drawdown = (peak - val) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            if metrics_calculator and hasattr(metrics_calculator, "calculate"):
                custom_metrics = metrics_calculator.calculate(data)
            else:
                custom_metrics = {}
            return {
                "total_return": total_return,
                "max_drawdown": max_drawdown,
                "final_capital": final,
                "initial_capital": initial,
                "num_trades": len(data.get("positions", [])),
                "num_bars": data.get("num_bars", 0),
                "strategy": data.get("strategy", "unknown"),
                "custom_metrics": custom_metrics,
            }

        metrics_step = TransformDataStep(
            name="calculate_metrics",
            transform_fn=calculate_metrics_fn,
            input_key="run_backtest_result",
        )
        steps.append(metrics_step)

        def validate_metrics_fn(data: Any) -> bool:
            min_return = config.get("min_return", -1.0)
            max_allowed_drawdown = config.get("max_drawdown", 1.0)
            total_return = data.get("total_return", 0)
            max_drawdown = data.get("max_drawdown", 0)
            if total_return < min_return:
                return False
            return not max_drawdown > max_allowed_drawdown

        validate_step = ValidateDataStep(
            name="validate_metrics",
            validator_fn=validate_metrics_fn,
            input_key="calculate_metrics_result",
            error_message="Backtest validation failed: metrics outside acceptable range",
        )
        steps.append(validate_step)

        def generate_report_fn(data: Any) -> Any:
            report = {
                "backtest_id": workflow_id,
                "strategy": data.get("strategy", "unknown"),
                "summary": {
                    "total_return": data.get("total_return", 0),
                    "max_drawdown": data.get("max_drawdown", 0),
                    "final_capital": data.get("final_capital", 0),
                    "initial_capital": data.get("initial_capital", 0),
                    "num_trades": data.get("num_trades", 0),
                    "num_bars": data.get("num_bars", 0),
                },
                "config": config,
                "custom_metrics": data.get("custom_metrics", {}),
                "status": "passed",
            }
            return report

        report_step = TransformDataStep(
            name="generate_report",
            transform_fn=generate_report_fn,
            input_key="calculate_metrics_result",
        )
        steps.append(report_step)

        persist_step = PersistDataStep(
            name="persist_report",
            repository=report_repository,
            input_key="generate_report_result",
            persist_method="save_report",
        )
        steps.append(persist_step)

        steps.extend(self._custom_steps)

        class _BacktestWorkflow(Workflow):
            async def execute(self_wf, context: Any) -> Any:
                return context

        workflow = _BacktestWorkflow(
            workflow_id=workflow_id,
            name="backtest",
            steps=steps,
        )
        logger.info(
            f"Created BacktestFlow workflow {workflow_id} "
            f"with {len(steps)} steps for strategy "
            f"{type(strategy).__name__ if strategy else 'unknown'}"
        )
        return workflow

    def create_simple_flow(
        self,
        strategy: Any,
        symbols: list[str],
        start_date: str = "",
        end_date: str = "",
    ) -> Workflow:
        config = {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
        }
        return self.create_flow(strategy=strategy, config=config)
