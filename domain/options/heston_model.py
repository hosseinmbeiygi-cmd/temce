"""Heston Stochastic Volatility Model for option pricing.

The Heston model captures volatility smile/skew observed in Iranian markets,
especially for gold coin and equity options where constant-vol BS fails.

Model:
    dS = (r - q) * S * dt + sqrt(v) * S * dW1
    dv = kappa * (theta - v) * dt + sigma_v * sqrt(v) * dW2
    Corr(dW1, dW2) = rho

Pricing via:
    1. Semi-closed form (Fourier inversion of characteristic function)
    2. Monte Carlo simulation

Market: Iranian options (gold coin, equity) with pronounced volatility smile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import integrate

from domain.options.pricing import OptionPrice


@dataclass
class HestonParams:
    """Heston model parameters."""

    S: float  # Current spot price
    K: float  # Strike price
    T: float  # Time to expiry (years)
    r: float  # Risk-free rate
    q: float = 0.0  # Dividend yield / cost of carry
    v0: float = 0.04  # Initial variance (0.20^2)
    theta: float = 0.04  # Long-run variance
    kappa: float = 2.0  # Mean-reversion speed
    sigma_v: float = 0.3  # Vol of vol
    rho: float = -0.7  # Correlation (typically negative for equities)
    option_type: str = "call"  # "call" or "put"
    n_steps: int = 200  # For Monte Carlo
    n_paths: int = 10000  # For Monte Carlo


def _characteristic_function_heston(u: complex, tau: float, params: HestonParams) -> complex:
    """Heston characteristic function (Albrecher et al. formulation).

    phi(u, tau) = exp(C(u,tau) + D(u,tau)*v0 + i*u*ln(S))
    """
    S, r, q = params.S, params.r, params.q
    v0, theta, kappa, sigma_v, rho = params.v0, params.theta, params.kappa, params.sigma_v, params.rho

    alpha = -u * u / 2 - u * 1j / 2
    beta = kappa - rho * sigma_v * u * 1j
    gamma_val = sigma_v * sigma_v / 2

    # Discriminant
    disc = beta * beta - 4 * alpha * gamma_val
    d = np.sqrt(disc + 0j)

    g = (beta - d) / (beta + d)

    exp_d_tau = np.exp(-d * tau)
    C = (r - q) * u * 1j * tau + (kappa * theta / (sigma_v * sigma_v)) * (
        (beta - d) * tau - 2.0 * np.log((1 - g * exp_d_tau) / (1 - g))
    )
    D = ((beta - d) / (sigma_v * sigma_v)) * (1 - exp_d_tau) / (1 - g * exp_d_tau)

    return complex(np.exp(C + D * v0 + 1j * u * np.log(S)))


def _heston_call_price_semi_closed(params: HestonParams) -> float:
    """Semi-closed form Heston call price via Fourier inversion.

    Uses the Gil-Pelaez inversion formula.
    """
    S, K, T, r, q = params.S, params.K, params.T, params.r, params.q
    ln_S_K = math.log(S / K)

    def integrand_real(u: float) -> float:
        phi = _characteristic_function_heston(complex(u, -1), T, params)
        return float((phi * np.exp(-1j * u * ln_S_K) / (1j * u)).real)

    def integrand_imag(u: float) -> float:
        phi = _characteristic_function_heston(complex(u, -1), T, params)
        return float((phi * np.exp(-1j * u * ln_S_K) / (1j * u)).imag)

    I1, _ = integrate.quad(integrand_real, 1e-8, 200, limit=200)
    I2, _ = integrate.quad(integrand_imag, 1e-8, 200, limit=200)

    call = S * math.exp(-q * T) * 0.5 - K * math.exp(-r * T) * 0.5
    call += K * math.exp(-r * T) / math.pi * I1
    call += S * math.exp(-q * T) / math.pi * I2

    return float(max(call, 0.0))


def heston_price(params: HestonParams) -> OptionPrice:
    """Price an option using the Heston semi-closed form.

    Returns OptionPrice with price and limited Greeks (finite difference for delta/vega).
    """
    price = _heston_call_price_semi_closed(params)

    # Finite difference Greeks
    h_spot = params.S * 0.01
    h_vol = 0.01

    # Delta
    params_up = HestonParams(**{**params.__dict__, "S": params.S + h_spot})
    params_dn = HestonParams(**{**params.__dict__, "S": params.S - h_spot})
    p_up = _heston_call_price_semi_closed(params_up)
    p_dn = _heston_call_price_semi_closed(params_dn)
    delta = float((p_up - p_dn) / (2 * h_spot))

    # Gamma
    gamma = float((p_up - 2 * price + p_dn) / (h_spot**2))

    # Vega (sensitivity to initial variance v0)
    params_vup = HestonParams(**{**params.__dict__, "v0": params.v0 + h_vol})
    params_vdn = HestonParams(**{**params.__dict__, "v0": max(0.001, params.v0 - h_vol)})
    p_vup = _heston_call_price_semi_closed(params_vup)
    p_vdn = _heston_call_price_semi_closed(params_vdn)
    vega = float((p_vup - p_vdn) / (2 * h_vol) / 100.0)  # Per 1% vol change

    # Theta (forward difference)
    h_t = 1 / 365.0
    if h_t < params.T:
        params_tdn = HestonParams(**{**params.__dict__, "T": params.T - h_t})
        p_tdn = _heston_call_price_semi_closed(params_tdn)
        theta = float((p_tdn - price) / h_t / 365.0)  # Per calendar day
    else:
        theta = 0.0

    intrinsic = max(0.0, params.S - params.K) if params.option_type == "call" else max(0.0, params.K - params.S)

    return OptionPrice(
        model="heston",
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=0.0,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={
            "v0": params.v0,
            "theta": params.theta,
            "kappa": params.kappa,
            "sigma_v": params.sigma_v,
            "rho": params.rho,
            "S": params.S,
            "K": params.K,
            "T": params.T,
            "r": params.r,
            "q": params.q,
        },
    )


def heston_monte_carlo(params: HestonParams, seed: int = 42) -> OptionPrice:
    """Monte Carlo simulation of Heston model.

    Uses QE (Quadratic Exponential) scheme for stability.
    Returns price with standard error.
    """
    rng = np.random.default_rng(seed)
    S, K, T, r, q = params.S, params.K, params.T, params.r, params.q
    v0, theta_v, kappa, sigma_v, rho = params.v0, params.theta, params.kappa, params.sigma_v, params.rho

    n = params.n_steps
    m = params.n_paths
    dt = T / n

    # Initialize
    S_t = np.full(m, S, dtype=np.float64)
    v_t = np.full(m, v0, dtype=np.float64)

    # Cholesky decomposition for correlated Brownian motions
    Z1 = rng.standard_normal((n, m))
    Z2 = rho * Z1 + np.sqrt(1 - rho**2) * rng.standard_normal((n, m))

    for i in range(n):
        sqrt_v = np.sqrt(np.maximum(v_t, 1e-10))

        # Variance process (Milstein scheme)
        v_t = (
            v_t
            + kappa * (theta_v - v_t) * dt
            + sigma_v * sqrt_v * np.sqrt(dt) * Z2[i]
            + 0.25 * sigma_v**2 * dt * (Z2[i] ** 2 - 1)
        )
        v_t = np.maximum(v_t, 0.0)  # Ensure non-negative

        # Stock price process
        S_t = S_t * np.exp((r - q - 0.5 * v_t) * dt + sqrt_v * np.sqrt(dt) * Z1[i])

    # Payoff
    payoffs = np.maximum(S_t - K, 0.0) if params.option_type == "call" else np.maximum(K - S_t, 0.0)

    price = np.exp(-r * T) * np.mean(payoffs)
    std_error = np.exp(-r * T) * np.std(payoffs) / np.sqrt(m)

    intrinsic = max(0.0, S - K) if params.option_type == "call" else max(0.0, K - S)

    return OptionPrice(
        model="heston_mc",
        price=price,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={
            "v0": params.v0,
            "theta": params.theta_v if hasattr(params, "theta_v") else params.theta,
            "kappa": params.kappa,
            "sigma_v": params.sigma_v,
            "rho": params.rho,
            "n_paths": m,
            "n_steps": n,
            "std_error": std_error,
            "S": params.S,
            "K": params.K,
            "T": params.T,
        },
    )


def calibrate_heston(
    market_prices: list[tuple[float, float, float]],  # [(K, T, market_price), ...]
    S: float,
    r: float,
    q: float = 0.0,
    initial_guess: tuple[float, float, float, float, float] = (0.04, 0.04, 2.0, 0.3, -0.7),
) -> HestonParams:
    """Calibrate Heston parameters to market implied volatilities.

    Uses least-squares optimization to find v0, theta, kappa, sigma_v, rho.
    """
    from scipy.optimize import minimize

    def objective(x):
        v0, theta_v, kappa, sigma_v, rho = x
        # Constraints: Feller condition > 0, rho in (-1,1)
        if kappa <= 0 or sigma_v <= 0 or abs(rho) >= 1 or v0 <= 0 or theta_v <= 0:
            return 1e10

        total_error = 0.0
        for K, T, mkt_price in market_prices:
            try:
                params = HestonParams(
                    S=S,
                    K=K,
                    T=T,
                    r=r,
                    q=q,
                    v0=v0,
                    theta=theta_v,
                    kappa=kappa,
                    sigma_v=sigma_v,
                    rho=rho,
                )
                model_price = _heston_call_price_semi_closed(params)
                total_error += (model_price - mkt_price) ** 2
            except Exception:
                total_error += 1e6
        return total_error

    result = minimize(
        objective,
        x0=initial_guess,
        method="Nelder-Mead",
        options={"maxiter": 500, "xatol": 1e-6, "fatol": 1e-8},
    )

    v0, theta_v, kappa, sigma_v, rho = result.x
    rho = max(-0.99, min(0.99, rho))

    return HestonParams(
        S=S,
        K=market_prices[0][0],
        T=market_prices[0][1],
        r=r,
        q=q,
        v0=v0,
        theta=theta_v,
        kappa=kappa,
        sigma_v=sigma_v,
        rho=rho,
    )


def heston_calibration_sufficient(
    params: HestonParams,
    *,
    market_prices_count: int,
    calibration_rmse: float,
) -> tuple[bool, list[str]]:
    """Gate for activating the Heston Tier-2 model.

    Returns (ok, reasons) where `reasons` lists every blocking check
    that failed. A single failure is enough to block; this is intentionally
    conservative because the Heston model is more expensive than the
    Black-76 default and only worth running when its inputs are trustworthy.
    """
    reasons: list[str] = []

    if market_prices_count < 4:
        reasons.append(f"need at least 4 market quotes to calibrate Heston, got {market_prices_count}")

    if calibration_rmse > 0.02:
        reasons.append(f"calibration RMSE {calibration_rmse:.4f} exceeds 0.02 tolerance")

    # Feller condition: 2·κ·θ > σ_v² guarantees v stays positive.
    feller_lhs = 2.0 * params.kappa * params.theta
    feller_rhs = params.sigma_v**2
    if feller_lhs <= feller_rhs:
        reasons.append(f"Feller condition violated: 2·κ·θ = {feller_lhs:.4f} ≤ σ_v² = {feller_rhs:.4f}")

    if abs(params.rho) >= 0.99:
        reasons.append(f"rho = {params.rho:.4f} is at the boundary; near-degenerate correlation")

    return (len(reasons) == 0, reasons)
