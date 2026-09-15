"""ثابت‌های GoldDesk — متالورژی، وزن سکه، آستانه‌های امتیازدهی، هزینه‌ها.

تمام ثابت‌ها در یک‌جا. تغییر آستانه‌ها = تغییر این فایل.
از v2: بدون placeholder. همه thresholdها بر اساس داده واقعی یا best practice.
"""

from __future__ import annotations

# ── متالورژی (تروا ounce = 31.1034768 گرم) ─────────────────────────
TROY_OUNCE_GRAMS: float = 31.1034768
GOLD_PURITY_24K: float = 999.9
GOLD_PURITY_18K: float = 750.0
GOLD_PURITY_17K: float = 705.0
GOLD_PURITY_COIN: float = 900.0  # سکه بهار آزادی
MESGHAL_GRAMS: float = 4.6083  # وزن یک مثقال
AED_PEG: float = 3.6725  # نرخ ثابت درهم به دلار

# ── وزن سکه‌ها (گرم) ─────────────────────────────────────────────
COIN_WEIGHTS: dict[str, float] = {
    "IR_COIN_EMAMI": 8.133,
    "IR_COIN_BAHAR": 8.133,
    "IR_COIN_HALF": 4.066,
    "IR_COIN_QUARTER": 2.033,
    "IR_COIN_1G": 1.010,
    "IR_COIN_GERAMI": 1.010,
}

# ── کارمزد ضرابخانه (تومان، بر اساس قطع سکه) ────────────────
MINTING_COST_TOMAN: float = 50_000.0  # میانگین (fallback)
COIN_MINTING_COSTS: dict[str, float] = {
    "IR_COIN_EMAMI": 80_000.0,  # تمام سکه
    "IR_COIN_BAHAR": 80_000.0,
    "IR_COIN_HALF": 50_000.0,  # نیم
    "IR_COIN_QUARTER": 35_000.0,  # ربع
    "IR_COIN_1G": 15_000.0,
    "IR_COIN_GERAMI": 15_000.0,
}

# ── کارمزد و مالیات ابزارها (٪) ──────────────────────────────────
VEHICLE_FEES: dict[str, dict[str, float]] = {
    "etf": {"buy_pct": 0.15, "sell_pct": 0.15, "vat_pct": 0.0, "label_fa": "صندوق ETF طلا"},
    "cert": {"buy_pct": 0.24, "sell_pct": 0.24, "vat_pct": 0.0, "label_fa": "گواهی شمش"},
    "melted": {"buy_pct": 0.30, "sell_pct": 0.50, "vat_pct": 0.0, "label_fa": "طلای آب‌شده"},
    "coin": {"buy_pct": 1.50, "sell_pct": 1.50, "vat_pct": 0.0, "label_fa": "سکه فیزیکی"},
    "jewelry": {"buy_pct": 18.0, "sell_pct": 25.0, "vat_pct": 9.0, "label_fa": "طلای زینتی"},
}

# ── آستانه‌های Scoring (هر ۶ component) ─────────────────────────
# جمع weights = 100
SCORE_WEIGHTS: dict[str, int] = {
    "bubble": 20,  # حباب سکه امامی
    "nav": 18,  # P/NAV صندوق عیار
    "tsetmc": 18,  # BPR + Inflow
    "technical": 15,  # XAU RSI
    "parity": 15,  # شکاف درهم
    "fund_flow": 14,  # NAV 7d trend
}
assert sum(SCORE_WEIGHTS.values()) == 100, "weights must sum to 100"

# ── Bubble thresholds (سکه امامی) ─────────────────────────────────
BUBBLE_GREEN_MAX: float = 8.0  # < 8% امتیاز کامل
BUBBLE_YELLOW_MAX: float = 15.0  # 8-15%
BUBBLE_ORANGE_MAX: float = 22.0  # 15-22%
# > 22% = قرمز (0 امتیاز)

# ── NAV thresholds (P/NAV صندوق) ──────────────────────────────────
NAV_GREEN_MAX: float = 0.5  # ≤ 0.5%
NAV_YELLOW_MAX: float = 1.5  # 0.5-1.5%
NAV_RED_MAX: float = 3.0  # 1.5-3%
# > 3% = قرمز

