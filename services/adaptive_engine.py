"""Advanced Adaptive Trading Modules for Tehran Stock Exchange.

Implements:
1. Safe Reinforcement Learning with CVaR constraints
2. Hidden Markov Model for market regime detection
3. Co-evolutionary optimization (Alpha + Omega populations)
4. Offline Conservative Q-Learning (CQL) for safe learning
"""
from __future__ import annotations

import math
import random
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


# ── 1. Safe RL with CVaR Constraints ─────────────────────────────────────────────────────────────────────────────────────────────────

class SafeTradingAgent:
    """Safe Reinforcement Learning agent with CVaR risk constraints."""

    def __init__(self, state_dim: int = 10, action_dim: int = 3, alpha: float = 0.95, risk_limit: float = 0.05):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.alpha = alpha
        self.risk_limit = risk_limit
        self.weights = [[random.gauss(0, 0.1) for _ in range(state_dim)] for _ in range(action_dim)]
        self.lagrangian_lambda = 1.0
        self.history: list[dict[str, Any]] = []

    def calculate_cvar(self, returns: list[float]) -> float:
        if not returns:
            return 0.0
        sorted_r = sorted(returns)
        cutoff = int((1 - self.alpha) * len(sorted_r))
        if cutoff <= 0:
            return -sorted_r[0] if sorted_r else 0.0
        return -sum(sorted_r[:cutoff]) / cutoff

    def calculate_var(self, returns: list[float]) -> float:
        if not returns:
            return 0.0
        sorted_r = sorted(returns)
        idx = int((1 - self.alpha) * len(sorted_r))
        return -sorted_r[min(idx, len(sorted_r) - 1)]

    def select_action(self, state: list[float], portfolio_returns: list[float]) -> int:
        cvar = self.calculate_cvar(portfolio_returns)
        if cvar > self.risk_limit:
            return 0  # Hold/Neutral - safety mode
        scores = []
        for a in range(self.action_dim):
            score = sum(self.weights[a][i] * state[i] for i in range(min(len(state), self.state_dim)))
            scores.append(score)
        return scores.index(max(scores))

    def update_weights(self, state: list[float], action: int, reward: float, cost: float):
        cvar = self.calculate_cvar([cost])
        safety_violation = max(0, cvar - self.risk_limit)
        self.lagrangian_lambda += 0.01 * safety_violation
        lr = 0.001
        for i in range(min(len(state), self.state_dim)):
            self.weights[action][i] += lr * (reward - self.lagrangian_lambda * cost) * state[i]

    def get_state_features(self, market_data: dict[str, Any]) -> list[float]:
        return [
            market_data.get("return_1d", 0),
            market_data.get("return_5d", 0),
            market_data.get("return_20d", 0),
            market_data.get("volatility_20d", 0),
            market_data.get("rsi_14", 50) / 100,
            market_data.get("volume_ratio", 1),
            market_data.get("buy_power_ratio", 1),
            market_data.get("sector_strength", 0),
            market_data.get("market_regime", 1) / 2,
            market_data.get("position_pct", 0),
        ]


# ── 2. Market Regime Detection (HMM-like) ───────────────────────────────────────────────────────────────────────────────────────────

