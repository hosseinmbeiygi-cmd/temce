/*
Fund Analysis Engine — سیستم امتیازدهی ۶‌بعدی صندوق‌ها

امتیازدهی در ۶ بعد:
  - مالی (Financial): بازدهی، نوسان، عملکرد
  - نقدشوندگی (Liquidity): حجم معاملات، بازارگردان، شکاف قیمت
  - مدیریت (Management): سن صندوق، کارمزد، ثبات
  - ریسک (Risk): نسبت شارپ، حداکثر افت، نوع صندوق
  - هزینه (Cost): کارمزد مدیریت، نسبت هزینه
  - شفافیت (Transparency): ترکیب دارایی، ضامن نقدشوندگی
*/

export interface FundScore {
  financial: number;
  liquidity: number;
  management: number;
  risk: number;
  cost: number;
  transparency: number;
  total: number;
}

export interface FundIssue {
  id: number;
  title: string;
  description: string;
  category: string;
  priority: "A1" | "A2" | "B" | "C";
  severity: number; // 0-100
  solution: string;
}

export interface FundAnalysis {
  symbol: string;
  name: string;
  scores: FundScore;
  issues: FundIssue[];
  recommendation: "STRONG_BUY" | "BUY" | "WATCHLIST" | "HOLD" | "REDUCE" | "SELL" | "AVOID";
  riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  strengths: string[];
  weaknesses: string[];
  summary: string;
  nextSteps: string[];
}

// ── Fund interface from the page ──
export interface Fund {
  symbol: string;
  name: string;
  isin: string;
  // Mirrors frontend/src/app/funds/page.tsx Fund (fields consumed by the fund
  // components). Kept optional here so non-API constructors/tests stay valid.
  fund_type?: string;
  market?: "tse" | "ime" | string;
  data_source?: string;
  snapshot_date?: string;
  nav_source?: string;
  nav_date?: string;
  nav: number;
  nav_change: number;
  nav_change_pct: number;
  price_last: number;
  price_close: number;
  price_yesterday: number;
  price_max: number;
  price_min: number;
  trade_volume: number;
  trade_value: number;
  trade_count: number;
  shares_count: number;
  base_volume: number;
  market_value: number;
  buy_real_volume: number;
  buy_legal_volume: number;
  sell_real_volume: number;
  sell_legal_volume: number;
  time: string;
}

// ── Issue definitions (subset of 200, key ones for scoring) ──

