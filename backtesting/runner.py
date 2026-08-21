"""BacktestRunner — the single entry point for running backtests.

Executes audit finding **D1** (consolidation of the six parallel backtest
engines): instead of each engine exposing its own divergent result contract,
every backtest entry point routes through this runner.

The **canonical** engine is
:class:`backtesting.engine.simulator.BacktestSimulator` — it is what every
production service uses (``services/backtest_service``, ``cascade_engine``,
``strategy_generator``, ``mass_scanner``, composer, walk-forward, scripts) and
it is the only engine with a synchronous, deterministic core.

The other engines remain available for their **specialised** research
use-cases, but are dispatched through the same result normalisation and the
same canonical cost model (see ``backtesting.costs.iran_costs`` / the F2
parity guard) so their outputs are directly comparable:

| engine name      | class                                     | use-case                      | status |
|------------------|-------------------------------------------|-------------------------------|--------|
| ``simulator``    | ``BacktestSimulator``                     | canonical bar-based           | ✅ canonical |
| ``replay``       | ``ReplayEngine``                          | event-driven replay           | supported |
| ``hybrid``       | ``HybridMarketSimulator``                 | ABM + microstructure          | supported |
| ``portfolio``    | ``PortfolioBacktestSimulator``            | multi-instrument              | supported |
| ``simulation``   | ``SimulationEngine``                      | legacy kernel                 | 🔴 deprecated — no production consumers |
| ``backtest_engine`` | ``BacktestEngine``                     | legacy engine                 | 🔴 deprecated — diagnostics smoke only |

Usage::

    from backtesting.runner import BacktestRunner

    runner = BacktestRunner()
    summary = await runner.run("simulator", strategy=strategy, data=bars,
                               initial_capital=1_000_000_000)
    # or with an engine instance (research_api passes instances):
    summary = await runner.run(BacktestSimulator(), initial_capital=1_000_000_000, **kwargs)
"""

from __future__ import annotations

import warnings
from typing import Any

from backtesting.analytics.engine import AnalyticsEngine
from backtesting.engine.backtest_engine import BacktestEngine
from backtesting.engine.portfolio_simulator import PortfolioBacktestSimulator
from backtesting.engine.replay_engine import ReplayEngine
from backtesting.engine.simulation_engine import SimulationEngine
from backtesting.engine.simulator import BacktestSimulator
from backtesting.hybrid.hybrid_simulator import HybridMarketSimulator
from backtesting.types import BacktestResult
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

DEPRECATED_ENGINES = {"simulation", "backtest_engine"}


