"""Second batch of hand-verified findings (sync service + read queries).

Anchors are matched inside the named file only; the builder resolves each to
the exact current line and quotes it.
"""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append({"cat": cat, "file": file, "anchor": anchor, "occ": occ, "title": title,
                  "sev": sev, "status": status, "impact": impact, "fix": fix})


add("DATA", "brsapi/services/sync_service.py", r"if brs_resp\.is_empty:", 1,
    "پاسخ خالی منبع با status=success ثبت می‌شود و این شاخه commit نمی‌کند",
    "P1", "تأییدشده",
    "لاگ «موفق با صفر داده» ممکن است ذخیره نشود و پاسخ خالی از پاسخ پرمحتوا تفکیک نمی‌گردد.",
    "وضعیت empty جدا، commit یکنواخت در همه خروجی‌ها.")
add("DATA", "brsapi/services/sync_service.py", r"# Normalise to list", 1,
    "خروجی پارسر با نوع غیرمنتظره به لیست خالی تبدیل و «موفق» گزارش می‌شود",
    "P1", "تأییدشده",
    "تغییر قرارداد منبع یا باگ پارسر به‌جای خطا، موفقیت صفررکورد می‌شود و در پایش دیده نمی‌شود.",
    "نوع غیرمجاز را ParseError بدانید؛ فقط آرایه خالی معتبر status=empty بگیرد.")
add("DATA", "brsapi/services/sync_service.py", r"sections: list\[tuple\[str, Callable", 1,
    "سه بخش طلا/ارز/رمزارز در یک session و یک تراکنش ذخیره می‌شوند",
    "P0", "تأییدشده",
    "خطای بخش سوم باعث rollback بخش‌های اول و دوم (و لاگ‌هایشان) می‌شود؛ گزارش موفق قبلی هم از بین می‌رود.",
    "تراکنش مستقل per-section یا اتمیک کردن کل عملیات با گزارش صریح.")
add("DATA", "brsapi/services/sync_service.py", r"await repo\.truncate\(\)", 2,
    "مسیر Gold_Currency_Pro جدول را قبل از هر اعتبارسنجی کیفیت خالی می‌کند",
    "P0", "تأییدشده",
    "پاسخ ناقص ولی غیرخالی، جدول را با مجموعه کوچک‌تر جایگزین می‌کند و نمادها از خروجی ناپدید می‌شوند.",
    "staging + اعتبارسنجی حداقل رکورد و سپس تعویض اتمیک.")
add("DB", "brsapi/services/query_service.py", r"max\(IndexValueModel\.created_at\)", 1,
    "آخرین مقدار شاخص با created_at انتخاب می‌شود نه fetched_at",
    "P2", "تأییدشده",
    "درج مجدد داده قدیمی (backfill) رکورد قدیمی را به‌عنوان مقدار جاری معرفی می‌کند.",
    "مرتب‌سازی بر اساس fetched_at با tie-break.")
add("DB", "brsapi/services/query_service.py", r"order_by\(NavRecordModel\.created_at\.desc\(\)\)", 1,
    "آخرین NAV با created_at انتخاب می‌شود نه تاریخ خود NAV",
    "P2", "تأییدشده",
    "اگر منبع NAV با تاریخ قدیمی‌تر را دیرتر درج کند، همان به‌عنوان NAV فعلی نمایش داده می‌شود.",
    "مرتب‌سازی بر اساس date نرمال‌شده و سپس created_at.")
add("DB", "brsapi/services/query_service.py", r"async def get_options_by_underlying", 1,
    "قراردادهای اختیار معامله همهٔ snapshotها را برمی‌گرداند",
    "P1", "تأییدشده",
    "با هر پنج دقیقه sync، قرارداد تکراری با قیمت‌های قدیمی در خروجی ظاهر می‌شود.",
    "آخرین snapshot هر قرارداد بر اساس fetched_at.")
add("DB", "brsapi/services/query_service.py", r"ShareholderRecordModel\.percent\.desc", 1,
    "فهرست سهام‌داران بر اساس درصد مرتب می‌شود، نه آخرین snapshot",
    "P2", "تأییدشده",
    "ترکیب سهام‌داران چند تاریخ با هم مخلوط می‌شود.",
    "ابتدا آخرین تاریخ snapshot را انتخاب کنید.")
add("DB", "brsapi/services/query_service.py", r"IntradayTradeModel\.created_at\.desc", 1,
    "معاملات درون‌روزی بدون فیلتر تاریخ بازار و بدون کلید یکتای معامله خوانده می‌شوند",
    "P2", "تأییدشده",
    "معامله تکراری در فهرست «اخیر» دیده می‌شود و رکوردهای روزهای قبل باقی می‌مانند.",
    "کلید یکتای منبع + فیلتر روز معاملاتی.")
add("DB", "brsapi/services/query_service.py", r"latest_only: bool = False,", 1,
    "قیمت کالاها به‌صورت پیش‌فرض کل تاریخچه را برمی‌گرداند",
    "P1", "تأییدشده",
    "بسیاری از فراخوان‌ها (market_dashboard، gold live، macro) پارامتر latest_only را نمی‌دهند و چند نسخه زمانی از یک کالا می‌گیرند.",
    "پیش‌فرض latest_only=True برای نمای جاری.")
add("DB", "brsapi/services/query_service.py", r"async def get_crypto_prices", 1,
    "قیمت رمزارزها بر اساس rank مرتب و محدود می‌شود، بدون انتخاب آخرین رکورد هر نماد",
    "P1", "تأییدشده",
    "یک رمزارز چند بار در ۵۰ نتیجه ظاهر می‌شود و ردیف‌های قدیمی جای بقیه را می‌گیرند.",
    "آخرین ردیف هر symbol بر اساس fetched_at.")
add("DB", "brsapi/services/query_service.py", r"async def get_ime_futures", 1,
    "قراردادهای IME تمام ردیف‌های ذخیره‌شده را برمی‌گردانند",
    "P2", "تأییدشده",
    "نسخه‌های قدیمی قرارداد در خروجی جاری می‌مانند (وابسته به dedup sync).",
    "کلید طبیعی قرارداد + upsert و انتخاب آخرین نسخه.")
add("DB", "brsapi/services/query_service.py", r"SymbolSnapshotModel\.ins_id\.is_\(None\)", 1,
    "شاخهٔ fallback اتصال بر اساس symbol عملاً غیرقابل وقوع است",
    "P2", "تأییدشده",
    "چون ins_id در مدل nullable=False است، شرط IS NULL هرگز برقرار نمی‌شود؛ در صورت ناسازگاری شناسه، فیلدهای غنی (sector/EPS) بی‌صدا خالی می‌مانند.",
    "سیاست تطبیق symbol با کنترل ابهام و متریک no-match.")