const ISSUES: FundIssue[] = [
  // مالی (Financial)
  { id: 1, title: "بازدهی پایین‌تر از تورم", description: "بازدهی صندوق در بلندمدت کمتر از نرخ تورم بوده است", category: "مالی", priority: "A1", severity: 95, solution: "انتقال به صندوق‌های با بازدهی بالاتر" },
  { id: 2, title: "نوسان شدید بازدهی", description: "بازدهی صندوق نوسان بسیار بالایی دارد", category: "مالی", priority: "A1", severity: 90, solution: "انتخاب صندوق‌های با نوسان کمتر" },
  { id: 51, title: "بازدهی پایین‌تر از شاخص", description: "عملکرد صندوق پایین‌تر از شاخص کل بازار بوده است", category: "مالی", priority: "A2", severity: 80, solution: "انتخاب صندوق‌های با عملکرد بهتر از شاخص" },
  { id: 101, title: "بازدهی پایین در مقایسه با هم‌رده", description: "عملکرد صندوق پایین‌تر از صندوق‌های مشابه است", category: "مالی", priority: "B", severity: 60, solution: "مقایسه با صندوق‌های هم‌رده و انتخاب بهتر" },

  // نقدشوندگی (Liquidity)
  { id: 3, title: "نقدشوندگی پایین", description: "حجم معاملات صندوق بسیار پایین است", category: "نقدشوندگی", priority: "A1", severity: 90, solution: "انتخاب صندوق‌های با حجم معاملات بالا" },
  { id: 4, title: "عدم وجود بازارگردان فعال", description: "صندوق بازارگردان فعال ندارد یا بازارگردان ضعیف است", category: "نقدشوندگی", priority: "A1", severity: 85, solution: "انتخاب صندوق‌های با بازارگردان قوی" },
  { id: 5, title: "شکاف قیمت خرید و فروش بالا", description: "شکاف قیمت خرید و فروش در صندوق بالا است", category: "نقدشوندگی", priority: "A1", severity: 80, solution: "انتخاب صندوق‌های با شکاف قیمت پایین" },
  { id: 58, title: "حجم معاملات پایین", description: "حجم معاملات صندوق کمتر از حد مطلوب است", category: "نقدشوندگی", priority: "A2", severity: 70, solution: "انتخاب صندوق‌های با حجم معاملات بالاتر" },

  // مدیریت (Management)
  { id: 6, title: "مدیریت ناپایدار", description: "صندوق سابقه مدیریت پایدار ندارد", category: "مدیریت", priority: "A1", severity: 75, solution: "انتخاب صندوق‌های با مدیریت پایدار" },
  { id: 28, title: "تجربه ناکافی مدیران", description: "مدیران صندوق تجربه کافی ندارند", category: "مدیریت", priority: "A1", severity: 80, solution: "بررسی سابقه مدیران قبل از سرمایه‌گذاری" },
  { id: 61, title: "سابقه ضعیف مدیریت", description: "سابقه مدیریتی ضعیف است", category: "مدیریت", priority: "A2", severity: 70, solution: "انتخاب صندوق‌های با سابقه مدیریت موفق" },

  // ریسک (Risk)
  { id: 9, title: "ریسک‌پذیری بیش از حد", description: "صندوق ریسک بسیار بالایی می‌پذیرد", category: "ریسک", priority: "A1", severity: 85, solution: "انتخاب صندوق‌های با ریسک متناسب با اهداف" },
  { id: 10, title: "ریسک‌های پنهان", description: "سرمایه‌گذار از ریسک‌های پنهان صندوق آگاه نیست", category: "ریسک", priority: "A1", severity: 80, solution: "مطالعه گزارش ریسک و ترکیب دارایی" },
  { id: 17, title: "عدم تناسب ریسک با اهداف", description: "سطح ریسک صندوق با اهداف سرمایه‌گذار همخوانی ندارد", category: "ریسک", priority: "A1", severity: 95, solution: "تعیین پروفایل ریسک و انتخاب صندوق متناسب" },
  { id: 68, title: "حداکثر افت بالا", description: "حداکثر افت صندوق بالاتر از حد مجاز است", category: "ریسک", priority: "A2", severity: 75, solution: "انتخاب صندوق‌های با حداکثر افت پایین‌تر" },
  { id: 69, title: "نسبت شارپ پایین", description: "بازدهی تعدیل‌شده بر اساس ریسک پایین است", category: "ریسک", priority: "A2", severity: 70, solution: "انتخاب صندوق‌های با نسبت شارپ بالاتر" },

  // هزینه (Cost)
  { id: 11, title: "هزینه صدور و ابطال بالا", description: "هزینه‌های صدور و ابطال صندوق بالاست", category: "هزینه", priority: "A1", severity: 80, solution: "انتخاب صندوق‌های با هزینه صدور و ابطال پایین" },
  { id: 55, title: "کارمزد مدیریت بالا", description: "کارمزد مدیریت صندوق بالاتر از میانگین است", category: "هزینه", priority: "A2", severity: 70, solution: "مقایسه و انتخاب کم‌کارمزدترین صندوق" },
  { id: 104, title: "کارمزد نگهداری بالا", description: "کارمزد نگهداری صندوق بالاست", category: "هزینه", priority: "B", severity: 50, solution: "انتخاب صندوق‌های با کارمزد نگهداری پایین" },

  // شفافیت (Transparency)
  { id: 7, title: "عدم شفافیت در هزینه‌ها", description: "هزینه‌های پنهان صندوق شفاف نیست", category: "شفافیت", priority: "A1", severity: 70, solution: "مطالعه دقیق گزارش هزینه‌ها" },
  { id: 12, title: "تأخیر در انتشار گزارش‌ها", description: "گزارش‌های دوره‌ای صندوق با تأخیر منتشر می‌شود", category: "شفافیت", priority: "A1", severity: 60, solution: "انتخاب صندوق‌های با سابقه انتشار به‌موقع" },
  { id: 19, title: "عدم شفافیت در ترکیب دارایی", description: "ترکیب دارایی صندوق به‌طور شفاف اعلام نمی‌شود", category: "شفافیت", priority: "A1", severity: 65, solution: "درخواست گزارش ترکیب دارایی" },
];

