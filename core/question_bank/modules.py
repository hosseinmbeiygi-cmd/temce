"""🧩 The non-equity instrument modules (سؤالات ۱۱۶ تا ۲۳۴).

Transcribed from the user's own document «بانک سؤالات پیش از خرید … — سایر ابزارهای بازار
ایران», which continues the stock numbering: the codes stay **PB-116 … PB-234** so one bank
holds every class and a saved sheet is never renumbered. The class boundaries are the
document's:

    A اوراق با درآمد ثابت ۱۱۶–۱۳۵ · B صندوق‌ها ۱۳۶–۱۵۵ · C طلا و گواهی سکه ۱۵۶–۱۶۵
    D املاک (REIT) ۱۶۶–۱۷۵ · E بورس کالا ۱۷۶–۱۸۷ · F اختیار معامله ۱۸۸–۱۹۹
    G آتی و مارجین ۲۰۰–۲۱۱ · H صندوق اهرمی ۲۱۲–۲۱۹ · I سطح سبد ۲۲۰–۲۳۴

A module is the document's class as one middle stage, composed by the registry with the
shared core the framework itself declares instrument-invariant (stage 0, and the sizing /
sell-plan / mirror stages), so a fund sheet is 56 questions and not 20: the middle of the
rail changes, the discipline around it does not.

Three deliberate choices:

* **D (REIT) is absent.** No table holds a property fund, its occupancy rate or its
  valuation date, so those ten questions would be unanswerable from data and unstorable
  from a symbol; they stay declared in ``registry.GAP_REASONS``.
* **★ without a veto is still a stopper.** The document's star means «رد یا تعلیق», and most
  of its starred questions are open prose («پشتوانه دقیقاً چیست؟») where no click can be the
  wrong answer. For those, ★ keeps the stage closed while unanswered or «نمی‌دانم», and no
  rejection is invented. ``_VETO`` names the handful where the failing answer is explicit.
* **Evidence is bound or declared, never proxied** — see ``_EV`` and
  ``services/pre_buy_evidence.py``; ``test_pre_buy_registry`` fails on a third state.
"""

from __future__ import annotations

from core.question_bank import bank
from core.question_bank.registry import InstrumentModule
from core.question_bank.schema import Evidence, InstrumentType, Question, Stage

#: The few stars whose *answer* rejects the sheet, as the document states it. Everything
#: else that is starred only blocks while unanswered or «نمی‌دانم».
_VETO: dict[int, str] = {
    128: "no",  # «با سپرده و گزینه‌های کم‌ریسک دیگر مقایسه نکرده‌ام»
    153: "yes",  # «بله، دارم دو بار همان ریسک را می‌خرم»
}

_FUND: tuple[tuple[int, str, str, bool], ...] = (
    (136, "نوع صندوق با هدف و افق من همخوان است؟", "y", True),
    (137, "مدیر صندوق کیست؟ در بازارهای نزولی چه کرده؟ (عملکرد گذشته تضمین نیست)", "t", False),
    (138, "دارایی تحت مدیریت چقدر است؟ خیلی کوچک = ریسک نقدشوندگی/تعطیلی؛ خیلی بزرگ = چابکی کم.", "t", False),
    (139, "کارمزد و هزینه‌ها در بازده خالص من چه اثری دارد؟", "t", False),
    (140, "پرتفوی فعلی صندوق چیست؟ اگر سهامی است، در چه صنایعی متمرکز است — و با سبد سهام خودم هم‌پوشانی دارد؟", "t", False),
    (141, "NAV روزانه را از کجا می‌گیرم و پریمیوم/دیسکانت الان چقدر است؟", "t", False),
    (142, "پریمیوم الان چند درصد است؟ چه چیزی آن را جمع می‌کند (بازارگردان/ایجاد-ابطال)؟ اگر هیچ، پس چه چیزی؟", "t", True),
    (143, "بازارگردان صندوق فعال است یا غایب؟", "y", False),
    (144, "درآمد ثابت: سود ماهانه از درآمد واقعی صندوق است یا از اصل سرمایه (NAV تدریجی خورده می‌شود)؟", "t", False),
    (145, "تاریخچه NAV را دیده‌ام؟ در اصلاح‌های بزرگ بازار، افتش چقدر بوده؟", "t", False),
    (146, "تقسیم سود یعنی NAV کم می‌شود — آیا «سود اضافه» فرض نکرده‌ام؟", "y", False),
    (147, "مالیات فروش واحد صندوق با مالیات فروش سهام چه فرقی دارد؟", "t", False),
    (148, "نقدشوندگی واحدها در تابلو چقدر است؟ اگر صف فروش باشد چطور خارج می‌شوم؟", "t", False),
    (149, "شرط‌های ابطال/ایجاد واحد: زمان، هزینه، سقف؟", "t", False),
    (150, "صندوق شاخصی/طلا: خطای ردیابی نسبت به شاخص/پشتوانه چقدر است؟", "t", False),
    (151, "سابقه صندوق چند سال است؟ در دوره‌های تند نزولی چه کرده؟", "t", False),
    (152, "مختلط: نسبت فعلی سهام/درآمد ثابت را از آخرین گزارش ماهانه چک کرده‌ام؟", "y", False),
    (153, "آیا دارم دو بار همان ریسک را می‌خرم؟ (چند صندوق سهامی ≈ یک پرتفوی تکراری)", "y", True),
    (154, "صندوق فعال چه برتری‌ای نسبت به شاخص نشان داده که هزینه‌اش را جواب داده باشد؟", "t", False),
    (155, "اگر صندوق منحل شود چه می‌شود و پولم کی برمی‌گردد؟", "t", False),
)

