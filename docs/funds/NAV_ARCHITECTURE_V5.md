# معماری جامع سامانه پرتفومحور محاسبه و تطبیق NAV صندوق‌های بورسی تهران

> نسخه: **۵.۱ — سند ادغام‌شده نهایی**
> دامنه: صندوق‌های سرمایه‌گذاری قابل معامله (ETF) و مشترک بورس تهران و فرابورس، همه انواع.
> وضعیت: معماری هدف و نقشه پیاده‌سازی؛ اعداد مقرراتی در کد ثابت نمی‌شوند و از «قواعد نسخه‌دار» می‌آیند.
> این سند حاصل ادغام سه سند قبلی + نقدهای فنی + چهار دور بررسی شکاف‌ها (بیش از ۹۰ قلم) است.
> افزوده‌های ۵.۱: AML/CFT کامل، انطباق شرعی و کمیته فقهی، ساختار واقعی کارمزد و مجمع امیدنامه‌ای، انواع ارزی/تضمین تسویه، تملک اهرمی، سپرده وکالتی، استقراض و فهرست رسمی هزینه‌ها.
> وضعیت پیاده‌سازی: `docs/funds/NAV_IMPLEMENTATION_STATUS.md` — موتور NAV مستقل + تطبیق سه‌بُعدی + پنل صفحه صندوق (فازهای ۱–۵ + اجرای سایه).

---

## فهرست

۰. اصول بنیادین
۱. دامنه و انواع صندوق
۲. اکوسیستم طرف‌ها و ارکان
۳. نمای کلان و جریان داده
۴. چرخه عملیاتی روز
۵. ماژول‌های کامل
۶. قرارداد داده
۷. مدل داده کامل + DDL
۸. دفتر مالی
۹. موتور ارزش‌گذاری
۱۰. موتور NAV
۱۱. موتور تطبیق
۱۲. رویدادهای شرکتی
۱۳. چرخه واحدها و توزیع
۱۴. انطباق و نصاب‌ها
۱۵. وثیقه، مارجین و ریپو
۱۶. شاخص، رتبه‌بندی و عملکرد
۱۷. ریسک و تحلیل
۱۸. کیفیت داده و Lineage
۱۹. رویداد و تاب‌آوری
۲۰. ذخیره‌سازی و زیرساخت
۲۱. API، داشبورد، امنیت، حسابرسی، درگاه نظارتی
۲۲. حاکمیت شرکتی و کنترل داخلی
۲۳. تعارض منافع و رفتار حرفه‌ای
۲۴. حقوقی، انتظامی و شکایات
۲۴.۱ مبارزه با پولشویی و تأمین مالی تروریسم (AML/CFT)
۲۴.۲ انطباق شرعی و کمیته فقهی
۲۵. مالیات
۲۶. چرخه عمر صندوق
۲۷. لایه معامله (اختیاری)
۲۸. آزمون‌ها و معیار پذیرش
۲۹. تداوم و بازیابی
۳۰. فازبندی پیاده‌سازی
۳۱. ضمائم

---

## ۰. اصول بنیادین

1. NAV هر صندوق فقط از «دفتر موقعیت معتبر + قیمت سیاست‌محور + تعهدات + تعداد واحدها» محاسبه می‌شود.
2. مسیر محاسبه مستقل و مسیر دریافت NAV مرجع کاملاً جدا هستند؛ لنگر انداختن به مرجع = محصول جدا با برچسب «تخمینی».
3. تحلیل رفتار (صنعت، پول، حباب، اخبار) هرگز وارد محاسبه NAV نمی‌شود.
4. هیچ پارامتر بازاری در کد hard-code نمی‌شود؛ همه در قواعد نسخه‌دار با `effective_from` و `source_document_id`.
5. هر محاسبه با `input_hash` + نسخه دفتر/قیمت/سیاست/موتور قابل بازتولید است.
6. هرجا داده واقعی نیست: `ESTIMATED / PARTIAL / BLOCKED` — نه NAV دقیق.
7. چهار زمان (`effective_at`, `published_at`, `received_at`, `recorded_at`) روی داده‌های مهم.
8. تحویل at-least-once؛ اثر تکراری با `idempotency_key` و قید یکتا؛ ادعای Exactly-once سرتاسری ممنوع.
9. دفتر مالی دوطرفه است و توازن، علامت مبالغ، عدم‌هم‌پوشانی شناسه و idempotency در DB اجبار می‌شوند.
10. سه بُعد وضعیت تطبیق (قابلیت مقایسه / اعتبار مرجع / اندازه اختلاف) هرگز در یک enum تخت نمی‌شوند.

---

## ۱. دامنه و انواع صندوق (پیامد معماری)

| نوع | دارایی‌های شاخص | مکانیک ویژه | NAV ویژه |
|---|---|---|---|
| سهامی ETF / مشترک | سهام، حق تقدم، نقد | بازارگردان، صف صدور/ابطال، توقف نماد | آماری/صدور/ابطال |
| درآمد ثابت | اوراق، سپرده، گواهی سپرده، نقد | سود تعهدی روزشمار، جریمه شکست، نسبت نظارتی اوراق | آماری/ابطال |
| مختلط | سهام + اوراق + سپرده | تفکیک اثر دو بازار | ترکیبی |
| طلا / نقره / کالایی | گواهی شمش/سکه/نقره/کالا (IME) | ضریب گواهی، حباب، انبار، تحویل فیزیکی | آماری/ابطال |
| اهرمی | سهام (حداقل ۷۰٪) + طبقات عادی/ممتاز | بازده روزشمار کف/سقف، انتقال ریالی روزانه بین طبقات، هزینه بهره، سقف ۲ برابری عادی | دو NAV طبقاتی |
| تضمین اصل سرمایه | مختلط | دو ساختار: رکن ضامن / واحد ممتاز؛ دوره نگهداری ≥ ۹۰ روز؛ FIFO؛ ذخیره کارمزد ضامن؛ جریمه تأخیر | آماری + تعهد احتمالی |
| فراصندوق (صندوق در صندوق) | واحد صندوق‌های دیگر (حداقل ۸۵٪) | سقف‌های نصاب، NAV مرکب، حلقه حلقوی | NAV از NAV |
| بخشی / شاخصی | سبد موضوعی یا ردیاب | بازتوازن، Tracking Error، Active Share | آماری |
| پوشش ریسک / اختیار | سهام + اختیار + وجه تضمین | MTM، زیان فروش، تماس مارجین | آماری با مدل مصوب |
| املاک و مستغلات | املاک، پروژه | آیین‌نامه ۱۴۰۴، ارزیاب رسمی، اجاره، درصد تکمیل | مصوب کمیته |
| زمین و ساختمان | پروژه ساختمانی | درصد تکمیل، پیش‌فروش | مصوب کمیته |
| جسورانه / خصوصی | سهام غیربورسی، سهم‌الشرکه | سرمایه تعهدشده در مقابل پرداخت‌شده (Capital Call)، عمر ۷ ساله، حداقل سرمایه‌گذاری هر سرمایه‌گذار | ارزش‌گذاری شرکتی |
| اختصاصی بازارگردانی | اوراق موضوع بازارگردانی | تعهد مظنه/انباشته/حجم، حداقل سرمایه یک‌درهزار ارزش بازار | آماری |
| نیکوکاری | طبق امیدنامه | حداقل سرمایه کاهش‌یافته | آماری |
| مختص اوراق دولتی / نوع دوم | اوراق دولت | نصاب‌های خاص | آماری |
| صندوق تضمین (قانون تأمین مالی تولید و زیرساخت) | ضمانت | کارگروه وزارت اقتصاد، صلاحیت حرفه‌ای اختصاصی | خارج از NAV سرمایه‌گذاری |
| ارزی | سپرده/دارایی ارزی، گواهی ارزی | نرخ ارز مرجع، انطباق فقهی سپرده وکالتی | آماری |
| تضمین تسویه وجوه | ضمانت تسویه | ساختار فقهی مصوب کمیته فقهی | خارج از NAV سرمایه‌گذاری |

هیچ‌یک از این انواع به فرمول واحد `quantity × price + interest` فشرده نمی‌شود؛ هر نوع Rule ارزش‌گذاری، Rule تخصیص و Rule انطباق مستقل دارد.

---

## ۲. اکوسیستم طرف‌ها و ارکان

