/**
 * صندوق‌یار — دسته‌بندی صندوق‌ها با زیرگروه‌های بخشی
 *
 * هر صندوق دارای گروه اصلی + زیرگروه (مخصوص بخشی) است.
 * وزن‌های امتیازدهی بر اساس نوع صندوق متفاوت است.
 */

// ── گروه‌های اصلی صندوق‌ها ──────────────────────────────────────
export type FundGroup =
  | "equity"       // سهامی
  | "fixed_income" // درآمد ثابت
  | "mixed"        // مختلط
  | "gold"         // طلا و فلزات گران‌بها
  | "leveraged"    // اهرمی
  | "sector"       // بخشی
  | "index"        // شاخصی
  | "fof"          // صندوق در صندوق
  | "guarantee"    // تضمین اصل سرمایه
  | "special"      // اختصاصی / جسورانه / خصوصی
  | "commodity"    // کالایی (زعفران و...)
  | "other";       // سایر

// ── زیرگروه‌های صندوق‌های بخشی ─────────────────────────────────
export type SectorSubgroup =
  | "refining"     // پالایشی
  | "petrochemical"// پتروشیمی
  | "auto"         // خودرو و فلزات
  | "pharma"       // دارویی
  | "banking"      // بانکی و اعتباری
  | "steel"        // فولاد و معدنی
  | "it"           // فناوری اطلاعات
  | "cement"       // سیمان
  | "other_sector"; // سایر بخشی

export type FundSubgroup =
  | "fixed_income_fixed"    // با درآمد تثبیت‌شده
  | "fixed_income_variable" // بدون تثبیت
  | "gold_etf"              // ETF طلا
  | "gold_coin"             // مبتنی بر گواهی سکه
  | SectorSubgroup
  | null;

// ── تعریف گروه‌ها ──────────────────────────────────────────────
export interface FundGroupDef {
  id: FundGroup;
  label: string;
  icon: string;
  color: string;         // Tailwind classes
  bgColor: string;
  textColor: string;
  dotColor: string;      // CSS color for dot indicators
}

export const FUND_GROUPS: FundGroupDef[] = [
  { id: "equity",       label: "سهامی",       icon: "📈", color: "bg-emerald-500/15",  bgColor: "bg-emerald-500/10",  textColor: "text-emerald-400", dotColor: "#10b981" },
  { id: "fixed_income", label: "درآمد ثابت",  icon: "🏦", color: "bg-cyan-500/15",    bgColor: "bg-cyan-500/10",    textColor: "text-cyan-400",    dotColor: "#06b6d4" },
  { id: "mixed",        label: "مختلط",       icon: "⚖️", color: "bg-amber-500/15",    bgColor: "bg-amber-500/10",    textColor: "text-amber-400",    dotColor: "#f59e0b" },
  { id: "gold",         label: "طلا و کالا",  icon: "🪙", color: "bg-yellow-500/15",   bgColor: "bg-yellow-500/10",   textColor: "text-yellow-400",   dotColor: "#eab308" },
  { id: "leveraged",    label: "اهرمی",       icon: "⚡", color: "bg-purple-500/15",   bgColor: "bg-purple-500/10",   textColor: "text-purple-400",   dotColor: "#a855f7" },
  { id: "sector",       label: "بخشی",        icon: "🏭", color: "bg-orange-500/15",   bgColor: "bg-orange-500/10",   textColor: "text-orange-400",   dotColor: "#f97316" },
  { id: "index",        label: "شاخصی",       icon: "📊", color: "bg-blue-500/15",     bgColor: "bg-blue-500/10",     textColor: "text-blue-400",     dotColor: "#3b82f6" },
  { id: "fof",          label: "صندوق در صندوق", icon: "📦", color: "bg-indigo-500/15", bgColor: "bg-indigo-500/10",  textColor: "text-indigo-400",   dotColor: "#6366f1" },
  { id: "guarantee",    label: "تضمین سرمایه", icon: "🛡️", color: "bg-teal-500/15",  bgColor: "bg-teal-500/10",    textColor: "text-teal-400",     dotColor: "#14b8a6" },
  { id: "special",      label: "اختصاصی",      icon: "🎯", color: "bg-rose-500/15",    bgColor: "bg-rose-500/10",    textColor: "text-rose-400",     dotColor: "#f43f5e" },
  { id: "commodity",    label: "کالایی",       icon: "🌿", color: "bg-lime-500/15",    bgColor: "bg-lime-500/10",    textColor: "text-lime-400",     dotColor: "#84cc16" },
  { id: "other",        label: "سایر",         icon: "📋", color: "bg-gray-500/15",    bgColor: "bg-gray-500/10",    textColor: "text-gray-400",     dotColor: "#6b7280" },
];