_GOLD: tuple[tuple[int, str, str, bool], ...] = (
    (156, "پشتوانه دقیقاً چیست (سکه/شمش/طلا) و هر واحد معادل چقدر از آن است؟", "t", True),
    (157, "پریمیوم نسبت به ارزش پشتوانه الان چند درصد است؟", "t", False),
    (158, "پریمیوم تاریخی این نماد چه رده‌ای بوده و الان کجاست؟", "t", False),
    (159, "گواهی سکه: برداشت فیزیکی ممکن است؟ شرایط، هزینه و مهلتش؟", "t", False),
    (160, "اگر پریمیوم از مثلاً ۲۰٪ به صفر برسد، حتی با ثابت‌ماندن طلا چقدر ضرر می‌کنم؟", "t", False),
    (161, "مالیات فروش گواهی با فروش سکه فیزیکی چه فرقی دارد؟", "t", False),
    (162, "در روزهای جهش، این نماد چند روز طول می‌کشد به قیمت واقعی سکه همگرا شود؟", "t", False),
    (163, "هزینه مدیریت و نگهداری صندوق طلا چقدر است؟", "t", False),
    (164, "آیا دارم برای «شرایط بحرانی که بورس و اینترنت قطع است» گواهی می‌خرم به‌جای سکه فیزیکی؟ این فرض درست است؟", "y", True),
    (165, "هدف من پوشش تورم است یا سفته‌بازی نوسان سکه؟ رفتار نگهداری‌ام با کدام سازگار است؟", "t", False),
)

_COMMODITY: tuple[tuple[int, str, str, bool], ...] = (
    (176, "سازوکار دقیق چیست: تحویل فیزیکی، پشتوانه کالایی، یا تعهد یک طرف؟", "t", True),
    (177, "سلف‌دهنده/تأمین‌کننده کیست و اعتبارش چیست؟", "t", False),
    (178, "ریسک عدم تحویل یا تأخیر — چه کسی جبران می‌کند و چطور؟", "t", False),
    (179, "قیمت این ابزار چقدر واقعاً به قیمت نقدی کالا وصل است؟ فاصله تاریخی‌اش چه رده بوده؟", "t", False),
    (180, "گواهی کالایی: انبار و تأییدیه کیفیت کیست؟ هزینه انبارداری بر گردن کیست؟", "t", False),
    (181, "اگر تحویل فیزیکی بخواهم، هزینه و تشریفات چیست؟", "t", False),
    (182, "دامنه نوسان و قواعد معاملاتی بورس کالا با بورس سهام چه فرق دارد؟", "t", False),
    (183, "ریسک تأمین مالی مجدد در ابزارهای سررسیددار چقدر است؟", "t", False),
    (184, "این ابزار در شوک‌های قبلی کالا چه رفتاری داشته؟", "t", False),
    (185, "کارمزد و مالیات را در بازده گذاشته‌ام؟", "y", False),
    (186, "خرید من سفته‌بازی روی کالاست یا سرمایه‌گذاری؟ قواعد خروجم با کدام نوشته شده؟", "t", False),
    (187, "نقدشوندگی روزانه چند است؟ روزهای بی‌معامله چه می‌شود؟", "t", False),
)

