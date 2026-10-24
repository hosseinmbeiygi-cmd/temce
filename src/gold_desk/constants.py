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
# Single source of truth: services.gold.constants.COIN_MINTING_COSTS.
# IR_COIN_EMAMI = 80,000 IRR — same full-coin weight (8.133 g) and same
# physical mint cost as IR_COIN_BAHAR. (STEP 6-FIX-2: previously this file
# said 80,000 while services/gold/constants.py said 0.0; unified on 80,000
# because the two full coins share weight/purity and the services 0.0 value
# had no documented source. Reason documented here per gate requirement.)
from services.gold.constants import COIN_MINTING_COSTS as _CANONICAL_MINTING_COSTS
from services.gold.constants import COIN_SPECS as _CANONICAL_COIN_SPECS  # noqa: F401  (re-export parity)

MINTING_COST_TOMAN: float = 50_000.0  # میانگین (fallback)
COIN_MINTING_COSTS: dict[str, float] = dict(_CANONICAL_MINTING_COSTS)

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

# ── P/NAV policy (نسخهٔ واحد برای سیگنال خرید/فروش) ────────────────
# پیش‌تر سه مجموعهٔ آستانهٔ متناقض وجود داشت: constants (۰.۵/۱.۵/۳.۰)، antigravity
# (فروش > +۲٪، خرید < −۱٪) و fund_scoring (حباب > +۳٪ / < −۲٪). اکنون همهٔ ماژول‌ها
# سیگنال‌دهی را از این policy واحد می‌گیرند (GS-14).
NAV_PREMIUM_POLICY_VERSION: str = "nav-premium-v1"
NAV_PREMIUM_BUY_BELOW: float = -2.0  # حباب < −۲٪ → کاندید خرید
NAV_PREMIUM_SELL_ABOVE: float = 3.0  # حباب > +۳٪ → کاندید فروش/اجتناب

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

# ── پنجره‌های اندیکاتور (تکنیکال بک‌تست/الگو) ────────────────────────
# «حباب تکنیکال» = درصد فاصلهٔ قیمت از میانگین متحرک سادهٔ trailing همین تعداد
# روز معاملاتی. تنها تعریف واحد این کمیت در indicators.bubble_pct است؛ پیش‌تر
# سه پیاده‌سازی (convolve در backtest، backfill در pattern_detector و حلقهٔ
# backtest_runner) با نتایج متفاوت وجود داشت.
SMA_BUBBLE_WINDOW: int = 30

# ── حداقل پوشش داده برای تصمیم امتیاز ─────────────────────────────
# امتیاز روی وزنِ کامپوننت‌های *موجود* نرمال می‌شود؛ بدون سقف پوشش، یک جزء
# تنها (مثلاً bubble=20) هم می‌تواند به ۱۰۰/GREEN برسد. آستانه ۶۰ از ۱۰۰ یعنی
# دست‌کم معادل سه جزء از شش جزء باید داده داشته باشد، وگرنه تصمیم NO_DATA است
# ولی خودِ عدد امتیاز برای نمودار حفظ می‌شود (E-C5).
MIN_SCORE_COVERAGE_WEIGHT: int = 60

# ── Hard Stop thresholds (شرایط بحران) ──────────────────────────
HARDSTOP_TSE_CRASH_PCT: float = -5.0  # سقوط شاخص کل > 5%
HARDSTOP_DXY_SPIKE_PCT: float = 3.0  # جهش دلار جهانی > 3%
HARDSTOP_USD_SPIKE_PCT: float = 5.0  # جهش دلار تهران > 5% روزانه