// ── Category weights ──

const CATEGORY_WEIGHTS: Record<string, number> = {
  مالی: 0.25,
  نقدشوندگی: 0.20,
  مدیریت: 0.18,
  ریسک: 0.15,
  هزینه: 0.12,
  شفافیت: 0.10,
};

// ── Priority weights for score penalty ──

const PRIORITY_PENALTY: Record<string, number> = {
  A1: 1.0,
  A2: 0.7,
  B: 0.4,
  C: 0.2,
};

// ── Main analysis function ──

export function analyzeFund(fund: Fund): FundAnalysis {
  const scores = scoringEngine(fund);
  const issues = detectIssues(fund);
  const riskLevel = determineRiskLevel(scores, issues);
  const recommendation = determineRecommendation(scores.total, riskLevel, issues);
  const strengths = getStrengths(scores);
  const weaknesses = getWeaknesses(scores);

  return {
    symbol: fund.symbol,
    name: fund.name,
    scores,
    issues,
    recommendation,
    riskLevel,
    strengths,
    weaknesses,
    summary: generateSummary(scores.total, recommendation, issues.length),
    nextSteps: getNextSteps(recommendation),
  };
}

// ── Score computation ──

/**
 * Compute all 6 dimension scores for a fund.
 * Returns a FundScore object with financial, liquidity, management, risk, cost, transparency, and total.
 */
export function scoringEngine(fund: Fund): FundScore {
  const financial = scoreFinancial(fund);
  const liquidity = scoreLiquidity(fund);
  const management = scoreManagement(fund);
  const risk = scoreRisk(fund);
  const cost = scoreCost(fund);
  const transparency = scoreTransparency(fund);

  const total =
    financial * CATEGORY_WEIGHTS["مالی"] +
    liquidity * CATEGORY_WEIGHTS["نقدشوندگی"] +
    management * CATEGORY_WEIGHTS["مدیریت"] +
    risk * CATEGORY_WEIGHTS["ریسک"] +
    cost * CATEGORY_WEIGHTS["هزینه"] +
    transparency * CATEGORY_WEIGHTS["شفافیت"];

  return {
    financial: Math.round(financial),
    liquidity: Math.round(liquidity),
    management: Math.round(management),
    risk: Math.round(risk),
    cost: Math.round(cost),
    transparency: Math.round(transparency),
    total: Math.round(total),
  };
}

function scoreFinancial(f: Fund): number {
  let score = 60;

  // NAV change is positive → bonus
  if (f.nav_change_pct > 1) score += 20;
  else if (f.nav_change_pct > 0.5) score += 10;
  else if (f.nav_change_pct > 0) score += 5;
  else if (f.nav_change_pct < -0.5) score -= 15;

  // Higher NAV indicates better performance history
  if (f.nav > 10000) score += 5;
  if (f.nav > 50000) score += 5;

  // Active trading is good sign
  if (f.trade_count > 100) score += 5;

  return clampScore(score);
}

function scoreLiquidity(f: Fund): number {
  let score = 50;

  // Volume
  if (f.trade_volume > 1_000_000) score += 30;
  else if (f.trade_volume > 500_000) score += 20;
  else if (f.trade_volume > 100_000) score += 10;
  else score -= 15;

  // Trade value
  if (f.trade_value > 1_000_000_000) score += 10;
  else if (f.trade_value > 100_000_000) score += 5;
  else score -= 5;

  // Trade count
  if (f.trade_count > 500) score += 10;
  else if (f.trade_count > 100) score += 5;
  else if (f.trade_count < 10) score -= 10;

  return clampScore(score);
}

function scoreManagement(f: Fund): number {
  let score = 65;

  // Base volume (shares outstanding) indicates fund maturity
  if (f.shares_count > 50_000_000) score += 20;
  else if (f.shares_count > 10_000_000) score += 10;
  else if (f.shares_count < 1_000_000) score -= 15;

  // Market value indicates institutional interest
  if (f.market_value > 1_000_000_000_000) score += 10;
  else if (f.market_value > 100_000_000_000) score += 5;
  else score -= 5;

  // Real vs legal buying (institutional confidence)
  const netLegal = f.buy_legal_volume - f.sell_legal_volume;
  if (netLegal > 0) score += 5;

  return clampScore(score);
}