_OPTION: tuple[tuple[int, str, str, bool], ...] = (
    (188, "خریدارم یا فروشنده؟ (خریدار: زیان محدود به پرمیوم ولی احتمال زیان بالا؛ فروشنده: سود محدود، زیان بالقوه بزرگ — دو دنیای کاملاً متفاوت)", "t", True),
    (189, "دارایی پایه و سررسید چیست؟", "t", False),
    (190, "اعماله نسبت به قیمت جاری کجاست (سری‌الحساب/حقیقی)؟", "t", False),
    (191, "چقدر از پول من ارزش زمانی است که با گذر روزها می‌سوزد؟", "t", False),
    (192, "نقدشوندگی و اسپرد این قرارداد؟ اگر خریدار در بازار نباشد خروج چطور؟", "t", False),
    (193, "فروشنده‌ام: مارجین و ریسک مارجین‌کال را کامل فهمیده‌ام؟", "y", False),
    (194, "سناریوی «منقضی شدن بی‌ارزش» چقدر محتمل است؟ (بخش بزرگی از اختیارها همین‌سر می‌روند)", "t", False),
    (195, "نوسان ضمنی الان گران است یا ارزان؟ با IV بالا، حتی پیش‌بینی درست جهت هم می‌تواند زیان‌ده باشد.", "t", False),
    (196, "کارمزد و مالیات در بازده محاسبه شده؟", "y", False),
    (197, "اندازه موقعیت را با منطق «حداکثر پولی که از دست رفتنی است» گذاشته‌ام یا با اهرم ظاهری؟", "t", False),
    (198, "این برای پوشش ریسک است یا سفته‌بازی؟ هر کدام قواعد مستقل می‌خواهد.", "t", False),
    (199, "رفتار قیمت این قرارداد را در روزهای پرنوسان واقعی دیده‌ام یا فقط در نمودار ایده‌آل؟", "y", False),
)

_FUTURE: tuple[tuple[int, str, str, bool], ...] = (
    (200, "اهرم واقعی من چند است؟ یک حرکت چنددرصدی مخالف چقدر از سرمایه را می‌سوزاند؟", "t", True),
    (201, "مارجین اولیه و آستانه فراخوان را از قواعد رسمی می‌دانم؟", "y", False),
    (202, "اگر یک‌شبه گپ شدید بخورد (پیشینه تاریخی سکه را ببینید)، فراخوان با چه سرعتی می‌آید و اگر واریز نکنم چه می‌شود؟", "t", False),
    (203, "تسویه روزانه سود/زیان برای جریان نقدی من یعنی چه؟", "t", False),
    (204, "هزینه رول‌اور بین قراردادها چقدر است؟ استراتژی‌ام به نگهداری چندماهه نیاز دارد؟", "t", False),
    (205, "فاصله آتی از نقدی الان چقدر است؟ همگرایی در سررسید چه معنایی برای پوزیشنم دارد؟", "t", False),
    (206, "این پوزیشن پوشش ریسک است یا شرط‌بندی جهت؟ با سبد سهامم هم‌ریسک است؟", "t", False),
    (207, "سقف ضرر روزانه خودم کجاست و کجا قطع می‌کنم؟", "t", False),
    (208, "در روز صف، خروج از پوزیشن اهرمی عملاً ممکن است؟", "y", False),
    (209, "سرمایه جدا و قابل‌ازدست‌دادن برای مشتقه دارم، یا از سرمایه اصلی؟", "y", False),
    (210, "اندازه موقعیت مخصوص مشتقه (کوچک‌تر از معاملات نقدی) را اجرا می‌کنم؟", "y", False),
    (211, "اگر دو روز پیاپی فراخوان شود، برنامه نوشته‌شده‌ام چیست؟", "t", True),
)

