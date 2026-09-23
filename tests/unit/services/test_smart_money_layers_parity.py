"""Parity safety net for smart_money layers 7/8 (P2 / Step 2 — TDD).

The production modules are being vectorized (NumPy single-pass) for the 40x
engine. This file freezes the *legacy* loop implementations as reference code
and demands equality between legacy and production outputs:

    - m < 8 history rows  → **bit-exact** (==) — NumPy reductions are
      sequential below 8 elements, so exact equality is enforceable.
    - larger randomized inputs → pytest.approx(rel=1e-12, abs=1e-15) —
      "logical parity": only float summation-order ulps may differ, never a
      decision-relevant digit (final scores are rounded to 4 decimals).

Reference implementations below are verbatim copies of the pre-refactor
modules — do NOT "fix" them; they are the parity oracle.
"""

from __future__ import annotations

import math
import random

import pytest

from services.smart_money.layer7_buyer_power import BuyerPowerLayer
from services.smart_money.layer8_microstructure import MicrostructureLayer
from services.smart_money.normalizer import MinMaxClipped

# ════════════════════════════════════════════════════════════════════════════
# Frozen legacy reference — VERBATIM pre-refactor code (parity oracle)
# ════════════════════════════════════════════════════════════════════════════

_norm_ref = MinMaxClipped()


