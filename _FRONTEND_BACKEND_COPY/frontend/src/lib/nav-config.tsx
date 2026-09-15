import {
  Activity,
  BarChart3,
  Bitcoin,
  Building2,
  CandlestickChart,
  Database,
  FlaskConical,
  Globe,
  Layers,
  LayoutDashboard,
  LineChart,
  Plug,
  Radar,
  Settings2,
  Sparkles,
  TrendingUp,
  Wrench,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavLeaf {
  label: string;
  href: string;
  desc?: string;
}

export interface NavGroup {
  title: string;
  icon?: LucideIcon;
  items: NavLeaf[];
}

export interface NavItem {
  label: string;
  icon: LucideIcon;
  href?: string;
  groups?: NavGroup[];
}

export const NAV_CONFIG: NavItem[] = [
  {
    label: "داشبورد",
    icon: LayoutDashboard,
    href: "/",
    groups: [
      {
        title: "اصلی",
        icon: LayoutDashboard,
        items: [
          { label: "داشبورد اختصاصی", href: "/", desc: "نمای کلی بازار و قیمت‌ها" },
          { label: "داشبورد اقتصادی", href: "/analysis", desc: "تحلیل و شاخص‌های کلان" },
          { label: "داشبورد شخصی", href: "/personal", desc: "پرتفوی و علاقه‌مندی‌ها" },
        ],
      },
      {
        title: "داشبوردهای تخصصی",
        icon: Sparkles,
        items: [
          { label: "بازار طلا", href: "/markets/gold", desc: "طلا، سهام، کریپتو و سبد در یک نما" },
          { label: "پرتفوی", href: "/portfolio", desc: "مدیریت سبد سهام" },
          { label: "لیست پیگیری", href: "/watchlist", desc: "نمادهای مورد نظر" },
          { label: "بازار نقره", href: "/markets/silver", desc: "انس نقره و صندوق‌های مرتبط" },
          { label: "کدال", href: "/codal", desc: "اطلاعیه‌ها و گزارش‌های شرکت‌ها" },
        ],
      },
    ],
  },
  {
    label: "بازارها",
    icon: CandlestickChart,
    href: "/markets",
    groups: [
      {
        title: "شاخص‌ها",
        icon: LineChart,
        items: [
          { label: "شاخص کل بورس", href: "/markets/indices", desc: "شاخص کل و هموزن" },
          { label: "نرخ ارز", href: "/markets/fx", desc: "دلار، یورو، درهم" },
          { label: "بازار جفت‌ارز", href: "/crypto-market", desc: "جفت‌ارزهای رمزپایه" },
        ],
      },
      {
        title: "سهام",
        icon: BarChart3,
        items: [
          { label: "حق تقدم", href: "/markets/stocks/rights" },
          { label: "نمادهای متوقف", href: "/markets/stocks/suspended" },
          { label: "پرداخت سود نقدی", href: "/markets/stocks/dividends" },
          { label: "معاملات پایانی", href: "/markets/stocks/closing" },
          { label: "تال", href: "/markets/stocks/tal" },
          { label: "اوراق", href: "/markets/stocks/bonds" },
          { label: "امتیاز تسهیلات مسکن", href: "/markets/stocks/maskan" },
        ],
      },
      {
        title: "ابزارهای مالی",
        icon: Layers,
        items: [
          { label: "اوراق", href: "/markets/bonds" },
          { label: "آتی", href: "/markets/futures" },
          { label: "سلف و موازی", href: "/markets/futures/salaf" },
          { label: "صندوق", href: "/funds" },
          { label: "صندوق درون‌روز", href: "/funds/intraday" },
          { label: "اختیار", href: "/options" },
        ],
      },
      {
        title: "بازار آپشن و کالا",
        icon: Layers,
        items: [
          { label: "بازار آپشن", href: "/markets/options-market", desc: "نمای کلی بازار اختیار معامله" },
          { label: "بازار کالا", href: "/markets/commodities-market", desc: "قیمت جهانی کامودیتی‌ها" },
          { label: "جستجوی آپشن و کالا", href: "/markets/search", desc: "جستجوی یکپارچه در قراردادها و کالاها" },
        ],
      },
      {
        title: "سایر بازارها",
        icon: Globe,
        items: [
          { label: "تابلویی", href: "/markets/tabaei" },
          { label: "فروش", href: "/markets/sales" },
          { label: "کامودیتی", href: "/commodities" },
          { label: "کامودیتی (IME)", href: "/markets/commodity", desc: "بازار فیزیکی بورس کالا" },
          { label: "نمادها", href: "/instruments" },
          { label: "کریپتو", href: "/crypto" },
        ],
      },
      {
        title: "طلا و سکه",
        icon: Sparkles,
        items: [
          { label: "نمای کلی طلا", href: "/gold", desc: "نمای کلی بازار طلا و سکه" },
          { label: "تحلیل تکنیکال طلا", href: "/gold/technical" },
          { label: "سکه‌ها", href: "/gold/coins" },
          { label: "صندوق‌های طلا", href: "/gold/funds" },
          { label: "فیزیکی طلا", href: "/gold/physical" },
          { label: "آپشن طلا", href: "/gold/options" },
          { label: "آتی طلا", href: "/gold/futures" },
          { label: "پرتفوی طلا", href: "/gold/portfolio" },
          { label: "DCA طلا", href: "/gold/dca" },
          { label: "توکن‌های طلا", href: "/gold/tokens" },
          { label: "هشدارهای طلا", href: "/gold/alerts" },
          { label: "تحلیل طلا", href: "/gold/analytics" },
        ],
      },
    ],
  },
  {
    label: "تحلیل و سیگنال",
    icon: Activity,
    href: "/signals",
    groups: [
      {
        title: "تحلیل",
        icon: TrendingUp,
        items: [
          { label: "تحلیل بازار", href: "/analysis" },
          { label: "تحلیل بنیادی", href: "/fundamental", desc: "تحلیل بنیادی شرکت‌ها" },
          { label: "ترازنامه", href: "/fundamental/balance-sheet" },
          { label: "صورت سود و زیان", href: "/fundamental/income" },
          { label: "جریان نقدی", href: "/fundamental/cashflow" },
          { label: "نسبت‌ها", href: "/fundamental/ratios" },
          { label: "افزایش سرمایه", href: "/fundamental/capital-increase" },
          { label: "EPS", href: "/fundamental/eps" },
          { label: "DPS", href: "/fundamental/dps" },
          { label: "تولیدات", href: "/fundamental/production" },
          { label: "دیده‌بان آلفا", href: "/alpha" },
          { label: "دیده‌بان بازار", href: "/market-watch", desc: "نمایش لحظه‌ای نمادها" },
          { label: "عمق بازار", href: "/market-depth" },
          { label: "بینش بازار", href: "/market-insights" },
        ],
      },
      {
        title: "غربالگری",
        icon: Radar,
        items: [
          { label: "غربالگر هوشمند", href: "/smart-screener" },
          { label: "غربالگر ساده", href: "/screener" },
          { label: "غربالگر 110", href: "/screener110" },
          { label: "نقشه بازار", href: "/heatmap" },
        ],
      },
      {
        title: "سیگنال",
        icon: Zap,
        items: [
          { label: "سیگنال‌ها", href: "/signals" },
          { label: "سیگنال‌های چندبازاره", href: "/signals/dashboard" },
          { label: "سیگنال‌های سهام", href: "/signals/stocks" },
          { label: "همه سیگنال‌ها", href: "/signals/all" },
          { label: "ثبت سیگنال", href: "/signals/register" },
          { label: "سیگنال‌های چندبازاره", href: "/multi-market-signals" },
          { label: "معاملات آزمایشی", href: "/paper-trading" },
        ],
      },
      {
        title: "بک‌تست و پژوهش",
        icon: FlaskConical,
        items: [
          { label: "بک‌تست", href: "/backtest" },
          { label: "اسکن کامل", href: "/backtest/full-scan" },
          { label: "تولید خودکار", href: "/backtest/generate" },
          { label: "ترکیب استراتژی", href: "/backtest/compose" },
          { label: "Walk-Forward", href: "/backtest/walk-forward" },
          { label: "Monte Carlo", href: "/backtest/monte-carlo" },
          { label: "روش‌ها", href: "/backtest/methods" },
          { label: "مرکز تصمیم", href: "/backtest/decision" },
          { label: "سیستم انطباقی", href: "/backtest/adaptive" },
          { label: "کاسکد", href: "/backtest/cascade" },
          { label: "موتور استراتژی", href: "/backtest/engine" },
          { label: "یادگیری ماشین", href: "/ml" },
          { label: "موتور تصمیم", href: "/decision-engine" },
        ],
      },
      {
        title: "دیجیتال",
        icon: Bitcoin,
        items: [
          { label: "بازارهای رمزارز", href: "/crypto-market" },
          { label: "صرافی رمزارز", href: "/crypto-exchange" },
          { label: "دیجیتال", href: "/crypto" },
          { label: "آلفا", href: "/alpha" },
          { label: "API تبدیل", href: "/tabdeal-api" },
        ],
      },
    ],
  },
  {
    label: "کاربری",
    icon: LayoutDashboard,
    href: "/watchlist",
    groups: [
      {
        title: "پیگیری و سبد",
        icon: TrendingUp,
        items: [
          { label: "لیست پیگیری", href: "/watchlist" },
          { label: "پرتفوی", href: "/portfolio" },
          { label: "پرتفوی طلا", href: "/gold/portfolio" },
          { label: "پیش‌بینی‌ها", href: "/forecasts" },
          { label: "همبستگی‌ها", href: "/correlations" },
          { label: "توصیه‌ها", href: "/recommendations" },
          { label: "پذیرش ریسک", href: "/risk" },
        ],
      },
      {
        title: "پیکربندی",
        icon: Zap,
        items: [
          { label: "اطلاعیه‌ها", href: "/alerts" },
          { label: "اخبار", href: "/news" },
          { label: "چت هوشمند", href: "/chat" },
          { label: "ساعت بازار", href: "/economic-calendar" },
          { label: "نتایج", href: "/results" },
        ],
      },
    ],
  },
  {
    label: "داده و مدیریت",
    icon: Database,
    href: "/data",
    groups: [
      {
        title: "داده‌ها",
        icon: Database,
        items: [
          { label: "نمادها", href: "/instruments", desc: "لیست همه نمادهای بورسی" },
          { label: "واردات نماد", href: "/instruments/import" },
          { label: "تابلوی معاملات", href: "/trades" },
          { label: "قیمت‌ها", href: "/quotes" },
          { label: "واردات قیمت", href: "/quotes/import" },
          { label: "کدال", href: "/codal" },
          { label: "حسابرسی کدال", href: "/codal/audit" },
          { label: "واردات کدال", href: "/codal/import" },
          { label: "اخبار", href: "/news" },
          { label: "داده‌های کلان", href: "/macro" },
          { label: "انبار داده", href: "/data" },
        ],
      },
      {
        title: "زیرساخت",
        icon: Settings2,
        items: [
          { label: "پنل مدیریت", href: "/admin" },
          { label: "همگام‌سازی", href: "/sync" },
          { label: "مدیریت همگام‌سازی", href: "/sync-manager" },
          { label: "تنظیمات همگام‌سازی", href: "/sync-settings" },
          { label: "تنظیمات", href: "/settings" },
          { label: "امنیت", href: "/settings/security" },
          { label: "پروفایل", href: "/profile" },
          { label: "گزارش‌ها", href: "/reports" },
          { label: "سازمانده", href: "/scheduler" },
          { label: "وظایف", href: "/jobs" },
          { label: "آزمایش‌ها", href: "/experiments" },
          { label: "ویجت‌ها", href: "/widgets" },
          { label: "افزونه‌ها", href: "/plugins" },
          { label: "افزودن رهاورد", href: "/plugins/rahavard" },
        ],
      },
      {
        title: "حرفه‌ای",
        icon: FlaskConical,
        items: [
          { label: "پس‌تست", href: "/backtest" },
          { label: "معامله آزمایشی", href: "/paper-trading" },
          { label: "کیفیت داده", href: "/data-import" },
          { label: "سلامت داده", href: "/data-health" },
          { label: "انتقال داده", href: "/data-transfer" },
          { label: "نمایها", href: "/indicators" },
          { label: "ریسک", href: "/risk" },
          { label: "موتور تصمیم", href: "/decision-engine" },
        ],
      },
      {
        title: "API و دسترسی",
        icon: Plug,
        items: [
          { label: "BrsApi", href: "/brsapi" },
          { label: "BrsApi کدال", href: "/brsapi/codal" },
          { label: "API تبدیل", href: "/tabdeal-api" },
          { label: "نقل داده‌ها", href: "/data-transfer" },
          { label: "واردات", href: "/data-import" },
          { label: "جداول", href: "/tables" },
        ],
      },
    ],
  },
];

export const SEARCH_SHORTCUTS: NavLeaf[] = [
  { label: "نقشه بازار", href: "/heatmap" },
  { label: "غربالگر هوشمند", href: "/smart-screener" },
  { label: "صندوق‌ها", href: "/funds" },
  { label: "آپشن", href: "/options" },
  { label: "بازار آپشن", href: "/markets/options-market" },
  { label: "بازار کالا", href: "/markets/commodities-market" },
  { label: "جستجوی آپشن و کالا", href: "/markets/search" },
  { label: "کدال", href: "/codal" },
  { label: "اخبار", href: "/news" },
  { label: "طلا", href: "/gold" },
  { label: "پرتفوی", href: "/portfolio" },
  { label: "لیست پیگیری", href: "/watchlist" },
];

export type { LucideIcon };
