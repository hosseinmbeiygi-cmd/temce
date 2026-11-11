// User personas — خرد / نهادی / اسکالپر.
//
// This is intentionally a *UI preference*, not an authorization model. It only
// decides which default view, shortcuts, density and refresh cadence the
// interface leads with. Roles/permissions stay in `auth-context` + `RoleGate`.

export const PERSONA_IDS = ["retail", "institutional", "scalper"] as const;

export type PersonaId = (typeof PERSONA_IDS)[number];

export interface PersonaQuickLink {
  label: string;
  href: string;
  desc: string;
}

export interface PersonaFeatures {
  /** Higher information density (tighter tables/lists). */
  denseLayout: boolean;
  /** Surface options / derivatives workspaces. */
  showDerivatives: boolean;
  /** Surface fundamentals (P/E, EPS, financial statements). */
  showFundamentals: boolean;
  /** Surface real/legal order-flow and market-depth panels. */
  showOrderFlow: boolean;
  /** Preferred polling cadence for live market widgets (ms). */
  marketRefreshMs: number;
}

export interface PersonaDefinition {
  id: PersonaId;
  /** Persian label used in the switcher and badges. */
  label: string;
  /** Latin name for docs and telemetry. */
  englishName: string;
  /** One-line description shown under the badge. */
  description: string;
  /** Where this persona should start. */
  defaultLandingPath: string;
  /** Primary shortcuts for the persona bar. */
  quickLinks: PersonaQuickLink[];
  features: PersonaFeatures;
  /** Persona-specific caution shown next to the shortcuts. */
  riskNote: string;
}

export const PERSONAS: Record<PersonaId, PersonaDefinition> = {
  retail: {
    id: "retail",
    label: "خرد",
    englishName: "Retail",
    description: "نمای ساده برای سرمایه‌گذار شخصی: طلا، صندوق‌ها و روند کلی بازار.",
    defaultLandingPath: "/markets/gold",
    quickLinks: [
      { label: "بازار طلا", href: "/markets/gold", desc: "انس، سکه و طلای ۱۸ عیار" },
      { label: "صندوق‌ها", href: "/funds", desc: "NAV و عملکرد صندوق‌ها" },
      { label: "دیده‌بان من", href: "/watchlist", desc: "نمادهای منتخب شما" },
      { label: "اخبار بازار", href: "/news", desc: "تیترهای مؤثر بر بازار" },
    ],
    features: {
      denseLayout: false,
      showDerivatives: false,
      showFundamentals: false,
      showOrderFlow: false,
      marketRefreshMs: 60_000,
    },
    riskNote: "این نما اطلاعات عمومی بازار است و توصیه سرمایه‌گذاری محسوب نمی‌شود.",
  },
  institutional: {
    id: "institutional",
    label: "نهادی",
    englishName: "Institutional",
    description: "نمای تحلیلی برای تصمیم‌گیری مبتنی بر بنیادی، پرتفوی و مشتقه.",
    defaultLandingPath: "/portfolio",
    quickLinks: [
      { label: "پرتفوی", href: "/portfolio", desc: "ترکیب دارایی و ریسک" },
      { label: "بنیادی", href: "/fundamental", desc: "صورت‌های مالی و نسبت‌ها" },
      { label: "اختیار معامله", href: "/options", desc: "زنجیره و تحلیل آپشن" },
      { label: "کدال", href: "/codal", desc: "اطلاعیه‌ها و گزارش‌ها" },
    ],
    features: {
      denseLayout: true,
      showDerivatives: true,
      showFundamentals: true,
      showOrderFlow: true,
      marketRefreshMs: 30_000,
    },
    riskNote: "داده‌های بنیادی و پرتفوی تنها پس از همگام‌سازی کامل معتبرند.",
  },
  scalper: {
    id: "scalper",
    label: "اسکالپر",
    englishName: "Scalper",
    description: "نمای متراکم و سریع برای معامله‌گری کوتاه‌مدت و رصد عمق بازار.",
    defaultLandingPath: "/market-depth",
    quickLinks: [
      { label: "عمق بازار", href: "/market-depth", desc: "دفتر سفارش و صف‌ها" },
      { label: "نقشه بازار", href: "/heatmap", desc: "تغییرات لحظه‌ای نمادها" },
      { label: "اختیار معامله", href: "/options", desc: "زنجیره و نوسان ضمنی" },
      { label: "سیگنال‌ها", href: "/signals", desc: "سیگنال‌های کوتاه‌مدت" },
    ],
    features: {
      denseLayout: true,
      showDerivatives: true,
      showFundamentals: false,
      showOrderFlow: true,
      marketRefreshMs: 5_000,
    },
    riskNote: "داده لحظه‌ای به تأخیر منبع وابسته است؛ قیمت اجرا ممکن است متفاوت باشد.",
  },
};

export const DEFAULT_PERSONA: PersonaId = "retail";

export const PERSONA_STORAGE_KEY = "temce.persona";

export function isPersonaId(value: unknown): value is PersonaId {
  return typeof value === "string" && (PERSONA_IDS as readonly string[]).includes(value);
}

/** Typed lookup with a safe fallback for unknown persisted values. */
export function personaOrDefault(value: unknown): PersonaId {
  return isPersonaId(value) ? value : DEFAULT_PERSONA;
}
