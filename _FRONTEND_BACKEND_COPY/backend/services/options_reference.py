"""Options Knowledge Base - complete reference from the book (all appendices, glossary, examples)."""

from __future__ import annotations

from typing import Any

# ── ضمیمه ۱: راهنمای انتخاب استراتژی ─────────────────────────────────────────

STRATEGY_SELECTION_GUIDE: list[dict[str, Any]] = [
    {
        "question": "پیش‌بینی شما از بازار چیست؟",
        "answers": [
            {"condition": "صعودی قوی", "strategies": ["long_call", "bull_call_spread", "strap"], "risk": "high"},
            {"condition": "صعودی ملایم", "strategies": ["covered_call", "bull_put_spread"], "risk": "medium"},
            {"condition": "نزولی قوی", "strategies": ["long_put", "bear_put_spread", "strip"], "risk": "high"},
            {"condition": "نزولی ملایم", "strategies": ["bear_call_spread"], "risk": "medium"},
            {
                "condition": "خنثی (رنج)",
                "strategies": ["short_straddle", "iron_condor", "butterfly", "covered_call"],
                "risk": "medium",
            },
            {
                "condition": "پرنوسان (جهت نامشخص)",
                "strategies": ["long_straddle", "long_strangle", "reverse_iron_butterfly"],
                "risk": "high",
            },
        ],
    },
    {
        "question": "میزان تحمل ریسک شما چقدر است؟",
        "answers": [
            {
                "condition": "ریسک‌پذیر",
                "strategies": ["short_straddle", "short_strangle", "ratio_spread"],
                "description": "سود و زیان نامحدود",
            },
            {
                "condition": "ریسک‌پذیر متوسط",
                "strategies": ["long_call", "long_put", "straddle"],
                "description": "سود نامحدود و زیان محدود",
            },
            {
                "condition": "ریسک‌گریز",
                "strategies": ["bull_call_spread", "bear_put_spread", "butterfly", "iron_condor"],
                "description": "سود و زیان محدود",
            },
        ],
    },
    {
        "question": "افق زمانی شما چقدر است؟",
        "answers": [
            {
                "condition": "کوتاه‌مدت (چند روز تا چند هفته)",
                "strategies": ["straddle", "strangle", "short_straddle"],
                "description": "استراتژی‌های نوسانی و فروش پریمیوم",
            },
            {
                "condition": "میان‌مدت (چند هفته تا چند ماه)",
                "strategies": ["spread", "covered_call", "collar"],
                "description": "اسپردها و پوشش ریسک",
            },
            {
                "condition": "بلندمدت (بیش از ۶ ماه)",
                "strategies": ["married_put", "long_call", "long_put"],
                "description": "خرید اختیار با سررسید بلند",
            },
        ],
    },
]


# ── ضمیمه ۲: ۱۰ اشتباه رایج معامله‌گران ایرانی ──────────────────────────────

COMMON_MISTAKES: list[dict[str, str]] = [
    {
        "mistake": "خرید صرف Call یا Put بدون استراتژی",
        "solution": "همیشه حداقل یک استراتژی ترکیبی ساده (مانند Covered Call یا Spread) داشته باشید",
    },
    {
        "mistake": "بی‌توجهی به نقدشوندگی (حجم معاملات)",
        "solution": "فقط نمادهای با حجم بالای معاملات را انتخاب کنید",
    },
    {
        "mistake": "نادیده گرفتن تاثیر زمان (Theta)",
        "solution": "از قراردادهای با سررسید حداقل ۲ ماهه برای خرید استفاده کنید",
    },
    {
        "mistake": "انتخاب قیمت اعمال نامناسب",
        "solution": "قیمت اعمال را بر اساس تحلیل تکنیکال و فاصله از قیمت فعلی انتخاب کنید",
    },
    {
        "mistake": "معامله بدون حد ضرر",
        "solution": "برای هر موقعیت، حد ضرر مشخصی تعیین کنید",
    },
    {
        "mistake": "استفاده از کل سرمایه در یک استراتژی",
        "solution": "حداکثر ۲۰٪ سرمایه را در هر موقعیت به کار بگیرید",
    },
    {
        "mistake": "اجرای استراتژی Short بدون پشتوانه",
        "solution": "در بازار ایران، موقعیت Short فقط با پشتوانه دارایی پایه انجام شود",
    },
    {
        "mistake": "معامله بر اساس هیجان و اخبار لحظه‌ای",
        "solution": "قبل از هر معامله، تحلیل بنیادی و تکنیکال انجام دهید",
    },
    {
        "mistake": "عدم مدیریت موقعیت پس از ورود",
        "solution": "موقعیت خود را روزانه بررسی کرده و در صورت لزوم تعدیل کنید",
    },
    {
        "mistake": "نادیده گرفتن کارمزدها و مالیات",
        "solution": "کارمزد خرید ۰.۱۲۵٪ و فروش ۰.۶۲۵٪ (شامل مالیات) را در محاسبه لحاظ کنید",
    },
]