// ── زیرگروه‌های بخشی ──────────────────────────────────────────
export const SECTOR_SUBGROUPS: { id: SectorSubgroup; label: string; icon: string; keywords: string[] }[] = [
  { id: "refining",      label: "پالایشی",       icon: "🛢️", keywords: ["پالایش", "پالایشگاه"] },
  { id: "petrochemical", label: "پتروشیمی",      icon: "🧪", keywords: ["پترو", "پتروشیمی", "پتروآ", "آلکان", "اکتان"] },
  { id: "auto",          label: "خودرو و فلزات",  icon: "🚗", keywords: ["خودرو", "اتو", "فلز", "سیمان"] },
  { id: "pharma",        label: "دارویی",         icon: "💊", keywords: ["دارو", "فارما", "pharma"] },
  { id: "banking",       label: "بانکی و اعتباری", icon: "🏦", keywords: ["بانک", "اعتبار", "مالی"] },
  { id: "steel",         label: "فولاد و معدنی",   icon: "⚒️", keywords: ["فولاد", "معدن", "استیل", "metal"] },
  { id: "it",            label: "فناوری اطلاعات",  icon: "💻", keywords: ["فناوری", "IT", "نرم‌افزار", "انفورماتیک"] },
  { id: "cement",        label: "سیمان",           icon: "🏗️", keywords: ["سیمان"] },
  { id: "other_sector",  label: "سایر بخشی",       icon: "🏭", keywords: [] },
];

// ── کلمات کلیدی تشخیص گروه اصلی ──────────────────────────────
const GROUP_KEYWORDS: Record<FundGroup, string[]> = {
  equity:       ["سهام", "سهامی", "آگاس", "سرو", "دارا", "پالایش", "دارا یکم", "ثروتم", "افق", "سلام", "کاردان", "تمشک", "پیشتاز"],
  fixed_income: ["درآمد ثابت", "ثابت", "کارین", "کمند", "اعتماد", "یاقوت", "افران", "لبخند", "کارا", "صایند", "آوند", "اوج", "خاتم", "پاداش", "ثبات", "اونیکس", "دارا", "بانک", "اوراق"],
  mixed:        ["مختلط", "زیتون", "آرمان"],
  gold:         ["طلا", "سکه", "عیار", "کهربا", "زر ", "مثقال", "گوهر", "ناب", "نفیس", "جواهر", "تابش", "زرفام", "گنج", "درین", "طلایی"],
  leveraged:    ["اهرم", "اهرمی", "موج", "شتاب", "توان", "جهش", "بیدار", "نارنج", "پیشران", "دواییان", "دوایکس"],
  sector:       ["پترو", "بخشی", "صنعت", "پالایشگاه", "خودرو", "اتو", "دارو", "فارما", "فولاد", "معدن", "سیمان", "فلز", "بانک"],
  index:        ["شاخصی", "شاخص", "فیروزه", "هم‌تراز", "کاریس", "آرام"],
  fof:          ["صندوق در صندوق", "فراز", "تمشک", "داناسرمایه", "اطلس"],
  guarantee:    ["تضمین", "گارانتی", "ضامن", "حفاظت"],
  special:      ["اختصاصی", "جسورانه", "VC", "PE", "خصوصی", "رویشنکین", "سپهر"],
  commodity:    ["زعفران", "سحرخیز", "نهال", "زرین", "کشاورزی"],
  other:        [],
};

