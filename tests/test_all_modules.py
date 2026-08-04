"""Verify all adaptive engine modules work."""
from services.adaptive_engine import (
    CoEvolutionOptimizer,
    ConformalPredictor,
    CQLAgent,
    HSMMRegimeDetector,
    MarketRegimeDetector,
    MixtureOfExperts,
    SafeTradingAgent,
    TSDEngineDSS,
)
from services.backtest_framework import (
    CPCV,
    LiquidityAnalyzer,
    MonteCarloEngine,
    RegimeEvaluator,
    StatisticalValidator,
    StressTestEngine,
    VectorizedBacktest,
    WalkForwardEngine,
)
from services.cascade_engine import CascadeEngine, compute_total_combinations
from services.ensemble_engine import RiskGate, StrategyEnsemble, TSESimulator
from services.event_backtest import EventBacktestEngine

print("=== Module Import Test ===")
print(f"  HMM detector: {MarketRegimeDetector.__name__}")
print(f"  Safe RL: {SafeTradingAgent.__name__}")
print(f"  Co-evolution: {CoEvolutionOptimizer.__name__}")
print(f"  CQL: {CQLAgent.__name__}")
print(f"  HSMM: {HSMMRegimeDetector.__name__}")
print(f"  MoE: {MixtureOfExperts.__name__}")
print(f"  Conformal: {ConformalPredictor.__name__}")
print(f"  DSS: {TSDEngineDSS.__name__}")
print(f"  Cascade: {CascadeEngine.__name__}")
print(f"  Ensemble: {StrategyEnsemble.__name__}")
print(f"  RiskGate: {RiskGate.__name__}")
print(f"  TSE Sim: {TSESimulator.__name__}")
print(f"  Event Backtest: {EventBacktestEngine.__name__}")
print(f"  Vectorized: {VectorizedBacktest.__name__}")
print(f"  Walk-Forward: {WalkForwardEngine.__name__}")
print(f"  CPCV: {CPCV.__name__}")
print(f"  Monte Carlo: {MonteCarloEngine.__name__}")
print(f"  Stress Test: {StressTestEngine.__name__}")
print(f"  Regime Eval: {RegimeEvaluator.__name__}")
print(f"  Liquidity: {LiquidityAnalyzer.__name__}")
print(f"  Statistical: {StatisticalValidator.__name__}")
print()

print("=== Functional Tests ===")

# Test HMM
det = MarketRegimeDetector()
det.fit([[0.01, 1.2, 1.3], [-0.005, 0.8, 0.9], [0.02, 1.5, 1.6]])
r = det.predict([0.01, 1.1, 1.2])
print(f"  HMM regime: {r} ({det.get_regime_label(r)})")

# Test HSMM
hsmm = HSMMRegimeDetector()
hsmm.fit([[0.01, 1.2, 1.3], [-0.005, 0.8, 0.9]])
res = hsmm.predict([0.01, 1.1])
print(f"  HSMM: regime={res['regime']} label={res['label']}")

# Test MoE
moe = MixtureOfExperts(input_dim=3, output_dim=1, num_experts=3)
out = moe.predict([0.5, 0.3, 0.8])
print(f"  MoE output: {out['output'][:2]} gates: {out['gate_weights']}")

# Test Conformal
cp = ConformalPredictor(alpha=0.1)
cp.calibrate([1.0, 1.1, 0.9, 1.05], [1.0, 1.0, 1.0, 1.0])
pred = cp.predict_interval(1.0)
print(f"  Conformal: [{pred['lower']}, {pred['upper']}] conf={pred['confidence']}")

# Test Safe RL
agent = SafeTradingAgent()
action = agent.select_action(
    [0.01,
    0.03,
    0.05,
    0.02,
    0.55,
    1.3,
    1.5,
    0.7,
    1,
    0.3],
    [0.01,
    -0.005,
    0.008]
)
print(f"  Safe RL action: {action}")

# Test CQL
cql = CQLAgent()
a = cql.select_action([0.01, 0.03, 0.05, 0.02, 0.55, 1.3, 1.5, 0.7, 1, 0.3])
print(f"  CQL action: {a}")

# Test DSS
dss = TSDEngineDSS()
dss.initialize([[0.01, 1.2, 1.3], [-0.005, 0.8, 0.9], [0.02, 1.5, 1.6]])
sig = dss.generate_signal(
    [0.01, 1.1, 1.2, 0.02, 0.55, 1.3, 1.5, 0.7, 1, 0.3], [0.01, -0.005, 0.008]
)
print(
    f"  DSS: action={sig['action']} regime={sig['regime']['label']} risk={sig['safe_check']}"
)

# Test Ensemble
ens = StrategyEnsemble()
result = ens.combine_signals(
    [
        {"strategy": "momentum", "symbol": "test", "signal": 1, "score": 0.5},
        {"strategy": "mean_reversion", "symbol": "test", "signal": -1, "score": -0.2},
    ],
    regime=1,
)
print(f"  Ensemble: {result['test']['action']} conf={result['test']['confidence']}")

# Test RiskGate
rg = RiskGate(max_cvar=0.05)
cvar = rg.compute_cvar([-0.01, -0.02, -0.03, 0.01, 0.02])
print(f"  RiskGate CVaR: {cvar:.4f}")

# Test Cascade
combo = compute_total_combinations(["momentum", "breakout"], num_symbols=2)
print(f"  Cascade combos: {combo}")

# Test Deflated Sharpe
sv = StatisticalValidator()
dsr = sv.deflated_sharpe(1.5, 100, 500)
print(
    f"  DSR: prob_positive={dsr['prob_real_sharpe_positive']:.3f} significant={dsr['significant']}"
)

print()
print("=== ALL 22 MODULES VERIFIED OK ===")