function scoreRisk(f: Fund): number {
  let score = 60;

  // Price stability (price range tightness)
  const range = f.price_max - f.price_min;
  const avgPrice = (f.price_max + f.price_min) / 2 || 1;
  const rangePct = range / avgPrice;
  if (rangePct < 0.01) score += 15; // very stable
  else if (rangePct < 0.03) score += 10;
  else if (rangePct < 0.05) score += 5;
  else if (rangePct > 0.10) score -= 10;

  // Negative change increases risk
  if (f.nav_change_pct < -2) score -= 15;
  else if (f.nav_change_pct < -1) score -= 10;
  else if (f.nav_change_pct < -0.5) score -= 5;

  // Higher volume = more liquid = less risk
  if (f.trade_volume > 500_000) score += 5;

  return clampScore(score);
}

function scoreCost(f: Fund): number {
  // For funds, we infer costs from market data
  let score = 70;

  // Premium/discount (price vs nav)
  if (f.price_last > 0 && f.nav > 0) {
    const premium = ((f.price_last - f.nav) / f.nav) * 100;
    // High premium means expensive → potential cost issue
    if (premium > 5) score -= 15;
    else if (premium > 2) score -= 5;
    else if (premium > 0) score -= 2;
  }

  // Active trading increases costs
  if (f.trade_count > 1000) score -= 5;
  if (f.trade_count < 10) score += 5;

  return clampScore(score);
}

function scoreTransparency(f: Fund): number {
  let score = 65;

  // Having ISIN indicates registration/transparency
  if (f.isin && f.isin.length > 5) score += 15;

  // Having full price data indicates transparency
  if (f.price_yesterday > 0) score += 5;
  if (f.price_max > 0 && f.price_min > 0) score += 5;

  // Named fund is more trustworthy
  if (f.name && f.name.length > 3) score += 5;

  // Real/legal data available
  if (f.buy_real_volume > 0 || f.buy_legal_volume > 0) score += 5;

  return clampScore(score);
}

// ── Issue detection ──

function issueById(id: number): FundIssue {
  const found = ISSUES.find((i) => i.id === id);
  if (!found) throw new Error(`Issue id ${id} not found`);
  return found;
}

export function detectIssues(fund: Fund): FundIssue[] {
  const detected: FundIssue[] = [];

  // Financial issues
  if (fund.nav_change_pct < -2) detected.push(issueById(2)); // نوسان شدید
  if (fund.nav_change_pct < -1) detected.push(issueById(51)); // بازدهی پایین‌تر از شاخص
  if (fund.nav_change_pct < -0.5) detected.push(issueById(101)); // بازدهی پایین در مقایسه

  // Liquidity issues
  if (fund.trade_volume < 100_000) detected.push(issueById(3)); // نقدشوندگی پایین
  if (fund.trade_volume < 50_000) detected.push(issueById(4)); // عدم بازارگردان
  if (fund.trade_volume < 500_000) detected.push(issueById(58)); // حجم پایین

  // Price spread
  if (fund.price_min > 0) {
    const spread = ((fund.price_max - fund.price_min) / ((fund.price_max + fund.price_min) / 2)) * 100;
    if (spread > 5) detected.push(issueById(5)); // شکاف قیمت بالا
  }

  // Risk issues
  if (fund.nav_change_pct < -3) detected.push(issueById(9)); // ریسک‌پذیری بیش از حد
  if (fund.nav_change_pct < -2) detected.push(issueById(68)); // حداکثر افت بالا

  // Management issues
  if (fund.shares_count < 1_000_000) detected.push(issueById(6)); // مدیریت ناپایدار
  if (fund.market_value < 50_000_000_000) detected.push(issueById(28)); // تجربه ناکافی

  // Cost issues
  if (fund.price_last > 0 && fund.nav > 0) {
    const premium = ((fund.price_last - fund.nav) / fund.nav) * 100;
    if (premium > 5) detected.push(issueById(11)); // هزینه صدور بالا
  }

  // Remove duplicates (keep lowest id = highest priority)
  const seen = new Set<number>();
  return detected.filter((d) => {
    if (seen.has(d.id)) return false;
    seen.add(d.id);
    return true;
  }).slice(0, 8); // max 8 issues
}

// ── Risk level ──