def _ref_zscore(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    if n < 2:
        return 0.0, 1.0
    mu = sum(vals) / n
    var = sum((x - mu) ** 2 for x in vals) / (n - 1)
    std = var**0.5 or 1.0
    return mu, std


def _ref_layer7(quote: dict, history: list[dict]) -> dict[str, float]:
    ab = quote.get("avg_buy", 0.0) or 1.0
    as_ = quote.get("avg_sell", 0.0) or 1.0
    rbv = quote.get("real_buy_value", 0.0) or 0.0
    rsv = quote.get("real_sell_value", 0.0) or 0.0
    rbc = quote.get("real_buy_count", 1) or 1
    rsc = quote.get("real_sell_count", 1) or 1
    val = quote.get("value", 0) or 1

    vol_ratio = ab / as_ if as_ else 1.0
    val_ratio = rbv / rsv if rsv else 1.0
    count_ratio = rbc / rsc if rsc else 1.0

    rbp_val = (val_ratio + vol_ratio + count_ratio) / 3.0
    rbp_n = _norm_ref(rbp_val, 0.8, 3.0)

    hist_rbp: list[float] = []
    hist_val_ratio: list[float] = []
    for q in history:
        hab = q.get("avg_buy", 0.0) or 1.0
        has_ = q.get("avg_sell", 0.0) or 1.0
        hrbv = q.get("real_buy_value", 0.0) or 1.0
        hrsv = q.get("real_sell_value", 0.0) or 1.0
        hrbc = q.get("real_buy_count", 1) or 1
        hrsc = q.get("real_sell_count", 1) or 1
        hvr = hab / has_ if has_ else 1.0
        hvar = hrbv / hrsv if hrsv else 1.0
        hcr = hrbc / hrsc if hrsc else 1.0
        hist_rbp.append((hvr + hvar + hcr) / 3.0)
        hist_val_ratio.append(hvar)

    mu_rbp, std_rbp = _ref_zscore(hist_rbp) if hist_rbp else (1.0, 1.0)
    z_rbp = (rbp_val - mu_rbp) / std_rbp if std_rbp else 0.0
    z_rbp_n = _norm_ref(z_rbp, 1.5, 4.0)

    mu_vr, std_vr = _ref_zscore(hist_val_ratio) if hist_val_ratio else (1.0, 1.0)
    z_vr = (val_ratio - mu_vr) / std_vr if std_vr else 0.0
    z_vr_n = _norm_ref(z_vr, 1.5, 4.0)

    hist_pc: list[float] = (
        [q.get("real_buy_value", 0.0) / max(q.get("real_buy_count", 1), 1) for q in history] if history else [0.0]
    )
    mu_pc, std_pc = _ref_zscore(hist_pc)
    pc_today = rbv / rbc if rbc else 0.0
    z_pc = (pc_today - mu_pc) / std_pc if std_pc else 0.0
    z_pc_n = _norm_ref(z_pc, 1.5, 4.0)

    hist_nrmf: list[float] = []
    for q in history:
        hrbv = q.get("real_buy_value", 0.0) or 0.0
        hrsv = q.get("real_sell_value", 0.0) or 0.0
        hval = q.get("value", 0) or 1
        hist_nrmf.append((hrbv - hrsv) / hval if hval else 0.0)
    nrmf_today = (rbv - rsv) / val if val else 0.0
    mu_nrmf, std_nrmf = _ref_zscore(hist_nrmf) if hist_nrmf else (0.0, 1.0)
    z_nrmf = (nrmf_today - mu_nrmf) / std_nrmf if std_nrmf else 0.0
    z_nrmf_n = _norm_ref(z_nrmf, 1.0, 3.0)

    c = quote.get("price_close", 0.0)
    o = quote.get("price_open", 0.0)
    rt = (c - o) / o if o else 0.0
    amihud = abs(rt) / val if val else 0.0
    hist_amihud: list[float] = []
    for q in history:
        hc = q.get("price_close", 0.0)
        ho = q.get("price_open", 0.0)
        hv = q.get("value", 0) or 1
        hrt = (hc - ho) / ho if ho else 0.0
        hist_amihud.append(abs(hrt) / hv if hv else 0.0)
    mu_am, std_am = _ref_zscore(hist_amihud) if hist_amihud else (0.0, 1.0)
    z_am = (amihud - mu_am) / std_am if std_am else 0.0
    z_am_n = 1.0 - _norm_ref(z_am, -0.5, 2.0)

    bp_score = 0.25 * rbp_n + 0.20 * z_rbp_n + 0.15 * z_vr_n + 0.15 * z_pc_n + 0.15 * z_nrmf_n + 0.10 * z_am_n

    return {
        "bps": min(1.0, max(0.0, bp_score)),
        "rbp_n": rbp_n,
        "z_rbp_n": z_rbp_n,
        "z_vr_n": z_vr_n,
        "z_pc_n": z_pc_n,
        "z_nrmf_n": z_nrmf_n,
        "z_am_n": z_am_n,
    }


def _ref_layer8(quote: dict, history: list[dict]) -> dict[str, float]:
    ab = quote.get("avg_buy", 0.0) or 1.0
    as_ = quote.get("avg_sell", 0.0) or 1.0
    v = quote.get("volume", 0) or 1
    c = quote.get("price_close", 0.0)
    o = quote.get("price_open", 0.0)
    h = quote.get("price_high", 0.0)
    low = quote.get("price_low", 0.0)
    quote.get("value", 0) or 1

    vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]
    avg_vol_20 = sum(vols_20) / len(vols_20)

    abs(ab - as_) / (ab + as_) if (ab + as_) else 0.0
    hist_imb: list[float] = []
    for q in history:
        hab = q.get("avg_buy", 0.0) or 1.0
        has_ = q.get("avg_sell", 0.0) or 1.0
        hist_imb.append(abs(hab - has_) / (hab + has_) if (hab + has_) else 0.0)
    vpin = sum(hist_imb[-10:]) / max(len(hist_imb[-10:]), 1) if hist_imb else 0.0
    vpin_n = _norm_ref(vpin, 0.1, 0.6)

    rt = (c - o) / o if o else 0.0
    dpv: list[float] = []
    upv: list[float] = []
    for q in history:
        qc = q.get("price_close", 0.0)
        qo = q.get("price_open", 0.0)
        qrt = (qc - qo) / qo if qo else 0.0
        qv = q.get("volume", 0) or 1
        if qrt < 0:
            dpv.append(qv / abs(qrt) if abs(qrt) > 0 else qv * 100)
        else:
            upv.append(qv / max(qrt, 0.001) if qrt > 0 else qv * 100)
    avg_dpv = sum(dpv) / len(dpv) if dpv else 0.0
    avg_upv = sum(upv) / len(upv) if upv else 1.0
    abs_refined = avg_dpv / avg_upv if avg_upv else 0.0
    abs_n = _norm_ref(abs_refined, 0.8, 3.0)

    dps = (v / avg_vol_20 / abs(rt) if abs(rt) > 0 else 0.0) if rt < 0 else 0.0
    dps_n = _norm_ref(dps, 20.0, 300.0)

    up_vol_5 = sum(
        q.get("volume", 0) or 0
        for q in history[-5:]
        if (q.get("price_close", 0) or 0) >= (q.get("price_open", 0) or 0)
    )
    dn_vol_5 = sum(
        q.get("volume", 0) or 0
        for q in history[-5:]
        if (q.get("price_close", 0) or 0) < (q.get("price_open", 0) or 0)
    )
    dry_ratio = up_vol_5 / max(dn_vol_5, 1)
    dry_n = _norm_ref(dry_ratio, 0.5, 3.0)

    rng = h - low
    ((c - low) - (h - c)) / rng if rng else 0.0

    ratio = v / avg_vol_20 if avg_vol_20 else 1.0
    sell_shock = ratio if rt < 0 else 0.0
    shock_absorption = sell_shock / (abs(rt) + 0.0001) if rt < 0 else 0.0
    sa_n = _norm_ref(shock_absorption, 20.0, 300.0)

    mcs = 0.25 * vpin_n + 0.22 * abs_n + 0.18 * dps_n + 0.18 * dry_n + 0.17 * sa_n

    return {
        "mcs": min(1.0, max(0.0, mcs)),
        "vpin_n": vpin_n,
        "abs_n": abs_n,
        "dpsv_n": dps_n,
        "dry_n": dry_n,
        "sa_n": sa_n,
    }