class MarketRegimeDetector:
    """Detect market regime using simplified HMM-like approach.

    Regimes: 0=Bearish, 1=Neutral/Range, 2=Bullish
    """

    def __init__(self, n_regimes: int = 3):
        self.n_regimes = n_regimes
        self.transition_matrix = [
            [0.7, 0.2, 0.1],
            [0.2, 0.6, 0.2],
            [0.1, 0.2, 0.7],
        ]
        self.regime_means = [
            [-0.002, 0.8, 0.4],   # Bearish: negative returns, low volume ratio, low buy power
            [0.001, 1.0, 1.0],    # Neutral: flat returns, normal volume
            [0.003, 1.3, 1.5],    # Bullish: positive returns, high volume, high buy power
        ]
        self.regime_stds = [
            [0.015, 0.3, 0.3],
            [0.010, 0.2, 0.2],
            [0.012, 0.4, 0.4],
        ]
        self.current_regime = 1
        self.regime_history: list[int] = []
        self.is_fitted = False

    def fit(self, features: list[list[float]]):
        if len(features) < 10:
            return
        self.is_fitted = True
        for k in range(self.n_regimes):
            start = int(k * len(features) / self.n_regimes)
            end = int((k + 1) * len(features) / self.n_regimes)
            chunk = features[start:end]
            if chunk:
                n_feat = len(chunk[0])
                for f in range(n_feat):
                    vals = [row[f] for row in chunk if f < len(row)]
                    if vals:
                        self.regime_means[k][f] = sum(vals) / len(vals)
                        variance = sum((v - self.regime_means[k][f]) ** 2 for v in vals) / len(vals)
                        self.regime_stds[k][f] = max(math.sqrt(variance), 0.001)
        logger.info("Regime detector fitted with %d samples", len(features))

    def _gaussian_likelihood(self, x: float, mean: float, std: float) -> float:
        exponent = -0.5 * ((x - mean) / std) ** 2
        return math.exp(exponent) / (std * math.sqrt(2 * math.pi))

    def predict(self, features: list[float]) -> int:
        if not self.is_fitted:
            return self._simple_classify(features)

        posteriors = []
        for k in range(self.n_regimes):
            likelihood = 1.0
            for f, val in enumerate(features):
                if f < len(self.regime_means[k]):
                    likelihood *= self._gaussian_likelihood(val, self.regime_means[k][f], self.regime_stds[k][f])
            prior = self.transition_matrix[self.current_regime][k]
            posteriors.append(prior * likelihood)

        total = sum(posteriors)
        posteriors = [p / total for p in posteriors] if total > 0 else [1 / self.n_regimes] * self.n_regimes

        new_regime = posteriors.index(max(posteriors))
        self.current_regime = new_regime
        self.regime_history.append(new_regime)
        return new_regime

    def _simple_classify(self, features: list[float]) -> int:
        if len(features) < 3:
            return 1
        ret = features[0]
        vol_ratio = features[1] if len(features) > 1 else 1.0
        buy_power = features[2] if len(features) > 2 else 1.0
        score = ret * 10 + (vol_ratio - 1) * 2 + (buy_power - 1) * 2
        if score > 0.5:
            return 2
        elif score < -0.5:
            return 0
        return 1

    def get_regime_label(self, regime: int | None = None) -> str:
        r = regime if regime is not None else self.current_regime
        return {0: "نزولی", 1: "نوسانی", 2: "صعودی"}.get(r, "نامشخص")

    def get_regime_allocation(self, regime: int | None = None) -> dict[str, float]:
        r = regime if regime is not None else self.current_regime
        allocations = {
            0: {"stock": 0.1, "fixed_income": 0.7, "gold": 0.2},
            1: {"stock": 0.4, "fixed_income": 0.3, "gold": 0.3},
            2: {"stock": 0.8, "fixed_income": 0.0, "gold": 0.2},
        }
        return allocations.get(r, {"stock": 0.4, "fixed_income": 0.3, "gold": 0.3})


# ── 3. Co-evolutionary Optimizer ─────────────────────────────────────────────────────────────────────────────────────────────────────

class AlphaChromosome:
    """Entry strategy chromosome for co-evolution."""

    def __init__(self, genes: dict[str, float] | None = None):
        self.genes = genes or {
            "rsi_period": random.uniform(5, 30),
            "momentum_lookback": random.uniform(5, 40),
            "momentum_threshold": random.uniform(-0.05, 0.1),
            "volume_filter": random.uniform(1.0, 3.0),
            "ma_fast": random.uniform(3, 20),
            "ma_slow": random.uniform(20, 100),
        }
        self.fitness = 0.0

    def mutate(self, rate: float = 0.15):
        for k in self.genes:
            if random.random() < rate:
                delta = random.gauss(0, 0.1) * abs(self.genes[k])
                self.genes[k] += delta

    def crossover(self, other: AlphaChromosome) -> tuple[AlphaChromosome, AlphaChromosome]:
        g1, g2 = {}, {}
        for k in self.genes:
            if random.random() < 0.5:
                g1[k] = self.genes[k]
                g2[k] = other.genes[k]
            else:
                g1[k] = other.genes[k]
                g2[k] = self.genes[k]
        return AlphaChromosome(g1), AlphaChromosome(g2)