// ── زیرگروه‌های طلا ──────────────────────────────────────────
const GOLD_KEYWORDS: Record<string, string[]> = {
  gold_etf: ["طلا", "سکه", "عیار", "کهربا", "زر ", "مثقال", "گوهر", "ناب", "نفیس", "جواهر", "تابش", "زرفام", "گنج", "درین"],
  gold_coin: ["سکه"],
};

const FIXED_INCOME_KEYWORDS: Record<string, string[]> = {
  fixed_income_fixed:    ["ثابت", "تثبیت"],
  fixed_income_variable: [], // default
};

// ── وزن‌های امتیازدهی بر اساس نوع صندوق ─────────────────────
export interface ScoringWeights {
  financial: number;
  liquidity: number;
  management: number;
  risk: number;
  cost: number;
  transparency: number;
}

export const SCORING_WEIGHTS_BY_GROUP: Record<FundGroup, ScoringWeights> = {
  equity:       { financial: 0.28, liquidity: 0.18, management: 0.18, risk: 0.18, cost: 0.10, transparency: 0.08 },
  fixed_income: { financial: 0.20, liquidity: 0.20, management: 0.15, risk: 0.25, cost: 0.12, transparency: 0.08 },
  mixed:        { financial: 0.25, liquidity: 0.18, management: 0.18, risk: 0.20, cost: 0.10, transparency: 0.09 },
  gold:         { financial: 0.25, liquidity: 0.20, management: 0.12, risk: 0.20, cost: 0.13, transparency: 0.10 },
  leveraged:    { financial: 0.20, liquidity: 0.22, management: 0.15, risk: 0.25, cost: 0.10, transparency: 0.08 },
  sector:       { financial: 0.25, liquidity: 0.15, management: 0.20, risk: 0.20, cost: 0.10, transparency: 0.10 },
  index:        { financial: 0.22, liquidity: 0.22, management: 0.15, risk: 0.18, cost: 0.13, transparency: 0.10 },
  fof:          { financial: 0.22, liquidity: 0.18, management: 0.22, risk: 0.18, cost: 0.10, transparency: 0.10 },
  guarantee:    { financial: 0.15, liquidity: 0.20, management: 0.20, risk: 0.25, cost: 0.10, transparency: 0.10 },
  special:      { financial: 0.25, liquidity: 0.15, management: 0.25, risk: 0.18, cost: 0.08, transparency: 0.09 },
  commodity:    { financial: 0.25, liquidity: 0.18, management: 0.15, risk: 0.22, cost: 0.10, transparency: 0.10 },
  other:        { financial: 0.25, liquidity: 0.18, management: 0.18, risk: 0.20, cost: 0.10, transparency: 0.09 },
};

// ── توابع تشخیص ──────────────────────────────────────────────