# ── Symbol registry (canonical → BrsApi) ─────────────────────────
# منابع قیمت BrsApi این نمادها را برمی‌گردانند:
#   gold_coin_prices: IR_COIN_1G | IR_COIN_BAHAR | IR_COIN_EMAMI |
#                     IR_COIN_HALF | IR_COIN_QUARTER | IR_GOLD_18K |
#                     IR_GOLD_24K | IR_GOLD_MELTED | XAUUSD
# پیش‌تر IR_GOLD_1G و IR_COIN_GERAMI در رجیستری بودند ولی در هیچ منبعی وجود
# نداشتند و ۲ بلوک از ۹ بلوک snapshot همیشه خالی می‌ماند؛ در عوض IR_COIN_1G
# (که در منبع موجود است) ثبت نشده بود (GS-20).
GOLD_SYMBOLS: dict[str, str] = {
    "gold_18k": "IR_GOLD_18K",
    "gold_24k": "IR_GOLD_24K",
    "gold_melted": "IR_GOLD_MELTED",
}
COIN_SYMBOLS: dict[str, str] = {
    "coin_emami": "IR_COIN_EMAMI",
    "coin_bahar": "IR_COIN_BAHAR",
    "coin_half": "IR_COIN_HALF",
    "coin_quarter": "IR_COIN_QUARTER",
    "coin_1g": "IR_COIN_1G",
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

# ── Live signals (مقایسهٔ snapshot قبلی/فعلی) ─────────────────────
# فاصلهٔ تولید snapshot (ثانیه) — مرجع TTL مقایسه و «کهنگی» prev.
LIVE_SNAPSHOT_INTERVAL_SEC: int = 300
# TTL snapshot قبلی: دو برابر بازهٔ تولید، تا مقایسه هرگز با دادهٔ دیروز انجام نشود.
LIVE_PREV_SNAPSHOT_TTL_SEC: int = 2 * LIVE_SNAPSHOT_INTERVAL_SEC
# فاصلهٔ تکرار همان سیگنال (ثانیه).
LIVE_SIGNAL_COOLDOWN_SEC: int = 600
# آستانه‌های درصدی تغییر (٪) در یک بازهٔ snapshot.
LIVE_PRICE_SPIKE_PCT: float = 1.5  # تغییر قیمت طلا/سکه
LIVE_PRICE_SPIKE_CRITICAL_PCT: float = 3.0  # مرز severity=critical
LIVE_USD_SPIKE_PCT: float = 2.0  # دلار تهران
LIVE_AED_SPIKE_PCT: float = 3.0  # درهم
LIVE_BUBBLE_EXTREME_PCT: float = 25.0  # قدرمطلق حباب (٪)
# تغییر امتیاز کل (نقطه از ۱۰۰) که سیگنال می‌سازد.
LIVE_SCORE_DELTA: int = 10

# ── Redis keys ────────────────────────────────────────────────────
REDIS_KEY_SNAPSHOT: str = "golddesk:snapshot:latest"
REDIS_KEY_BUBBLE_TS: str = "golddesk:bubble:ts:{symbol}"  # سری زمانی
REDIS_KEY_ALERT_LOCK: str = "golddesk:alert:lock:{rule_id}"  # cooldown
REDIS_KEY_WATCHLIST: str = "golddesk:watchlist"

# ── Portfolio targets (ری‌بالانس) ─────────────────────────────────
# وزن هدف بر اساس «کلاس ابزار» (نه نماد) تا با هر ترکیب holding کار کند.
# مجموع باید ۱۰۰ باشد؛ تغییر این dict تنها محل تغییر سیاست ری‌بالانس است.
PORTFOLIO_TARGET_WEIGHTS: dict[str, float] = {
    "etf": 40.0,  # صندوق طلا / گواهی
    "melted": 40.0,  # طلای آب‌شده / فیزیکی ۱۸-۲۴ عیار
    "coin": 20.0,  # سکه
}
assert abs(sum(PORTFOLIO_TARGET_WEIGHTS.values()) - 100.0) < 1e-9, "target weights must sum to 100"

# انحراف مجاز هر کلاس از وزن هدف (واحد درصد) — آستانهٔ پیش‌فرض هشدار.
PORTFOLIO_DRIFT_TOLERANCE_PCT: float = 10.0
# آستانهٔ تمرکز: بیشترین وزن یک دارایی که بالاتر از آن پرتفوی «متمرکز» است.
PORTFOLIO_CONCENTRATION_WARN_PCT: float = 60.0
# آستانهٔ افت سرمایه که هشدار می‌دهد.
PORTFOLIO_DRAWDOWN_WARN_PCT: float = 15.0
# بازهٔ پیش‌فرض پنجرهٔ کارایی (روز) برای TWR/نوسان/افت.
PORTFOLIO_PERFORMANCE_WINDOW_DAYS: int = 90
# نگاشت صریح نماد → کلاس (override تشخیص خودکار در portfolio_history).
PORTFOLIO_SYMBOL_VEHICLE_OVERRIDES: dict[str, str] = {}

# ── Benchmarks (مقایسهٔ بازده پرتفوی) ─────────────────────────────
# هر بنچمارک یک سری روزانه از یک جدول واقعی است؛ در نبود داده، مقدار None
# برمی‌گردد (هرگز عدد جعلی ساخته نمی‌شود).
PORTFOLIO_BENCHMARKS: dict[str, dict[str, str]] = {
    "gold": {
        "label": "طلای آب‌شده (بازار ایران)",
        "kind": "gold_coin_history",
        "symbol": "IR_GOLD_MELTED",
    },
    "usd": {
        "label": "دلار آمریکا (تهران)",
        "kind": "gcph_daily",
        "symbol": "USD",
    },
    "tedpix": {
        "label": "شاخص کل بورس تهران",
        "kind": "index_values",
        "name": "شاخص کل",
    },
}

# ── Data freshness (صفحهٔ سلامت داده) ────────────────────────────
# حداکثر سن مجاز پیش‌فرض برای منابعی که آستانهٔ اختصاصی ندارند.
FRESHNESS_DEFAULT_MAX_AGE_MIN: int = 120

# ── Validation bounds (self-check) ────────────────────────────────
VALID_XAU_RANGE: tuple[float, float] = (1000.0, 10000.0)
VALID_USD_RANGE: tuple[float, float] = (10_000.0, 10_000_000.0)
VALID_BUBBLE_PCT_RANGE: tuple[float, float] = (-50.0, 100.0)
VALID_PARITY_GAP_RANGE: tuple[float, float] = (-10.0, 10.0)
