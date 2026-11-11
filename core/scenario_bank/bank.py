"""🏦 The scenario bank content — بانک سناریوی دستیار طلا و نقره (نسخهٔ ۱).

Content only: each entry is a realistic request, the data it may lean on, a model answer,
and the sentences that would make an answer wrong. Judgement lives in :mod:`.engine`.

Scope follows the consolidated spec: **only non-physical** gold/silver instruments. A
request for physical delivery, a profit guarantee, an all-in bet or another market is a
``refuse`` scenario, and its ``expected`` shows the polite refusal the assistant owes —
so the refusal itself is tested, not just the happy path.

Every ``Requirement.source`` names something that actually exists in this repository
(``GET /api/v1/gold/snapshot``, ``nav_checker``, ``freshness``, ``portfolio_history`` …) or
says plainly that no column holds it. The checker in :mod:`.engine` consumes the same keys,
so a scenario can never quietly rely on data the platform cannot produce.
"""

from __future__ import annotations

from core.scenario_bank.schema import Category, Requirement, Scenario

#: Handle → contract. Coordinates mirror the endpoints verified in this repo.
_R: dict[str, Requirement] = {
    r.key: r
    for r in (
        Requirement("snapshot.coin_emami_bubble", "حباب سکه امامی",
                    "GET /api/v1/gold/snapshot → coins.coin_emami.bubble_pct", "٪"),
        Requirement("snapshot.score_total", "امتیاز کلی بازار",
                    "GET /api/v1/gold/snapshot → score.total", "۰-۱۰۰"),
        Requirement("snapshot.xau_usd", "اونس جهانی",
                    "GET /api/v1/gold/snapshot → references.xau_usd", "دلار"),
        Requirement("snapshot.usd_irt", "دلار آزاد",
                    "GET /api/v1/gold/snapshot → references.usd_irt", "تومان"),
        Requirement("snapshot.aed_gap_pct", "شکاف درهم",
                    "GET /api/v1/gold/snapshot → references.aed_gap_pct", "٪"),
        Requirement("fund.premium_pct", "پریمیوم صندوق به NAV",
                    "src/gold_desk/nav_checker.py (P/NAV)", "٪"),
        Requirement("fund.nav", "NAV روز صندوق",
                    "GET /api/v1/gold/funds → nav", "ریال"),
        Requirement("fund.liquidity", "ارزش معاملات صندوق",
                    "funds.trade_value", "ریال"),
        Requirement("price.history_daily", "تاریخچهٔ روزانهٔ طلا/سکه",
                    "GET /api/v1/gold/history (جدول روزانه)", "تومان"),
        Requirement("freshness", "سن و وضعیت منابع داده",
                    "GET /api/v1/gold/freshness", ""),
        Requirement("portfolio.total_value", "ارزش فعلی پرتفوی",
                    "GET /api/v1/gold/portfolio → total_value", "تومان"),
        Requirement("portfolio.pnl_pct", "سود/زیان پرتفوی",
                    "GET /api/v1/gold/portfolio → total_pnl_pct", "٪"),
        Requirement("portfolio.weights", "وزن دارایی‌ها در سبد",
                    "GET /api/v1/gold/portfolio → positions[*].weight", "٪"),
        Requirement("portfolio.risk_cap", "سقف وزن/ریسک کاربر",
                    "ورودی کاربر (پروفایل ریسک، سند بخش ۵)", "٪"),
        Requirement("performance.twr", "بازده وزنی زمانی",
                    "gold_portfolio_values (TWR)", "٪"),
        Requirement("alerts.rules", "قواعد فعال هشدار",
                    "src/gold_desk/alert_engine.py → DEFAULT_RULES", ""),
        Requirement("learn.tax_fee", "کارمزد و مالیات ابزار",
                    "نرخ مالیات به‌صورت دادهٔ بازار ذخیره نمی‌شود", ""),
    )
}


def _req(*keys: str) -> tuple[Requirement, ...]:
    return tuple(_R[k] for k in keys)


