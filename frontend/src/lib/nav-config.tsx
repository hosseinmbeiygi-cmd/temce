import {
  Activity,
  BarChart3,
  Bitcoin,
  Building2,
  CandlestickChart,
  Database,
 FlaskConical,
  Shield,
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

/**
 * Top-nav information architecture — up to 3 levels (item → group → leaf).
 * Mirrors the product IA: dashboards, markets (multi-level), tools (with
 * the بنیادی sub-tree), analysis & signals, data & management, digital assets.
 * Nothing from the desktop menu is dropped — everything is grouped.
 */

export interface NavLeaf {
  label: string;
  href: string;
  /** Short Persian helper shown in mega panels. */
  desc?: string;
}

export interface NavGroup {
  /** Group title (e.g. سهام, بنیادی). */
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
        ],
      },
      {
        title: "داشبوردهای تخصصی",
        icon: Sparkles,
        items: [
          { label: "اختیار معامله", href: "/options", desc: "قراردادهای اختیار و سطح آپشن" },
          { label: "بازار طلا", href: "/markets/gold", desc: "انس، سکه و طلای ۱۸ عیار" },
         { label: "بازار نقره", href: "/markets/silver", desc: "انس نقره و صندوق‌های مرتبط" },
          { label: "داشبورد زرهی", href: "/armor", desc: "محاسبه امتیاز زرهی (Armor Score) برای کل بازار" },
         { label: "کدال", href: "/codal", desc: "اطلاعیه‌ها و گزارش‌های شرکتها" },
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
          { label: "اختیار", href: "/options" },
          { label: "تبعـی", href: "/markets/tabaei" },
          { label: "فروش", href: "/markets/sales" },
        ],
      },
      {
        title: "سایر بازارها",
        icon: Globe,
        items: [
          { label: "کالا", href: "/commodities" },
          { label: "نمادها", href: "/instruments" },
          { label: "ارز دیجیتال", href: "/crypto" },
          { label: "بازار رمز ارز", href: "/crypto-market" },
        ],
      },
    ],
  },
  {
    label: "ابزارها",
    icon: Wrench,
    href: "/instruments",
    groups: [
      {
        title: "تحلیل",
        icon: Radar,
        items: [
          { label: "نمودار تکنیکال", href: "/instruments", desc: "نمودار شمعی و اندیکاتورها" },
          { label: "دیده‌بان", href: "/watchlist", desc: "لیست پیگیری شخصی" },
          { label: "نقشه بازار", href: "/heatmap", desc: "نمای حرارتی همه نمادها" },
          { label: "فیلتر", href: "/screener", desc: "غربال‌گری ساده و حرفه‌ای" },
        ],
      },
      {
        title: "بنیادی",
        icon: Building2,
        items: [
          { label: "ترازنامه", href: "/fundamental/balance-sheet" },
          { label: "سود و زیان", href: "/fundamental/income" },
          { label: "گردش وجوه نقد", href: "/fundamental/cashflow" },
          { label: "نسبت‌های مالی", href: "/fundamental/ratios" },
          { label: "تولید و فروش", href: "/fundamental/production" },
          { label: "افزایش سرمایه", href: "/fundamental/capital-increase" },
          { label: "EPS", href: "/fundamental/eps" },
          { label: "DPS", href: "/fundamental/dps" },
        ],
      },
      {
        title: "اتصال و سفارشی‌سازی",
        icon: Plug,
        items: [
          { label: "هشدارها", href: "/alerts" },
          { label: "تقویم", href: "/economic-calendar" },
          { label: "انتقال داده", href: "/data-transfer" },
          { label: "ویجت‌ها", href: "/widgets" },
          { label: "افزونه‌ها", href: "/plugins" },
          { label: "افزودن رهاورد", href: "/plugins/rahavard" },
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
          { label: "پیشبینی قیمتها", href: "/predictions" },
          { label: "دیده‌بان آلفا", href: "/alpha" },
          { label: "بک‌تست", href: "/backtest" },
          { label: "یادگیری ماشین", href: "/ml" },
          { label: "ریسک", href: "/risk" },
          { label: "غربالگری هوشمند", href: "/smart-screener" },
          { label: "غربالگری ساده", href: "/screener" },
        ],
      },
      {
        title: "سیگنال",
        icon: Zap,
        items: [
          { label: "سیگنال‌ها", href: "/signals" },
          { label: "سیگنال‌های چندبازاره", href: "/signals/dashboard" },
          { label: "ثبت سیگنال", href: "/signals/register" },
          { label: "معاملات آزمایشی", href: "/paper-trading" },
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
          { label: "قیمت‌ها", href: "/quotes" },
          { label: "کدال", href: "/codal" },
          { label: "اخبار", href: "/news" },
          { label: "داده‌های کلان", href: "/macro" },
          { label: "اطلاعیه‌ها", href: "/alerts" },
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
          { label: "تنظیمات", href: "/settings" },
        ],
      },
      {
        title: "حرفه‌ای",
        icon: FlaskConical,
        items: [
          { label: "پس‌تست", href: "/backtest" },
          { label: "معامله آزمایشی", href: "/paper-trading" },
          { label: "کیفیت داده", href: "/data-import" },
        ],
      },
    ],
  },
];

/** Quick "جستجو در کل محصول" shortcuts for the symbol search dropdown. */
export const SEARCH_SHORTCUTS: NavLeaf[] = [
  { label: "نقشه بازار", href: "/heatmap" },
  { label: "غربالگر هوشمند", href: "/smart-screener" },
  { label: "صندوق‌ها", href: "/funds" },
  { label: "آپشن", href: "/options" },
  { label: "داشبورد زرهی", href: "/armor" },
  { label: "کدال", href: "/codal" },
  { label: "اخبار", href: "/news" },
];

export type { LucideIcon };