_LEVERAGED: tuple[tuple[int, str, str, bool], ...] = (
    (212, "ضریب اهرم دقیق و نوعش (یک‌سویه/دوسویه) چیست؟", "t", True),
    (213, "بازسازی روزانه پرتفوی یعنی «بازده چندروزه ≈ اهرم × بازده شاخص» نیست؛ مسیر قیمت مهم است. این را با یک مثال عددی آزمون کرده‌ام؟", "y", False),
    (214, "در روزهای +۵٪ و −۵٪ متوالی، افت ساختاری این صندوق چقدر است؟", "t", False),
    (215, "سازوکار کم‌کردن اهرم در نوسان شدید را فهمیده‌ام؟", "y", False),
    (216, "چرا این ابزار را برای نگهداری بلندمدت نمی‌خرم؟ (نمی‌خرم — درست؟)", "t", False),
    (217, "NAV و پریمیومش را هم‌زمان چک می‌کنم؟", "y", False),
    (218, "سقف زمانی نگهداری و شرط خروجم نوشته شده؟", "y", False),
    (219, "همان هدف را با صندوق ساده + اندازه مناسب موقعیت می‌شد گرفت؟ چرا اهرم لازم است؟", "t", False),
)

_FIXED_INCOME: tuple[tuple[int, str, str, bool], ...] = (
    (116, "ناشر کیست و اعتبارش را با چه شواهدی سنجیده‌ام؟ (دولت/بانک/شرکت — رتبه اعتباری یا جایگزینش)", "t", True),
    (117, "نرخ سود اسمی و سازوکار پرداخت (ماهانه/پای سررسید) چیست؟", "t", False),
    (118, "سود واقعی پس از مالیات و تورم انتظاری چند است؟ نرخ اسمی بی‌معنی است.", "t", True),
    (119, "شرط تسریع در پرداخت (بازخرید زودتر توسط ناشر) دارد؟ اگر نرخ‌های بازار بیفتد، پولم را زودتر پس می‌گیرد و باید پایین‌تر دوباره سرمایه‌گذاری کنم؟", "t", False),
    (120, "سررسید دقیق کی است؟ جریان نقدی من تا آن موقع دقیقاً چیست؟", "t", False),
    (121, "اگر پیش از سررسید بفروشم، قیمتش به نرخ سود بازار چطور حساس است؟", "t", False),
    (122, "میانگین معاملات روزانه این اوراق چقدر است؟ آیا اصلاً معامله می‌شود یا تا سررسید خوابیده می‌ماند؟", "t", False),
    (123, "اگر ناشر دچار مشکل شود، وثیقه و پشتوانه چیست و کی به آن دسترسی دارم؟", "t", False),
    (124, "گواهی سپرده بانکی: جریمه ابطال پیش از موعد چقدر است؟ اگر در سال آخر ابطال کنم، عملاً چه سودی برده‌ام؟", "t", False),
    (125, "مالیات این ابزار چیست؟ با سپرده معمولی چه فرقی دارد؟", "t", False),
    (126, "اگر نرخ این اوراق به‌طور غیرعادی بالاتر از مشابه‌هاست، ریسک پنهانش کجاست؟ (نرخ بالا = پیام، نه هدیه)", "t", False),
    (127, "اخزا/اوراق تسویه: بازده تا سررسید از قیمت خرید فعلی چقدر می‌شود و معادل سالانه‌اش چند است؟", "t", False),
    (128, "با سپرده بانکی و گزینه‌های کم‌ریسک دیگر مقایسه کرده‌ام یا فقط «سود بالاتر» دیده‌ام؟", "y", True),
    (129, "اگر نرخ سود سپرده‌ها در این مدت بالا برود، قیمت اوراقم چه می‌شود؟", "t", False),
    (130, "ریسک بازسرمایه‌گذاری: سود دوره‌ای را با چه نرخی دوباره جا می‌دهم؟", "t", False),
    (131, "پرداخت سود از درآمد واقعی ناشر است یا از فروش اوراق جدید (چرخشی)؟", "t", False),
    (132, "صکوک شرکتی: گزارش مالی ناشر، وثایق و اظهارنظر کارشناس ارزش‌گذاری را خوانده‌ام؟", "y", False),
    (133, "اگر نقدینگی فوری لازم شد، این سرمایه کی و چقدر آزاد می‌شود؟", "t", False),
    (134, "اندازه خرید را با نقدشوندگی واقعی (نه حجم عرضه اولیه) هماهنگ کرده‌ام؟", "y", False),
    (135, "در تورم جهشی، سود ثابت من چند ماه چه قدرت خریدی از دست می‌دهد؟", "t", False),
)