# ── ضمیمه ۳: اصطلاحات کلیدی بازار آپشن (فارسی-انگلیسی) ───────────────────────

GLOSSARY: list[dict[str, str]] = [
    {"fa": "اختیار خرید", "en": "Call Option", "desc": "حق خرید دارایی پایه"},
    {"fa": "اختیار فروش", "en": "Put Option", "desc": "حق فروش دارایی پایه"},
    {"fa": "قیمت اعمال", "en": "Strike Price", "desc": "قیمت توافقی قرارداد"},
    {"fa": "پریمیوم", "en": "Premium", "desc": "قیمت قرارداد اختیار معامله"},
    {"fa": "تاریخ سررسید", "en": "Expiration Date", "desc": "آخرین روز اعتبار قرارداد"},
    {"fa": "در سود", "en": "In The Money (ITM)", "desc": "قیمت دارایی بهتر از قیمت اعمال"},
    {"fa": "در نقطه سر به سر", "en": "At The Money (ATM)", "desc": "قیمت دارایی تقریباً برابر با قیمت اعمال"},
    {"fa": "در زیان", "en": "Out of The Money (OTM)", "desc": "قیمت دارایی بدتر از قیمت اعمال"},
    {"fa": "حساسیت نسبت به قیمت", "en": "Delta", "desc": "تغییر قیمت اختیار به ازای تغییر ۱ واحدی دارایی پایه"},
    {"fa": "نرخ تغییر دلتا", "en": "Gamma", "desc": "نرخ تغییر دلتا نسبت به قیمت"},
    {"fa": "حساسیت نسبت به زمان", "en": "Theta", "desc": "کاهش قیمت اختیار با گذشت زمان"},
    {"fa": "حساسیت نسبت به نوسان", "en": "Vega", "desc": "تغییر قیمت اختیار به ازای تغییر نوسان"},
    {"fa": "حساسیت نسبت به نرخ بهره", "en": "Rho", "desc": "تغییر قیمت اختیار به ازای تغییر نرخ بهره"},
    {"fa": "پوشش ریسک", "en": "Hedging", "desc": "استفاده از اختیار برای کاهش ریسک"},
    {"fa": "آربیتراژ", "en": "Arbitrage", "desc": "کسب سود از اختلاف قیمت در بازارهای مختلف"},
    {"fa": "وجه تضمین", "en": "Margin", "desc": "مبلغ بلوکه شده برای پشتیبانی از موقعیت"},
    {"fa": "اندازه قرارداد", "en": "Contract Size", "desc": "تعداد سهم پایه در هر قرارداد (۱۰۰۰ در ایران)"},
    {"fa": "نوسان‌پذیری ضمنی", "en": "Implied Volatility (IV)", "desc": "نوسان‌پذیری استخراج شده از قیمت بازار اختیار"},
    {"fa": "نوسان‌پذیری تاریخی", "en": "Historical Volatility (HV)", "desc": "نوسان‌پذیری گذشته دارایی پایه"},
    {"fa": "ارزش ذاتی", "en": "Intrinsic Value", "desc": "ارزش فوری اعمال اختیار"},
    {"fa": "ارزش زمانی", "en": "Time Value", "desc": "پریمیوم منهای ارزش ذاتی"},
    {"fa": "مدل بلک-شولز", "en": "Black-Scholes Model", "desc": "مدل ارزش‌گذاری رایج اختیار معامله"},
    {"fa": "نوسان‌پذیری ضمنی", "en": "Implied Volatility Smile", "desc": "الگوی نوسان ضمنی در قیمت‌های مختلف اعمال"},
    {"fa": "قرارداد آتی", "en": "Futures Contract", "desc": "قرارداد خرید/فروش دارایی در آینده"},
    {"fa": "فروش فزاینده", "en": "Short Selling", "desc": "فروش دارایی که مالک آن نیستید (ممنوع در ایران)"},
]