/** تشخیص گروه اصلی صندوق از روی نام و فیلد fund_type */
export function detectFundGroup(name: string, fundType?: string): FundGroup {
  const combined = `${name || ""} ${fundType || ""}`.toLowerCase();

  // اولویت با fund_type اگر مشخص باشد
  if (fundType) {
    const ft = fundType.toLowerCase();
    if (ft.includes("اهرم") || ft.includes("leveraged")) return "leveraged";
    if (ft.includes("طلا") || ft.includes("gold")) return "gold";
    if (ft.includes("درآمد") || ft.includes("ثابت") || ft.includes("fixed")) return "fixed_income";
    if (ft.includes("سهام") || ft.includes("equity")) return "equity";
    if (ft.includes("مختلط") || ft.includes("mixed")) return "mixed";
    if (ft.includes("بخشی") || ft.includes("sector")) return "sector";
    if (ft.includes("شاخص") || ft.includes("index")) return "index";
    if (ft.includes("صندوق در صندوق") || ft.includes("fof")) return "fof";
    if (ft.includes("تضمین") || ft.includes("guarantee")) return "guarantee";
    if (ft.includes("اختصاصی") || ft.includes("special")) return "special";
    if (ft.includes("کالا") || ft.includes("commodity")) return "commodity";
  }

  // تشخیص از روی نام با کلمات کلیدی
  for (const [group, keywords] of Object.entries(GROUP_KEYWORDS) as [FundGroup, string[]][]) {
    for (const kw of keywords) {
      if (combined.includes(kw.toLowerCase())) return group;
    }
  }

  return "other";
}

/** تشخیص زیرگروه صندوق بخشی */
export function detectSectorSubgroup(name: string): SectorSubgroup {
  const n = (name || "").toLowerCase();
  for (const sg of SECTOR_SUBGROUPS) {
    for (const kw of sg.keywords) {
      if (n.includes(kw.toLowerCase())) return sg.id;
    }
  }
  return "other_sector";
}

/** تشخیص زیرگروه کلی (شامل بخشی + طلا + درآمد ثابت) */
export function detectFundSubgroup(name: string, group: FundGroup): FundSubgroup {
  const n = (name || "").toLowerCase();

  if (group === "sector") {
    return detectSectorSubgroup(name);
  }

  if (group === "gold") {
    for (const [sg, keywords] of Object.entries(GOLD_KEYWORDS)) {
      for (const kw of keywords) {
        if (n.includes(kw.toLowerCase())) return sg as FundSubgroup;
      }
    }
    return "gold_etf";
  }

  if (group === "fixed_income") {
    for (const [sg, keywords] of Object.entries(FIXED_INCOME_KEYWORDS)) {
      for (const kw of keywords) {
        if (n.includes(kw.toLowerCase())) return sg as FundSubgroup;
      }
    }
    return "fixed_income_variable";
  }

  return null;
}

/** برگرداندن تعریف گروه از آی دی */
export function getGroupDef(groupId: FundGroup): FundGroupDef {
  return FUND_GROUPS.find((g) => g.id === groupId) ?? FUND_GROUPS[FUND_GROUPS.length - 1];
}

/** برگرداندن تعریف زیرگروه بخشی از آی دی */
export function getSectorSubgroupDef(subgroupId: SectorSubgroup) {
  return SECTOR_SUBGROUPS.find((sg) => sg.id === subgroupId) ?? SECTOR_SUBGROUPS[SECTOR_SUBGROUPS.length - 1];
}

/** محاسبه حباب P/NAV */
export function calcBubble(price: number, nav: number): number | null {
  if (price <= 0 || nav <= 0) return null;
  return ((price - nav) / nav) * 100;
}

/** رنگ حباب بر اساس درصد */
export function bubbleColor(pct: number): string {
  if (pct > 5) return "text-rose-400";
  if (pct > 2) return "text-amber-400";
  if (pct > -2) return "text-emerald-400";
  if (pct > -5) return "text-amber-400";
  return "text-rose-400";
}

/** برچسب حباب */
export function bubbleLabel(pct: number): string {
  if (pct > 5) return "حباب بالا ⚠️";
  if (pct > 2) return "حباب متوسط";
  if (pct > -2) return "منصفانه ✓";
  if (pct > -5) return "تخفیف متوسط";
  return "تخفیف بالا 🔻";
}

/** آیا صندوق قابل معامله در بورس است (ETF) */
export function isETF(fundType?: string, market?: string): boolean {
  if (market === "tse") return true;
  if (fundType) {
    const ft = fundType.toLowerCase();
    if (ft.includes("etf") || ft.includes("قابل معامله")) return true;
  }
  return false;
}