_ALLOCATION: tuple[tuple[int, str, str, bool], ...] = (
    (220, "چرا این کلاس دارایی؟ پاسخم با هدف و افقم یکی است یا دنبال هیجان امروز هستم؟", "t", True),
    (221, "تخصیص بین سهام/درآمد ثابت/طلا/نقد را از قبل نوشته‌ام یا الان بر اساس احساس می‌خرم؟", "t", False),
    (222, "همبستگی این دارایی با بقیه سبد در بحران چیست؟ (همبستگی روزهای عادی فریب می‌دهد)", "t", False),
    (223, "سناریوی تورم جهشی: این دارایی چه می‌کند؟", "t", False),
    (224, "سناریوی تثبیت یا افت ارز: چه می‌کند؟", "t", False),
    (225, "سناریوی افزایش نرخ سود سپرده: چه می‌کند؟", "t", False),
    (226, "در بدترین حالت (بحران + اختلال سامانه) نقدشوندگی این دارایی چه می‌شود؟", "t", False),
    (227, "هزینه نگهداری و مالیات در کل افق چقدر از بازده می‌خورد؟", "t", False),
    (228, "معیار مقایسه درست را انتخاب کرده‌ام؟ (درآمد ثابت ↔ سپرده؛ سهام ↔ شاخص؛ طلا ↔ قیمت جهانی×ارز)", "t", False),
    (229, "اگر ۳۰٪ بیفتد، دلیل بنیادی برای ماندن دارم یا فقط امید؟", "t", False),
    (230, "می‌فهمم سمت مقابل معامله من کیست و چرا می‌فروشد/می‌خرد؟", "y", False),
    (231, "برای این دارایی قواعد خروج نوشته‌ام؟", "y", False),
    (232, "نقد کم‌ریسک کافی برای خرج ضروری و فرصت‌ها دارم؟", "y", False),
    (233, "کل دارایی‌های زندگی‌ام (مسکن، خودرو، بدهی، درآمد شغلی) را دیده‌ام یا فقط بورس را؟", "y", False),
    (234, "اگر یک هفته همه درهای معاملات بسته شود، زندگی مالی‌ام پابرجاست؟", "y", True),
)