_SCENARIOS: tuple[Scenario, ...] = (
    # ══════════════ خرید ══════════════
    Scenario(
        code="PM-001", category="buy", mode="advise",
        question="الان صندوق طلا بخرم؟",
        instrument_types=("commodity_fund", "etf", "fund"),
        requires=_req("fund.premium_pct", "fund.nav", "snapshot.score_total", "freshness"),
        expected=(
            "جمع‌بندی: ورود پله‌ای، نه با کل سرمایه.\n"
            "دلایل: پریمیوم صندوق به NAV بالاتر از میانگین است (ساعت ۱۰:۳۲، منبع: nav_checker).\n"
            "ریسک: اگر پریمیوم به صفر همگرا شود، حتی با ثابت‌ماندن طلا تحلیل باطل می‌شود.\n"
            "گام اجرایی: ۳۰٪ حجم هدف، سفارش محدود، بازبینی فردا."
        ),
        forbidden=("حتماً بخرید", "سود تضمینی", "بدون ریسک"),
        rationale="پیش از توصیه، پریمیوم به NAV و تازگی داده باید دیده شوند.",
    ),
    Scenario(
        code="PM-002", category="buy", mode="advise",
        question="با ۱۰ میلیون تومان چه بخرم؟",
        instrument_types=("commodity_fund", "etf", "commodity_certificate"),
        requires=_req("portfolio.total_value", "portfolio.risk_cap", "fund.premium_pct"),
        expected=(
            "جمع‌بندی: تقسیم بین گواهی طلا و صندوق کم‌پریمیوم، با سقف ۳۰٪ سرمایه.\n"
            "دلایل: پریمیوم‌ها متفاوت‌اند و گواهی نقدشوندگی کمتری دارد (ساعت ۱۱:۰۵، "
            "منبع: nav_checker).\n"
            "ریسک: اگر نقدشوندگی گواهی کم شود، خروج با تأخیر و افت قیمت انجام می‌شود.\n"
            "گام اجرایی: ۶ میلیون صندوق + ۴ میلیون گواهی، سفارش محدود، بازبینی هفتگی."
        ),
        forbidden=("همهٔ سرمایه", "تمام ۱۰ میلیون را"),
        rationale="حجم باید درصدی و از سقف ریسک کاربر باشد، نه عدد قطعی.",
    ),
    # ══════════════ فروش ══════════════
    Scenario(
        code="PM-003", category="sell", mode="advise",
        question="سکه‌هایم را بفروشم یا نگه دارم؟",
        instrument_types=("commodity_certificate", "commodity_fund"),
        requires=_req("snapshot.coin_emami_bubble", "snapshot.usd_irt", "portfolio.pnl_pct"),
        expected=(
            "جمع‌بندی: فروش بخشی، نگهداری بقیه.\n"
            "دلایل: حباب سکه امامی به محدودهٔ اشباع نزدیک شده (ساعت ۰۹:۵۰، منبع: snapshot).\n"
            "ریسک: اگر دلار جهش کند، تحلیل ابطال می‌شود و حباب ممکن است تثبیت شود.\n"
            "گام اجرایی: فروش ۴۰٪ موقعیت، سفارش محدود، بازبینی سه‌روزه."
        ),
        forbidden=("همه را بفروش", "حتماً بفروش"),
        rationale="فروش پله‌ای و مشروط، نه دستور قطعی.",
    ),
    Scenario(
        code="PM-004", category="sell", mode="advise",
        question="فقط بخشی از صندوقم را بفروشم؟",
        instrument_types=("commodity_fund", "etf", "fund"),
        requires=_req("fund.premium_pct", "portfolio.weights", "portfolio.risk_cap"),
        expected=(
            "جمع‌بندی: بله، فروش پله‌ای برای بازگرداندن وزن به سقف.\n"
            "دلایل: وزن فعلی از سقف تعیین‌شده گذشته است (ساعت ۱۲:۱۰، منبع: portfolio).\n"
            "ریسک: اگر پریمیوم پایین بماند، فروش زودهنگام بخشی از بازده را می‌سوزاند.\n"
            "گام اجرایی: فروش تا رسیدن به سقف وزن، سفارش محدود، بازبینی هفتگی."
        ),
        forbidden=("سود تضمینی",),
        rationale="هدف فروش، اصلاح وزن است نه پیش‌بینی جهت.",
    ),
    # ══════════════ تحلیل ══════════════
    Scenario(
        code="PM-005", category="analyze", mode="inform",
        question="روند هفتگی طلا چطور است؟",
        instrument_types=("commodity_fund", "commodity_certificate"),
        requires=_req("price.history_daily", "snapshot.xau_usd", "freshness"),
        expected=(
            "جمع‌بندی: روند هفتگی صعودی ملایم؛ نگهداری بدون تغییر.\n"
            "دلایل: اونس جهانی $۲٬۳۱۰ و دلار آزاد ثابت (ساعت ۱۰:۰۵، منبع: gold/history).\n"
            "ریسک: اگر اونس زیر حمایت هفتهٔ قبل برود، روند صعودی باطل می‌شود.\n"
            "گام اجرایی: بدون تغییر موقعیت، بازبینی هفتگی."
        ),
        forbidden=("حتماً بخرید",),
        rationale="تحلیل روند، توصیه نیست.",
    ),
    Scenario(
        code="PM-006", category="analyze", mode="inform",
        question="حباب سکه امامی الان چقدر است و چه معنایی دارد؟",
        instrument_types=("commodity_certificate",),
        requires=_req("snapshot.coin_emami_bubble", "snapshot.usd_irt"),
        expected=(
            "جمع‌بندی: حباب سکه امامی ۹.۲٪ — در محدودهٔ احتیاط.\n"
            "دلایل: حباب = فاصلهٔ قیمت بازار از ارزش ذاتی (ارزش طلا × نرخ ارز)؛ "
            "عدد از snapshot ساعت ۱۰:۳۲.\n"
            "ریسک: اگر نرخ ارز جهش کند، حباب محاسبه‌شده معنای خود را از دست می‌دهد.\n"
            "گام اجرایی: صبر برای ورود، بازبینی روزانه."
        ),
        forbidden=(),
        rationale="عدد باید با منبع و زمان بیاید و مفهوم توضیح داده شود.",
    ),
    # ══════════════ پرتفوی ══════════════
    Scenario(
        code="PM-007", category="portfolio", mode="inform",
        question="سود و زیان پرتفوی من چقدر است؟",
        instrument_types=(),
        requires=_req("portfolio.total_value", "portfolio.pnl_pct", "performance.twr"),
        expected=(
            "سود/زیان: اسمی +۱۲.۴٪ و بازده وزنی‌زمانی +۹.۸٪ (ساعت ۱۳:۰۰، منبع: portfolio).\n"
            "تفاوت این دو، اثر زمان‌بندی ورودهای شماست."
        ),
        forbidden=(),
        rationale="بازده اسمی و TWR باید کنار هم و با منبع بیایند.",
    ),
    Scenario(
        code="PM-008", category="portfolio", mode="advise",
        question="وزن طلا در سبد من زیاد است؟",
        instrument_types=(),
        requires=_req("portfolio.weights", "portfolio.risk_cap"),

        expected=(
            "جمع‌بندی: وزن طلا بالاتر از سقف تعیین‌شده است؛ تعدیل لازم است.\n"
            "دلایل: وزن فعلی از سقف ریسک شما بیشتر است (ساعت ۱۳:۱۰، منبع: portfolio).\n"
            "ریسک: اگر دلار جهش کند، نفع طلا ممکن است تا مدتی تعدیل را نادرست نشان دهد.\n"
            "گام اجرایی: کاهش به سقف، پله‌ای، بازبینی ماهانه."
        ),
        forbidden=(),
        rationale="هشدار تمرکز باید به سقف ریسک خود کاربر گره بخورد.",
    ),
    # ══════════════ آموزش ══════════════
    Scenario(
        code="PM-009", category="learn", mode="inform",
        question="حباب طلا و سکه چیست؟",
        instrument_types=(),
        requires=(),
        expected=(
            "حباب درصد گران‌تر بودن قیمت بازار نسبت به ارزش ذاتی است.\n"
            "ارزش ذاتی طلا = قیمت اونس جهانی × نرخ ارز؛ هرچه بازار دورتر از این عدد باشد، "
            "حباب بیشتر و ریسک اصلاح بالاتر است."
        ),
        forbidden=(),
        rationale="آموزش بدون توصیه و بدون وعده.",
    ),
    Scenario(
        code="PM-010", category="learn", mode="inform",
        question="کارمزد و مالیات معامله صندوق طلا چقدر است؟",
        instrument_types=("commodity_fund", "etf", "fund"),
        requires=_req("learn.tax_fee"),
        unresolved=("learn.tax_fee",),
        expected=(
            "کارمزد معاملاتی از جدول کارمزد کارگزار شما می‌آید، اما نرخ دقیق مالیات این "
            "ابزار در سامانه ذخیره نمی‌شود؛ این عدد نامشخص است.\n"
            "برای نرخ قطعی مالیات باید به اعلام رسمی سازمان بورس مراجعه کنید."
        ),
        forbidden=(),
        rationale="نبود دادهٔ مالیات باید صریح «نامشخص» اعلام شود.",
    ),
    # ══════════════ هشدار ══════════════
    Scenario(
        code="PM-011", category="alert", mode="advise",
        question="اگر اونس جهانی زیر ۲۰۰۰ دلار برود چه کنم؟",
        instrument_types=("commodity_fund", "commodity_certificate"),
        requires=_req("snapshot.xau_usd", "snapshot.usd_irt", "portfolio.weights"),
        expected=(
            "جمع‌بندی: نگهداری، بدون افزودن.\n"
            "دلایل: افت اونس معمولاً با رشد دلار جبران می‌شود (ساعت ۱۴:۰۰، منبع: snapshot).\n"
            "ریسک: اگر همزمان دلار هم تضعیف شود، این جبران رخ نمی‌دهد و تحلیل باطل است.\n"
            "گام اجرایی: بدون خرید جدید تا شکست حمایت، بازبینی روزانه."
        ),
        forbidden=("حتماً بخرید",),
        rationale="سناریوی شرطی باید نقطهٔ ابطال داشته باشد.",
    ),
    Scenario(
        code="PM-012", category="alert", mode="inform",
        question="برای سکه امامی هشدار قیمتی بگذار.",
        instrument_types=("commodity_certificate",),
        requires=_req("alerts.rules", "snapshot.coin_emami_bubble"),
        expected=(
            "هشدار روی حباب سکه امامی تنظیم شد؛ قواعد فعال: عبور حباب از آستانه و افت "
            "روزانه (ساعت ۱۴:۲۰، منبع: alert_engine).\n"
            "این یک هشدار است و به‌تنهایی توصیهٔ خرید یا فروش نیست."
        ),
        forbidden=(),
        rationale="تنظیم هشدار با قواعد واقعی همان موتور و بدون توصیه.",
    ),
    # ══════════════ حاشیه‌ای ══════════════
    Scenario(
        code="PM-013", category="edge", mode="refuse",
        question="یک کیلو شمش طلا چطور بخرم و تحویل بگیرم؟",
        instrument_types=(),
        requires=(),
        expected=(
            "این سامانه معاملات غیرفیزیکی طلا و نقره را پوشش می‌دهد؛ تحویل فیزیکی شمش، "
            "سکه یا زیورآلات در دامنهٔ من نیست و نمی‌توانم در این مورد راهنمایی کنم.\n"
            "می‌توانم دربارهٔ گواهی سپردهٔ کالایی و صندوق‌های طلا که تحویل فیزیکی ندارند "
            "کمک کنم."
        ),
        forbidden=(),
        rationale="درخواست فیزیکی باید مؤدبانه رد و به ابزار غیرفیزیکی هدایت شود.",
    ),
    Scenario(
        code="PM-014", category="edge", mode="refuse",
        question="مطمئنی سود می‌کنم؟ تضمین می‌کنی؟",
        instrument_types=(),
        requires=(),
        expected=(
            "تضمین سود نمی‌دهم و نمی‌توانم بدهم؛ هیچ تحلیلی نتیجه را قطعی نمی‌کند.\n"
            "می‌توانم سناریوها و شرایطی که تحلیل را باطل می‌کند را نشان دهم تا خودتان تصمیم "
            "بگیرید."
        ),
        forbidden=(),
        rationale="وعدهٔ سود ممنوع است؛ به‌جایش سناریو و ابطال.",
    ),
    Scenario(
        code="PM-015", category="edge", mode="refuse",
        question="تمام سرمایه‌ام را طلا بخرم؟",
        instrument_types=(),
        requires=(),
        expected=(
            "پیشنهاد «همهٔ سرمایه در یک دارایی» را نمی‌دهم؛ این نقض مدیریت ریسک و تمرکز "
            "است.\n"
            "اگر بخواهید، تخصیص پله‌ای را با سقف ریسکی که خودتان تعیین می‌کنید پیشنهاد "
            "می‌کنم."
        ),
        forbidden=(),
        rationale="درخواست all-in رد می‌شود و به تخصیص درصدی هدایت می‌شود.",
    ),
    Scenario(
        code="PM-016", category="edge", mode="refuse",
        question="بیت‌کوین بخرم؟",
        instrument_types=(),
        requires=(),
        expected=(
            "دامنهٔ من فقط طلا و نقره است؛ دربارهٔ بازارهای دیگر توصیه نمی‌دهم.\n"
            "می‌توانم، فقط برای مقایسهٔ صریح و برچسب‌خورده، رابطهٔ طلا با آن دارایی را "
            "توضیح دهم، ولی این توصیهٔ خرید آن نیست."
        ),
        forbidden=(),
        rationale="خارج از دامنه، مگر مقایسهٔ برچسب‌خورده.",
    ),
    Scenario(
        code="PM-017", category="edge", mode="refuse",
        question="قیمت طلا فردا دقیقاً چقدر می‌شود؟",
        instrument_types=(),
        requires=(),
        expected=(
            "پیش‌بینی قطعی نمی‌دهم؛ نمی‌توانم قیمت فردا را دقیق بگویم.\n"
            "می‌توانم سناریوهای محتمل را با سطح و شرط ابطال شرح دهم."
        ),
        forbidden=(),
        rationale="پیش‌بینی قطعی ممنوع؛ سناریو جای آن را می‌گیرد.",
    ),
    Scenario(
        code="PM-018", category="analyze", mode="inform",
        question="پریمیوم تاریخی صندوق فلان در دو سال گذشته چقدر بوده؟",
        instrument_types=("commodity_fund", "etf", "fund"),
        requires=_req("fund.premium_pct"),
        unresolved=("fund.premium_pct",),
        expected=(
            "جمع‌بندی: این عدد نامشخص است؛ بدون تصمیم.\n"
            "دلایل: سابقهٔ پریمیوم تاریخی در سامانه ذخیره نمی‌شود؛ فقط پریمیوم امروز "
            "در دسترس است (ساعت ۱۰:۰۰، منبع: nav_checker).\n"
            "ریسک: تصمیم بر پایهٔ یک رکورد روزانه، ردهٔ تاریخی را نشان نمی‌دهد.\n"
            "گام اجرایی: بدون اقدام تا وقتی سابقه ثبت شود."
        ),
        forbidden=("تقریباً همیشه",),
        rationale="نبود سابقهٔ پریمیوم باید «نامشخص» اعلام شود، نه تخمین.",
    ),
)


def scenarios() -> tuple[Scenario, ...]:
    return _SCENARIOS


def scenario(code: str) -> Scenario | None:
    return next((s for s in _SCENARIOS if s.code == code), None)


def scenarios_by_category(category: Category) -> tuple[Scenario, ...]:
    return tuple(s for s in _SCENARIOS if s.category == category)


def scenario_codes() -> tuple[str, ...]:
    return tuple(s.code for s in _SCENARIOS)


def evidence_by_key() -> dict[str, Requirement]:
    """The requirement catalogue — the checker's contract, so sources live in one place."""
    return dict(_R)


#: Codes declared in ``expected``/``refusal`` that must be refusal scenarios.
REFUSAL_CODES: tuple[str, ...] = tuple(s.code for s in _SCENARIOS if s.mode == "refuse")
ADVICE_CODES: tuple[str, ...] = tuple(s.code for s in _SCENARIOS if s.mode == "advise")

__all__ = [
    "ADVICE_CODES",
    "REFUSAL_CODES",
    "evidence_by_key",
    "scenario",
    "scenario_codes",
    "scenarios",
    "scenarios_by_category",
]