# ── ضمیمه ۴: منابع و مراجع ───────────────────────────────────────────────────

REFERENCES: dict[str, list[str]] = {
    "کتاب‌های جهانی": [
        "Options, Futures, and Other Derivatives – John C. Hull",
        "Option Volatility and Pricing – Sheldon Natenberg",
        "Trading Options Greeks – Dan Passarelli",
        "The Option Trader's Hedge Fund – Dennis A. Chen & Mark Sebastian",
    ],
    "وب‌سایت‌ها": [
        "Investopedia.com",
        "OptionsIndustryCouncil.com",
        "CBOE.com",
        "TradingView.com",
    ],
    "منابع داخلی": [
        "سایت رسمی سازمان بورس و اوراق بهادار",
        "سامانه معاملاتی امکس کارگزاری پارسیان",
    ],
}


# ── مثال‌های واقعی از بازار ایران ──────────────────────────────────────────────

IRANIAN_EXAMPLES: list[dict[str, Any]] = [
    {
        "strategy": "covered_call",
        "symbol": "ذوب",
        "date": "اسفند ۱۴۰۳",
        "stock_price": 444,
        "strike": 400,
        "premium": 84,
        "expiry": "اردیبهشت ۱۴۰۴",
        "result": "بازدهی ۱۱٪ در دو ماه",
        "annualized": "حدود ۹۰٪ سالانه با سود مرکب",
    },
    {
        "strategy": "married_put",
        "symbol": "صندوق سلام فارابی",
        "date": "اسفند ۱۴۰۳",
        "stock_price": 810,
        "put_strike": 760,
        "put_premium": 40,
        "expiry": "یک‌ماهه",
        "result": "با ۴۰ تومان بیمه، از ۷۰ تومان زیان حفظ شد",
        "detail": "سهم تا ۷۴۰ افت کرد، Put تا ۲۵ سود داد",
    },
    {
        "strategy": "long_straddle",
        "symbol": "شپدیس",
        "date": "تاریخی",
        "stock_price": 10000,
        "strike": 10000,
        "result": "شایعات افزایش قیمت خوراک پتروشیمی",
        "detail": "خرید ATM Call + Put قبل از اخبار مهم",
    },
    {
        "strategy": "long_strangle",
        "symbol": "فارس",
        "date": "تابستان ۱۳۹۹",
        "stock_price": 3000,
        "call_strike": 5000,
        "put_strike": 2000,
        "result": "ریزش تا ۱۲۰۰ تومان - سود نامحدود از Put",
        "detail": "انتخابات آمریکا + ریزش بورس",
    },
    {
        "strategy": "arbitrage",
        "symbol": "خودرو",
        "date": "۲۳ مهر ۱۴۰۲",
        "option_strike": 150,
        "option_premium": 10,
        "stock_price": 170,
        "result": "خرید اختیار ۱۵۰ با پریمیوم ۱۰ = سهم ۱۶۰ در حالی که بازار ۱۷۰",
        "profit": "بیش از ۶٪ سود در یک روز",
    },
    {
        "strategy": "bull_call_spread",
        "symbol": "فملی",
        "date": "تاریخی",
        "stock_price": 400,
        "lower_strike": 250,
        "upper_strike": 400,
        "lower_premium": 20,
        "upper_premium": 50,
        "result": "پیش‌بینی صعود تا ۶۰۰ تومان",
        "detail": "Risk/reward بهتر از خرید صرف Call",
    },
    {
        "strategy": "bear_call_spread",
        "symbol": "نماد فرضی",
        "date": "تاریخی",
        "stock_price": 250,
        "lower_strike": 260,
        "upper_strike": 270,
        "lower_premium": 15,
        "upper_premium": 5,
        "result": "سود ۱۰ تومان اگر قیمت زیر ۲۶۰ بماند",
    },
    {
        "strategy": "long_call_butterfly",
        "symbol": "نماد فرضی",
        "date": "تاریخی",
        "stock_price": 140,
        "low_strike": 130,
        "mid_strike": 140,
        "high_strike": 150,
        "low_premium": 15,
        "mid_premium": 10,
        "high_premium": 5,
        "result": "حداکثر سود ۱۰ تومان اگر قیمت روی ۱۴۰ بماند",
    },
    {
        "strategy": "short_strangle",
        "symbol": "نماد فرضی",
        "date": "تاریخی",
        "stock_price": 2200,
        "call_strike": 2400,
        "put_strike": 2000,
        "total_premium": 120,
        "result": "سود ۱۲۰ تومان اگر قیمت بین ۲۰۰۰ تا ۲۴۰۰ بماند",
    },
    {
        "strategy": "long_call_condor",
        "symbol": "نماد فرضی",
        "date": "تاریخی",
        "stock_price": 1000,
        "strikes": [900, 950, 1000, 1050],
        "premiums": [100, 70, 60, 30],
        "net_cost": 40,
        "result": "حداکثر سود ۱۰ تومان اگر قیمت بین ۹۵۰ تا ۱۰۰۰ بماند",
    },
]