#: Every handle the new classes want. ``source`` is shown to the user verbatim, so a handle
#: with no column says «ذخیره نمی‌شود» in that field and is listed in
#: ``PERMANENTLY_UNAVAILABLE`` with the same honesty — never filled by a lookalike.
_EV: dict[str, Evidence] = {
    e.key: e
    for e in (
        Evidence("nav.value", "NAV روزنامه", "GET /brsapi/nav/{symbol} → `brsapi_nav_records`", "ریال"),
        Evidence("nav.premium_pct", "پریمیوم/دیسکانت به NAV", "محاسبه: (price_last − nav) ÷ nav × ۱۰۰", "٪"),
        Evidence("fund.type", "نوع صندوق", "`funds.fund_type`", ""),
        Evidence("fund.size", "دارایی تحت مدیریت", "`funds.market_value`", "ریال"),
        Evidence("fund.units", "تعداد واحدهای صندوق", "`funds.shares_count`", "واحد"),
        Evidence("fund.liquidity", "ارزش معاملات امروز صندوق", "`funds.trade_value`", "ریال"),
        Evidence("fund.nav_history", "سابقهٔ NAV صندوق", "`brsapi_nav_records` (چند رکورد اخیر)", ""),
        Evidence("fund.fee", "کارمزد صندوق", "هیچ ستونی کارمزد را ذخیره نمی‌کند"),
        Evidence("fund.manager", "مدیر صندوق و سابقهٔ او", "هیچ ستونی مدیر صندوق را ذخیره نمی‌کند"),
        Evidence("fund.track_error", "خطای ردیابی", "محاسبه نمی‌شود؛ شاخص مقایسه ذخیره نیست"),
        Evidence("fund.redemption", "شرایط و هزینهٔ ابطال/ایجاد واحد", "در جداول برنامه نیست"),
        Evidence("fund.dissolution", "شرایط انحلال صندوق", "در جداول برنامه نیست"),
        Evidence("fund.portfolio", "پرتفوی فعلی صندوق", "در جداول برنامه نیست (سهم صندوق‌ها از NAV قابل استخراج نیست)"),
        Evidence("fund.dividend", "تقسیم سود و اثرش بر NAV", "در جداول برنامه نیست"),
        Evidence("gold.backing", "پشتوانهٔ هر واحد", "در جداول برنامه نیست"),
        Evidence("gold.premium_history", "ردهٔ تاریخی پریمیوم", "سابقهٔ پریمیوم ذخیره نمی‌شود"),
        Evidence("gold.convergence", "سرعت همگرایی به قیمت واقعی", "در جداول برنامه نیست"),
        Evidence("gold.delivery", "شرایط برداشت فیزیکی", "در جداول برنامه نیست"),
        Evidence("commodity.mechanism", "سازوکار تحویل/پشتوانهٔ ابزار", "در جداول برنامه نیست"),
        Evidence("commodity.counterparty", "طرف تعهد و اعتبار او", "در جداول برنامه نیست"),
        Evidence("commodity.warehouse", "انبار، کیفیت و انبارداری", "در جداول برنامه نیست"),
        Evidence("commodity.spot_gap", "فاصلهٔ ابزار از قیمت نقدی کالا", "قیمت نقدی کالا برای مقایسه ذخیره نمی‌شود"),
        Evidence("commodity.shock_history", "رفتار ابزار در شوک‌های قبلی کالا", "سابقهٔ رویداد-محور ذخیره نیست"),
        Evidence("option.underlying", "دارایی پایهٔ قرارداد", "`options.underlying_symbol` / `commodity_options.underlying`", ""),
        Evidence("option.strike", "قیمت اعمال", "`options.strike_price` / `commodity_options.strike_price`", "ریال"),
        Evidence("option.expiry", "سررسید قرارداد", "`options.expiry_date` / `commodity_options.expiry_date`", ""),
        Evidence("option.kind", "نوع قرارداد (call/put)", "`options.option_type`", ""),
        Evidence("option.last", "آخرین قیمت معاملهٔ قرارداد", "`options.price_last`", "ریال"),
        Evidence("option.volume", "حجم معاملات امروز قرارداد", "`options.trade_volume`", "سهم"),
        Evidence("option.iv", "نوسان ضمنی", "محاسبه نمی‌شود؛ سابقهٔ قیمت لحظه‌ای قرارداد ذخیره نیست"),
        Evidence("option.spread", "اسپرد خرید/فروش قرارداد", "دو قیمت سفارش ذخیره نمی‌شود"),
        Evidence("future.expiry", "سررسید قرارداد آتی", "`brsapi_ime_futures.date_end`", ""),
        Evidence("future.margin_initial", "مارجین اولیه", "`brsapi_ime_futures.margin_initial`", "ریال"),
        Evidence("future.margin_maintenance", "مارجین نگهداشت (آستانهٔ فراخوان)", "`brsapi_ime_futures.margin_maintenance`", "ریال"),
        Evidence("future.open_interest", "موقعیت‌های باز", "`brsapi_ime_futures.open_interest`", "قرارداد"),
        Evidence("future.basis", "فاصلهٔ آتی از نقدی", "قیمت نقدی پایه در کنار آتی ذخیره نمی‌شود"),
        Evidence("future.rollover", "هزینهٔ رول‌اور", "در جداول برنامه نیست"),
        Evidence("future.settlement_history", "تسویهٔ روزانهٔ گذشته", "در جداول برنامه نیست"),
        Evidence("future.gap_history", "پیشینهٔ گپ‌های شدید", "در جداول برنامه نیست"),
        Evidence("leveraged.ratio", "ضریب اهرم صندوق", "در جداول برنامه نیست"),
        Evidence("leveraged.rebalance", "سازوکار بازسازی روزانه", "در جداول برنامه نیست"),
        Evidence("bond.publisher", "ناشر اوراق", "جدولی برای اوراق بدهی در برنامه نیست"),
        Evidence("bond.coupon", "نرخ سود اسمی و دورهٔ پرداخت", "جدولی برای اوراق بدهی در برنامه نیست"),
        Evidence("bond.maturity", "سررسید اوراق", "جدولی برای اوراق بدهی در برنامه نیست"),
        Evidence("bond.rating", "رتبهٔ اعتباری ناشر", "جدولی برای اوراق بدهی در برنامه نیست"),
        Evidence("bond.collateral", "وثیقه و پشتوانه", "جدولی برای اوراق بدهی در برنامه نیست"),
        Evidence("tax.rate", "مالیات این ابزار", "نرخ مالیات به‌صورت دادهٔ بازار ذخیره نمی‌شود"),
    )
}