| طرف | داده/نقش |
|---|---|
| سازمان بورس (SEO) | ضوابط، ابلاغ، مجوز، رسیدگی انتظامی، دسترسی نظارتی به نرم‌افزار صندوق |
| کدال | پرتفوی ماهانه (تا دهم ماه بعد)، صورت‌های مالی، اطلاعیه گروه الف/ب، تغییر نرخ سود یک ماه قبل |
| سنا / فیپیران | NAV اعلامی، اطلاعات صندوق، رتبه‌بندی |
| TSETMC / مرکز داده | تیک، عمق، قیمت پایانی، دامنه، حجم مبنا |
| CSDI | موجودی اوراق، ثبت واحد ETF، تسویه، مجامع، وثیقه/خروج از وثیقه واحدها |
| IME | گواهی کالا، آتی، وجه تضمین، انبار |
| کارگزاری / اتاق پایاپای | تأییدیه معامله، مانده نقد، DVP، ضمانت تسویه |
| فروشگاه صندوق / سامانه صدور-ابطال | درخواست‌ها، واحدداران مشترک |
| بازارگردان | دامنه مظنه، حداقل سفارش انباشته، حداقل معاملات روزانه، ممنوعیت هم‌جهت با صف |
| ضامن جبران اصل سرمایه | تعهد جبران، ذخیره کارمزد، جریمه تأخیر |
| ضامن نقدشوندگی | تضمین نقدشوندگی، کفایت سرمایه |
| مدیر ثبت (Transfer Agent) | ثبت واحد، انتقال، توزیع سود |
| متولی (امانیدار) | تأیید پرداخت، تطبیق روزانه بانک/CSDI/سود، نظارت |
| حسابرس (معتمد طبقه ۱/۲) | گزارش مستقل، کنترل‌های داخلی |
| مرجع ثبت شرکت‌ها | ثبت صندوق به‌عنوان شخصیت حقوقی |
| سازمان امور مالیاتی | معافیت‌ها، مالیات مقطوع، CGT، گزارش‌دهی |
| شورای پول و اعتبار | نرخ سود مصوب (منبع قاعده) |
| کارگروه صندوق تضمین (وزارت اقتصاد) | تأیید صلاحیت مدیران صندوق‌های تضمین |
| مرکز مبارزه با پولشویی و تأمین مالی تروریسم سازمان بورس | ابلاغیه‌ها، تأییدیه سامانه AML، استعلامات |
| مرکز اطلاعات مالی (FIU) | گزارش‌های مشکوک/حد نصاب/نقدی |
| کمیته فقهی سازمان بورس | تأیید شرعی ابزارها و نهادها، پاسخ به شبهات |
| سازمان برنامه و بودجه / بانک مسکن | مؤسس و متولی صندوق املاک و مستغلات دولتی (آیین‌نامه ۱۴۰۴) |
| اداره بازرسی صندوق‌ها (سازمان بورس) | نظارت بر تبلیغات و بازرسی انطباق |

---

## ۳. نمای کلان و جریان داده

```text
[منابع رسمی: TSETMC | کدال | CSDI | کارگزاری | فروشگاه صندوق | IME | API NAV | مدیر/متولی]
        │
        ├─────────────────────────────────────────────┐
        ▼ (مسیر محاسبه مستقل)                          ▼ (مسیر مرجع)
┌────────────────────────────┐                ┌────────────────────────────┐
│ Ingestion + Raw Archive    │                │ Reference NAV Adapter      │
│ (WORM، checksum، منبع)     │                │ (نوع NAV، زمان، نسخه)       │
└─────────────┬──────────────┘                └─────────────┬──────────────┘
              ▼                                             │
┌────────────────────────────┐                              │
│ Data Quality Gate          │──► قرنطینه / DLQ             │
└─────────────┬──────────────┘                              │
              ▼                                             │
┌────────────────────────────┐    ┌──────────────────────┐  │
│ Reference Master           │◄───│ Corporate Actions    │  │
│ (ابزار، صندوق، طبقات، قواعد)│    │ (سود، افزایش، حق‌تقدم)│  │
└─────────────┬──────────────┘    └──────────┬───────────┘  │
              ▼                              ▼              │
┌───────────────────────────────────────────────────────┐   │
│ Portfolio Ledger (دوطرفه) + Position/Cash + Unit Registry │
└───────────────────────────┬───────────────────────────┘   │
                            ▼                               │
┌───────────────────────────────────────────────────────┐   │
│ Point-in-Time Snapshot (دفتر + قیمت، نسخه‌دار، hash)   │   │
└───────────────────────────┬───────────────────────────┘   │
                            ▼                               │
┌───────────────────────────────────────────────────────┐   │
│ Pricing Service → Multi-Asset Valuation (+ کمیته)      │   │
└───────────────────────────┬───────────────────────────┘   │
                            ▼                               │
┌───────────────────────────────────────────────────────┐   │
│ NAV Engine (Total + Unit Classes + NAV Type)           │   │
└───────────────────────────┬───────────────────────────┘   │
                            └──────────────┬────────────────┘
                                           ▼
                         ┌─────────────────────────────────┐
                         │ Reconciliation Engine            │
                         │ ۱) گیت مقایسه‌پذیری              │
                         │ ۲) اختلاف مطلق + bps + ریشه      │
                         └───────────────┬─────────────────┘
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
   ┌───────────────────┐    ┌──────────────────────┐    ┌───────────────────┐
   │ Compliance/Breach │    │ Risk, Look-Through,  │    │ Audit Trail &     │
   │ + Fair Allocation │    │ Benchmark, Rating    │    │ Break Investigation│
   └───────────────────┘    └──────────────────────┘    └───────────────────┘
              └──────────────────────────┼──────────────────────────┘
                                         ▼
                          Disclosure/Reporting + API/Dashboard + Regulator Portal
                                         ▼
                          [اختیاری] Market Making / OMS
```

---

## ۴. چرخه عملیاتی روز

```text
T-1 شب:       قیمت پایانی رسمی، NAV رسمی روز، وضعیت صدور/ابطال
              رویدادهای شرکتی فردا، Snapshot پایانی نسخه‌دار

پیش‌بازار:    بارگذاری snapshot دیروز + رویدادها
              محاسبه قیمت مرجع روز طبق قواعد نسخه‌دار
              کنترل آمادگی فید، سهمیه API، تقویم

پیش‌گشایش:    مظنه و قیمت موازنه، تعدیل رویداد شرکتی (بازگشایی)

جلسه:         تیک/عمق → Pricing
              NAV تخمینی لحظه‌ای با ری‌محاسبه افزایشی (فقط تغییرات)
              تطبیق دوره‌ای با مرجع، هشدار حباب/واگرایی
              کنترل کیفیت دائمی (توقف، صفر، جهش، Crossed Book)
              رصد تعهدات بازارگردان و تخصیص عادلانه

پس از بسته:   NAV پایانی، تطبیق رسمی، بستن نسخه روز
              گزارش مغایرت، توزیع سود دوره‌ای، آماده‌سازی فردا
```

محاسبات سنگین در مسیر تیک اجرا نمی‌شوند؛ NAV لحظه‌ای با ری‌محاسبه افزایشی به‌روز می‌شود.

---

## ۵. ماژول‌های کامل