# ── سرفصل‌های دوره آموزشی ──────────────────────────────────────────────────────

COURSE_SYLLABUS: list[dict[str, Any]] = [
    {
        "section": 1,
        "title": "مقدمه و مفاهیم پایه",
        "topics": [
            "معرفی بازار مشتقه و انواع ابزارها",
            "تفاوت بازار نقد، آتی و اختیار",
            "ساختار بازار مشتقه در ایران",
            "نقش ابزارها در پوشش ریسک و آربیتراژ",
        ],
    },
    {
        "section": 2,
        "title": "قراردادهای اختیار معامله",
        "topics": [
            "تعریف اختیار خرید و فروش",
            "مفاهیم قیمت اعمال، پرمیوم، سررسید",
            "وضعیت‌های ITM، ATM، OTM",
            "محاسبه سود و زیان",
            "حساسیت‌ها (Delta, Gamma, Theta, Vega, Rho)",
            "مدل ارزش‌گذاری بلک-شولز",
        ],
    },
    {
        "section": 3,
        "title": "استراتژی‌های ترکیبی",
        "topics": [
            "Covered Call و Collar",
            "اسپردها (Vertical, Horizontal, Diagonal)",
            "استرادل و استرانگل",
            "باترفلای و کندور",
            "ترکیب آتی و اختیار",
            "تحلیل نمودار سود و زیان",
        ],
    },
    {
        "section": 4,
        "title": "قراردادهای آتی",
        "topics": [
            "تعریف و ویژگی‌ها",
            "وجه تضمین و مارجین کال",
            "تسویه روزانه",
            "مثال‌های کاربردی (آتی زعفران، طلا، سهام)",
        ],
    },
    {
        "section": 5,
        "title": "تحلیل عملی و پلتفرم‌های معاملاتی",
        "topics": [
            "معرفی سامانه‌های بازار مشتقه",
            "مشاهده دفتر سفارشات",
            "نحوه ثبت سفارش",
            "شبیه‌سازی معاملات",
        ],
    },
    {
        "section": 6,
        "title": "مدیریت ریسک و روانشناسی",
        "topics": [
            "اصول مدیریت سرمایه",
            "حد ضرر و اندازه موقعیت",
            "ریسک مارجین کال",
            "اشتباهات رایج",
            "روانشناسی معاملات اهرمی",
        ],
    },
    {
        "section": 7,
        "title": "پروژه نهایی",
        "topics": [
            "طراحی استراتژی روی داده واقعی",
            "اجرای آزمایشی و ارزیابی",
            "ارائه و تحلیل نتایج",
        ],
    },
]


