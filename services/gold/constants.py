"""Gold constants — single source of truth for gold calculations.

All values consolidated from existing codebase. Each coin spec documents
the source/assumption for traceability.
"""

from __future__ import annotations

# ── Troy ounce and weights ──────────────────────────────────────────
# Source/assumption: International standard troy ounce = 31.1034768 g.
TROY_OUNCE_GRAMS: float = 31.1034768

# Source/assumption: Mesghal = 4.6083 g (Iranian market convention).
MESGHAL_GRAMS: float = 4.6083

# ── Purities (fineness basis) ────────────────────────────────────────
# Source/assumption: 17K ≈ 705/1000, 18K=750/1000, 24K≈999.9/1000,
# coin purity 900/1000 (22K), IME bullion assay 995/1000.
PURITY_17K: float = 705.0
PURITY_18K: float = 750.0
PURITY_24K: float = 999.9
PURITY_COIN: float = 900.0  # 22K
PURITY_FINE: float = 999.9
PURITY_IME_BULLION: int = 995

# Compatibility names (for src.gold_desk.pricer)
GOLD_PURITY_24K: float = PURITY_24K
GOLD_PURITY_18K: float = PURITY_18K
GOLD_PURITY_17K: float = PURITY_17K
GOLD_PURITY_COIN: float = PURITY_COIN

# ── Currency/peg ────────────────────────────────────────────────────
AED_PEG: float = 3.6725

# ── Coin specs ──────────────────────────────────────────────────────
# Source/assumption: Standard Iranian coin specs; we standardize on
# values consistent with src.gold_desk.constants (8.133/4.066/2.033/1.010)
# for internal consistency across modules. Previous physical_arbitrage
# used slightly different rounding (8.136/4.068/2.034/1.000) - standardized.
COIN_SPECS: dict[str, dict[str, float]] = {
    "emami": {"weight_grams": 8.133, "purity": 0.900, "mint_fee_irr": 80_000.0},
    "bahar": {"weight_grams": 8.133, "purity": 0.900, "mint_fee_irr": 80_000.0},
    "half": {"weight_grams": 4.066, "purity": 0.900, "mint_fee_irr": 50_000.0},
    "quarter": {"weight_grams": 2.033, "purity": 0.900, "mint_fee_irr": 35_000.0},
    "gerami": {"weight_grams": 1.010, "purity": 0.900, "mint_fee_irr": 15_000.0},
    "1g": {"weight_grams": 1.010, "purity": 0.900, "mint_fee_irr": 15_000.0},
}

_COIN_ALIASES: dict[str, str] = {
    "emami": "emami",
    "bahar": "bahar",
    "full": "emami",
    "half": "half",
    "nim": "half",
    "quarter": "quarter",
    "rob": "quarter",
    "gerami": "gerami",
    "grami": "gerami",
    "gram": "gerami",
    "1g": "gerami",
    "coin_emami": "emami",
    "coin_bahar": "bahar",
    "coin_half": "half",
    "coin_quarter": "quarter",
    "coin_1g": "gerami",
    "ir_coin_emami": "emami",
    "ir_coin_bahar": "bahar",
    "ir_coin_half": "half",
    "ir_coin_quarter": "quarter",
    "ir_coin_gerami": "gerami",
    "ir_coin_1g": "gerami",
}

# ── Fees ──────────────────────────────────────────────────────────────
IME_EXCHANGE_FEE: float = 0.0015
IME_BULLION_ASSAY: int = PURITY_IME_BULLION
MIN_NET_SPREAD_PCT: float = 1.0
GERAMI_MINTING_FEE_IRR: float = 15_000.0

# ── Gold ETF / fund thresholds (single source of truth) ───────────────────
# P/NAV alert thresholds used by the pure fund engine and service layer.
ETF_PREMIUM_SELL_THRESHOLD: float = 2.0   # +%  → SELL hint
ETF_DISCOUNT_BUY_THRESHOLD: float = -1.0  # -%  → BUY hint

# ── Pricer compatibility ──────────────────────────────────────────────
# COIN_WEIGHTS keyed by IR_COIN_* symbols as pricer expects
COIN_WEIGHTS: dict[str, float] = {
    "IR_COIN_EMAMI": 8.133,
    "IR_COIN_BAHAR": 8.133,
    "IR_COIN_HALF": 4.066,
    "IR_COIN_QUARTER": 2.033,
    "IR_COIN_1G": 1.010,
    "IR_COIN_GERAMI": 1.010,
}

MINTING_COST_TOMAN: float = 50_000.0
# STEP 6-FIX-2 unified mint fee: IR_COIN_EMAMI = 80,000 IRR (same physical
# mint cost as IR_COIN_BAHAR — identical 8.133 g / 900-fine full coin).
# Previously this table said 0.0 for EMAMI, contradicting
# src/gold_desk/constants.py (80,000). Canonical value is 80,000 here;
# src/gold_desk/constants.py imports this table.
COIN_MINTING_COSTS: dict[str, float] = {
    "IR_COIN_EMAMI": 80_000.0,
    "IR_COIN_BAHAR": 80_000.0,
    "IR_COIN_HALF": 50_000.0,
    "IR_COIN_QUARTER": 35_000.0,
    "IR_COIN_1G": 15_000.0,
    "IR_COIN_GERAMI": 15_000.0,
}