| ماژول | مسئولیت | خروجی |
|---|---|---|
| Instrument Master | شناسه پایدار، نگاشت TSETMC/CSDI/IME/کدال، نماد و تاریخچه، ضریب، تیک، سررسید | مرجع ابزار |
| Fund Registry | منشور/امیدنامه، طبقات، سیاست ارزش‌گذاری، کارمزدها، نسخه | پیکربندی نسخه‌دار |
| Market Rules | دامنه، تیک، حجم مبنا، فرمول قیمت پایانی، سقف سفارش | قواعد با منبع رسمی |
| Source Adapters | دریافت، Retry، سهمیه، ثبت منبع و زمان‌ها | پیام خام |
| Data Quality & Lineage | ساختار، تازگی، سازگاری، پوشش، Crossed Book، جهش | پذیرش/قرنطینه |
| Portfolio Ledger | اسناد دوطرفه، بهای تمام‌شده، تعهد کارمزد، درآمد، ذخیره کاهش ارزش | تراز و سود/زیان |
| Position & Cash | موقعیت، نقد، دریافتنی، پرداختنی، سپرده، وجه تضمین | دفتر موقعیت |
| Corporate Actions | سود، افزایش سرمایه، حق تقدم، تغییر شناسه | اعمال نسخه‌دار |
| Unit Registry / TA | واحددار، صدور/ابطال، انتقال، توثیق، ارث، مسدودی، توزیع سود | دفتر واحدها |
| Pricing Service | انتخاب قیمت طبق سیاست هر نوع دارایی | قیمت با منشأ/کیفیت |
| Valuation Engine | Rule هر نوع + کمیته ارزش‌گذاری | ارزش ردیفی |
| NAV Engine | جمع، طبقات، انواع NAV، تخصیص اهرمی/تضمین، گردکردن | NAV نسخه‌دار |
| Reconciliation | گیت، اختلاف مطلق/bps، ریشه، پرونده | نتیجه + Break |
| Compliance | نصاب‌ها، نسبت اوراق، محدودیت‌ها، پیش/پس‌معامله | Breach Register |
| Collateral & Margin | وجه تضمین، مارجین، تسویه روزانه، ریپو، وثیقه | مانده و تعهد |
| Benchmark & Index | شاخص مبنا، Tracking Error، Active Share، بازتوازن | متریک ردیابی |
| Performance & Rating | TWR/MWR، شارپ/سورتینو/ترینر/امگا/M2، درجه‌بندی ستاره، کیفیت مدیریت | کارنامه عملکرد |
| Risk & Analytics | مواجهه، تمرکز، نقدشوندگی، حباب، اعتبار، عملیاتی، استرس، VaR/CVaR | تحلیل پرتفومحور |
| Disclosure & Reporting | کدال، سنا، ابلاغ NAV، فایل روزانه سازمان، صورت مالی | گزارش رسمی |
| Event/Integration | Outbox/Inbox، Idempotency، Replay، DLQ | جریان قابل بازیابی |
| API & Dashboard | سرویس و مسیر رهگیری | خروجی قابل حسابرسی |
| Audit & Assurance | Evidence Pack، زنجیره hash، تأیید | بسته حسابرسی |
| Identity & Access | RBAC صندوقی، SoD، 2FA، دیوار آتش اطلاعاتی | کنترل دسترسی |
| Governance | کمیته‌ها، حسابرسی داخلی، کنترل داخلی، معاملات وابسته، اخلاق، ESG | سوابق حاکمیتی |
| Fair Allocation & Best Execution | تخصیص عادلانه بین پرتفوها، عرضه اولیه، معاملات عمده، مانیتورینگ معاملات معکوس | گزارش تخصیص |
| Personal Trading | پیش‌تأیید معاملات کارکنان، لیست ممنوعه، تعارض منافع | سابقه پیش‌تأیید |
| Tax | معافیت‌ها، مالیات مقطوع، CGT، سود سپرده، گزارش‌دهی | محاسبه و اظهارنامه |
| Fund Lifecycle | تأسیس، پذیره‌نویسی، تمدید، ادغام/تبدیل، انحلال/تصفیه | گردش کار چرخه عمر |
| Eligibility | صلاحیت حرفه‌ای مدیران/ارکان، کفایت سرمایه، مالکیت حداقلی | وضعیت اعتبار |
| Guarantee | رکن ضامن، واحد ممتاز، ذخیره، جبران FIFO، جریمه | تعهد احتمالی |
| Trustee Panel | تطبیق روزانه بانک/CSDI/سود، تأیید پرداخت، چک‌لیست نظارتی | گزارش متولی |
| Regulator Portal | دسترسی خواندنی نظارتی با audit کامل | نمای سازمان |
| Complaint & Legal | شکایات، سمتا، داوری، دعاوی، بیمه D&O | پرونده حقوقی |
| Disciplinary | رسیدگی انتظامی، سابقه تخلف ارکان، پاسخ به استعلام | سابقه انتظامی |
| Merger & Liquidation | ادغام، تبدیل، تصفیه، آثار مالیاتی | اسناد انتقال |
| Market Making | تعهدات بازارگردان، مظنه/انباشته/حجم، موجودی | گزارش تعهد |
| AML/CFT | شناسایی مشتری، ریسک، هشدار، سه جریان گزارش، استعلامات، نگهداری/امحای اسناد | پرونده AML و تأییدیه سامانه |
| Sharia Compliance | تأیید ابزار، فیلتر شرعی، سابقه فتوای کمیته فقهی | انطباق شرعی |
| Prospectus Assembly | مجمع امیدنامه‌ای، تغییر کارمزد/نصاب/پارامترها، نسخه امیدنامه | نسخه جدید امیدنامه |
| Borrowing & Facility | تسهیلات بانکی، تعهد و سود روزشمار | بدهی و هزینه |
| Execution (اختیاری) | OMS، رزرو، کنترل ریسک | سفارش قابل رهگیری |

---

## ۶. قرارداد داده

| بُعد | قاعده |
|---|---|
| زمان | چهار برچسب TIMESTAMPTZ؛ ذخیره UTC، نمایش Asia/Tehran؛ monotonic فقط برای فاصله |
| ارز | `currency_code` صریح (IRR/IRT/…)، همسان‌سازی ریال/تومان در مرز ورود، `fx_rate_id` برای تبدیل |
| نوع NAV | `STATISTICAL`, `ISSUANCE`, `REDEMPTION`, `CLOSING`, `ESTIMATED`, `LIQUIDATION` |
| دقت اعشاری | ریال (28,0)؛ تومان (28,2)؛ تعداد/واحد (24,6)؛ قیمت (18,6)؛ نرخ ارز (18,8)؛ bps (12,4) |
| کیفیت | `COMPLETE / ESTIMATED / PARTIAL / BLOCKED` جدا از وضعیت اجرا (`RUNNING/SUCCEEDED/FAILED`) |
| تطبیق | سه بُعد مستقل: مقایسه‌پذیری، اعتبار مرجع، اختلاف |
| شناسه | `instrument_id` پایدار + نگاشت منبع با بازه اعتبار و قید عدم‌هم‌پوشانی |
| پرتفوی | `portfolio_age_days` و منبع افشا روی هر snapshot |
| قاعده | هر عدد مقرراتی با `effective_from`، `source_document_id`، `version` |

---

## ۷. مدل داده کامل + DDL

### گروه‌های جدول

| گروه | جداول |
|---|---|
| مرجع | `funds`, `unit_classes`, `fund_charters`, `fund_prospectuses`, `instruments`, `instrument_identifiers`, `instrument_names`, `sector_classifications`, `trading_calendars` |
| قواعد | `valuation_policies`, `fee_schedules`, `market_rules_effective`, `compliance_rules_effective`, `threshold_versions`, `reference_data_config` |
| منابع | `raw_documents`, `source_events`, `data_quality_issues`, `data_lineage`, `source_slas` |
| دفتر مالی | `journal_entries`, `journal_lines`, `chart_of_accounts`, `trades`, `settlements`, `fee_accruals`, `realized_pnl`, `impairment_reserves` |
| دارایی/تعهد | `position_snapshots`, `cash_accounts`, `deposits`, `receivables`, `liabilities`, `margin_balances`, `collateral_pledges` |
| واحدها | `unit_movements`, `unit_balance_snapshots`, `unit_holders`, `unit_transfers`, `unit_pledges`, `distributions`, `distribution_entitlements` |
| بازار | `quotes`, `trade_ticks`, `orderbook_snapshots`, `official_prices`, `index_values`, `fx_rates`, `bond_ratings` |
| رویداد | `corporate_actions`, `corporate_action_applications`, `ca_pending_queue` |
| ارزش‌گذاری | `valuation_runs`, `position_valuations`, `valuation_committee_cases`, `appraisals`, `nav_results` |
| تطبیق | `api_nav_reports`, `reconciliation_runs`, `reconciliation_results`, `reconciliation_breaks`, `statement_imports`, `portfolio_drift_checks` |
| انطباق | `compliance_checks`, `compliance_breaches`, `fair_allocation_reviews`, `personal_trading_requests`, `aml_customers`, `aml_risk_assessments`, `aml_alerts`, `aml_str_reports`, `aml_threshold_reports`, `aml_cash_reports`, `aml_inquiries`, `aml_document_retention`, `sharia_approvals`, `sharia_filters` |
| تضمین/اهرم | `guarantee_contracts`, `guarantee_reserves`, `class_allocation_runs`, `leverage_rates_effective` |
| حاکمیت | `governance_committees`, `internal_audit_reports`, `internal_control_reports`, `related_party_transactions`, `regulator_access_logs` |
| چرخه عمر | `fund_lifecycle_events`, `merger_plans`, `liquidation_plans`, `capital_commitments`, `capital_calls`, `prospectus_versions`, `prospectus_assemblies`, `borrowings`, `facility_contracts` |
| مالیات | `tax_exemptions`, `tax_calculations`, `tax_reports`, `cgt_records` |
| حقوقی | `complaints`, `disciplinary_cases`, `legal_claims`, `arbitration_cases` |
| کنترل | `audit_events` (append-only + hash chain), `approval_requests`, `inbox_events`, `outbox_events`, `dead_letter_queue`, `migration_batches`, `opening_balances` |