_STAGES: dict[str, tuple[str, str]] = {
    "fund_shape": ("ساختار صندوق", "پول را به دست چه کسی، در چه ظرفی و با چه هزینه‌ای می‌سپارم."),
    "gold_shape": ("پشتوانه و پریمیوم", "طلای فیزیکی نمی‌خرم — گواهی‌اش را؛ فاصله‌اش چقدر است."),
    "commodity_shape": ("سازوکار کالا", "تحویل، پشتوانه و طرف تعهد؛ نه فقط نمودار قیمت."),
    "option_shape": ("ساختار قرارداد", "سمت من، سررسید، و آنچه هر روز می‌سوزد."),
    "future_shape": ("اهرم و مارجین", "کوچک‌ترین حرکت مخالف چند درصد سرمایهٔ من را می‌برد."),
    "leveraged_shape": ("اهرم و مسیر", "اهرم روزشمار است؛ میانگین‌گیری ساده در آن کار نمی‌کند."),
    "bond_shape": ("ناشر و جریان نقد", "سود اسمی ادعاست؛ سود واقعی پس از تورم و مالیات تصمیم می‌گیرد."),
    "allocation_shape": ("تخصیص دارایی", "پول من کجا نشسته و در بحران چه می‌شود."),
}

#: (instrument, label, stage key, questions, question number → evidence handles)
_SPECS: tuple[tuple[InstrumentType, str, str, tuple[tuple[int, str, str, bool], ...], dict[int, list[str]]], ...] = (
    ("fund", "صندوق سرمایه‌گذاری", "fund_shape", _FUND, {
        136: ["fund.type"], 137: ["fund.manager"], 138: ["fund.size", "fund.units"],
        139: ["fund.fee"], 140: ["fund.portfolio"], 141: ["nav.value", "nav.premium_pct"],
        142: ["nav.premium_pct"], 144: ["fund.nav_history"], 145: ["fund.nav_history"],
        146: ["fund.dividend"], 147: ["tax.rate"], 148: ["fund.liquidity", "detail.base_volume"],
        149: ["fund.redemption"], 150: ["fund.track_error"], 153: ["fund.type"],
        155: ["fund.dissolution"]}),
    ("etf", "صندوق قابل‌معامله در بورس", "fund_shape", _FUND, {
        136: ["fund.type"], 137: ["fund.manager"], 138: ["fund.size", "fund.units"],
        139: ["fund.fee"], 140: ["fund.portfolio"], 141: ["nav.value", "nav.premium_pct"],
        142: ["nav.premium_pct"], 144: ["fund.nav_history"], 145: ["fund.nav_history"],
        146: ["fund.dividend"], 147: ["tax.rate"], 148: ["fund.liquidity", "detail.base_volume"],
        149: ["fund.redemption"], 150: ["fund.track_error"], 153: ["fund.type"],
        155: ["fund.dissolution"]}),
    ("commodity_fund", "صندوق کالایی یا طلا", "gold_shape", _GOLD, {
        156: ["gold.backing"], 157: ["nav.premium_pct", "nav.value"],
        158: ["gold.premium_history"], 159: ["gold.delivery"], 160: ["nav.premium_pct"],
        161: ["tax.rate"], 162: ["gold.convergence"], 163: ["fund.fee"], 164: ["gold.delivery"]}),
    ("commodity_certificate", "گواهی سپردهٔ کالایی", "commodity_shape", _COMMODITY, {
        176: ["commodity.mechanism"], 177: ["commodity.counterparty"], 178: ["commodity.mechanism"],
        179: ["commodity.spot_gap"], 180: ["commodity.warehouse"], 181: ["commodity.warehouse"],
        183: ["future.expiry"], 184: ["commodity.shock_history"], 185: ["tax.rate"],
        187: ["detail.trade_value", "detail.base_volume"]}),
    ("option", "اختیار معامله", "option_shape", _OPTION, {
        189: ["option.underlying", "option.expiry", "option.kind"],
        190: ["option.strike", "detail.price_last"],
        191: ["option.last", "option.expiry"], 192: ["option.volume", "option.spread"],
        193: ["future.margin_initial"], 194: ["option.strike"], 195: ["option.iv"],
        196: ["tax.rate"], 199: ["detail.price_last"]}),
    ("future", "قرارداد آتی", "future_shape", _FUTURE, {
        200: ["future.open_interest", "future.margin_initial"],
        201: ["future.margin_initial", "future.margin_maintenance"],
        202: ["future.gap_history", "future.margin_maintenance"],
        203: ["future.settlement_history", "future.margin_maintenance"],
        204: ["future.rollover", "future.expiry"], 205: ["future.basis", "future.expiry"],
        208: ["detail.base_volume"], 211: ["future.margin_maintenance"]}),
    ("leveraged_fund", "صندوق اهرمی", "leveraged_shape", _LEVERAGED, {
        212: ["leveraged.ratio"], 213: ["leveraged.rebalance"], 214: ["fund.nav_history"],
        215: ["leveraged.rebalance"], 217: ["nav.value", "nav.premium_pct"],
        219: ["fund.fee"]}),
    ("fixed_income", "صندوق درآمد ثابت / اوراق", "bond_shape", _FIXED_INCOME, {
        116: ["bond.publisher", "bond.rating"], 117: ["bond.coupon"],
        118: ["bond.coupon", "tax.rate"], 119: ["bond.coupon"], 120: ["bond.maturity"],
        122: ["detail.base_volume"], 123: ["bond.collateral"], 125: ["tax.rate"],
        127: ["bond.coupon", "bond.maturity"], 133: ["bond.maturity"]}),
    ("portfolio_allocation", "سطح سبد و تخصیص", "allocation_shape", _ALLOCATION, {
        221: ["detail.board"], 227: ["tax.rate"], 228: ["detail.sector"]}),
)


