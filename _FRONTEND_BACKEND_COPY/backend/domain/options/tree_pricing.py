"""Binomial and Trinomial tree pricing models for American/Bermudan options.

Supports:
- Cox-Ross-Rubinstein (CRR) binomial tree
- Trinomial tree for smoother convergence
- American early exercise
- Bermudan exercise (discrete exercise dates)
- Dividend yield (q) for commodity options
- Greeks extraction from tree

Market: Iranian options (TSE/IFB equity options, IME commodity options)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from domain.options.pricing import PRICING_MODEL_BINOMIAL, OptionPrice


class TreeType(Enum):
    BINOMIAL = "binomial"
    TRINOMIAL = "trinomial"


class OptionStyle(Enum):
    EUROPEAN = "european"
    AMERICAN = "american"
    BERMOUDAN = "bermoudan"


@dataclass
class TreeOptionParams:
    S: float  # Current spot price
    K: float  # Strike price
    T: float  # Time to expiry (years)
    r: float  # Risk-free rate (annualized, decimal)
    sigma: float  # Volatility (decimal)
    q: float = 0.0  # Continuous dividend yield / cost of carry
    option_type: str = "call"  # "call" or "put"
    style: OptionStyle = OptionStyle.AMERICAN
    N: int = 200  # Number of time steps
    tree_type: TreeType = TreeType.BINOMIAL
    exercise_dates: list[float] | None = None  # For Bermudan: fractional times [0.1, 0.2, ...]


def _crr_params(r: float, sigma: float, q: float, dt: float) -> tuple[float, float, float]:
    """Cox-Ross-Rubinstein parameters."""
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    return u, d, p


def _trinomial_params(r: float, sigma: float, q: float, dt: float) -> tuple[float, float, float, float, float, float]:
    """Trinomial tree parameters (Boyle, 1986)."""
    dx = sigma * math.sqrt(3 * dt)
    # drift and variance terms (kept for documentation; used implicitly in probabilities below)
    _drift = r - q - 0.5 * sigma**2
    _var = sigma**2 * dt
    pu = (
        (math.exp((r - q) * dt / 2) - math.exp(-sigma * math.sqrt(dt / 2)))
        / (math.exp(sigma * math.sqrt(dt / 2)) - math.exp(-sigma * math.sqrt(dt / 2)))
    ) ** 2
    pm = (
        1.0
        - pu
        - (
            (math.exp((r - q) * dt / 2) - math.exp(-sigma * math.sqrt(dt / 2)))
            / (math.exp(sigma * math.sqrt(dt / 2)) - math.exp(-sigma * math.sqrt(dt / 2)))
        )
        ** 2
    )
    # Simplified trinomial probabilities
    e_rdt = math.exp((r - q) * dt)
    e_sqdt = math.exp(sigma * math.sqrt(dt))
    e_nsqdt = 1.0 / e_sqdt
    pu = ((e_rdt - e_nsqdt) / (e_sqdt - e_nsqdt)) ** 2
    pd = ((e_sqdt - e_rdt) / (e_sqdt - e_nsqdt)) * ((e_rdt - e_nsqdt) / (e_sqdt - e_nsqdt))
    pm = 1.0 - pu - pd
    return e_sqdt, e_nsqdt, pu, pm, pd, dx


def binomial_tree_price(params: TreeOptionParams) -> OptionPrice:
    """Cox-Ross-Rubinstein binomial tree pricing.

    Supports American and Bermudan exercise styles.
    """
    S, K, T, r, sigma, q = params.S, params.K, params.T, params.r, params.sigma, params.q
    N = params.N
    dt = T / N
    is_call = params.option_type == "call"
    is_american = params.style == OptionStyle.AMERICAN
    is_bermoudan = params.style == OptionStyle.BERMOUDAN

    u, d, p = _crr_params(r, sigma, q, dt)
    disc = math.exp(-r * dt)

    # Build terminal payoff
    stock = np.zeros(N + 1)
    option = np.zeros(N + 1)
    for i in range(N + 1):
        stock[i] = S * (u ** (N - i)) * (d**i)
        option[i] = max(stock[i] - K, 0.0) if is_call else max(K - stock[i], 0.0)

    # Bermudan exercise dates as set of step indices
    exercise_set: set[int] = set()
    if is_bermoudan and params.exercise_dates:
        for frac in params.exercise_dates:
            step = int(frac * N)
            if 0 <= step <= N:
                exercise_set.add(step)

    # Backward induction
    for j in range(N - 1, -1, -1):
        for i in range(j + 1):
            hold = disc * (p * option[i] + (1 - p) * option[i + 1])
            stock_ij = S * (u ** (j - i)) * (d**i)
            exercise = max(stock_ij - K, 0.0) if is_call else max(K - stock_ij, 0.0)

            if is_american or is_bermoudan and j in exercise_set:
                option[i] = max(hold, exercise)
            else:
                option[i] = hold

    price = option[0]

    # Greeks from tree
    # Delta: from first two nodes at step 1
    delta = (option[0] - option[1]) / (S * u - S * d) if N >= 1 else 0.0

    # Gamma: from step 2
    if N >= 2:
        s00 = S * u * u
        s01 = S * u * d  # = S
        s02 = S * d * d
        delta_up = (option[0] - option[1]) / (s00 - s01) if abs(s00 - s01) > 1e-12 else 0.0
        delta_dn = (option[1] - option[2]) / (s01 - s02) if abs(s01 - s02) > 1e-12 else 0.0
        ds = S * (u - d)
        gamma = (delta_up - delta_dn) / (0.5 * ds) if abs(ds) > 1e-12 else 0.0
    else:
        gamma = 0.0

    # Theta: finite difference at root node (per year)
    theta_annual = (disc * (p * option[0] + (1 - p) * option[1]) - option[0]) / dt if N >= 2 else 0.0

    intrinsic = max(0.0, S - K) if is_call else max(0.0, K - S)

    return OptionPrice(
        model=PRICING_MODEL_BINOMIAL,
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta_annual / 365.0,  # Per calendar day
        vega=0.0,  # Would need tree re-computation
        rho=0.0,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={
            "tree_type": "binomial",
            "style": params.style.value,
            "N": N,
            "q": q,
            "S": S,
            "K": K,
            "T": T,
            "r": r,
            "sigma": sigma,
        },
    )


def trinomial_tree_price(params: TreeOptionParams) -> OptionPrice:
    """Trinomial tree pricing for American/Bermudan options.

    Generally converges faster than binomial for the same N.
    """
    S, K, T, r, sigma, q = params.S, params.K, params.T, params.r, params.sigma, params.q
    N = params.N
    dt = T / N
    is_call = params.option_type == "call"
    is_american = params.style == OptionStyle.AMERICAN

    e_sqdt, e_nsqdt, pu, pm, pd, dx = _trinomial_params(r, sigma, q, dt)
    disc = math.exp(-r * dt)

    # Number of nodes at each step: 2*j+1, indexed from -j to +j
    # Use offset indexing: node[i] corresponds to index i-j
    option_grids = []

    # Terminal payoff
    terminal = np.zeros(2 * N + 1)
    for j in range(-N, N + 1):
        stock = S * math.exp(j * dx)
        terminal[j + N] = max(stock - K, 0.0) if is_call else max(K - stock, 0.0)

    option_grids.append(terminal)

    # Backward induction
    for step in range(N - 1, -1, -1):
        curr_size = 2 * step + 1
        curr = np.zeros(curr_size)
        for i in range(curr_size):
            j = i - step  # actual index
            # Children indices in next grid (step+1): j-1, j, j+1
            idx_up = (j + 1) + (step + 1)
            idx_mid = j + (step + 1)
            idx_dn = (j - 1) + (step + 1)

            hold = disc * (pu * terminal[idx_up] + pm * terminal[idx_mid] + pd * terminal[idx_dn])
            stock_ij = S * math.exp(j * dx)
            exercise = max(stock_ij - K, 0.0) if is_call else max(K - stock_ij, 0.0)

            if is_american:
                curr[i] = max(hold, exercise)
            else:
                curr[i] = hold

        terminal = curr
        option_grids.append(terminal)

    price = terminal[0]

    # Greeks from trinomial tree
    if len(option_grids) >= 2:
        prev = option_grids[-2]  # step=1, size=3
        delta = (prev[2] - prev[0]) / (S * e_sqdt - S * e_nsqdt) if len(prev) >= 3 else 0.0
    else:
        delta = 0.0

    intrinsic = max(0.0, S - K) if is_call else max(0.0, K - S)

    return OptionPrice(
        model=PRICING_MODEL_BINOMIAL,
        price=price,
        delta=delta,
        gamma=0.0,
        theta=0.0,
        vega=0.0,
        rho=0.0,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={
            "tree_type": "trinomial",
            "style": params.style.value,
            "N": N,
            "q": q,
            "S": S,
            "K": K,
            "T": T,
            "r": r,
            "sigma": sigma,
        },
    )


def price_tree_option(params: TreeOptionParams) -> OptionPrice:
    """Unified entry point: select binomial or trinomial based on params."""
    if params.tree_type == TreeType.TRINOMIAL:
        return trinomial_tree_price(params)
    return binomial_tree_price(params)


def american_early_exercise_boundary(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    option_type: str = "put",
    N: int = 200,
) -> list[tuple[float, float]]:
    """Calculate the early exercise boundary S*(t) over time.

    For a put option, S*(t) is the price below which exercise is optimal.
    Returns list of (time_to_expiry, boundary_price) pairs.
    """
    dt = T / N
    u, d, p = _crr_params(r, sigma, q, dt)
    disc = math.exp(-r * dt)
    is_put = option_type == "put"

    stock = np.zeros(N + 1)
    option = np.zeros(N + 1)
    for i in range(N + 1):
        stock[i] = S * (u ** (N - i)) * (d**i)
        option[i] = max(stock[i] - K, 0.0) if not is_put else max(K - stock[i], 0.0)

    boundaries = []

    for j in range(N - 1, -1, -1):
        exercise_idx = None
        for i in range(j + 1):
            hold = disc * (p * option[i] + (1 - p) * option[i + 1])
            stock_ij = S * (u ** (j - i)) * (d**i)
            exercise = max(stock_ij - K, 0.0) if not is_put else max(K - stock_ij, 0.0)
            if hold < exercise:
                if exercise_idx is None or i > exercise_idx:
                    exercise_idx = i
            option[i] = max(hold, exercise)

        if exercise_idx is not None:
            boundary_price = S * (u ** (j - exercise_idx)) * (d**exercise_idx)
            time_remaining = j * dt
            boundaries.append((time_remaining, boundary_price))

    return boundaries