### DDL جداول بحرانی (اصلاح‌شده)

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE funds (
    fund_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_type       VARCHAR(32) NOT NULL, -- EQUITY, FIXED_INCOME, MIXED, GOLD, LEVERAGED,
                                          -- GUARANTEED, FOF, SECTOR, INDEX, OPTION, REAL_ESTATE,
                                          -- VC_PE, MARKET_MAKING, CHARITY, GOV_BOND
    legal_name      VARCHAR(256) NOT NULL,
    national_id     VARCHAR(16),
    status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    inception_date  DATE,
    maturity_date   DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE unit_classes (
    unit_class_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id         UUID NOT NULL REFERENCES funds(fund_id),
    class_code      VARCHAR(16) NOT NULL, -- ORDINARY, PREFERRED, PREFERRED_SPECIAL
    nav_type        VARCHAR(16) NOT NULL, -- STATISTICAL/ISSUANCE/REDEMPTION
    fee_profile     JSONB,
    allocation_rule JSONB,                -- فقط از امیدنامه نسخه‌دار
    UNIQUE (fund_id, class_code)
);

CREATE TABLE instruments (
    instrument_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_type VARCHAR(24) NOT NULL,  -- EQUITY, RIGHT, BOND, DEPOSIT, CERTIFICATE,
                                           -- ETF, OPTION, FUTURE, FUND_UNIT, PROPERTY
    currency_code   CHAR(3) NOT NULL,
    contract_size   NUMERIC(18,6) NOT NULL DEFAULT 1,
    underlying_id   UUID REFERENCES instruments(instrument_id),
    strike          NUMERIC(18,6),
    option_type     VARCHAR(4),
    expiry_at       TIMESTAMPTZ,
    maturity_date   DATE,
    valid_from      TIMESTAMPTZ NOT NULL,
    valid_to        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE instrument_identifiers (
    identifier_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id    UUID NOT NULL REFERENCES instruments(instrument_id),
    id_type          VARCHAR(16) NOT NULL,   -- TSETMC_ID, ISIN, TICKER, CSDI_ID, IME_ID
    identifier_value VARCHAR(64) NOT NULL,
    valid_from       TIMESTAMPTZ NOT NULL,
    valid_to         TIMESTAMPTZ,
    source_system    VARCHAR(32),
    EXCLUDE USING gist (
        id_type WITH =, identifier_value WITH =,
        tstzrange(valid_from, valid_to, '[)') WITH &&
    )
);

CREATE TABLE journal_entries (
    entry_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id           UUID NOT NULL REFERENCES funds(fund_id),
    event_type        VARCHAR(32) NOT NULL,  -- TRADE_BUY, TRADE_SELL, SETTLEMENT, DIVIDEND,
                                             -- FEE_ACCRUAL, UNITS_ISSUE, UNITS_REDEEM,
                                             -- DISTRIBUTION, CORP_ACTION, FX_REVAL,
                                             -- IMPAIRMENT, GUARANTEE_RESERVE
    status            VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
    effective_at      TIMESTAMPTZ NOT NULL,
    published_at      TIMESTAMPTZ,
    received_at       TIMESTAMPTZ,
    recorded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_system     VARCHAR(32),
    source_ref_id     VARCHAR(128),
    reverses_entry_id UUID REFERENCES journal_entries(entry_id),
    idempotency_key   VARCHAR(128) NOT NULL,
    UNIQUE (idempotency_key),
    UNIQUE (source_system, source_ref_id)
);

CREATE TABLE journal_lines (
    line_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id        UUID NOT NULL REFERENCES journal_entries(entry_id),
    account_code    VARCHAR(32) NOT NULL REFERENCES chart_of_accounts(account_code),
    instrument_id   UUID REFERENCES instruments(instrument_id),
    currency_code   CHAR(3) NOT NULL,
    debit_amount    NUMERIC(28,2) NOT NULL DEFAULT 0,
    credit_amount   NUMERIC(28,2) NOT NULL DEFAULT 0,
    quantity_delta  NUMERIC(24,6) NOT NULL DEFAULT 0,
    CONSTRAINT amount_sign CHECK (
        debit_amount >= 0 AND credit_amount >= 0
        AND NOT (debit_amount > 0 AND credit_amount > 0))
);
-- Constraint Trigger تعویق‌شده: SUM(debit)=SUM(credit) برای هر entry در commit

CREATE TABLE nav_results (
    nav_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID NOT NULL REFERENCES valuation_runs(run_id),
    fund_id           UUID NOT NULL REFERENCES funds(fund_id),
    unit_class_id     UUID NOT NULL REFERENCES unit_classes(unit_class_id),
    nav_type          VARCHAR(16) NOT NULL,
    valuation_at      TIMESTAMPTZ NOT NULL,
    net_assets        NUMERIC(28,2) NOT NULL,
    outstanding_units NUMERIC(24,6) NOT NULL CHECK (outstanding_units > 0),
    nav_per_unit      NUMERIC(28,2) NOT NULL,
    rounding_policy   VARCHAR(32) NOT NULL,
    quality_status    VARCHAR(16) NOT NULL,
    approved_by       UUID,
    approved_at       TIMESTAMPTZ,
    UNIQUE (run_id, unit_class_id, nav_type)
);

CREATE TABLE valuation_runs (
    run_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id            UUID NOT NULL REFERENCES funds(fund_id),
    valuation_at       TIMESTAMPTZ NOT NULL,
    knowledge_cutoff_at TIMESTAMPTZ NOT NULL,
    ledger_snapshot_id UUID,
    price_snapshot_id  UUID,
    policy_version     VARCHAR(32) NOT NULL,
    engine_version     VARCHAR(32) NOT NULL,
    input_hash         CHAR(64) NOT NULL,
    run_status         VARCHAR(16) NOT NULL,  -- RUNNING/SUCCEEDED/FAILED
    quality_status     VARCHAR(16) NOT NULL,  -- COMPLETE/ESTIMATED/PARTIAL/BLOCKED
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reconciliation_runs (
    recon_run_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id              UUID NOT NULL REFERENCES funds(fund_id),
    unit_class_id        UUID NOT NULL,
    nav_type             VARCHAR(16) NOT NULL,
    valuation_at         TIMESTAMPTZ NOT NULL,
    reference_id         UUID REFERENCES api_nav_reports(report_id),
    comparability_status VARCHAR(16) NOT NULL, -- COMPARABLE/NOT_COMPARABLE/INCOMPLETE
    reference_status     VARCHAR(12) NOT NULL, -- VALID/STALE/INVALID
    diff_status          VARCHAR(12),          -- MATCHED/WARNING/BREACH
    abs_diff             NUMERIC(28,2),
    bps_diff             NUMERIC(12,4),
    threshold_version    VARCHAR(32),
    residual_unexplained NUMERIC(28,2),
    probable_cause       JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reconciliation_breaks (
    break_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recon_run_id UUID NOT NULL REFERENCES reconciliation_runs(recon_run_id),
    lifecycle    VARCHAR(16) NOT NULL DEFAULT 'OPEN',
    owner_id     UUID REFERENCES users(user_id),
    opened_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at  TIMESTAMPTZ,
    sla_due_at   TIMESTAMPTZ,
    evidence     JSONB,
    notes        TEXT
);
```

**ایندکس‌های الزامی:** `journal_entries(fund_id, effective_at)`، `journal_lines(entry_id)`، `journal_lines(instrument_id)`، `nav_results(fund_id, valuation_at)`، `reconciliation_runs(fund_id, valuation_at)`. پارتیشن‌بندی `journal_lines` و تیک‌ها بر اساس تاریخ.

---

## ۸. دفتر مالی

**کدینگ:** دارایی‌ها (نقد/بانک، سپرده، دریافتنی کارگزار، دریافتنی سود سهام، سرمایه‌گذاری به تفکیک نوع، وجه تضمین، مشتقه، وثیقه)، بدهی‌ها (پرداختنی کارگزار، کارمزد پرداختنی، تعهد مشتقه، سود تقسیمی پرداختنی، ذخیره تضمین)، حقوق واحدها (سرمایه اسمی، اندوخته قانونی، **اندوخته غیرقابل تقسیم**، سود انباشته، تفاوت ارزش)، درآمد/هزینه.

**سیاست‌های الزامی نسخه‌دار:**

| سیاست | تصمیم صریح |
|---|---|
| مبنای شناسایی | تاریخ معامله + مطالبات/بدهی تسویه |
| بهای تمام‌شده | میانگین موزون یا FIFO — انتخاب صندوق |
| کارمزد ارکان | **چندجزئی و نسخه‌دار از امیدنامه:** مدیر (درصدی از سهام و حق تقدم + اوراق + سود سپرده + درآمد تعهدپذیره‌نویسی)، متولی (یک‌درهزار با کف و سقف ریالی)، ضامن نقدشوندگی، حسابرس، مدیر ثبت، ثبت و نظارت سازمان، نرم‌افزار/تارنما، رتبه‌بندی — تعهد روزشمار ۳۶۵ |
| کارمزد صدور/ابطال | صدور: ثابت به‌ازای هر گواهی + متغیر؛ ابطال: ثابت + **متغیر پله‌ای بر اساس مدت نگهداری** (Contingent Redemption Fee) طبق جدول امیدنامه |
| تسهیلات بانکی | سود روزشمار، تعهد در بدهی‌ها |
| سود اوراق/سپرده | تعهدی با Day-Count قرارداد |
| سود سهام | تاریخ تصویب مجمع یا Ex-Date — قابل پیکربندی |
| سود تقسیمی صندوق | کاهش NAV + بدهی به واحدداران در تاریخ استحقاق |
| ذخیره کاهش ارزش | برای غیربورسی/غیرفعال، با کمیته و مستند |
| اندوخته غیرقابل تقسیم | انتقال سود واگذاری طبق استاندارد ۱۵ بند ۵۷ |
| گردکردن | فقط در نقاط پایانی سیاست + سیاست رقیق‌سازی صدور/ابطال |
| تعهد احتمالی تضمین | ذخیره و افشا، جدا از NAV طبقات |

**کنترل‌های اجباری:** توازن سند، عدم ثبت تکراری، تطبیق نقد با بانک/کارگزار، تطبیق موقعیت با CSDI/متولی، اصلاح با سند برگشتی (نه حذف)، موجودی افتتاحیه با منبع و تأیید، تفکیک ثبت/تأیید/تسویه، تأیید دومرحله‌ای پرداخت (مدیر + متولی).

---

## ۹. موتور ارزش‌گذاری

| دارایی | قیمت/روش | کنترل ایران |
|---|---|---|
| سهام | قیمت پایانی رسمی طبق سیاست؛ توقف: قیمت نظری/مدل/Haircut | حجم مبنا، صف، دامنه، بازگشایی پس از مجمع |
| حق تقدم | قیمت تابلو حق تقدم، جدا از مادر | مهلت، حق استفاده‌نشده، تعهد پرداخت |
| اوراق بدهی | Clean + سود متعلقه یا Dirty (پیکربندی) | رتبه اعتباری، نکول، جلوگیری دوباره‌شماری سود |
| سپرده | اصل + سود تعهدی قرارداد | نرخ مصوب، روزشمار، جریمه شکست |
| گواهی کالا | قیمت IME × ضریب ابزار | حباب، انبار، عیار، تحویل فیزیکی |
| ETF داخلی | قیمت تابلو (حسابداری)؛ Look-through فقط تحلیل | عدم جمع دوباره با زیرین |
| صندوق دیگر (FOF) | NAV نسخه‌دار زیرصندوق + کنترل تازگی | کشف حلقه حلقوی، کارمزد مضاعف |
| اختیار | بازار یا مدل مصوب نسخه‌دار | ضریب، زیان فروش، وجه تضمین |
| آتی | MTM روزانه؛ فقط تغییرات در NAV | ارزش اسمی ≠ NAV |
| وجه تضمین | مانده بلوکه/قابل برداشت | تفکیک مسدودی از هزینه |
| املاک/پروژه | ارزیاب رسمی + کمیته؛ اجاره؛ درصد تکمیل | مستند، نسخه‌دار، تأیید دومرحله‌ای |
| جسورانه/خصوصی | ارزش‌گذاری شرکتی مصوب کمیته | سرمایه تعهدشده، Capital Call |
| ارز | نرخ مرجع اعلام‌شده سیاست | تجدید ارزیابی ارزی |
| مطالبات/بدهی | مبلغ شناسایی، احتمال وصول، ذخیره | عدم دوباره‌شماری با موقعیت |

**سه خروجی هم‌زمان:** NAV حسابداری (سیاست مصوب)، NAV تخمینی لحظه‌ای (با عدم‌قطعیت)، ارزش نقدشوندگی/سناریوی خروج (عمق، هزینه، محدودیت فروش).

**خروجی هر ردیف:** شناسه ابزار/موقعیت، تعداد و منبع، قیمت و زمان، ارز و ضریب، روش و نسخه مدل، سود تعلق‌گرفته، ارزش نهایی، کیفیت داده، شناسه مدارک.

---

## ۱۰. موتور NAV

```text
NetAssets = Σ FairValue + OtherAssets − Liabilities − AccruedFees − GuaranteeReserve
NAV_unit  = NetAssets / OutstandingUnits
NAV_c     = AllocatedNetAssets_c / Units_c
```

**انواع NAV:** `STATISTICAL`, `ISSUANCE` (NAV + کارمزد صدور), `REDEMPTION` (NAV − کارمزد ابطال), `CLOSING`, `ESTIMATED`, `LIQUIDATION`.

**اهرمی — الگوریتم روزانه:** بازده روزشمار سالانه‌شده صندوق با کف و سقف امیدنامه مقایسه می‌شود؛ کسری زیر کف از ممتاز به عادی و مازاد بالای سقف از عادی به ممتاز منتقل می‌شود؛ هزینه بهره روزانه ممتاز؛ سقف ۲ برابری عادی نسبت به ممتاز؛ تغییر نرخ فقط با اعلام یک ماه قبل در کدال و نسخه جدید در `leverage_rates_effective`.

**تضمین اصل سرمایه:** دو ساختار (رکن ضامن / واحد ممتاز)؛ دوره نگهداری؛ جبران FIFO هنگام ابطال؛ ذخیره کارمزد ضامن؛ واریز تکمیلی حداکثر ۳ روز کاری؛ جریمه تأخیر روزانه؛ تعهد به‌عنوان تعهد احتمالی جدا از NAV طبقات.

**فراصندوق:** NAV از NAV زیرصندوق‌های دارای مجوز؛ کنترل نسخه و تازگی NAV هر زیرصندوق؛ کشف حلقه حلقوی؛ سقف‌های نصاب.

**قرارداد بازتولید هر اجرا:** `valuation_run_id`, `fund_id`, `unit_class_id`, `nav_type`, `valuation_at`, `knowledge_cutoff_at`, `ledger_snapshot_id`, `price_snapshot_id`, `policy_version`, `engine_version`, `input_hash`, `quality_status`.

قواعد عمومی ممنوع: «NAV ممتاز = کل − تعهد عادی» یا «نسبت ۱٫۲۰ یعنی توقف» بدون سند همان صندوق. گردکردن فقط در پایان.

---

## ۱۱. موتور تطبیق

**مرحله ۱ — گیت‌های قابلیت مقایسه:** صندوق، طبقه واحد، نوع NAV، ارز/واحد (ریال/تومان)، زمان و knowledge cutoff، مبنای قیمت، نقطه زمانی واحدها، کامل‌بودن داخلی، اعتبار و تازگی مرجع.

**مرحله ۲ — محاسبه:**

```text
ΔNAV = NAV_internal − NAV_reference
bps  = ΔNAV / NAV_reference × 10000        (فقط اگر NAV_reference > 0)
```

**سه بُعد مستقل وضعیت:**

| بُعد | مقادیر |
|---|---|
| مقایسه‌پذیری | `COMPARABLE` / `NOT_COMPARABLE` / `INCOMPLETE` |
| اعتبار مرجع | `VALID` / `STALE` / `INVALID` |
| اختلاف | `MATCHED` / `WARNING` / `BREACH` |

**آستانه دوگانه (نه ثابت):** `|ΔNAV مطلق|` + `|bps|`، هر دو با نسخه و کالیبراسیون از توزیع تاریخی همان صندوق/نوع NAV. مقایسه روی مقدار گردنشده. `NAV_reference ≤ 0` → `INVALID_REFERENCE`.

**ریشه‌یابی:** با فقط یک عدد NAV از API، علت قطعی ممکن نیست → `probable_cause` + `residual_unexplained` جدا. چرخه Break: `OPEN → TRIAGED → INVESTIGATING → RESOLVED/ACCEPTED/ESCALATED` با مالک، SLA و شواهد. Restatement مرجع → نسخه جدید و بازتطبیق خودکار.

**علت‌های رایج ایران:** تفاوت زمان، نوع NAV، ریال/تومان، سود مجمع ثبت‌نشده، تسویه در راه، قیمت نماد متوقف، تأخیر اعمال صدور/ابطال، تفاوت فرمول سود اوراق/سپرده، حباب ETF داخلی، تأخیر NAV زیرصندوق، خطای منبع API.

---

## ۱۲. رویدادهای شرکتی

| رویداد | اثر دفتری | کنترل |
|---|---|---|
| سود نقدی | دریافتنی/نقد، درآمد | تاریخ تصویب/Ex، مالیات، ذخیره وصول |
| افزایش سرمایه از آورده | حق تقدم، تعهد پرداخت، افزایش تعداد | تأیید پرداخت |
| از سود انباشته | تغییر تعداد/قیمت، بدون اثر NAV | تعدیل قیمت پایه |
| تجدید ارزیابی | بدون اثر NAV | عدم شناسایی سود |
| حق تقدم استفاده‌نشده | فروش و دریافتنی | پیگیری تا تسویه |
| کاهش سرمایه | بازپرداخت/کاهش اسمی | تأیید مجمع |
| تغییر نماد/شناسه | نگاشت تاریخچه‌دار | جلوگیری از ابزار تکراری |
| تقسیم سود صندوق | بدهی به واحدداران، کاهش NAV | تاریخ استحقاق |
| ادغام/تفکیک | تبدیل واحدها | نسبت تبدیل مستند |
| تبدیل گواهی به کالا | تغییر نوع دارایی | رسید انبار |

هر رویداد باید `corporate_action_applications` با موقعیت، تاریخ اثر، مقدار، منبع و تأیید داشته باشد.

---

## ۱۳. چرخه واحدها و توزیع

- **ETF:** سبد صدور/ابطال (نقدی/فیزیکی طبق سند)، حداقل بسته، کارمزد، بازارگردان، تسویه T+X، ثبت CSDI.
- **مشترک:** درخواست در سامانه/فروشگاه، Cutoff، NAV صدور/ابطال (روز بعد از ثبت)، واحد اعشاری.
- **اهرمی:** عادی صدور/ابطال، ممتاز تابلویی، تخصیص روزانه.
- **تضمین:** عادی مشمول تضمین پس از دوره نگهداری، ممتاز/ضامن تأمین‌کننده.
- **توزیع سود:** تاریخ استحقاق، کاهش NAV، پرداخت ماهانه/دوره‌ای، عدم دوباره‌شماری با درآمد.
- **توثیق/ارث/مسدودی:** چرخه CSDI و انطباق روزانه با دفتر واحدها.
- **کارمزد ابطال پله‌ای بر اساس مدت نگهداری** و تخفیف‌های امیدنامه.
- **پنجره ابطال/تعلیق:** مدیریت فشار نقدشوندگی و ابطال انبوه.

---

## ۱۴. انطباق و نصاب‌ها

قواعد از `compliance_rules_effective`: حداقل درصد دارایی در سهام/اوراق بر حسب نوع صندوق (مثلاً اهرمی حداقل ۷۰٪ سهام)، سقف ناشر/صنعت، سقف واحد صندوق‌های دیگر (FOF: حداقل ۸۵٪ در صندوق‌ها، سقف ۵۰٪ درآمد ثابت، ۲۵٪ یک صندوق، ۳۰٪ از واحدهای یک صندوق، ۵۰٪ هم‌مدیر، ۱۵٪ سپرده)، محدودیت مشتقه، **نسبت مانده اوراق به دارایی صندوق‌های درآمد ثابت** (گزارش ماهانه)، ممنوعیت فعالیت خارج از مجوز. کنترل پیش‌معامله (مسدودسازی) و پس‌معامله (Breach Register). هیچ عددی در کد نیست. **تبلیغات:** ممنوعیت عبارات گمراه‌کننده (بازدهی پایدار، تضمین نرخ سود، بدون ریسک، سود قطعی، نرخ سود مؤثر و مشابه)، الزام درج ریسک، و کنترل محتوای تبلیغات پذیره‌نویسی؛ **حساب پذیره‌نویسی تا صدور مجوز فعالیت قفل است** و عدم شروع در مهلت به لغو مجوز و الزام انحلال می‌انجامد.

---

## ۱۵. وثیقه، مارجین و ریپو

وجه تضمین اولیه/نگهداری، Variation Margin روزانه، تماس مارجین، تفکیک مسدود/قابل برداشت، **توافق بازخرید (ریپو) اوراق دولتی** به‌عنوان ابزار تأمین نقد و وثیقه، توثیق دارایی‌های صندوق با تأیید ارکان، **استقراض/تسهیلات بانکی** با سود روزشمار و ثبت در بدهی‌ها، ثبت در دفتر به‌عنوان دارایی/تعهد.

---

## ۱۶. شاخص، رتبه‌بندی و عملکرد

- شاخص مبنا (TEDPIX/هموزن/صنعت)، Tracking Error، Active Share، بازتوازن.
- سنجه‌های عملکرد: TWR، MWR/IRR، بازدهی سالانه‌شده، Rolling؛ شارپ، سورتینو، ترینر، امگا، M2، آلفا، اطلاعات.
- **درجه‌بندی عملکرد ۱ تا ۵ ستاره** و **رتبه‌بندی کیفیت مدیریت** با تعدیل‌های تمرکز دارایی، نقدشوندگی، تمرکز مالکان.
- مقایسه با گروه همتا و گزارش دوره‌ای به سرمایه‌گذار.

---

## ۱۷. ریسک و تحلیل

مواجهه صنعتی، تمرکز (Top5/10، HHI)، نقدشوندگی نسبت به حجم/عمق، سناریوی خروج، حباب/پریمیوم با نوع NAV درست، تفکیک اثر قیمت/معامله/درآمد، Look-through فقط برای تحلیل.
ریسک‌های مکمل: اعتباری اوراق (رتبه/نکول)، نرخ بهره (Duration)، ارزی، عملیاتی، انطباق، حقوقی/شهرت، تمرکز واحددار، **تست استرس و ابطال انبوه، VaR/CVaR**.
تمایزها: وزن صنعت ≠ بتا؛ اسپرد مظنه ≠ Effective Spread؛ خرید حقیقی ≠ ورود پول نهادی.

---

## ۱۸. کیفیت داده و Lineage

کنترل‌ها: جهش غیرعادی، صفر/منفی، Crossed Book، تیک خارج دامنه، ترتیب زمانی، نگاشت نماد، تعدیل رویداد، ریال/تومان، جهش NAV مرجع، تازگی پرتفوی (`portfolio_age_days`)، پوشش قیمت، سهم قیمت مدل‌شده، تازگی NAV زیرصندوق (FOF). تطبیق دوره‌ای **پرتفوی افشاشده کدال با دفتر داخلی** (`portfolio_drift_checks`). Lineage کامل تا پاسخ خام.

---

## ۱۹. رویداد و تاب‌آوری

Outbox هم‌تراکنش با commit، at-least-once، `idempotency_key` + قید یکتا، Partition بر `fund_id`، داده دیررس → نسخه اصلاحی، Backoff+Jitter، DLQ، NAD، Replay، Shadow Accounting. Redis Streams با Consumer Group و PEL (نه Pub/Sub)؛ قفل مشورتی Postgres یا Fencing Token (نه Redlock)؛ ممنوعیت `allkeys-lru` برای داده حیاتی.

---

## ۲۰. ذخیره‌سازی و زیرساخت

| ذخیره‌ساز | کاربرد | نکته |
|---|---|---|
| PostgreSQL 16 | دفتر، قواعد، NAV، واحدها، انطباق | تراکنش، قید، ایندکس، پارتیشن، پشتیبان |
| TimescaleDB | تیک، عمق، OHLCV، متریک | Hypertable، refresh هماهنگ با retention |
| Redis | کش، سهمیه، Streams | TTL مشخص، بازیابی PEL |
| Object Storage | آرشیو خام WORM | Object Lock + checksum + timestamp |

```text
Clients → Nginx/Envoy → Core Service (FastAPI یا Go — یکی، نه هر دو)
                              ├── PostgreSQL 16 (+ TimescaleDB در همان instance)
                              ├── Redis (Streams + Cache + Rate Limit)
                              ├── Async Workers (Ingestion, Valuation, NAV, Recon, Tax, Rating)
                              ├── Object Storage (WORM)
                              └── Regulator Portal (read-only, audit-logged)
+ Secret Manager | Observability | Scheduler | Backup/DR | NTP | امنیت سایبری/برون‌سپاری
```

---

## ۲۱. API، داشبورد، امنیت، حسابرسی، درگاه نظارتی

- API: NAV جاری/تاریخی، ردیف‌های ارزش‌گذاری، NAV مرجع، تطبیق و Breakها، کیفیت/سن، مواجهه/ریسک، انطباق، عملکرد/رتبه، تعهدات بازارگردان، Evidence Pack.
- مسیر رهگیری: NAV → طبقه → موقعیت → تعداد/قیمت/قاعده → سند یا پاسخ خام.
- امنیت: RBAC صندوقی، SoD (سازنده/تأییدکننده)، 2FA، Secret Manager، عدم انتشار پورت DB/Redis، WS احرازهویت‌شده با توالی و snapshot، آزمون نفوذ.
- حسابرسی: `audit_events` append-only با زنجیره hash؛ نسخه‌بندی کامل خروجی.
- درگاه نظارتی: دسترسی خواندنی سازمان با ثبت کامل رخداد (الزام دسترسی نمایش اطلاعات نرم‌افزار).

---

## ۲۲. حاکمیت شرکتی و کنترل داخلی

- کمیته حسابرسی، کمیته انتصابات، کمیته ریسک با اکثریت عضو مستقل.
- واحد حسابرسی داخلی مستقل و گزارش سه‌ماهه به هیئت‌مدیره.
- گزارش سالانه کنترل‌های داخلی با اظهارنظر حسابرس.
- تصویب و افشای معاملات بااهمیت با اشخاص وابسته.
- منشور اخلاقی، کنترل اطلاعات نهانی، سوت‌زنی.
- شرایط ترهین/توثیق اموال، گزارش پایداری (ESG)، گزارش تفسیری مدیریت.

---

## ۲۳. تعارض منافع و رفتار حرفه‌ای

- **معاملات شخصی کارکنان:** پیش‌تأیید، لیست ممنوعه/تماشا، دوره نگهداری حداقلی، دیوار آتش اطلاعاتی.
- **تخصیص عادلانه معاملات بین پرتفوها/صندوق‌های هم‌مدیر:** قیمت اولویت‌دار، تخصیص نسبی، مانیتورینگ معاملات معکوس، گزارش دوره‌ای.
- **Best Execution** و مستندسازی انتخاب بازار/زمان.
- **عرضه اولیه و معاملات عمده:** تخصیص عادلانه، سوابق سفارش، جلوگیری از سود شخصی.
- **معاملات متقابل بین صندوق‌ها** فقط با رویه مصوب و قیمت منصفانه.

---

## ۲۴. حقوقی، انتظامی و شکایات

- صلاحیت حرفه‌ای مدیران نهادهای مالی (کمیته، شرایط، سلب، آموزش مستمر).
- رسیدگی انتظامی به تخلفات ارکان صندوق (مدیر، متولی، حسابرس، ضامن، مدیر ثبت) و سابقه تخلف.
- شکایات: سامانه سازمان (سمتا/سامانه جدید)، کمیته سازش کانون، هیئت داوری؛ مهلت و کد رهگیری.
- مسئولیت مدنی مؤسسین/مدیران و بیمه مسئولیت حرفه‌ای (D&O).
- دعاوی، احکام، و ثبت در بسته حسابرسی.

---

## ۲۴.۱ مبارزه با پولشویی و تأمین مالی تروریسم (AML/CFT)

- نهاد ناظر اختصاصی: مرکز مبارزه با پولشویی و تأمین مالی تروریسم سازمان بورس؛ صندوق‌ها «شخص مشمول» سطح ۳.
- شش دستورالعمل بازار سرمایه: شناسایی مشتریان، گزارش عملیات مشکوک، خدمات الکترونیک، مراقبت از اشخاص مظنون، ارسال اسناد، **نگهداری و امحای اسناد**.
- سه جریان گزارش با مهلت مستقل:
  1. معاملات/عملیات مشکوک → حداکثر پایان همان روز کاری، بدون اطلاع ارباب‌رجوع (ماده ۱۳۵).
  2. تراکنش‌های بیش از حد نصاب → طبق قالب مرکز (ماده ۱۳۷).
  3. تعاملات نقدی بیش از ۱۰٬۰۰۰ یورو یا ۱ میلیارد ریال، **تجمیعی** → خلاصه هفتگی (ماده ۱۳۹).
- صف استعلامات مرکز با پاسخ حداکثر یک روز کاری (تبصره ۲ ماده ۱۳۵).
- سامانه AML باید پیش از بهره‌برداری تأییدیه سازمان را بگیرد؛ الزامات فنی/زیرساختی برای سطح یک.
- طبقه‌بندی ریسک مشتری، شناسایی ذی‌نفع واقعی، فهرست‌های ابلاغی، عایق‌بندی وضعیت «گزارش‌شده» از هر کانال قابل‌مشاهده مشتری، ثبت تلاش‌های ناموفق، و نگهداری/امحای اسناد.
- خروجی: پرونده AML قابل ارائه به مرکز، داشبورد هشدار، سابقه رسیدگی.

---

## ۲۴.۲ انطباق شرعی و کمیته فقهی

- کمیته فقهی سازمان بورس مرجع تأیید ابزارها و نهادهاست؛ هر ابزار جدید باید سابقه تأیید فقهی نسخه‌دار داشته باشد.
- الزامات: نبود ربا و فعالیت حرام در بستر سرمایه‌گذاری؛ تفکیک احکام **سپرده وکالتی** از قرض؛ احکام بیع/وکالت/اجاره در صکوک.
- مرجع مقایسه بین‌المللی: استاندارد شرعی AAOIFI (از جمله استاندارد ۱۷ صکوک).
- ماژول: `sharia_approvals` برای هر ابزار/عملیات، فیلتر شرعی، گزارش انطباق و پرونده شبهات.

---

## ۲۵. مالیات

- **معافیت تبصره ۱ ماده ۱۴۳ مکرر:** کل درآمد صندوق، سود سپرده بانکی، صدور/ابطال — معاف از مالیات بر درآمد و ارزش افزوده.
- **مالیات مقطوع ۰.۵٪ نقل و انتقال سهام و حق تقدم** به‌عنوان هزینه معاملاتی؛ وضعیت واحدهای صندوق نیازمند تعیین تکلیف مستند.
- **CGT:** معافیت انتقال اوراق/کالا در بورس؛ تکالیف اطلاعاتی/گزارشی نهادهای مالی.
- مالیات ادغام (انتقال به ارزش دفتری، مازاد مشمول)، مالیات انحلال، گزارش‌دهی و اظهارنامه.
- **معافیت بازارگردان (تبصره ۵ ماده ۱۴۳ مکرر):** نقل و انتقال اوراق بازارگردانی بازارگردان مجاز، معاف از مالیات مقطوع ۰.۵٪.
- **گواهی سپرده کالایی:** سپرده‌گذاری کالا فروش نیست؛ معاملات میانی مشمول معافیت؛ خریدار نهایی هنگام تحویل کالا مشمول؛ فروش کالای پذیرفته‌شده در بورس کالا با نرخ صفر.
- **سود نقدی شرکت‌ها:** کسر ۱۰٪ توسط ناشر (نیازمند تعیین تکلیف برای صندوق معاف).
- **صندوق املاک دولتی:** معاملات صندوق طبق تبصره ۱ ماده ۵ قانون جهش تولید مسکن معاف.
- **تکلیف کارگزار:** وصول و واریز مالیات ۰.۵٪ و ارسال فهرست معاملات ظرف ۱۰ روز.

---

## ۲۶. چرخه عمر صندوق

تأسیس (موافقت اصولی، ثبت نهاد مالی، پذیره‌نویسی، مجوز فعالیت) → فعالیت → تمدید (شرایط: عدم نقض مجوز، حداقل سرمایه، نصاب، کفایت سرمایه ضامن/بازارگردان، مالکیت واحد مدیر، تارنمای به‌روز) → ادغام/تبدیل (با آثار مالیاتی) → انحلال و تصفیه و توزیع نهایی.

**مجمع امیدنامه‌ای** مرجع تغییر پارامترهای صندوق است: کارمزدها (مدیر، متولی، حسابرس، ضامن نقدشوندگی، رتبه‌بندی، نرم‌افزار)، نصاب ترکیب دارایی، سقف صندوق، پارامترهای بازارگردانی، نمادهای تحت بازارگردانی، محل اقامتگاه، متولی/حسابرس. هر تغییر، نسخه جدید امیدنامه و قواعد نسخه‌دار می‌سازد.

**برنامه هفتم توسعه:** الزام عرضه پروژه‌ها، اوراق بدهی ارزی/ریالی، گواهی سپرده مدت‌دار خاص، شفافیت معاملات اشخاص وابسته، گزارش شش‌ماهه ترکیب سهامداران دارای حق رأی، مقابله با سهامداری هرمی و شناسایی ذی‌نفع واحد، و مشوق تجدید ارزیابی دارایی‌ها.

---

## ۲۷. لایه معامله (اختیاری)

`تحلیل → پیشنهاد → ریسک مستقل → رزرو اتمیک → تأیید → ارسال → پیگیری → ثبت`. قواعد نماد از `market_rules_effective`، جلوگیری سفارش تکراری، کلید توقف اضطراری، تطبیق با کارگزار پس از قطعی. TWAP/Iceberg فقط با مدیریت اجرای جزئی. بازارگردانی الگوریتمی با کنترل منابع و تعهدات.

---

## ۲۸. آزمون‌ها و معیار پذیرش

حسابداری (توازن، تسویه در راه، عدم دوباره‌شماری، ذخیره کاهش ارزش)، NAV چنددارایی + صندوق ۵۰+ سهمی + اهرمی + تضمین + FOF، اوراق Clean/Dirty، واحدها (صدور/ابطال/توثیق/ارث)، رویداد شرکتی، تطبیق (ریال/تومان، نوع NAV، مرجع کهنه/نامعتبر، NAV≤۰)، پیام (تکرار/ترتیب/دیررس/قطعی هنگام ثبت)، DR واقعی، امنیت، کارایی با تعریف بار و صدک، بازتولید، انطباق، تخصیص عادلانه، مالیات، **AML (سه جریان و مهلت‌ها)، انطباق شرعی، کارمزد چندجزئی/پله‌ای، مجمع امیدنامه‌ای**.
افزودنی: property-based test ثابت‌های دفتر، Golden Dataset بی‌نام‌شده، بازمحاسبه تاریخی NAV، کالیبراسیون آستانه.

**شرط انتشار:** بازتولیدپذیری، اتصال ارقام به ورودی/سیاست، محدودیت صریح کیفیت ناکافی، پیگیری مغایرت، بازیابی آزمایش‌شده، دوره سایه کامل.

---

## ۲۹. تداوم و بازیابی

پشتیبان چندلایه (PG/Timescale/فایل) با RPO/RTO تعریف‌شده، آزمون دوره‌ای بازیابی، ثبت کامل رویدادها، تغییر قواعد فقط با تأیید رسمی، نسخه‌بندی در همه خروجی‌ها.

---

## ۳۰. فازبندی پیاده‌سازی

| فاز | تحویل |
|---|---|
| ۱ | قرارداد داده (منابع، زمان، ارز، نوع NAV، دامنه) |
| ۲ | مرجع و دفتر مالی + دفتر واحدها |
| ۳ | ارزش‌گذاری + Snapshot قابل بازتولید |
| ۴ | NAV مستقل و طبقاتی (شامل اهرمی/تضمین/FOF) |
| ۵ | تطبیق API + پرونده مغایرت |
| ۶ | تاب‌آوری (Outbox، Replay، DLQ، DR) |
| ۷ | انطباق، AML/CFT، انطباق شرعی، وثیقه/ریپو، شاخص و رتبه‌بندی |
| ۸ | حاکمیت، تعارض منافع، حقوقی/شکایات |
| ۹ | مالیات، چرخه عمر (ادغام/تصفیه)، مجمع امیدنامه‌ای |
| ۱۰ | گزارش/داشبورد/حسابرسی/درگاه نظارتی |
| ۱۱ | اجرای سایه |
| ۱۲ | مهاجرت تاریخی + Opening Balance + معامله اختیاری |

---

## ۳۱. ضمائم

### الف) فرمول‌های کلیدی

```text
NAV_unit = (Σ FairValue + OtherAssets − Liabilities − AccruedFees − GuaranteeReserve) / Units
Premium/Discount% = (MarketPrice / NAV_unit − 1) × 100
Δbps = (NAV_internal − NAV_reference) / NAV_reference × 10000
Dirty = Clean + AccruedInterest
NAV_issuance = NAV_unit + IssuanceFee
NAV_redemption = NAV_unit − RedemptionFee
```

### ب) پارامترهای نیازمند تأیید رسمی

فرمول/ضرایب قیمت پایانی و حجم مبنا، دامنه و تیک هر نوع، **جدول کامل کارمزد ارکان (چندجزئی)، جدول پله‌ای کارمزد ابطال**، سقف سفارش، دوره افشای پرتفوی، تعریف دقیق NAV هر API، کف/سقف و قواعد تخصیص اهرمی، شرایط تضمین (دوره، ذخیره، جریمه)، نصاب‌های FOF، منبع و ضریب گواهی کالا، قواعد مظنه ضربدری، نصاب‌های انطباق هر نوع، **آستانه‌های AML و قالب گزارش‌ها**، **فهرست تأییدشده ابزارها از کمیته فقهی**، نرخ سود مصوب، مهلت‌های افشا و مالیات.

### ج) ماتریس قاعده ← ماژول ← جدول ← تست

| قاعده | ماژول | جدول اصلی | تست |
|---|---|---|---|
| توازن دوطرفه | Portfolio Ledger | journal_lines + trigger | حسابداری |
| عدم ثبت تکراری | Ledger/Event | journal_entries(idempotency) | پیام/حسابداری |
| عدم‌هم‌پوشانی شناسه | Instrument Master | instrument_identifiers(EXCLUDE) | مرجع |
| انواع NAV | NAV Engine | nav_results(nav_type) | تطبیق/NAV |
| سه بُعد تطبیق | Reconciliation | reconciliation_runs | تطبیق |
| آستانه دوگانه | Reconciliation | threshold_versions | کالیبراسیون |
| تخصیص اهرمی | NAV Engine | class_allocation_runs | NAV |
| تضمین | Guarantee | guarantee_contracts/reserves | NAV/حقوقی |
| FOF و حلقه | Valuation | position_valuations + graph check | NAV |
| نصاب‌ها | Compliance | compliance_rules_effective | انطباق |
| نسبت اوراق | Compliance | compliance_checks | انطباق/گزارش |
| تخصیص عادلانه | Fair Allocation | fair_allocation_reviews | انطباق |
| معاملات شخصی | Personal Trading | personal_trading_requests | حاکمیت |
| کنترل داخلی | Governance | internal_control_reports | حاکمیت |
| صلاحیت ارکان | Eligibility | status + مدارک | حقوقی |
| تخلفات/شکایات | Disciplinary/Complaint | disciplinary_cases/complaints | حقوقی |
| مالیات | Tax | tax_calculations | مالیات |
| ادغام/تصفیه | Merger & Liquidation | merger_plans/liquidation_plans | چرخه عمر |
| بازارگردانی | Market Making | تعهدات + لاگ | بازار |
| AML و سه جریان گزارش | AML/CFT | aml_str_reports/aml_threshold_reports/aml_cash_reports | انطباق |
| انطباق شرعی | Sharia Compliance | sharia_approvals | انطباق |
| کارمزد چندجزئی/پله‌ای | Fee Schedules | fee_schedules | حسابداری |
| مجمع امیدنامه‌ای | Prospectus Assembly | prospectus_versions | حاکمیت |
| DR/بازیابی | زیرساخت | backup/restore drills | بازیابی |

### د) چک‌لیست شکاف‌های ادغام‌شده (خلاصه)

انواع صندوق (تضمین، اهرمی دقیق، FOF، جسورانه/خصوصی، بازارگردانی، املاک ۱۴۰۴، نیکوکاری، بخشی، نوع دوم)؛ انواع NAV و کارمزد صدور/ابطال؛ تعهد کارمزد ارکان؛ هزینه بهره اهرم؛ تقسیم سود ماهانه؛ تعلیق ابطال؛ امضای مشترک؛ مالیات (۱۴۳ مکرر، ۰.۵٪، CGT، سود سپرده، ادغام)؛ مقررات نام‌برده (رویدادهای مالی، قیمت‌گذاری، معاملات غیرمتعارف، امنیت/برون‌سپاری)؛ حاکمیت (کمیته‌ها، حسابرسی داخلی، کنترل داخلی، ESG، معاملات وابسته)؛ متولی (تطبیق روزانه، CSDI، وثیقه واحد)؛ بازارگردانی (مظنه/انباشته/حجم/صف)؛ ضامن نقدشوندگی؛ کفایت سرمایه و صلاحیت؛ مالکیت واحد مدیر؛ تمدید/انحلال؛ درگاه نظارتی؛ نسبت اوراق؛ فرابورس/آتی/پایاپای/DVP؛ تعارض منافع و معاملات شخصی؛ تخصیص عادلانه و Best Execution؛ شکایات و انتظامی؛ مسئولیت مدنی و D&O؛ ادغام/تبدیل؛ ذخیره کاهش ارزش؛ اندوخته غیرقابل تقسیم؛ انبار و تحویل فیزیکی؛ رتبه‌بندی اعتباری و نکول؛ ریسک‌های مکمل و استرس؛ CGT و گزارش مالیاتی؛ حقوق واحدداران (توثیق/ارث/مسدودی)؛ **AML/CFT (شش دستورالعمل، سه جریان گزارش، تأییدیه سامانه، سطوح مؤسسات)**؛ **انطباق شرعی و کمیته فقهی**؛ **ساختار چندجزئی کارمزد، کارمزد پله‌ای ابطال و مجمع امیدنامه‌ای**؛ **صندوق ارزی و تضمین تسویه وجوه**؛ **تملک اهرمی و سپرده وکالتی**؛ **استقراض و فهرست رسمی هزینه‌ها**؛ **تبلیغات ممنوع و قفل پذیره‌نویسی**؛ **معافیت بازارگردان، مالیات گواهی کالایی و سود نقدی، معافیت صندوق املاک دولتی**؛ **تکالیف برنامه هفتم توسعه**.

### هـ) رجیستر جامع کنترل‌ها (۷۰۰+ مورد)

کنترل‌ها، الزامات، تست‌ها و سنجه‌های عملیاتی به‌صورت شماره‌دار در سند پیوست ثبت شده‌اند:
`docs/funds/NAV_CONTROLS_REGISTER_500.md` — ۲۳ حوزه، بیش از ۷۰۰ قلم.

---

**جمع‌بندی:** زنجیره کامل این است:
`دفتر دوطرفه + دفتر واحدها → ارزش‌گذاری سیاست‌محور هر ابزار (با کمیته برای غیربورسی) → NAV نسخه‌دار با انواع مشخص و تخصیص طبقاتی → تطبیق سه‌بُعدی + تطبیق نقد/کارگزار/CSDI/پرتفوی افشاشده → انطباق، حاکمیت، تعارض منافع و ریسک → مالیات و چرخه عمر → انتشار امن، درگاه نظارتی و حسابرسی`.
هرجا اطلاعات واقعی در دسترس نیست، سامانه عدم‌قطعیت را اعلام می‌کند و عدد تخمینی را NAV دقیق نمی‌نامد.
