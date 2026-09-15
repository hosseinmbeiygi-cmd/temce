"""ثوابت سراسری صندوق‌یار."""

# ── کد نوع صندوق (محور اول Peer Group) ──────────────────────────────
TYPE_EQUITY = "EQ"  # سهامی
TYPE_FIXED_INCOME = "FI"  # درآمد ثابت
TYPE_GOLD = "GO"  # طلا / کالایی
TYPE_MIXED = "MX"  # مختلط
TYPE_LEVERAGED = "LV"  # اهرمی
TYPE_REAL_ESTATE = "RE"  # زمین و ساختمان
TYPE_INDEX = "IDX"  # شاخصی
TYPE_FOF = "FOF"  # صندوق در صندوق
TYPE_SECTOR = "SEC"  # بخشی
TYPE_GUARANTEE = "GUA"  # تضمین اصل سرمایه
TYPE_VC = "VC"  # جسورانه
TYPE_PRIVATE = "PE"  # خصوصی

TYPE_CODES: tuple[str, ...] = (
    TYPE_EQUITY,
    TYPE_FIXED_INCOME,
    TYPE_GOLD,
    TYPE_MIXED,
    TYPE_LEVERAGED,
    TYPE_REAL_ESTATE,
    TYPE_INDEX,
    TYPE_FOF,
    TYPE_SECTOR,
    TYPE_GUARANTEE,
    TYPE_VC,
    TYPE_PRIVATE,
)

TYPE_LABELS_FA: dict[str, str] = {
    TYPE_EQUITY: "سهامی",
    TYPE_FIXED_INCOME: "درآمد ثابت",
    TYPE_GOLD: "طلا و کالایی",
    TYPE_MIXED: "مختلط",
    TYPE_LEVERAGED: "اهرمی",
    TYPE_REAL_ESTATE: "زمین و ساختمان",
    TYPE_INDEX: "شاخصی",
    TYPE_FOF: "صندوق در صندوق",
    TYPE_SECTOR: "بخشی",
    TYPE_GUARANTEE: "تضمین اصل سرمایه",
    TYPE_VC: "جسورانه",
    TYPE_PRIVATE: "خصوصی",
}

# ── باند AUM (محور دوم اختیاری) ────────────────────────────────────
AUM_BAND_SMALL = "S"  # < ۵۰۰ میلیارد تومان
AUM_BAND_MEDIUM = "M"  # ۵۰۰ میلیارد تا ۵ هزار میلیارد
AUM_BAND_LARGE = "L"  # > ۵ هزار میلیارد تومان

AUM_BAND_THRESHOLDS_BTOMAN: dict[str, tuple[float | None, float]] = {
    AUM_BAND_SMALL: (None, 500),
    AUM_BAND_MEDIUM: (500, 5000),
    AUM_BAND_LARGE: (5000, None),
}

# ── سطوح پیشنهاد (Scoring Output) ──────────────────────────────────
SIGNAL_STRONG_BUY = "strong_buy"
SIGNAL_BUY = "buy"
SIGNAL_HOLD = "hold"
SIGNAL_CAUTION = "caution"
SIGNAL_AVOID = "avoid"

SIGNAL_LABELS_FA: dict[str, str] = {
    SIGNAL_STRONG_BUY: "خرید قوی",
    SIGNAL_BUY: "خرید",
    SIGNAL_HOLD: "نگهداری",
    SIGNAL_CAUTION: "احتیاط",
    SIGNAL_AVOID: "اجتناب",
}

# ── آستانه‌های پیش‌فرض ─────────────────────────────────────────────
# (طبق spec — می‌توان از scoring_config_history override کرد)
DEFAULT_BUBBLE_AVOID_THRESHOLD = 3.0  # حباب > ۳٪ = اجتناب خرید
DEFAULT_BUBBLE_ENTRY_THRESHOLD = -2.0  # حباب < -۲٪ = کاندید ورود
DEFAULT_SPREAD_PENALTY_THRESHOLD = 1.0  # اسپرد > ۱٪ = جریمه نقدشوندگی

# ── Cold Start: حداقل سابقه لازم (روز کاری) ────────────────────────
MIN_HISTORY_DAYS: dict[str, int] = {
    "twr": 30,
    "behavior_gap": 120,
    "sharpe": 120,
    "sortino": 120,
    "calmar": 240,
    "max_drawdown": 60,
    "beta": 480,
    "active_share": 30,
    "style_drift": 120,
    "post_change_alpha": 120,
    "volatility_decay": 60,
    "suspension_risk": 60,
    "fx_beta": 240,
    "inflation_beta": 240,
}

# ── TTL پیشنهادی کش برای هر منبع (ثانیه) ──────────────────────────
CACHE_TTL_SECONDS: dict[str, int] = {
    "fipiran": 24 * 3600,
    "tsetmc": 15 * 60,
    "codal": 12 * 3600,
    "ime": 24 * 3600,
    "cbi_macro": 30 * 24 * 3600,
    "news": 3600,
    "world_prices": 24 * 3600,
}

# ── Stale threshold برای Stale Data Flag (ساعت) ────────────────────
STALE_THRESHOLD_HOURS: dict[str, int] = {
    "fipiran": 25,
    "tsetmc": 2,
    "codal": 36,
    "ime": 36,
    "cbi_macro": 24 * 35,
    "news": 6,
}

# ── Circuit Breaker ─────────────────────────────────────────────────
CB_FAILURE_THRESHOLD = 5  # خطای متوالی برای باز شدن
CB_WINDOW_SECONDS = 60  # پنجره شمارش خطا
CB_OPEN_DURATION_SECONDS = 5 * 60  # ۵ دقیقه Open state

# ── نسخه پیش‌فرض جدول وزن‌دهی ─────────────────────────────────────
DEFAULT_SCORING_VERSION = "v1.0"

# ── Disclaimer سه‌لایه ──────────────────────────────────────────────
DISCLAIMER_API = (
    "این تحلیل خودکار و صرفاً اطلاعاتی است، توصیه مالی رسمی محسوب نمی‌شود و مسئولیت تصمیم سرمایه‌گذاری بر عهده کاربر است."
)
DISCLAIMER_UI = (
    "این پیشنهاد بر پایه تحلیل داده‌های تاریخی است، توصیه مالی محسوب نمی‌شود و ریسک هر تصمیم سرمایه‌گذاری بر عهده شماست."
)
DISCLAIMER_PROFILE = (
    "این ابزار تحلیلی است، نه مشاور سرمایه‌گذاری مجاز. مشاوره رسمی "
    "سرمایه‌گذاری نیازمند مجوز سازمان بورس و اوراق بهادار است."
)

# ── Cold Start labels ───────────────────────────────────────────────
COLD_START_LABELS: dict[str, str] = {
    "insufficient_history": "داده ناکافی",
    "short_window": "دوره کوتاه",
    "new_manager": "مدیر جدید — در انتظار",
    "insufficient_peers": "هم‌گروه ناکافی",
    "new_fund": "صندوق جدید — امتیازدهی در انتظار",
}

COLD_START_BLOCK_THRESHOLD = 0.40  # > ۴۰٪ شاخص‌ها = بلوکه شدن امتیاز