#: Any handle a module may surface: its own new ones plus the stock catalogue the shared
#: core stages already use.
_ANY_EVIDENCE: dict[str, Evidence] = {**bank.evidence_by_key(), **_EV}


def _question(num: int, text: str, kind: str, stopper: bool, handles: list[str]) -> Question:
    veto = _VETO.get(num) if stopper else None
    return Question(
        code=f"PB-{num:03d}",
        stage=0,  # the registry re-sequences every module stage into play order
        text=text,
        kind="yes_no_unknown" if kind == "y" else "text",
        stopper=stopper,
        veto_values=(veto,) if veto else (),
        evidence=tuple(_ANY_EVIDENCE[h] for h in handles),
    )


def build_modules() -> dict[InstrumentType, InstrumentModule]:
    """One :class:`InstrumentModule` per class the document defines and the data can name."""

    out: dict[InstrumentType, InstrumentModule] = {}
    for key, label, stage_key, block, handles_by_num in _SPECS:
        title, purpose = _STAGES[stage_key]
        stage = Stage(
            id=0, key=stage_key, title=title, purpose=purpose,
            rule="پاسخ «نمی‌دانم» در همین مرحله، رفتن به مرحلهٔ بعد را می‌بندد.",
        )
        used = {h for list_ in handles_by_num.values() for h in list_}
        out[key] = InstrumentModule(
            key=key,
            label=label,
            stages=(stage,),
            questions=tuple(
                _question(num, text, kind, stopper, handles_by_num.get(num, []))
                for num, text, kind, stopper in block
            ),
            # Core stages keep their own (stock) handles, so both catalogues must be visible.
            evidence={**bank.evidence_by_key(), **{h: _ANY_EVIDENCE[h] for h in used}},
        )
    return out


__all__ = ["build_modules"]
