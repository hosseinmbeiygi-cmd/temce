// منبع واحد نگاشت decision → برچسب و رنگ (F3 / قرارداد C1).
//
// قبلاً چهار جای مختلف جدول رنگی خودشان را داشتند و سه‌تایی‌های if/else:
//   * ScoreGauge و DecisionBadge با `map[decision]` بدون fallback — هر مقدار
//     ناشناخته TypeError می‌ساخت.
//   * صفحهٔ analytics با ternary — هر مقدار ناشناخته **قرمز** می‌شد، یعنی «داده
//     ناکافی» دقیقاً مثل «توقف/فروش» دیده می‌شد. این بدترین حالت ممکن بود.
// همه از این فایل تغذیه می‌کنند تا آن واگرایی دوباره ممکن نباشد.

import type { Decision } from "@/types/gold";

export interface DecisionView {
  /** برچسب فارسی. برای GREEN هرگز عبارت «خرید» یا «قطعی» به کار نمی‌رود (F3). */
  label: string;
  /** کلاس‌های Tailwind برای badge (پس‌زمینه + متن + حلقه). */
  cls: string;
  /** کلاس متن خالی برای عدد درشت (بدون پس‌زمینه). */
  text: string;
  /** رنگ نقطه/خط در نمودار (SVG به کلاس Tailwind نمی‌تواند). */
  dot: string;
  /** true یعنی «داوری ندارد» — نباید سبز یا قرمز دیده شود. */
  neutral: boolean;
}

const VIEWS: Record<Decision, DecisionView> = {
  // «شرایط مناسب‌تر» نه «بخر» — این ابزار توصیهٔ مالی نیست.
  GREEN: {
    label: "سبز — شرایط مناسب‌تر",
    cls: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
    text: "text-emerald-400",
    dot: "#10b981",
    neutral: false,
  },
  YELLOW: {
    label: "زرد — احتیاط",
    cls: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
    text: "text-amber-400",
    dot: "#f59e0b",
    neutral: false,
  },
  RED: {
    label: "قرمز — صبر",
    cls: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
    text: "text-rose-400",
    dot: "#f43f5e",
    neutral: false,
  },
  // C1: وقتی available_weight زیر آستانه باشد موتور NO_DATA می‌دهد؛ total همچنان
  // عددی می‌ماند (برای رسم نمودار) ولی رنگ داوری ندارد.
  NO_DATA: {
    label: "داده ناکافی",
    cls: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30",
    text: "text-zinc-400",
    dot: "#a1a1aa",
    neutral: true,
  },
};

const FALLBACK: DecisionView = VIEWS.NO_DATA;

/** نگاشت ایمن: مقدار ناشناخته/خالی هرگز قرمز نمی‌شود، خنثی می‌شود. */
export function decisionView(decision: Decision | string | null | undefined): DecisionView {
  if (typeof decision === "string" && decision in VIEWS) {
    return VIEWS[decision as Decision];
  }
  return FALLBACK;
}

export function isNeutralDecision(view: DecisionView): boolean {
  return view.neutral;
}
