# 🎨 داشبورد سرمه‌ای + سفید — یادداشت‌های طراحی

## 1) شناسه‌های طراحی (Design Tokens)

همه در `src/app/globals.css` (Tailwind v4 `@theme`):

| توکن | روشن | تیره (سرمه‌ای) |
|---|---|---|
| `--app-bg` | `#f6f8fb` | `#0b1220` |
| `--card-bg` | `#ffffff` | `#0f172a` |
| `--line` | `rgba(15,23,42,.08)` | `rgba(255,255,255,.08)` |
| `--ink` | `#0f172a` | `#f8fafc` |
| `--up` | `#16a34a` | `#22c55e` |
| `--down` | `#dc2626` | `#ef4444` |
| `--warn` | `#d97706` | `#f59e0b` |

- کلاس‌های کاربردی: `bg-canvas`, `bg-card`, `bg-soft`, `border-line`, `text-ink/ink-2/ink-3`, `text-up/down/warn`, `bg-up/12`.
- **قانون رنگ سخت**: سبز/قرمز فقط برای جهت بازار (+/-)، جریان مالکیت و تأثیر — هرگز به‌عنوان پرکننده تزئینی بزرگ.
- پالت اولیه (primary) کل سیستم به سرمه‌ای (navy) تغییر کرد: `primary-600: #33486b`.

## 2) اعداد و واحدها

- همه آمار به **میلیارد تومان** (`fmtBillion`).
- **جداکننده هزارگان** در همه اعداد (`fmtInt`).
- اعداد بازار با **ارقام لاتین tabular + `dir="ltr"` + `font-mono`** رندر می‌شوند تا هم‌تراز و «پایانه‌ای» دیده شوند؛ متن‌ها فارسی‌اند.
- ارقام فارسی برای متن‌های روان (`faNum`).

## 3) نکات استایل نمودارها (recharts)

- **سه نمودار ستونی در یک گروه** (`TripleChartsGroup`): ۳ ستون دسکتاپ → ۱ ستون موبایل.
- فاصله مناسب بین ستون‌ها: `barCategoryGap="24–30%"` تا مقادیر خوانا بمانند.
- نمودار امضا شده (جریان نقدینگی): `Cell` سبز `var(--up)` / قرمز `var(--down)` بر اساس علامت.
- محورها: `tick={{ fill: "var(--ink-3)", fontSize: 10 }}`، شبکه `strokeDasharray` ظریف، بدون خط محور.
- `YAxis tickFormatter` اعداد بزرگ → `12.8k`.
- Tooltip سفارشی `ChartTooltip` با پس‌زمینه `bg-card/95` و سایه کارت؛ روی هر دو تم خوانا.
- پای (ترکیب دارایی): palet سرمه‌ای `#33486b → #a3b7d2` + یک `#d97706` و یک `#16a34a`.

## 4) رفتار ریسپانسیو

- دسکتاپ‌-اول؛ پوسته `max-w-[1600px]`.
- کارت‌های شاخص: `grid-cols-2 → sm:3 → xl:6` — آیتم‌های جا‌نمانده به‌راحتی به ردیف بعد می‌روند (بدون فشردگی).
- کارت‌های قیمت: `2 → 3 → 6`.
- سه نمودار: `lg:grid-cols-3` (دسکتاپ کنار هم، موبایل پشت سر هم با ترتیب منطقی).
- تیکر: marquee افقی، روی عرض کم اسکرول می‌شود؛ با hover مکث می‌کند.
- منوی موبایل: دراور کشویی با آکاردئون (زیر ۱۰۲۴px).

## 5) میکرو-اینترکشن‌ها

- هاور کارت‌ها: `-translate-y-0.5` + تقویت مرز + سایه (بیش از ۲۰۰ms نشود).
- منوهای مگا: `AnimatePresence` + fade/y با `0.16s easeOut` — بدون جابه‌جایی چیدمان (مطلق positioning).
- آیکون chevron منو هنگام باز ۱۸۰ درجه می‌چرخد.
- اسکلتون بارگذاری ۶۲۰ms با فید-آپ stagger (framer-motion).
- دکمه تغییر تم: سان/ماه با هاور روشن‌تر.

## 6) چک‌لیست دسترس‌پذیری و کنتراست (که عمداً درست شد)

- **«سفید روی سفید»** حذف شد: همه متن‌ها توکن `ink/ink-2/ink-3` دارند — در تم روشن متن تیره روی کارت سفید، در تم تیره متن روشن روی سرمه‌ای.
- **«خاکستری روی خاکستری»** ممنوع: متن `ink-3` فقط روی `bg-card`/سفید/سرمه‌ای استفاده می‌شود، نه روی `bg-soft` هم‌خانواده.
- نوار بالا همیشه سرمه‌ای است: متن سفید/`brand-100` — کنتراست > 4.5:1.
- فوکوس قابل مشاهده: `:focus-visible` با `--ring` (سرمه‌ای در روشن، روشن در تیره).
- آیکون‌ها SVG (lucide) — **صفر ایموجی** در داشبورد.
- `cursor-pointer` روی همه لینک/دکمه/کارت تعاملی.
- `prefers-reduced-motion` انیمیشن‌ها را خاموش می‌کند.
- Tooltip/chart: رنگ به‌تنهایی معنا نمی‌دهد — عدد همیشه همراه است.
- ورود/خروج از کروم کاملاً حذف شد (هم داشبورد هم سایدبار).

## 7) معماری کامپوننت

```
src/components/layout/
  TopNavbar.tsx        — فیکس‌تاپ، RTL، ۳ سطح، مگا منو، حالت compact، جستجو، تم
  TickerBar.tsx        — نوار بازار (marquee)
  DashboardShell.tsx   — پوسته داشبورد
  DashboardSkeleton.tsx
src/components/dashboard/
  primitives.tsx       — SectionHeader, DeltaBadge, Sparkline, ChartTooltip, SkeletonBlock, MiniMetric
  NewsStrip / QuoteCards / IndexCards / MarketMap / AssetAllocationPie
  MarketOverview / TopStocksToday / OwnershipChange / IndexImpacts
  ValueVolumePanel / TripleChartsGroup / LiquidityBlocks
src/lib/
  nav-config.tsx       — IA کامل منو (۳ سطح)
  market-mock.ts       — داده نمونه (میلیارد تومان)
  market-format.ts     — قالب‌بندی اعداد
  cn.ts
```