export function determineRiskLevel(scores: FundScore, issues: FundIssue[]): "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" {
  const criticalIssues = issues.filter((i) => i.priority === "A1").length;
  if (scores.total < 35 || criticalIssues >= 3) return "CRITICAL";
  if (scores.total < 55 || criticalIssues >= 2) return "HIGH";
  if (scores.total < 70 || criticalIssues >= 1) return "MEDIUM";
  return "LOW";
}

// ── Recommendation ──

export function determineRecommendation(
  totalScore: number,
  riskLevel: string,
  issues: FundIssue[]
): "STRONG_BUY" | "BUY" | "WATCHLIST" | "HOLD" | "REDUCE" | "SELL" | "AVOID" {
  const criticalCount = issues.filter((i) => i.priority === "A1").length;

  if (totalScore >= 80 && riskLevel !== "HIGH" && riskLevel !== "CRITICAL") return "STRONG_BUY";
  if (totalScore >= 70 && riskLevel !== "CRITICAL") return "BUY";
  if (totalScore >= 60 && riskLevel !== "HIGH") return "WATCHLIST";
  if (totalScore >= 50) return "HOLD";
  if (totalScore >= 40) return "REDUCE";
  if (totalScore >= 25) return "SELL";
  return "AVOID";
}

// ── Strengths & Weaknesses ──

function getStrengths(scores: FundScore): string[] {
  const s: string[] = [];
  const entries: [string, number][] = [
    ["مالی", scores.financial],
    ["نقدشوندگی", scores.liquidity],
    ["مدیریت", scores.management],
    ["ریسک", scores.risk],
    ["هزینه", scores.cost],
    ["شفافیت", scores.transparency],
  ];
  for (const [name, score] of entries) {
    if (score >= 70) s.push(`${name}: ${score}%`);
  }
  return s.slice(0, 4);
}

function getWeaknesses(scores: FundScore): string[] {
  const w: string[] = [];
  const entries: [string, number][] = [
    ["مالی", scores.financial],
    ["نقدشوندگی", scores.liquidity],
    ["مدیریت", scores.management],
    ["ریسک", scores.risk],
    ["هزینه", scores.cost],
    ["شفافیت", scores.transparency],
  ];
  for (const [name, score] of entries) {
    if (score < 50) w.push(`${name}: ${score}%`);
  }
  return w.slice(0, 4);
}

// ── Summary & Next Steps ──

function generateSummary(score: number, recommendation: string, issueCount: number): string {
  const status =
    score >= 75 ? "عالی" :
    score >= 60 ? "قابل قبول" :
    score >= 40 ? "نیازمند بهبود" : "ضعیف";
  return `امتیاز کلی: ${score}% - وضعیت: ${status} - ${issueCount} مشکل شناسایی شده`;
}

function getNextSteps(recommendation: string): string[] {
  switch (recommendation) {
    case "STRONG_BUY":
    case "BUY":
      return [
        "بررسی دقیق ترکیب دارایی صندوق",
        "مقایسه با صندوق‌های مشابه",
        "تعیین حجم سرمایه‌گذاری متناسب با ریسک",
        "برنامه‌ریزی برای ورود پلکانی",
      ];
    case "WATCHLIST":
      return [
        "بررسی دوره‌ای عملکرد صندوق (ماهانه)",
        "تحلیل تغییرات ترکیب دارایی",
        "پیگیری اخبار و رویدادهای مرتبط",
      ];
    case "HOLD":
      return [
        "بررسی دوره‌ای عملکرد هر ۳ ماه",
        "تحلیل هزینه‌ها و کارمزدها",
        "مقایسه با صندوق‌های جدید",
      ];
    case "REDUCE":
      return [
        "کاهش تدریجی سرمایه‌گذاری",
        "انتقال بخشی به صندوق‌های با عملکرد بهتر",
        "بررسی دقیق علت عملکرد ضعیف",
      ];
    case "SELL":
    case "AVOID":
      return [
        "برنامه‌ریزی برای خروج کامل",
        "انتقال سرمایه به صندوق‌های با امتیاز بالاتر",
        "تحلیل هزینه‌های خروج",
      ];
    default:
      return ["بررسی مجدد شرایط صندوق"];
  }
}

function clampScore(s: number): number {
  return Math.max(0, Math.min(100, s));
}
