"""Fourth batch of hand-verified findings (frontend live hooks + flow summary)."""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append({"cat": cat, "file": file, "anchor": anchor, "occ": occ, "title": title,
                  "sev": sev, "status": status, "impact": impact, "fix": fix})


add("FE", "frontend/src/hooks/useMarketData.ts", r"await Promise\.allSettled\(\[", 1,
    "شکست هر منبع در کارت‌های قیمت بی‌صدا به آرایه خالی تبدیل می‌شود",
    "P2", "تأییدشده",
    "allSettled از reject جلوگیری می‌کند، اما useQuery خطا نمی‌بیند؛ اگر رمزارز خراب باشد، isError=false می‌ماند و فقط کارت‌ها کم می‌شوند.",
    "وضعیت partial/منبع ناموفق را در خروجی برگردانید و در UI نشان دهید.")
add("FE", "frontend/src/hooks/useMarketData.ts", r"await Promise\.allSettled\(\[", 2,
    "بازارهای جهانی هم شکست منبع را بی‌صدا حذف می‌کنند",
    "P2", "تأییدشده",
    "نبود طلا/برنت/BTC از خطای endpoint قابل تفکیک نیست.",
    "نتیجه per-source با وضعیت و زمان آخرین موفقیت.")
add("FE", "frontend/src/hooks/useMarketData.ts", r'console\.warn\("\[useSectorMap\]', 1,
    "پاسخ success:false نقشه صنایع فقط warn می‌شود و به فهرست خالی تبدیل می‌گردد",
    "P2", "تأییدشده",
    "خطا و «صنعت بدون داده» یکسان دیده می‌شوند؛ heuristic طول صفر هم بازار خالی را خطا علامت می‌زند.",
    "حالت error جدا از empty با پیام قابل مشاهده.")
add("FE", "frontend/src/hooks/useMarketData.ts", r'console\.warn\("\[useOwnershipFlows\]', 1,
    "خطای جریان حقیقی/حقوقی فقط warn و آرایه خالی برمی‌گرداند",
    "P2", "تأییدشده",
    "خرابی endpoint با «جریان مالی وجود ندارد» اشتباه می‌شود.",
    "isError واقعی و پیام در UI.")
add("FE", "frontend/src/hooks/useMarketData.ts", r'console\.warn\("\[useFlowSummary\]', 1,
    "خلاصه جریان در خطا null برمی‌گرداند و catch خالی است",
    "P2", "تأییدشده",
    "null می‌تواند یعنی خطا یا نبود داده؛ مصرف‌کننده تفکیک نمی‌کند.",
    "نوع نتیجه با وضعیت خطا و updatedAt.")
add("FE", "frontend/src/hooks/useMarketData.ts", r'console\.warn\("\[useMarketEvents\]', 1,
    "خطای تقویم اقتصادی با «بدون رویداد» یکسان می‌شود",
    "P2", "تأییدشده",
    "اختلال API به «هیچ رویداد اقتصادی وجود ندارد» تبدیل می‌شود.",
    "تفکیک empty از error و ثبت payload نامعتبر.")
add("API", "apps/api/endpoints/market.py", r"limit: int = Query\(500, ge=50, le=2000\),", 1,
    "خلاصه جریان بازار روی حداکثر ۵۰۰ snapshot محاسبه می‌شود",
    "P1", "تأییدشده",
    "real_net_b/legal_net_b/queue_buy/queue_sell نماینده کل بازار نیستند و به انتخاب ۵۰۰ نماد سوگیری دارند.",
    "تجمیع در SQL روی کل چرخه آخر یا افزودن sample_size/is_partial.")
add("API", "apps/api/endpoints/market.py", r"rows\.reverse\(\)  # oldest-first for charting", 1,
    "ترتیب تاریخچه شاخص به معکوس‌سازی در دو لایه وابسته است",
    "P2", "تأییدشده",
    "سرویس created_at DESC می‌دهد و endpoint reverse می‌کند؛ مصرف‌کننده دیگر ترتیب متفاوتی می‌بیند و tie-breaker ندارد.",
    "قرارداد ترتیب در یک لایه با (created_at, id).")
add("API", "brsapi/services/query_service.py", r"SymbolSnapshotModel\.ins_id == symbol,", 1,
    "جست‌وجوی نماد با یک پارامتر روی دو ستون symbol و ins_id انجام می‌شود",
    "P2", "تأییدشده",
    "اگر رشته ورودی با ins_id رکورد دیگری برابر باشد، رکورد نامرتبط انتخاب می‌شود؛ اولویت ins_id/symbol صریح نیست.",
    "ابتدا تطبیق دقیق ins_id و سپس fallback symbol با کنترل ابهام.")