class BacktestRunner:
    """Canonical dispatcher for all backtest engines.

    The runner:
      1. Resolves an engine name *or* an engine instance to a canonical name.
      2. Dispatches to the engine (preserving each engine's native call
         signature).
      3. Normalises every engine result to a single ``BacktestResult``
         (hybrid's ``HybridResult`` is converted via ``to_backtest_result``).
      4. Summarises with :class:`backtesting.analytics.engine.AnalyticsEngine`
         so all engines expose the same metric contract.
    """

    # name → (engine class, deprecated)
    _ENGINES: dict[str, tuple[type[Any], bool]] = {
        "simulator": (BacktestSimulator, False),
        "replay": (ReplayEngine, False),
        "hybrid": (HybridMarketSimulator, False),
        "portfolio": (PortfolioBacktestSimulator, False),
        "simulation": (SimulationEngine, True),       # orphaned — no production consumers
        "backtest_engine": (BacktestEngine, True),      # legacy — diagnostics smoke only
    }

    def __init__(self, analytics_engine: AnalyticsEngine | None = None) -> None:
        self.analytics_engine = analytics_engine or AnalyticsEngine()

    # ── Resolution ─────────────────────────────────────────────────

    def resolve(self, engine: str | Any) -> str:
        """Map an engine name or instance to its canonical name."""
        if isinstance(engine, str):
            if engine not in self._ENGINES:
                raise ValueError(
                    f"unknown backtest engine {engine!r} — choose from {list(self._ENGINES)}"
                )
            return engine
        for name, (cls, _deprecated) in self._ENGINES.items():
            if isinstance(engine, cls):
                return name
        raise ValueError(
            f"unsupported backtest engine instance {type(engine).__name__} — "
            f"pass a BacktestSimulator/ReplayEngine/HybridMarketSimulator/"
            f"PortfolioBacktestSimulator/SimulationEngine/BacktestEngine or a "
            f"name from {list(self._ENGINES)}"
        )

    @classmethod
    def list_engines(cls) -> list[dict[str, Any]]:
        """Registry for UI/API surfaces (name, class, deprecated)."""
        return [
            {
                "name": name,
                "class": cls.__name__,
                "canonical": name == "simulator",
                "deprecated": deprecated,
            }
            for name, (cls, deprecated) in cls._ENGINES.items()
        ]

    # ── Public API ─────────────────────────────────────────────────

    async def run(
        self,
        engine: str | Any,
        strategy: Any = None,
        initial_capital: float = 1_000_000_000,
        data: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a backtest through any engine and return a normalised summary.

        ``engine`` is either a canonical name (``"simulator"`` …) or an engine
        instance. ``strategy``/``data`` are used by the bar-based engines
        (simulator, replay, portfolio, backtest_engine); event-driven engines
        (hybrid) receive their own parameters via ``kwargs``.

        Returns the same dict schema for every engine (see ``_summarize``).
        Raises ``ValueError`` for unknown engines and ``RuntimeError`` when an
        engine reports failure.
        """
        name = self.resolve(engine)
        if name in DEPRECATED_ENGINES:
            warnings.warn(
                f"Backtest engine {name!r} is deprecated (audit D1) — use "
                f"'simulator' (BacktestSimulator) instead",
                DeprecationWarning,
                stacklevel=2,
            )

        if isinstance(engine, str):
            engine = self._ENGINES[name][0]()

        bt_result = await self._dispatch(name, engine, strategy, initial_capital, data, kwargs)
        return self._summarize(bt_result, name, initial_capital)

    # ── Dispatch ───────────────────────────────────────────────────

    async def _dispatch(
        self,
        name: str,
        engine: Any,
        strategy: Any,
        initial_capital: float,
        data: list[dict[str, Any]] | None,
        kwargs: dict[str, Any],
    ) -> BacktestResult:
        """Call the engine with its native signature and normalise to
        ``BacktestResult``."""
        try:
            if name == "simulator":
                raw = engine.run(strategy, initial_capital, data)
            elif name == "replay":
                raw = await engine.run(strategy, initial_capital, **kwargs)
            elif name == "hybrid":
                raw = await engine.run(**kwargs)
            elif name == "portfolio":
                raw = await engine.run(strategy, initial_capital, **kwargs)
            elif name == "simulation":
                raw = await engine.run(initial_capital, **kwargs)
            elif name == "backtest_engine":
                raw = await engine.run(strategy, data)  # legacy: returns bare BacktestResult
            else:  # pragma: no cover — resolve() already validated
                raise ValueError(f"unknown engine {name!r}")
        except Exception as exc:  # noqa: BLE001 — engines raise on bad input
            raise RuntimeError(f"backtest engine {name!r} failed: {exc}") from exc

        strategy_name = (
            getattr(strategy, "__class__", None).__name__
            if strategy is not None
            else "Strategy"
        )
        return self._to_backtest_result(raw, strategy_name, initial_capital)

    @staticmethod
    def _to_backtest_result(
        raw: Any, strategy_name: str, initial_capital: float
    ) -> BacktestResult:
        """Unwrap Result/backend result types into a BacktestResult."""
        if isinstance(raw, Result):
            if not raw.success:
                raise RuntimeError(raw.error or "backtest engine reported failure")
            obj = raw.unwrap()
        else:
            obj = raw
        if isinstance(obj, BacktestResult):
            return obj
        if hasattr(obj, "to_backtest_result"):
            return obj.to_backtest_result(
                strategy_name=strategy_name, initial_capital=initial_capital
            )
        raise RuntimeError(
            f"engine returned unsupported result type {type(obj).__name__} — "
            "expected BacktestResult (or Result[BacktestResult])"
        )

    # ── Summary ────────────────────────────────────────────────────

    def _summarize(
        self, bt: BacktestResult, engine: str, initial_capital: float
    ) -> dict[str, Any]:
        """Normalised result contract — identical for every engine."""
        analytics = self.analytics_engine.compute(bt)
        return {
            "engine": engine,
            "strategy_name": bt.strategy_name or "Strategy",
            "initial_capital": bt.initial_capital or initial_capital,
            "final_capital": bt.final_capital,
            "total_return": bt.total_return,
            "total_return_pct": bt.total_return_pct,
            "total_trades": bt.total_trades,
            "sharpe_ratio": analytics.sharpe_ratio,
            "sortino_ratio": analytics.sortino_ratio,
            "max_drawdown_pct": analytics.max_drawdown_pct,
            "cagr": analytics.cagr,
            "win_rate": analytics.win_rate,
            "profit_factor": analytics.profit_factor,
            "volatility": analytics.volatility,
            "equity_points": [
                {
                    "timestamp": str(p.timestamp),
                    "nav": p.nav,
                    "cash": p.cash,
                    "positions_value": p.positions_value,
                }
                for p in (bt.equity_curve or [])
            ],
        }


# ── Module-level convenience ──────────────────────────────────────────────

_runner: BacktestRunner | None = None


def get_backtest_runner() -> BacktestRunner:
    """Return the process-wide runner singleton."""
    global _runner
    if _runner is None:
        _runner = BacktestRunner()
    return _runner
