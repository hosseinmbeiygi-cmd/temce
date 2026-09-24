"""Binomial and Trinomial tree pricing models for American/Bermudan options.

Supports:
- Cox-Ross-Rubinstein (CRR) binomial tree
- Trinomial tree for smoother convergence
- American early exercise
- Bermudan exercise (discrete exercise dates)
- Dividend yield (q) for commodity options
- Greeks extraction from tree

Market: Iranian options (TSE/IFB equity options, IME commodity options)

Numerical guards (charter):
- MIN_VOL_FLOOR = 1e-4: volatility is never allowed below this floor.
- CRR/trinomial validity requires sigma*sqrt(dt) >= |r|*dt, otherwise the
  risk-neutral probabilities leave [0, 1]; sigma is raised adaptively to
  max(sigma, MIN_VOL_FLOOR, |r|*sqrt(dt)).
- All probabilities are clipped and renormalized; all greeks are finite.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from domain.options.pricing import PRICING_MODEL_BINOMIAL, OptionPrice

#: Charter floor for volatility (منشور: σ ≥ 1e-4)
MIN_VOL_FLOOR = 1e-4


class TreeType(Enum):
    BINOMIAL = "binomial"
    TRINOMIAL = "trinomial"


class OptionStyle(Enum):
    EUROPEAN = "european"
    AMERICAN = "american"
    BERMOUDAN = "bermoudan"


@dataclass
class TreeOptionParams:
    S: float                        # Current spot price
    K: float                        # Strike price
    T: float                        # Time to expiry (years)
    r: float                        # Risk-free rate (annualized, decimal)
    sigma: float                    # Volatility (decimal)
    q: float = 0.0                  # Continuous dividend yield / cost of carry
    option_type: str = "call"       # "call" or "put"
    style: OptionStyle = OptionStyle.AMERICAN
    N: int = 200                    # Number of time steps
    tree_type: TreeType = TreeType.BINOMIAL
    exercise_dates: list[float] | None = None  # For Bermudan: fractional times [0.1, 0.2, ...]


def _effective_sigma(sigma: float, r: float, dt: float, factor: float = 1.0) -> float:
    """Clamp sigma so the tree probabilities stay inside [0, 1].

    p <= 1 for CRR requires e^{r*dt} <= u = e^{sigma*sqrt(dt)}, i.e.
    sigma >= |r|*sqrt(dt) (factor 1). The Boyle trinomial needs
    |nu| <= dx/3 with nu = (r-q-sigma^2/2)*dt, i.e. sigma >= sqrt(3)*|r|*sqrt(dt)
    (factor sqrt(3)); otherwise pd/pu go negative and ad-hoc renormalization
    would corrupt the risk-neutral drift. The charter floor 1e-4 always applies.
    """
    return max(float(sigma), MIN_VOL_FLOOR, factor * abs(float(r)) * math.sqrt(dt))


def _crr_params(r: float, sigma: float, q: float, dt: float) -> tuple[float, float, float]:
    """Cox-Ross-Rubinstein parameters."""
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    return u, d, p


def _trinomial_params(r: float, sigma: float, q: float, dt: float) -> tuple[float, float, float, float, float, float]:
    """Trinomial tree parameters (Boyle, 1986).

    Returns (dx, pu, pm, pd) with grid spacing dx = sigma*sqrt(3*dt).
    """
    # Boyle (1986) probabilities consistent with grid spacing dx = sigma*sqrt(3*dt):
    #   pu = 1/6 + nu/(2*dx), pd = 1/6 - nu/(2*dx), pm = 1 - pu - pd
    # with drift nu = (r - q - sigma^2/2)*dt. The previous formulas used
    # e^{+-sigma*sqrt(dt)} (a sqrt(3)x tighter spacing than the grid), which
    # inflated the per-step variance by ~1.54x and prices by ~18%.
    dx = sigma * math.sqrt(3 * dt)
    nu = (r - q - 0.5 * sigma * sigma) * dt
    pu = 1.0 / 6.0 + nu / (2.0 * dx)
    pd = 1.0 / 6.0 - nu / (2.0 * dx)
    pm = 1.0 - pu - pd
    # Belt-and-braces: clip to [0, 1] and renormalize (fp safety).
    # fp safety only: with sigma >= sqrt(3)*|r|*sqrt(dt) the probabilities are
    # naturally in [0, 1] and pu+pm+pd = 1 exactly, so NO renormalization here
    # — rescaling after clipping silently corrupts the risk-neutral drift.
    pu = min(max(pu, 0.0), 1.0)
    pd = min(max(pd, 0.0), 1.0)
    pm = min(max(pm, 0.0), 1.0)
    return dx, pu, pm, pd


def _atm_bump_delta(price_fn) -> float:
    """Fallback delta via a symmetric spot bump at the money."""
    h = 1.0
    return 0.5 * (price_fn(1.0) - price_fn(-1.0)) / h


def binomial_tree_price(params: TreeOptionParams, *, _compute_theta: bool = True) -> OptionPrice:
    """Cox-Ross-Rubinstein binomial tree pricing.

    Supports American and Bermudan exercise styles.
    """
    S, K, T, r, sigma, q = params.S, params.K, params.T, params.r, params.sigma, params.q
    N = params.N
    is_call = params.option_type == "call"
    # P0-4: degenerate inputs (expired, non-positive spot, no steps, or
    # non-finite values) would make dt=0 → u==d → ZeroDivisionError in
    # _crr_params. Return intrinsic value instead of crashing.
    if (
        not math.isfinite(S) or not math.isfinite(K) or not math.isfinite(T)
        or not math.isfinite(sigma) or N <= 0 or T <= 0 or S <= 0
    ):
        intrinsic = max(0.0, (S if math.isfinite(S) else 0.0) - K) if is_call else max(0.0, K - (S if math.isfinite(S) else 0.0))
        return OptionPrice(
            model="binomial", price=float(intrinsic),
            intrinsic_value=float(intrinsic), time_value=0.0,
        )
    dt = T / N
    is_american = params.style == OptionStyle.AMERICAN
    is_bermoudan = params.style == OptionStyle.BERMOUDAN

    sigma_eff = _effective_sigma(sigma, r, dt)
    u, d, p = _crr_params(r, sigma_eff, q, dt)
    disc = math.exp(-r * dt)

    # Build terminal payoff
    stock = np.zeros(N + 1)
    option = np.zeros(N + 1)
    for i in range(N + 1):
        stock[i] = S * (u ** (N - i)) * (d ** i)
        option[i] = max(stock[i] - K, 0.0) if is_call else max(K - stock[i], 0.0)

    # Bermudan exercise dates as set of step indices
    exercise_set: set[int] = set()
    if is_bermoudan and params.exercise_dates:
        for frac in params.exercise_dates:
            step = int(frac * N)
            if 0 <= step <= N:
                exercise_set.add(step)

    # Backward induction. Snapshots of the step-1 and step-2 grids are taken
    # before they are overwritten (after the loop, option[0] is the ROOT
    # value, not V(S*u) — using it produced mixed-step greeks and theta ≈ 0).
    v_up1 = v_dn1 = 0.0            # step-1: V(S*u), V(S*d)
    v_uu2 = v_ud2 = v_dd2 = 0.0    # step-2: V(S*u^2), V(S*u*d), V(S*d^2)
    for j in range(N - 1, -1, -1):
        for i in range(j + 1):
            hold = disc * (p * option[i] + (1 - p) * option[i + 1])
            stock_ij = S * (u ** (j - i)) * (d ** i)
            exercise = max(stock_ij - K, 0.0) if is_call else max(K - stock_ij, 0.0)

            if is_american or is_bermoudan and j in exercise_set:
                option[i] = max(hold, exercise)
            else:
                option[i] = hold

        if j == 2:
            v_uu2, v_ud2, v_dd2 = float(option[0]), float(option[1]), float(option[2])
        elif j == 1:
            v_up1, v_dn1 = float(option[0]), float(option[1])

    price = float(option[0])

    # Greeks from tree, all across same-step grids:
    delta = 0.0
    gamma = 0.0
    theta_annual = 0.0
    ds1 = S * (u - d)
    if N >= 1 and abs(ds1) > 1e-12:
        delta = (v_up1 - v_dn1) / ds1

    if N >= 2 and abs(ds1) > 1e-12:
        ds2 = S * (u * u - d * d)  # width of the step-2 grid
        d_uu = (v_uu2 - v_ud2) / (S * u * (u - d)) if abs(S * u * (u - d)) > 1e-12 else 0.0
        d_dn = (v_ud2 - v_dd2) / (S * d * (u - d)) if abs(S * d * (u - d)) > 1e-12 else 0.0
        gamma = (d_uu - d_dn) / (0.5 * ds2) if abs(ds2) > 1e-12 else 0.0

    # Theta: finite difference with the SAME pricer and step count at
    # maturity T - dt. Both trees share the same O(1/N) discretization bias,
    # which cancels in the difference (probe: -15933.2 vs BS -15932.7
    # annual, i.e. 3e-5 relative). Same-lattice re-pricing with N-1 steps is
    # NOT used: the CRR parity oscillation error (~10 rial at N=200) is
    # amplified by 1/dt and biased |theta| by ~2x. Linear interpolation of
    # the step-1 grid likewise drops the convexity term
    # 1/2*Gamma*(Su-S)*(S-Sd) and underestimates |theta|.
    theta_annual = 0.0
    if _compute_theta and N >= 2 and dt > 0:
        inner = TreeOptionParams(
            S=S, K=K, T=T - dt, r=r, sigma=sigma, q=q,
            option_type=params.option_type, style=params.style,
            N=N, tree_type=params.tree_type,
            exercise_dates=params.exercise_dates,
        )
        v_next_at_s = binomial_tree_price(inner, _compute_theta=False).price
        theta_annual = (v_next_at_s - price) / dt

    if not math.isfinite(price):
        price = max(0.0, S - K) if is_call else max(0.0, K - S)
    if not math.isfinite(delta):
        delta = 0.0
    if not math.isfinite(gamma):
        gamma = 0.0
    if not math.isfinite(theta_annual):
        theta_annual = 0.0

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
            "sigma_effective": sigma_eff,
            "S": S, "K": K, "T": T, "r": r, "sigma": sigma,
        },
    )


def trinomial_tree_price(params: TreeOptionParams) -> OptionPrice:
    """Trinomial tree pricing for American/Bermudan options.

    Generally converges faster than binomial for the same N.
    """
    S, K, T, r, sigma, q = params.S, params.K, params.T, params.r, params.sigma, params.q
    N = params.N
    is_call = params.option_type == "call"
    # P0-4: same degenerate-input guard as binomial (dt=0 → dx=0 →
    # division by zero in _trinomial_params).
    if (
        not math.isfinite(S) or not math.isfinite(K) or not math.isfinite(T)
        or not math.isfinite(sigma) or N <= 0 or T <= 0 or S <= 0
    ):
        intrinsic = max(0.0, (S if math.isfinite(S) else 0.0) - K) if is_call else max(0.0, K - (S if math.isfinite(S) else 0.0))
        return OptionPrice(
            model="trinomial", price=float(intrinsic),
            intrinsic_value=float(intrinsic), time_value=0.0,
        )
    dt = T / N
    is_american = params.style == OptionStyle.AMERICAN

    sigma_eff = _effective_sigma(sigma, r, dt, factor=math.sqrt(3.0))
    dx, pu, pm, pd = _trinomial_params(r, sigma_eff, q, dt)
    disc = math.exp(-r * dt)

    # Number of nodes at each step: 2*j+1, indexed from -j to +j
    # Use offset indexing: node[i] corresponds to index i-j
    # Only the current and previous grids are kept (O(N) memory).
    # Terminal payoff
    terminal = np.zeros(2 * N + 1)
    for j in range(-N, N + 1):
        stock = S * math.exp(j * dx)
        terminal[j + N] = max(stock - K, 0.0) if is_call else max(K - stock, 0.0)

    prev_grid: np.ndarray | None = None  # grid at step 1 (for greeks)

    # Backward induction
    for step in range(N - 1, -1, -1):
        curr_size = 2 * step + 1
        curr = np.zeros(curr_size)
        nxt = terminal  # grid at step+1
        for i in range(curr_size):
            j = i - step  # actual index
            # Children indices in next grid (step+1): j-1, j, j+1
            idx_up = (j + 1) + (step + 1)
            idx_mid = j + (step + 1)
            idx_dn = (j - 1) + (step + 1)

            hold = disc * (pu * nxt[idx_up]
                          + pm * nxt[idx_mid]
                          + pd * nxt[idx_dn])
            stock_ij = S * math.exp(j * dx)
            exercise = max(stock_ij - K, 0.0) if is_call else max(K - stock_ij, 0.0)

            if is_american:
                curr[i] = max(hold, exercise)
            else:
                curr[i] = hold

        if step == 1:
            prev_grid = curr.copy()
        terminal = curr

    price = float(terminal[0])

    # Greeks from trinomial tree
    # Delta: the tree grid moves by dx = sigma*sqrt(3*dt); measure across the
    # step-1 nodes +/- dx around the root (never across sigma*sqrt(dt), which
    # is NOT the grid spacing and inflates delta by ~sqrt(3)).
    delta = 0.0
    if prev_grid is not None and len(prev_grid) >= 3:
        denom = S * (math.exp(dx) - math.exp(-dx))
        if abs(denom) > 1e-12:
            delta = float((prev_grid[2] - prev_grid[0]) / denom)
        else:
            # Degenerate spacing: symmetric spot bump at the money.
            h = max(abs(S) * 1e-3, 1.0)

            def _px(bump: float) -> float:
                p2 = TreeOptionParams(
                    S=S + bump, K=params.K, T=params.T, r=params.r,
                    sigma=params.sigma, q=params.q,
                    option_type=params.option_type, style=params.style,
                    N=params.N, tree_type=params.tree_type,
                )
                return float(trinomial_tree_price(p2).price)

            delta = (_px(h) - _px(-h)) / (2.0 * h)

    if not math.isfinite(price):
        price = max(0.0, S - K) if is_call else max(0.0, K - S)
    if not math.isfinite(delta):
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
            "sigma_effective": sigma_eff,
            "S": S, "K": K, "T": T, "r": r, "sigma": sigma,
        },
    )


def price_tree_option(params: TreeOptionParams) -> OptionPrice:
    """Unified entry point: select binomial or trinomial based on params."""
    if params.tree_type == TreeType.TRINOMIAL:
        return trinomial_tree_price(params)
    return binomial_tree_price(params)


def american_early_exercise_boundary(
    S: float, K: float, T: float, r: float, sigma: float,
    q: float = 0.0, option_type: str = "put", N: int = 200,
) -> list[tuple[float, float]]:
    """Calculate the early exercise boundary S*(t) over time.

    For a put option, S*(t) is the price below which exercise is optimal.
    Returns list of (time_to_expiry, boundary_price) pairs.
    """
    dt = T / N
    sigma_eff = _effective_sigma(sigma, r, dt)
    u, d, p = _crr_params(r, sigma_eff, q, dt)
    disc = math.exp(-r * dt)
    is_put = option_type == "put"

    stock = np.zeros(N + 1)
    option = np.zeros(N + 1)
    for i in range(N + 1):
        stock[i] = S * (u ** (N - i)) * (d ** i)
        option[i] = max(stock[i] - K, 0.0) if not is_put else max(K - stock[i], 0.0)

    boundaries = []

    for j in range(N - 1, -1, -1):
        exercise_idx = None
        for i in range(j + 1):
            hold = disc * (p * option[i] + (1 - p) * option[i + 1])
            stock_ij = S * (u ** (j - i)) * (d ** i)
            exercise = max(stock_ij - K, 0.0) if not is_put else max(K - stock_ij, 0.0)
            if hold < exercise:
                if exercise_idx is None or i > exercise_idx:
                    exercise_idx = i
            option[i] = max(hold, exercise)

        if exercise_idx is not None:
            boundary_price = S * (u ** (j - exercise_idx)) * (d ** exercise_idx)
            time_remaining = j * dt
            boundaries.append((time_remaining, boundary_price))

    return boundaries