# ════════════════════════════════════════════════════════════════════════════
# Deterministic input builders
# ════════════════════════════════════════════════════════════════════════════


def _base_quote() -> dict:
    return {
        "symbol": "TEST1",
        "price_close": 105.0,
        "price_open": 102.0,
        "price_high": 107.0,
        "price_low": 101.0,
        "price_last": 104.7,
        "volume": 7_000_000,
        "value": 7_000_000 * 104.0,
        "avg_buy": 1050.0,
        "avg_sell": 980.0,
        "real_buy_value": 4.2e9,
        "real_sell_value": 3.1e9,
        "real_buy_count": 540,
        "real_sell_count": 510,
    }


def _random_history(m: int, seed: int) -> list[dict]:
    """Deterministic pseudo-random history incl. zeros / missing keys / flat days."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for i in range(m):
        c = 100.0 + rng.uniform(-8.0, 8.0) + i * 0.05
        o = c - rng.uniform(-2.5, 2.5)
        h = max(c, o) + rng.uniform(0.1, 2.0)
        low = min(c, o) - rng.uniform(0.1, 2.0)
        vol = rng.uniform(1e6, 9e6)
        row = {
            "price_close": c,
            "price_open": o,
            "price_high": h,
            "price_low": low,
            "volume": int(vol),
            "value": vol * c,
            "avg_buy": rng.uniform(800.0, 1300.0),
            "avg_sell": rng.uniform(800.0, 1300.0),
            "real_buy_value": vol * c * rng.uniform(0.35, 0.65),
            "real_sell_value": vol * c * rng.uniform(0.35, 0.65),
            "real_buy_count": rng.randint(300, 800),
            "real_sell_count": rng.randint(300, 800),
        }
        if i % 37 == 0:
            row["volume"] = 0            # → `or 1` default path
        if i % 53 == 0:
            row.pop("real_buy_count", None)   # → missing-key default
        if i % 29 == 0:
            row["price_open"] = row["price_close"]  # flat day → qrt == 0
        if i % 71 == 0:
            row["avg_sell"] = 0.0        # → `or 1.0` default path
        if i % 91 == 0:
            row["real_sell_value"] = 0.0
        rows.append(row)
    return rows


def _flat_history(m: int) -> list[dict]:
    row = {
        "price_close": 100.0, "price_open": 100.0, "price_high": 100.0,
        "price_low": 100.0, "volume": 1_000_000, "value": 1e8,
        "avg_buy": 1000.0, "avg_sell": 1000.0,
        "real_buy_value": 5e8, "real_sell_value": 5e8,
        "real_buy_count": 500, "real_sell_count": 500,
    }
    return [dict(row) for _ in range(m)]


def _degenerate_quote() -> dict:
    """All optional keys missing/zero → every `or default` path fires."""
    return {"price_close": 10.0, "price_open": 10.0, "price_high": 10.0, "price_low": 10.0}


_SMALL_MS = [0, 1, 2, 3, 7]   # < 8 → NumPy reductions sequential → bit-exact
_LARGE_MS = [20, 60, 250]     # ≥ 8 → summation-order ulps → rel 1e-12 parity


def _assert_parity(quote: dict, history: list[dict], exact: bool) -> None:
    ref7 = _ref_layer7(quote, history)
    ref8 = _ref_layer8(quote, history)
    prod7 = BuyerPowerLayer().compute(quote, history)
    prod8 = MicrostructureLayer().compute(quote, history)

    assert set(prod7) == set(ref7), "layer7 key drift"
    assert set(prod8) == set(ref8), "layer8 key drift"

    if exact:
        assert prod7 == ref7, f"layer7 NOT bit-exact: {prod7} vs {ref7}"
        assert prod8 == ref8, f"layer8 NOT bit-exact: {prod8} vs {ref8}"
    else:
        for k in ref7:
            assert prod7[k] == pytest.approx(ref7[k], rel=1e-12, abs=1e-15), f"layer7[{k}] parity"
        for k in ref8:
            assert prod8[k] == pytest.approx(ref8[k], rel=1e-12, abs=1e-15), f"layer8[{k}] parity"


# ════════════════════════════════════════════════════════════════════════════
# Parity tests — layers 7 & 8
# ════════════════════════════════════════════════════════════════════════════


class TestLayerParityBitExact:
    """m < 8 → production must match the legacy oracle bit-for-bit."""

    @pytest.mark.parametrize("m", _SMALL_MS)
    def test_small_random_history_bit_exact(self, m: int) -> None:
        _assert_parity(_base_quote(), _random_history(m, seed=20260922), exact=True)

    @pytest.mark.parametrize("m", _SMALL_MS)
    def test_small_flat_history_bit_exact(self, m: int) -> None:
        _assert_parity(_base_quote(), _flat_history(m), exact=True)

    @pytest.mark.parametrize("m", _SMALL_MS)
    def test_degenerate_quote_bit_exact(self, m: int) -> None:
        _assert_parity(_degenerate_quote(), _random_history(m, seed=7), exact=True)

    @pytest.mark.parametrize("m", _SMALL_MS)
    def test_degenerate_quote_flat_history_bit_exact(self, m: int) -> None:
        _assert_parity(_degenerate_quote(), _flat_history(m), exact=True)

    def test_empty_history_bit_exact(self) -> None:
        _assert_parity(_base_quote(), [], exact=True)


class TestLayerParityLogical:
    """Large deterministic inputs → 1e-12 relative parity (float ulps only)."""

    @pytest.mark.parametrize("m", _LARGE_MS)
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_random_history_parity(self, m: int, seed: int) -> None:
        _assert_parity(_base_quote(), _random_history(m, seed=seed * 1000 + m), exact=False)

    @pytest.mark.parametrize("m", _LARGE_MS)
    def test_flat_history_parity(self, m: int) -> None:
        _assert_parity(_base_quote(), _flat_history(m), exact=False)

    def test_benchmark_shaped_history_parity(self) -> None:
        """Same shape as the P2 benchmark script (sine waves, m=250)."""
        history = []
        for i in range(250):
            c = 100 + 10 * math.sin(i * 0.37) + i * 0.05
            o = c - 2 * math.cos(i * 0.21)
            vol = 5e6 * (1 + math.sin(i * 0.53))
            history.append({
                "price_close": c, "price_open": o,
                "price_high": max(c, o) + 1.5, "price_low": min(c, o) - 1.5,
                "volume": int(vol), "value": vol * c,
                "avg_buy": 1000 + 100 * math.sin(i * 0.11),
                "avg_sell": 950 + 90 * math.cos(i * 0.13),
                "real_buy_value": vol * c * 0.55, "real_sell_value": vol * c * 0.45,
                "real_buy_count": int(500 + 40 * math.sin(i * 0.7)),
                "real_sell_count": int(520 + 30 * math.cos(i * 0.5)),
            })
            if i % 37 == 0:
                history[-1]["volume"] = 0
        _assert_parity(_base_quote(), history, exact=False)


class TestLayerInvariants:
    """Domain invariants that must hold for any implementation."""

    @pytest.mark.parametrize("m", [0, 1, 7, 60, 250])
    def test_outputs_finite_and_bounded(self, m: int) -> None:
        quote = _base_quote()
        history = _random_history(m, seed=99)
        for out in (BuyerPowerLayer().compute(quote, history), MicrostructureLayer().compute(quote, history)):
            for k, v in out.items():
                assert isinstance(v, float), f"{k} must be Python float"
                assert math.isfinite(v), f"{k} not finite: {v}"
                assert 0.0 <= v <= 1.0, f"{k} out of [0,1]: {v}"

    def test_output_keys_stable(self) -> None:
        assert set(BuyerPowerLayer().compute(_base_quote(), [])) == {
            "bps", "rbp_n", "z_rbp_n", "z_vr_n", "z_pc_n", "z_nrmf_n", "z_am_n",
        }
        assert set(MicrostructureLayer().compute(_base_quote(), [])) == {
            "mcs", "vpin_n", "abs_n", "dpsv_n", "dry_n", "sa_n",
        }