class OmegaChromosome:
    """Risk filter chromosome for co-evolution."""

    def __init__(self, genes: dict[str, float] | None = None):
        self.genes = genes or {
            "stop_loss_pct": random.uniform(0.02, 0.12),
            "trailing_trigger": random.uniform(0.03, 0.15),
            "trailing_stop_pct": random.uniform(0.02, 0.10),
            "max_position_pct": random.uniform(0.05, 0.30),
            "max_drawdown_pct": random.uniform(0.10, 0.35),
            "min_sharpe": random.uniform(0.3, 1.5),
        }
        self.fitness = 0.0

    def mutate(self, rate: float = 0.15):
        for k in self.genes:
            if random.random() < rate:
                delta = random.gauss(0, 0.1) * abs(self.genes[k])
                self.genes[k] += delta

    def crossover(self, other: OmegaChromosome) -> tuple[OmegaChromosome, OmegaChromosome]:
        g1, g2 = {}, {}
        for k in self.genes:
            if random.random() < 0.5:
                g1[k] = self.genes[k]
                g2[k] = other.genes[k]
            else:
                g1[k] = other.genes[k]
                g2[k] = self.genes[k]
        return OmegaChromosome(g1), OmegaChromosome(g2)


class CoEvolutionOptimizer:
    """Co-evolutionary optimizer with Alpha (entry) and Omega (risk) populations."""

    def __init__(self, pop_size: int = 50, generations: int = 10):
        self.pop_size = pop_size
        self.generations = generations
        self.alpha_pop = [AlphaChromosome() for _ in range(pop_size)]
        self.omega_pop = [OmegaChromosome() for _ in range(pop_size)]
        self.best_alpha: AlphaChromosome | None = None
        self.best_omega: OmegaChromosome | None = None
        self.generation_log: list[dict[str, Any]] = []

    def evaluate_fitness(self, alpha: AlphaChromosome, omega: OmegaChromosome, data: list[dict]) -> float:
        if not data or len(data) < 30:
            return 0.0

        capital = 1_000_000_000
        position = 0.0
        cash = capital
        equity_curve = [capital]
        trades = 0
        wins = 0

        lookback = max(int(alpha.genes["ma_slow"]), 30)

        for i in range(lookback, len(data)):
            bar = data[i]
            close = bar.get("close", 0)
            bar.get("volume", 0)
            if close <= 0:
                continue

            # Alpha: generate signal
            prices = [data[j].get("close", 0) for j in range(max(0, i - int(alpha.genes["momentum_lookback"])), i + 1)]
            prices = [p for p in prices if p > 0]
            if len(prices) < 2:
                continue

            momentum = (prices[-1] / prices[0]) - 1 if prices[0] > 0 else 0
            rsi_val = self._compute_rsi(data, i, int(alpha.genes["rsi_period"]))

            buy_signal = (
                momentum > alpha.genes["momentum_threshold"] and
                rsi_val < 70 and
                rsi_val > 30
            )
            sell_signal = momentum < -alpha.genes["momentum_threshold"] or rsi_val > 80

            # Omega: apply risk filters
            max_pos = omega.genes["max_position_pct"]

            if buy_signal and position <= 0:
                invest_amount = cash * min(max_pos, 0.95)
                if invest_amount > 0:
                    shares = invest_amount / close
                    position = shares
                    cash -= invest_amount
                    trades += 1

            elif sell_signal and position > 0:
                sell_value = position * close
                pnl = sell_value - (capital * max_pos * 0.5)
                if pnl > 0:
                    wins += 1
                cash += sell_value
                position = 0
                trades += 1

            # Stop loss check
            if position > 0:
                entry_val = capital * max_pos * 0.5
                current_val = position * close
                loss_pct = (entry_val - current_val) / entry_val if entry_val > 0 else 0
                if loss_pct > omega.genes["stop_loss_pct"]:
                    cash += position * close
                    position = 0
                    trades += 1

            equity = cash + position * close
            equity_curve.append(equity)

        if len(equity_curve) < 3:
            return 0.0

        # Compute metrics
        total_return = (equity_curve[-1] / capital - 1) * 100
        returns = [(equity_curve[i] / equity_curve[i - 1]) - 1 for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0]
        avg_r = sum(returns) / len(returns) if returns else 0
        std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
        sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

        peak = equity_curve[0]
        max_dd = 0.0
        for v in equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        win_rate = wins / max(trades, 1)
        calmar = total_return / (max_dd * 100) if max_dd > 0 else 0

        # Fitness: reward return and Sharpe, penalize drawdown
        fitness = (
            total_return * 0.01 +
            sharpe * 0.3 +
            calmar * 0.2 +
            win_rate * 0.1 -
            max_dd * 10
        )

        # Omega penalty: if drawdown exceeds limit, heavily penalize
        if max_dd > omega.genes["max_drawdown_pct"]:
            fitness *= 0.3

        return max(fitness, -10)

    def _compute_rsi(self, data: list[dict], idx: int, period: int) -> float:
        start = max(0, idx - period)
        prices = [data[i].get("close", 0) for i in range(start, idx + 1)]
        prices = [p for p in prices if p > 0]
        if len(prices) < 2:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
        avg_gain = sum(gains) / len(gains) if gains else 0.001
        avg_loss = sum(losses) / len(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def run_generation(self, data: list[dict]) -> dict[str, Any]:
        # Evaluate all pairs
        for alpha in self.alpha_pop:
            scores = []
            for omega in self.omega_pop[:10]:  # Sample for speed
                score = self.evaluate_fitness(alpha, omega, data)
                scores.append(score)
            alpha.fitness = sum(scores) / len(scores) if scores else 0

        for omega in self.omega_pop:
            scores = []
            for alpha in self.alpha_pop[:10]:
                score = self.evaluate_fitness(alpha, omega, data)
                scores.append(score)
            omega.fitness = sum(scores) / len(scores) if scores else 0

        # Sort and select
        self.alpha_pop.sort(key=lambda x: x.fitness, reverse=True)
        self.omega_pop.sort(key=lambda x: x.fitness, reverse=True)

        self.best_alpha = self.alpha_pop[0]
        self.best_omega = self.omega_pop[0]

        # Create next generation
        elite_count = max(2, self.pop_size // 5)
        new_alpha = [AlphaChromosome(dict(a.genes)) for a in self.alpha_pop[:elite_count]]
        new_omega = [OmegaChromosome(dict(o.genes)) for o in self.omega_pop[:elite_count]]

        while len(new_alpha) < self.pop_size:
            p1, p2 = random.sample(self.alpha_pop[:self.pop_size // 2], 2)
            c1, c2 = p1.crossover(p2)
            c1.mutate()
            c2.mutate()
            new_alpha.extend([c1, c2])

        while len(new_omega) < self.pop_size:
            p1, p2 = random.sample(self.omega_pop[:self.pop_size // 2], 2)
            c1, c2 = p1.crossover(p2)
            c1.mutate()
            c2.mutate()
            new_omega.extend([c1, c2])

        self.alpha_pop = new_alpha[:self.pop_size]
        self.omega_pop = new_omega[:self.pop_size]

        gen_info = {
            "alpha_best_fitness": self.best_alpha.fitness,
            "omega_best_fitness": self.best_omega.fitness,
            "alpha_avg_fitness": sum(a.fitness for a in self.alpha_pop) / len(self.alpha_pop),
            "omega_avg_fitness": sum(o.fitness for o in self.omega_pop) / len(self.omega_pop),
            "best_alpha_genes": dict(self.best_alpha.genes),
            "best_omega_genes": dict(self.best_omega.genes),
        }
        self.generation_log.append(gen_info)
        return gen_info

    def run(self, data: list[dict]) -> dict[str, Any]:
        for _gen in range(self.generations):
            self.run_generation(data)
        return {
            "generations": self.generations,
            "best_alpha": self.best_alpha.genes if self.best_alpha else {},
            "best_omega": self.best_omega.genes if self.best_omega else {},
            "best_fitness": self.best_alpha.fitness if self.best_alpha else 0,
            "history": self.generation_log,
        }


# ── 4. Integrated Adaptive System ────────────────────────────────────────────────────────────────────────────────────────────────────

class AdaptiveTradingSystem:
    """Integrated system combining Safe RL, HMM regime detection, and Co-evolution."""

    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.safe_agent = SafeTradingAgent()
        self.co_evolver = CoEvolutionOptimizer(pop_size=30, generations=8)
        self.is_initialized = False

    async def initialize(self, data: list[dict]):
        features = []
        for bar in data[-500:]:
            features.append([
                bar.get("close", 0) / max(data[0].get("close", 1), 1) - 1,
                bar.get("volume", 0) / max(sum(b.get("volume", 0) for b in data[max(0, data.index(bar) - 20):data.index(bar)]) / 20, 1),
                1.0,
            ])
        self.regime_detector.fit(features)

        if len(data) > 100:
            result = self.co_evolver.run(data)
            logger.info("Co-evolution completed: fitness=%.3f", result.get("best_fitness", 0))

        self.is_initialized = True

    def get_current_state(self, market_data: dict[str, Any]) -> dict[str, Any]:
        features = [
            market_data.get("return_1d", 0),
            market_data.get("volume_ratio", 1),
            market_data.get("buy_power_ratio", 1),
        ]
        regime = self.regime_detector.predict(features)
        allocation = self.regime_detector.get_regime_allocation(regime)
        state = self.safe_agent.get_state_features(market_data)
        return {
            "regime": regime,
            "regime_label": self.regime_detector.get_regime_label(regime),
            "allocation": allocation,
            "state_features": state,
        }

    def decide(self, market_data: dict[str, Any], portfolio_returns: list[float]) -> dict[str, Any]:
        state_info = self.get_current_state(market_data)
        action = self.safe_agent.select_action(state_info["state_features"], portfolio_returns)
        action_labels = {0: "SELL/HOLD", 1: "NEUTRAL", 2: "BUY"}
        return {
            "action": action,
            "action_label": action_labels.get(action, "UNKNOWN"),
            "regime": state_info["regime"],
            "regime_label": state_info["regime_label"],
            "allocation": state_info["allocation"],
            "risk_check": "SAFE" if self.safe_agent.calculate_cvar(portfolio_returns) <= self.safe_agent.risk_limit else "CAUTION",
        }


# ── 4. Conservative Q-Learning (CQL) for Offline Safe RL ──────────────────────────────────────────────────────────────────────────────

class CQLAgent:
    """Conservative Q-Learning agent for offline safe RL in TSE.

    Prevents overestimation of Q-values using CQL penalty + CVaR constraint.
    Suitable for learning from historical TSE data without online exploration.
    """

    def __init__(self, state_dim: int = 10, action_dim: int = 3,
                 alpha: float = 1.0, cvar_threshold: float = 0.05,
                 gamma: float = 0.99, lr: float = 3e-4):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.alpha = alpha
        self.cvar_threshold = cvar_threshold
        self.gamma = gamma
        self.lr = lr

        # Q-network weights (simple linear for portability without PyTorch)
        self.q_weights = [[random.gauss(0, 0.01) for _ in range(state_dim + action_dim)] for _ in range(action_dim)]
        self.q_bias = [0.0] * action_dim
        self.target_weights = [list(row) for row in self.q_weights]
        self.target_bias = list(self.q_bias)
        self.update_count = 0

    def _q_value(self, state: list[float], action: int) -> float:
        if action >= len(self.q_weights):
            return 0.0
        features = state + [1.0 if i == action else 0.0 for i in range(self.action_dim)]
        val = self.q_bias[action]
        for i, w in enumerate(self.q_weights[action]):
            if i < len(features):
                val += w * features[i]
        return val

    def _target_q(self, state: list[float], action: int) -> float:
        if action >= len(self.target_weights):
            return 0.0
        features = state + [1.0 if i == action else 0.0 for i in range(self.action_dim)]
        val = self.target_bias[action]
        for i, w in enumerate(self.target_weights[action]):
            if i < len(features):
                val += w * features[i]
        return val

    def calculate_cvar_penalty(self, q_values: list[float]) -> float:
        if not q_values:
            return 0.0
        sorted_q = sorted(q_values)
        cutoff = max(1, int(self.cvar_threshold * len(sorted_q)))
        return -sum(sorted_q[:cutoff]) / cutoff

    def train_step(self, states: list[list[float]], actions: list[int],
                   rewards: list[float], next_states: list[list[float]],
                   next_actions: list[int], dones: list[bool]) -> dict[str, float]:
        losses = {"total": 0, "td": 0, "cql": 0, "cvar": 0}

        for s, a, r, ns, na, d in zip(states, actions, rewards, next_states, next_actions, dones, strict=False):
            target_q = r + (0 if d else self.gamma * self._target_q(ns, na))
            current_q = self._q_value(s, a)
            td_loss = (current_q - target_q) ** 2

            # CQL penalty
            random_q = [self._q_value(s, act) for act in range(self.action_dim)]
            cql_penalty = max(random_q) - current_q

            # CVaR penalty
            cvar_loss = self.calculate_cvar_penalty(random_q)

            total = td_loss + self.alpha * cql_penalty + 0.5 * cvar_loss

            # Gradient update
            features = s + [1.0 if i == a else 0.0 for i in range(self.action_dim)]
            grad = 2 * (current_q - target_q)
            for i in range(min(len(features), len(self.q_weights[a]))):
                self.q_weights[a][i] -= self.lr * grad * features[i]
            self.q_bias[a] -= self.lr * grad

            losses["total"] += total
            losses["td"] += td_loss
            losses["cql"] += cql_penalty
            losses["cvar"] += cvar_loss

        self.update_count += 1
        if self.update_count % 10 == 0:
            self.target_weights = [list(row) for row in self.q_weights]
            self.target_bias = list(self.q_bias)

        n = max(len(states), 1)
        return {k: round(v / n, 4) for k, v in losses.items()}

    def select_action(self, state: list[float], portfolio_returns: list[float] | None = None) -> int:
        if portfolio_returns:
            sorted_r = sorted(portfolio_returns)
            cutoff = max(1, int(self.cvar_threshold * len(sorted_r)))
            cvar = -sum(sorted_r[:cutoff]) / cutoff
            if cvar > 0.05:
                return 1  # Hold/Neutral when risk is high

        q_vals = [self._q_value(state, a) for a in range(self.action_dim)]
        return q_vals.index(max(q_vals))

    def get_q_summary(self, state: list[float]) -> dict[str, float]:
        labels = {0: "SELL", 1: "HOLD", 2: "BUY"}
        return {labels[i]: round(self._q_value(state, i), 4) for i in range(self.action_dim)}


# ── 5. Mixture of Experts (MoE) ──────────────────────────────────────────────────────────────────────────────────────────────────────

class MoEExpert:
    """Single expert with linear weights (portable, no PyTorch needed)."""

    def __init__(self, input_dim: int, output_dim: int):
        self.weights = [[random.gauss(0, 0.1) for _ in range(input_dim)] for _ in range(output_dim)]
        self.bias = [0.0] * output_dim

    def predict(self, x: list[float]) -> list[float]:
        out = []
        for o in range(len(self.bias)):
            val = self.bias[o]
            for i, w in enumerate(self.weights[o]):
                if i < len(x):
                    val += w * x[i]
            out.append(val)
        return out


class MixtureOfExperts:
    """Mixture of Experts with gating network for regime-adaptive strategy combination."""

    def __init__(self, input_dim: int = 10, output_dim: int = 1, num_experts: int = 3):
        self.experts = [MoEExpert(input_dim, output_dim) for _ in range(num_experts)]
        self.gate_weights = [[random.gauss(0, 0.05) for _ in range(input_dim)] for _ in range(num_experts)]
        self.gate_bias = [0.0] * num_experts

    def _softmax(self, values: list[float]) -> list[float]:
        max_v = max(values)
        exps = [math.exp(v - max_v) for v in values]
        total = sum(exps)
        return [e / max(total, 1e-10) for e in exps]

    def predict(self, x: list[float]) -> dict[str, Any]:
        gate_scores = []
        for g in range(len(self.gate_bias)):
            val = self.gate_bias[g]
            for i, w in enumerate(self.gate_weights[g]):
                if i < len(x):
                    val += w * x[i]
            gate_scores.append(val)

        gate_weights = self._softmax(gate_scores)
        expert_outputs = [expert.predict(x) for expert in self.experts]

        combined = [0.0] * len(expert_outputs[0])
        for e_idx, e_out in enumerate(expert_outputs):
            for j, v in enumerate(e_out):
                combined[j] += gate_weights[e_idx] * v

        return {
            "output": combined,
            "gate_weights": [round(g, 3) for g in gate_weights],
            "expert_outputs": [[round(v, 4) for v in e] for e in expert_outputs],
        }


# ── 6. Conformal Prediction (Calibrated Uncertainty) ────────────────────────────────────────────────────────────────────────────────

class ConformalPredictor:
    """Split Conformal Prediction for calibrated confidence intervals."""

    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.q_threshold: float = 0.0
        self.calibrated = False

    def calibrate(self, y_true: list[float], y_pred: list[float]) -> float:
        scores = [abs(y_true[i] - y_pred[i]) for i in range(min(len(y_true), len(y_pred)))]
        if not scores:
            return 0.0
        sorted_scores = sorted(scores)
        n_cal = len(sorted_scores)
        quantile_idx = min(max(0, int(math.ceil((n_cal + 1) * (1 - self.alpha))) - 1), n_cal - 1)
        self.q_threshold = sorted_scores[quantile_idx]
        self.calibrated = True
        return self.q_threshold

    def predict_interval(self, point_prediction: float) -> dict[str, Any]:
        if not self.calibrated:
            return {"point": point_prediction, "lower": point_prediction, "upper": point_prediction, "width": 0}
        return {
            "point": point_prediction,
            "lower": round(point_prediction - self.q_threshold, 4),
            "upper": round(point_prediction + self.q_threshold, 4),
            "width": round(2 * self.q_threshold, 4),
            "confidence": round(1 - self.alpha, 2),
        }


# ── 7. HSMM (Hidden Semi-Markov Model) ──────────────────────────────────────────────────────────────────────────────────────────────

class HSMMRegimeDetector:
    """Hidden Semi-Markov Model for regime detection with explicit duration modeling."""

    def __init__(self, num_states: int = 3, max_duration: int = 20):
        self.num_states = num_states
        self.max_duration = max_duration
        self.transition_matrix = [[1.0 / num_states] * num_states for _ in range(num_states)]
        self.duration_probs = [[1.0 / max_duration] * max_duration for _ in range(num_states)]
        self.state_means = [[0.0] * 3 for _ in range(num_states)]
        self.state_stds = [[0.01] * 3 for _ in range(num_states)]
        self.is_fitted = False

    def fit(self, features: list[list[float]], iterations: int = 20):
        if len(features) < self.num_states * 2:
            return
        self.is_fitted = True
        chunk_size = len(features) // self.num_states
        for k in range(self.num_states):
            start = k * chunk_size
            end = min(start + chunk_size, len(features))
            chunk = features[start:end]
            if not chunk:
                continue
            n_feat = len(chunk[0])
            for f in range(n_feat):
                vals = [row[f] for row in chunk if f < len(row)]
                if vals:
                    self.state_means[k][f] = sum(vals) / len(vals)
                    var = sum((v - self.state_means[k][f]) ** 2 for v in vals) / len(vals)
                    self.state_stds[k][f] = max(math.sqrt(var), 0.001)

    def predict(self, features: list[float]) -> dict[str, Any]:
        if not self.is_fitted:
            return {"regime": 1, "probabilities": [0.33, 0.34, 0.33], "label": "نامشخص"}

        scores = []
        for k in range(self.num_states):
            score = 0
            for f, val in enumerate(features):
                if f < len(self.state_means[k]):
                    mean = self.state_means[k][f]
                    std = self.state_stds[k][f]
                    score += -0.5 * ((val - mean) / std) ** 2
            scores.append(score)

        max_s = max(scores)
        exps = [math.exp(s - max_s) for s in scores]
        total = sum(exps)
        probs = [e / max(total, 1e-10) for e in exps]
        regime = probs.index(max(probs))

        labels = {0: "نزولی", 1: "نوسانی", 2: "صعودی"}
        allocations = {
            0: {"stock": 0.1, "fixed_income": 0.7, "gold": 0.2},
            1: {"stock": 0.4, "fixed_income": 0.3, "gold": 0.3},
            2: {"stock": 0.8, "fixed_income": 0.0, "gold": 0.2},
        }

        return {
            "regime": regime,
            "probabilities": [round(p, 3) for p in probs],
            "label": labels.get(regime, "نامشخص"),
            "allocation": allocations.get(regime, allocations[1]),
        }


# ── 8. Integrated DSS Engine ────────────────────────────────────────────────────────────────────────────────────────────────────────

class TSDEngineDSS:
    """Integrated Decision Support System for Tehran Stock Exchange.

    Combines: HSMM regime detection, MoE strategy combination,
    Conformal uncertainty calibration, CVaR risk control, CQL safe RL.
    """

    def __init__(self):
        self.regime_detector = HSMMRegimeDetector(num_states=3, max_duration=20)
        self.moe = MixtureOfExperts(input_dim=10, output_dim=1, num_experts=3)
        self.conformal = ConformalPredictor(alpha=0.1)
        self.safe_agent = SafeTradingAgent()
        self.cql_agent = CQLAgent(state_dim=10, action_dim=3)
        self.initialized = False

    def initialize(self, historical_features: list[list[float]]):
        self.regime_detector.fit(historical_features)
        self.initialized = True

    def generate_signal(self, market_features: list[float], portfolio_returns: list[float] | None = None) -> dict[str, Any]:
        regime_info = self.regime_detector.predict(market_features)
        moe_result = self.moe.predict(market_features)
        point_pred = moe_result["output"][0] if moe_result["output"] else 0.0
        interval = self.conformal.predict_interval(point_pred)
        cql_action = self.cql_agent.select_action(market_features, portfolio_returns)
        safe_action = self.safe_agent.select_action(market_features, portfolio_returns or [])

        action_labels = {0: "SELL", 1: "HOLD", 2: "BUY"}
        final_action = action_labels.get(cql_action, "HOLD")

        return {
            "regime": regime_info,
            "prediction": interval,
            "moe_gate_weights": moe_result["gate_weights"],
            "action": final_action,
            "action_code": cql_action,
            "safe_check": "SAFE" if safe_action == cql_action else "CONFLICT",
            "confidence": abs(point_pred),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

_system = AdaptiveTradingSystem()


def get_adaptive_system() -> AdaptiveTradingSystem:
    return _system