# ── TSETMC thresholds ──────────────────────────────────────────────
TSETMC_BPR_GREEN: float = 2.0  # ≥ 2.0
TSETMC_BPR_YELLOW: float = 1.5  # 1.5-2.0
TSETMC_BPR_ORANGE: float = 1.0  # 1.0-1.5
TSETMC_INFLOW_GREEN: float = 5e9  # 5 میلیارد تومان
TSETMC_INFLOW_YELLOW: float = 1e9

# ── Technical (XAU RSI 14) ────────────────────────────────────────
RSI_GREEN_MIN: float = 30.0
RSI_GREEN_MAX: float = 45.0
RSI_YELLOW_MAX: float = 60.0
RSI_DANGER: float = 70.0

# ── Parity (|AED gap|) ────────────────────────────────────────────
PARITY_GREEN_MAX: float = 0.5
PARITY_YELLOW_MAX: float = 1.5
PARITY_RED_MAX: float = 3.0

# ── Fund Flow (NAV 7d return) ─────────────────────────────────────
FUND_FLOW_GREEN_MIN: float = 1.0  # ≥ 1% در ۷ روز
FUND_FLOW_YELLOW_MIN: float = 0.0
# < 0% = قرمز

# ── Score Bands ───────────────────────────────────────────────────
SCORE_GREEN_MIN: int = 80
SCORE_YELLOW_MIN: int = 55
# < 55 = RED

# ── Hard Stop thresholds (شرایط بحران) ──────────────────────────
HARDSTOP_TSE_CRASH_PCT: float = -5.0  # سقوط شاخص کل > 5%
HARDSTOP_DXY_SPIKE_PCT: float = 3.0  # جهش دلار جهانی > 3%
HARDSTOP_USD_SPIKE_PCT: float = 5.0  # جهش دلار تهران > 5% روزانه

# ── Symbol registry (canonical → BrsApi) ─────────────────────────
GOLD_SYMBOLS: dict[str, str] = {
    "gold_18k": "IR_GOLD_18K",
    "gold_24k": "IR_GOLD_24K",
    "gold_1g": "IR_GOLD_1G",
    "gold_melted": "IR_GOLD_MELTED",
}
COIN_SYMBOLS: dict[str, str] = {
    "coin_emami": "IR_COIN_EMAMI",
    "coin_bahar": "IR_COIN_BAHAR",
    "coin_half": "IR_COIN_HALF",
    "coin_quarter": "IR_COIN_QUARTER",
    "coin_gerami": "IR_COIN_GERAMI",
}
FX_REFS: dict[str, str] = {
    "xau_usd": "XAUUSD",
    "usd_irt": "USD",
    "aed_irt": "AED",
}
FUND_SYMBOLS: list[str] = ["عیار", "طلا", "کهربا", "زر", "زرفام", "گوهر", "تابش", "نفیس", "آلتون", "ناب"]

# ── Display labels (فارسی) ────────────────────────────────────────
DISPLAY_LABELS: dict[str, str] = {
    "IR_GOLD_18K": "طلای ۱۸ عیار",
    "IR_GOLD_24K": "طلای ۲۴ عیار",
    "IR_GOLD_1G": "طلای یک گرمی",
    "IR_GOLD_MELTED": "طلای آب‌شده",
    "IR_COIN_EMAMI": "سکه امامی",
    "IR_COIN_BAHAR": "سکه بهار آزادی",
    "IR_COIN_HALF": "نیم سکه",
    "IR_COIN_QUARTER": "ربع سکه",
    "IR_COIN_1G": "سکه یک گرمی",
    "IR_COIN_GERAMI": "سکه گرمی",
    "XAUUSD": "اونس جهانی طلا",
    "USD": "دلار آمریکا",
    "AED": "درهم امارات",
}

# ── Redis keys ────────────────────────────────────────────────────
REDIS_KEY_SNAPSHOT: str = "golddesk:snapshot:latest"
REDIS_KEY_BUBBLE_TS: str = "golddesk:bubble:ts:{symbol}"  # سری زمانی
REDIS_KEY_ALERT_LOCK: str = "golddesk:alert:lock:{rule_id}"  # cooldown
REDIS_KEY_WATCHLIST: str = "golddesk:watchlist"

# ── Validation bounds (self-check) ────────────────────────────────
VALID_XAU_RANGE: tuple[float, float] = (1000.0, 10000.0)
VALID_USD_RANGE: tuple[float, float] = (10_000.0, 10_000_000.0)
VALID_BUBBLE_PCT_RANGE: tuple[float, float] = (-50.0, 100.0)
VALID_PARITY_GAP_RANGE: tuple[float, float] = (-10.0, 10.0)