# ── قوانین بازار ایران ─────────────────────────────────────────────────────────

IRAN_MARKET_RULES: dict[str, Any] = {
    "lot_size": 1000,
    "commissions": {
        "buy": "۰.۱۲۵٪",
        "sell": "۰.۶۲۵٪ (شامل ۰.۵٪ مالیات فروش + کارگزاری)",
    },
    "short_selling": "فروش فزاینده روی دارایی پایه مجاز نیست (فقط با پشتوانه سهام)",
    "settlement": "T+2 (تسویه دو روز کاری)",
    "price_limits": "±۵٪ (سهام) / ±۱۰٪ (صندوق‌ها)",
    "option_style": "اروپایی (فقط در تاریخ سررسید قابل اعمال)",
    "min_capital_recommendation": "حداقل ۵۰ میلیون تومان",
    "max_position_recommendation": "حداکثر ۲۰٪ سرمایه در هر موقعیت",
    "active_brokerages": [
        "کارگزاری پارسیان (سامانه امکس)",
        "کارگزاری مفید",
        "کارگزاری آگاه",
        "کارگزاری گنجینه",
    ],
}


# ── آمار بازار آپشن ایران ──────────────────────────────────────────────────────

IRAN_OPTIONS_STATS: dict[str, Any] = {
    "year_1403_growth": "۳.۲ برابر نسبت به سال قبل",
    "new_trader_failure_rate": "بیش از ۷۵٪ فقط خریدار ساده Call/Put هستند",
    "top_3_strategies": ["covered_call", "married_put", "collar"],
    "best_monthly_target": "۴٪ سود ماهانه مرکب = ۶۰.۱٪ سالانه",
    "key_insight": "ترکیب نوسان‌گیری و پوشش ریسک بهترین نتیجه را می‌دهد",
}


# ── فرمول‌های کلیدی ────────────────────────────────────────────────────────────

KEY_FORMULAS: dict[str, str] = {
    "black_scholes_call": "C = S·N(d1) - K·e^(-rT)·N(d2)",
    "black_scholes_put": "P = K·e^(-rT)·N(-d2) - S·N(-d1)",
    "d1": "d1 = [ln(S/K) + (r + σ²/2)·T] / (σ·√T)",
    "d2": "d2 = d1 - σ·√T",
    "delta_call": "Δ_call = N(d1)",
    "delta_put": "Δ_put = N(d1) - 1",
    "gamma": "Γ = N'(d1) / (S·σ·√T)",
    "theta_call": "Θ_call = [-S·N'(d1)·σ/(2√T) - rKe^(-rT)·N(d2)] / 365",
    "vega": "V = S·N'(d1)·√T / 100",
    "implied_vol": "σ_new = σ_old - [BS(σ_old) - MarketPrice] / Vega",
    "covered_call_max_profit": "(Strike - StockPrice) + Premium",
    "covered_call_max_loss": "-StockPrice + Premium",
    "bull_spread_max_profit": "(UpperStrike - LowerStrike) - NetCost",
    "bull_spread_max_loss": "-NetCost",
    "straddle_max_loss": "-(CallPremium + PutPremium)",
    "straddle_break_even": "Strike ± (CallPremium + PutPremium)",
    "compound_return": "(1 + monthly_rate)^12 - 1",
}
