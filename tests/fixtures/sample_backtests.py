from __future__ import annotations

from datetime import UTC, datetime

from core.ids import new_id


def sample_backtest_run(
    run_id: str | None = None,
    name: str = "Test Backtest",
    status: str = "completed",
) -> dict:
    return {
        "id": run_id or new_id("bt"),
        "name": name,
        "strategy_type": "moving_average_crossover",
        "symbols": ["فولاد"],
        "status": status,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 1_000_000_000,
        "current_value": 1_250_000_000,
        "total_return_pct": 25.0,
        "metrics": {
            "sharpe_ratio": 1.5,
            "max_drawdown_pct": -12.0,
            "win_rate": 0.65,
            "total_trades": 45,
        },
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
    }


def sample_backtest_result() -> dict:
    return {
        "id": new_id("bt"),
        "name": "Test Backtest Result",
        "status": "completed",
        "total_return_pct": 25.0,
        "annualized_return_pct": 25.0,
        "sharpe_ratio": 1.5,
        "max_drawdown_pct": -12.0,
        "win_rate": 0.65,
        "total_trades": 45,
        "winning_trades": 29,
        "losing_trades": 16,
        "initial_capital": 1_000_000_000,
        "final_value": 1_250_000_000,
        "equity_curve": [
            {"date": "2024-01-01", "value": 1_000_000_000, "drawdown_pct": 0.0},
            {"date": "2024-06-30", "value": 1_150_000_000, "drawdown_pct": -3.0},
            {"date": "2024-12-31", "value": 1_250_000_000, "drawdown_pct": 0.0},
        ],
        "trades": [
            {
                "entry_date": "2024-02-01",
                "exit_date": "2024-02-15",
                "symbol": "فولاد",
                "direction": "long",
                "entry_price": 15000,
                "exit_price": 16500,
                "return_pct": 10.0,
            },
        ],
        "metrics": {"sharpe_ratio": 1.5, "sortino_ratio": 2.0, "calmar_ratio": 2.08},
        "completed_at": datetime.now(UTC).isoformat(),
    }

