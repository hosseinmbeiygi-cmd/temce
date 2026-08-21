/**
 * Realistic mock data for the premium navy/white market dashboard.
 * All money figures are in میلیارد تومان (billion toman).
 */

export interface TickerItem {
  symbol: string;
  price: number;
  changePct: number;
  market: string;
}

export interface QuoteItem {
  id: string;
  title: string;
  subtitle: string;
  price: number;
  unit: string;
  change: number;
  changePct: number;
  spark: number[];
  kind: "gold" | "coin" | "dollar" | "tether" | "euro" | "dirham";
}

export interface IndexQuote {
  id: string;
  name: string;
  short: string;
  value: number;
  change: number;
  changePct: number;
  spark: number[];
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  time: string;
  published_at?: string;
  sentiment: "positive" | "negative" | "neutral";
  symbols: string[];
}

export interface SectorCell {
  name: string;
  changePct: number;
  count: number;
}

export interface AssetSlice {
  label: string;
  value: number;
  color: string;
}

export interface TopStock {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  tradeValueB: number;
}

export interface OwnershipRow {
  symbol: string;
  name: string;
  realNet: number;
  legalNet: number;
}

export interface ImpactRow {
  symbol: string;
  name: string;
  impact: number;
}

export interface Top5Symbol {
  symbol: string;
  name: string;
  tradeValueB: number;
  changePct: number;
}

export interface Breadth {
  up: number;
  down: number;
  flat: number;
}

export interface SectorFlowBar {
  name: string;
  value: number;
}

export interface ValueDayBar {
  day: string;
  value: number;
}

export interface OwnershipDayBar {
  day: string;
  real: number;
  legal: number;
}

export interface SearchSymbol {
  symbol: string;
  name: string;
  market: string;
}

export interface GlobalQuote {
  id: string;
  title: string;
  subtitle: string;
  price: number;
  unit: string;
  changePct: number;
  spark: number[];
}

export interface IntradayPoint {
  time: string;
  value: number;
}

export interface MarketEvent {
  id: string;
  title: string;
  date: string;
  day: string;
  type: "مجمع" | "سود نقدی" | "افزایش سرمایه" | "اعلامیه";
  symbol: string;
}

/* ── Market session ─────────────────────────────────────────── */

/**
 * وضعیت زنده بازار بر اساس ساعت و روز تهران (Asia/Tehran).
 * سشن بورس/فرابورس: شنبه تا چهارشنبه، ۰۸:۴۵ تا ۱۲:۳۰.
 * تعطیلات رسمی ایران (شمسی ثابت + قمری متغیر) نیز لحاظ می‌شود.
 */
export interface MarketSession {
  dateFa: string;
  status: string;
  note: string;
  isOpen: boolean;
  /** نام تعطیل رسمی امروز (اگر تعطیل باشد)، وگرنه null */
  holiday: string | null;
  /** epoch ms رویداد بعدی بازار (بازگشایی/بستن) — برای countdown */
  nextEventAt: number | null;
  /** برچسب رویداد بعدی: "بازگشایی بازار" | "بستن بازار" */
  nextEventLabel: string;
}

const MARKET_OPEN_MIN = 8 * 60 + 45; // 08:45
const MARKET_CLOSE_MIN = 12 * 60 + 30; // 12:30
const TRADING_WEEKDAYS = new Set(["Sat", "Sun", "Mon", "Tue", "Wed"]);

// ── تعطیلات ثابت شمسی (هر سال یکسان — بر اساس تقویم جلالی) ──
// کلید: ماه/روز شمسی (۱-۱۲ / ۱-۳۱)
const SOLAR_HOLIDAYS: Record<string, string> = {
  "1/1": "نوروز",
  "1/2": "نوروز",
  "1/3": "نوروز",
  "1/4": "نوروز",
  "1/12": "روز جمهوری اسلامی",
  "1/13": "روز طبیعت",
  "3/14": "رحلت امام خمینی",
  "3/15": "قیام ۱۵ خرداد",
  "11/22": "پیروزی انقلاب اسلامی",
  "12/29": "ملی‌شدن صنعت نفت",
};

// ── تعطیلات قمری متغیر (هر سال جابه‌جا می‌شود — جدول میلادی) ──
// کلید: تاریخ میلادی YYYY-MM-DD. این جدول برای سال‌های شمسی ۱۴۰۴ و ۱۴۰۵
// تنظیم شده؛ برای سال‌های بعد باید به‌روزرسانی شود.
const LUNAR_HOLIDAYS: Record<string, string> = {
  // ۱۴۰۴ (۲۰۲۵-۲۰۲۶)
  "2025-03-31": "عید فطر",
  "2025-04-01": "عید فطر",
  "2025-06-06": "عید قربان",
  "2025-06-14": "عید غدیر خم",
  "2025-06-26": "تاسوعا",
  "2025-06-27": "عاشورا",
  "2025-08-05": "اربعین",
  "2025-08-13": "رحلت پیامبر اکرم",
  "2025-08-15": "شهادت امام رضا",
  "2025-09-01": "میلاد پیامبر اکرم",
  // ۱۴۰۵ (۲۰۲۶-۲۰۲۷)
  "2026-03-21": "عید فطر",
  "2026-03-22": "عید فطر",
  "2026-05-27": "عید قربان",
  "2026-06-04": "عید غدیر خم",
  "2026-06-24": "تاسوعا",
  "2026-06-25": "عاشورا",
  "2026-08-04": "اربعین",
  "2026-08-12": "رحلت پیامبر اکرم",
  "2026-08-14": "شهادت امام رضا",
  "2026-08-30": "میلاد پیامبر اکرم",
  "2027-03-10": "عید فطر",
  "2027-03-11": "عید فطر",
};

function teheranParts(now: Date) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Tehran",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);
}

function teheranYmdKey(now: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** تاریخ شمسی به‌صورت «ماه/روز» برای جستجو در تعطیلات ثابت. */
function teheranSolarMD(now: Date): string {
  const parts = new Intl.DateTimeFormat("en-US-u-ca-persian", {
    timeZone: "Asia/Tehran",
    month: "numeric",
    day: "numeric",
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${Number(get("month"))}/${Number(get("day"))}`;
}

/** نام تعطیل رسمی امروز (تهران) یا null اگر تعطیل نیست. */
export function getIranianHoliday(now = new Date()): string | null {
  const solar = SOLAR_HOLIDAYS[teheranSolarMD(now)];
  if (solar) return solar;
  return LUNAR_HOLIDAYS[teheranYmdKey(now)] ?? null;
}

function toFaDate(now: Date): string {
  return new Intl.DateTimeFormat("fa-IR", { timeZone: "Asia/Tehran" }).format(now);
}

/**
 * Epoch ms برای یک ساعت مشخص در روز جاری تهران.
 * (محاسبه ساده با offset ثابت +03:30 — بدون احتساب DST.)
 */
function tehranMidnightUtc(now: Date): number {
  const ymd = teheranYmdKey(now);
  const [y, m, d] = ymd.split("-").map(Number);
  return Date.UTC(y, m - 1, d) - 3.5 * 3600_000;
}

function addDaysTehran(now: Date, days: number): Date {
  return new Date(tehranMidnightUtc(now) + days * 86_400_000 + 12 * 3600_000);
}

export function getMarketSession(now = new Date()): MarketSession {
  const parts = teheranParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const weekday = get("weekday");
  const minutes = Number(get("hour")) * 60 + Number(get("minute"));
  const holiday = getIranianHoliday(now);

  const isWeekend = !TRADING_WEEKDAYS.has(weekday);
  const isTradingDay = !isWeekend && !holiday;
  const isOpen = isTradingDay && minutes >= MARKET_OPEN_MIN && minutes < MARKET_CLOSE_MIN;

  let status = "بسته";
  let note = "بازار سرمایه بسته است — معاملات فردا ساعت ۰۸:۴۵";
  if (holiday) {
    status = "تعطیل";
    note = `بازار سرمایه تعطیل است — ${holiday}`;
  } else if (isWeekend) {
    status = "تعطیل";
    note = "بازار سرمایه تعطیل است — معاملات از شنبه";
  } else if (minutes < MARKET_OPEN_MIN) {
    note = "بازار سرمایه بسته است — بازگشایی ساعت ۰۸:۴۵";
  } else if (isOpen) {
    status = "باز";
    note = "بازار سرمایه باز است — تا ساعت ۱۲:۳۰";
  }

  // ── رویداد بعدی برای countdown ──
  let nextEventAt: number | null = null;
  let nextEventLabel = "";
  if (isOpen) {
    // در حال باز بودن → تا بستن (امروز ۱۲:۳۰)
    nextEventAt = tehranMidnightUtc(now) + MARKET_CLOSE_MIN * 60_000;
    nextEventLabel = "بستن بازار";
  } else {
    // بسته → تا بازگشایی بعدی (فردا یا اولین روز معاملاتی بعد).
    // اگر امروز روز معاملاتی است ولی ساعتش گذشته (بعد از ۱۲:۳۰)،
    // بازگشایی «امروز ۰۸:۴۵» قبلاً سپری شده — باید از فردا شروع کنیم.
    const startOffset = isTradingDay && minutes >= MARKET_CLOSE_MIN ? 1 : 0;
    for (let i = startOffset; i < 8; i++) {
      const cand = addDaysTehran(now, i);
      const candWeekday = new Intl.DateTimeFormat("en-US", {
        timeZone: "Asia/Tehran",
        weekday: "short",
      }).format(cand);
      if (TRADING_WEEKDAYS.has(candWeekday) && !getIranianHoliday(cand)) {
        nextEventAt = tehranMidnightUtc(cand) + MARKET_OPEN_MIN * 60_000;
        nextEventLabel = "بازگشایی بازار";
        break;
      }
    }
  }

  return { dateFa: toFaDate(now), status, note, isOpen, holiday, nextEventAt, nextEventLabel };
}

/** Legacy static constant — kept for imports that only need a default shape. */
export const MARKET_SESSION = getMarketSession();

/* ── Ticker / Sitebar strip ─────────────────────────────────── */

export const TICKER_ITEMS: TickerItem[] = [
  { symbol: "شاخص کل", price: 2486500, changePct: 0.5, market: "بورس" },
  { symbol: "هموزن", price: 848220, changePct: -0.25, market: "بورس" },
  { symbol: "دلار", price: 105850, changePct: 0.82, market: "ارز" },
  { symbol: "سکه امامی", price: 98650000, changePct: 1.24, market: "طلا" },
  { symbol: "طلای ۱۸", price: 7856400, changePct: 0.61, market: "طلا" },
  { symbol: "تتر", price: 108200, changePct: 0.94, market: "دیجیتال" },
  { symbol: "یورو", price: 118420, changePct: -0.38, market: "ارز" },
  { symbol: "فولاد", price: 14850, changePct: 2.31, market: "بورس" },
  { symbol: "شستا", price: 1260, changePct: 1.85, market: "بورس" },
  { symbol: "فملی", price: 9740, changePct: -1.62, market: "بورس" },
  { symbol: "خساپا", price: 620, changePct: 3.08, market: "بورس" },
  { symbol: "کگل", price: 2340, changePct: -2.15, market: "فرابورس" },
];

/* ── Quote cards: طلا / سکه / ارزها / تتر / دلار ─────────────── */

export const QUOTES: QuoteItem[] = [
  {
    id: "gold18",
    title: "طلای ۱۸ عیار",
    subtitle: "هر گرم",
    price: 7856400,
    unit: "تومان",
    change: 48200,
    changePct: 0.61,
    kind: "gold",
    spark: [7.41, 7.43, 7.47, 7.5, 7.52, 7.55, 7.58, 7.61, 7.63, 7.66, 7.71, 7.86],
  },
  {
    id: "coin",
    title: "سکه امامی",
    subtitle: "طرح جدید",
    price: 98650000,
    unit: "تومان",
    change: 1210000,
    changePct: 1.24,
    kind: "coin",
    spark: [94.2, 94.8, 95.1, 95.9, 96.4, 96.8, 97.5, 98.1, 98.65],
  },
  {
    id: "dollar",
    title: "دلار",
    subtitle: "بازار آزاد",
    price: 105850,
    unit: "تومان",
    change: 860,
    changePct: 0.82,
    kind: "dollar",
    spark: [103.6, 104.1, 104.4, 104.9, 105.2, 105.6, 105.85],
  },
  {
    id: "tether",
    title: "تتر",
    subtitle: "پ2پ",
    price: 108200,
    unit: "تومان",
    change: 1008,
    changePct: 0.94,
    kind: "tether",
    spark: [106.9, 107.3, 107.6, 107.9, 108.2, 108.2],
  },
  {
    id: "euro",
    title: "یورو",
    subtitle: "بازار آزاد",
    price: 118420,
    unit: "تومان",
    change: -452,
    changePct: -0.38,
    kind: "euro",
    spark: [120.4, 119.9, 119.5, 119.1, 118.9, 118.4],
  },
  {
    id: "dirham",
    title: "درهم",
    subtitle: "بازار آزاد",
    price: 29050,
    unit: "تومان",
    change: 190,
    changePct: 0.66,
    kind: "dirham",
    spark: [28.5, 28.7, 28.8, 28.9, 29.0, 29.05],
  },
];

/* ── Global markets (S&P / SINX pattern) ────────────────────── */

export const GLOBAL_MARKETS: GlobalQuote[] = [
  { id: "sp500", title: "S&P 500", subtitle: "شاخص آمریکا", price: 5410.8, unit: "واحد", changePct: 0.62, spark: [5348, 5362, 5375, 5389, 5398, 5405, 5410] },
  { id: "dow", title: "داو جونز", subtitle: "شاخص آمریکا", price: 43102.5, unit: "واحد", changePct: 0.31, spark: [42984, 43012, 43045, 43071, 43088, 43096, 43102] },
  { id: "nasdaq", title: "ناسداک", subtitle: "شاخص آمریکا", price: 17688.3, unit: "واحد", changePct: 0.84, spark: [17321, 17398, 17485, 17562, 17601, 17654, 17688] },
  { id: "gold-oz", title: "انس طلا", subtitle: "کامکس", price: 2408.6, unit: "دلار", changePct: 0.45, spark: [2388, 2392, 2396, 2400, 2403, 2406, 2408] },
  { id: "brent", title: "نفت برنت", subtitle: "ICE", price: 84.6, unit: "دلار", changePct: -1.12, spark: [86.1, 85.9, 85.6, 85.3, 85.0, 84.8, 84.6] },
  { id: "btc", title: "بیت‌کوین", subtitle: "رمزارز", price: 63480, unit: "دلار", changePct: 1.9, spark: [61020, 61540, 61980, 62410, 62850, 63120, 63480] },
];

/* ── Indices ────────────────────────────────────────────────── */

export const INDICES: IndexQuote[] = [
  {
    id: "idx-tse",
    name: "شاخص کل بورس",
    short: "شاخص کل",
    value: 2486500,
    change: 12340,
    changePct: 0.5,
    spark: [2412, 2421, 2438, 2450, 2461, 2473, 2486],
  },
  {
    id: "idx-equal",
    name: "شاخص کل هم‌وزن",
    short: "هم‌وزن",
    value: 848220,
    change: -2124,
    changePct: -0.25,
    spark: [856, 854, 853, 851, 850, 849, 848],
  },
  {
    id: "idx-price",
    name: "شاخص قیمت (وزنی-ارزشی)",
    short: "قیمت",
    value: 348900,
    change: 1850,
    changePct: 0.53,
    spark: [339, 340, 342, 344, 345, 347, 348],
  },
  {
    id: "idx-otc",
    name: "شاخص کل فرابورس",
    short: "فرابورس",
    value: 26152,
    change: -76,
    changePct: -0.29,
    spark: [2631, 2629, 2626, 2623, 2620, 2618, 2615],
  },
  {
    id: "idx-float",
    name: "شاخص آزاد شناور",
    short: "شناور",
    value: 27804,
    change: 138,
    changePct: 0.5,
    spark: [2704, 2712, 2725, 2736, 2749, 2761, 2771, 2780],
  },
  {
    id: "idx-industry",
    name: "شاخص صنعت",
    short: "صنعت",
    value: 2315400,
    change: 14700,
    changePct: 0.64,
    spark: [2234, 2248, 2261, 2279, 2292, 2301, 2315],
  },
];

/* ── شاخص کل — روند امروز (داخل روز) ─────────────────────────── */

export const INDEX_INTRADAY: IntradayPoint[] = [
  { time: "09:00", value: 2468010 },
  { time: "09:15", value: 2471280 },
  { time: "09:30", value: 2469530 },
  { time: "09:45", value: 2473140 },
  { time: "10:00", value: 2475820 },
  { time: "10:15", value: 2474210 },
  { time: "10:30", value: 2477930 },
  { time: "10:45", value: 2480540 },
  { time: "11:00", value: 2479140 },
  { time: "11:15", value: 2482430 },
  { time: "11:30", value: 2484520 },
  { time: "11:45", value: 2486230 },
  { time: "12:00", value: 2485020 },
  { time: "12:15", value: 2486500 },
];

/* ── News strip ─────────────────────────────────────────────── */

export const NEWS: NewsItem[] = [
  {
    id: "n1",
    title: "شاخص کل بورس از مرز ۲ میلیون و ۴۸۶ هزار واحد عبور کرد",
    source: "اقتصادنیوز",
    time: "10:42",
    sentiment: "positive",
    symbols: ["شاخص کل"],
  },
  {
    id: "n2",
    title: "بازگشت تقاضا به سهام پتروشیمی پس از دو هفته اصلاح",
    source: "دنیای اقتصاد",
    time: "10:18",
    sentiment: "positive",
    symbols: ["شپنا", "پارسان"],
  },
  {
    id: "n3",
    title: "افزایش نرخ دلار آزاد؛ اثرگذاری بر سودآوری صادرات‌محورها",
    source: "اکوایران",
    time: "09:55",
    sentiment: "neutral",
    symbols: ["فولاد", "فملی"],
  },
  {
    id: "n4",
    title: "سکه امامی در کانال ۹۸ میلیون تومان معامله شد",
    source: "بازار",
    time: "09:31",
    sentiment: "negative",
    symbols: ["سکه"],
  },
  {
    id: "n5",
    title: "واریز مرحله دوم سود سهام عدالت آغاز شد",
    source: "تسنیم",
    time: "09:12",
    sentiment: "positive",
    symbols: [],
  },
  {
    id: "n6",
    title: "توقف عرضه خودرو در بورس کالا؛ واکنش نمادهای گروه خودرو",
    source: "ایبِنا",
    time: "08:47",
    sentiment: "negative",
    symbols: ["خودرو", "خساپا"],
  },
];

/* ── Market map (sectors) ───────────────────────────────────── */

export type MapView = "stocks" | "funds" | "monthly";

export const MARKET_MAP_SECTORS: SectorCell[] = [
  { name: "فلزات اساسی", changePct: 2.4, count: 32 },
  { name: "شیمیایی", changePct: 1.8, count: 41 },
  { name: "فرآورده‌های نفتی", changePct: 1.5, count: 12 },
  { name: "بانک‌ها", changePct: 1.1, count: 18 },
  { name: "خودرو", changePct: 0.8, count: 22 },
  { name: "کانه فلزی", changePct: 0.6, count: 15 },
  { name: "سیمان", changePct: 0.4, count: 27 },
  { name: "مخابرات", changePct: 0.2, count: 6 },
  { name: "دارویی", changePct: 0.0, count: 25 },
  { name: "غذایی", changePct: -0.2, count: 28 },
  { name: "بیمه", changePct: -0.4, count: 9 },
  { name: "سرمایه‌گذاری", changePct: -0.6, count: 35 },
  { name: "ماشین‌آلات", changePct: -0.9, count: 8 },
  { name: "انبوه‌سازی", changePct: -1.2, count: 14 },
  { name: "زراعت", changePct: -1.5, count: 5 },
  { name: "قند و شکر", changePct: -1.8, count: 10 },
  { name: "کاشی و سرامیک", changePct: -2.1, count: 7 },
  { name: "لاستیک", changePct: 0.3, count: 4 },
  { name: "نساجی", changePct: -0.1, count: 11 },
  { name: "حمل و نقل", changePct: 0.9, count: 6 },
];

export const FUND_MAP_SECTORS: SectorCell[] = [
  { name: "سهامی", changePct: 1.9, count: 42 },
  { name: "طلا", changePct: 1.4, count: 12 },
  { name: "جسورانه", changePct: 1.1, count: 4 },
  { name: "نقره", changePct: 0.9, count: 2 },
  { name: "بخشی", changePct: 0.8, count: 9 },
  { name: "اهرمی", changePct: 0.6, count: 5 },
  { name: "مختلط", changePct: 0.5, count: 7 },
  { name: "تضمین سرمایه", changePct: 0.2, count: 6 },
  { name: "درآمد ثابت", changePct: 0.1, count: 35 },
  { name: "املاک", changePct: -0.3, count: 3 },
];

export const MONTHLY_MAP_SECTORS: SectorCell[] = [
  { name: "فلزات", changePct: 6.8, count: 32 },
  { name: "پتروشیمی", changePct: 4.2, count: 41 },
  { name: "نفتی", changePct: 5.1, count: 12 },
  { name: "دارو", changePct: 3.4, count: 25 },
  { name: "بانک", changePct: 2.9, count: 18 },
  { name: "ماشین‌آلات", changePct: 2.2, count: 8 },
  { name: "غذایی", changePct: 1.2, count: 28 },
  { name: "بیمه", changePct: 0.7, count: 9 },
  { name: "مخابرات", changePct: -0.9, count: 6 },
  { name: "خودرو", changePct: -1.8, count: 22 },
  { name: "سیمان", changePct: -2.6, count: 27 },
  { name: "کانی", changePct: -3.4, count: 15 },
];

/* ── Asset allocation (donut) ───────────────────────────────── */

export const ASSET_ALLOCATION: AssetSlice[] = [
  { label: "سهام", value: 35, color: "#33486b" },
  { label: "اوراق درآمد ثابت", value: 22, color: "#718db0" },
  { label: "صندوق سهامی", value: 16, color: "#a3b7d2" },
  { label: "صندوق طلا", value: 12, color: "#d97706" },
  { label: "نقد", value: 9, color: "#64748b" },
  { label: "ارز و تتر", value: 6, color: "#16a34a" },
];

/* ── Top stocks today ───────────────────────────────────────── */

export const TOP_STOCKS_TODAY: TopStock[] = [
  { symbol: "خساپا", name: "سایپا", price: 620, changePct: 3.08, tradeValueB: 765.2 },
  { symbol: "فولاد", name: "فولاد مبارکه", price: 14850, changePct: 2.31, tradeValueB: 1240.8 },
  { symbol: "شستا", name: "س.تأمین اجتماعی", price: 1260, changePct: 1.85, tradeValueB: 985.4 },
  { symbol: "شپنا", name: "پالایش نفت اصفهان", price: 24350, changePct: 1.42, tradeValueB: 643.7 },
  { symbol: "وبملت", name: "بانک ملت", price: 980, changePct: 1.18, tradeValueB: 872.1 },
  { symbol: "پارسان", name: "پتروشیمی پارس", price: 27450, changePct: 1.05, tradeValueB: 520.3 },
  { symbol: "کگل", name: "گل‌گهر", price: 2340, changePct: 0.92, tradeValueB: 648.3 },
  { symbol: "فملی", name: "ملی صنایع مس", price: 9740, changePct: 0.78, tradeValueB: 431.9 },
  { symbol: "خودرو", name: "ایران‌خودرو", price: 4150, changePct: 0.65, tradeValueB: 388.4 },
  { symbol: "وتجارت", name: "بانک تجارت", price: 3120, changePct: 0.54, tradeValueB: 356.7 },
  { symbol: "ذوب", name: "ذوب‌آهن اصفهان", price: 1890, changePct: 0.48, tradeValueB: 302.1 },
  { symbol: "شتران", name: "پالایش نفت تهران", price: 12650, changePct: 0.41, tradeValueB: 287.5 },
];

/* ── Ownership flow (حقیقی/حقوقی) ───────────────────────────── */

export const OWNERSHIP_CHANGE: OwnershipRow[] = [
  { symbol: "فولاد", name: "فولاد مبارکه", realNet: 320, legalNet: -318 },
  { symbol: "شستا", name: "س.تأمین اجتماعی", realNet: 281, legalNet: -277 },
  { symbol: "خساپا", name: "سایپا", realNet: 194, legalNet: -191 },
  { symbol: "کگل", name: "گل‌گهر", realNet: 152, legalNet: -150 },
  { symbol: "وبملت", name: "بانک ملت", realNet: -92, legalNet: 95 },
  { symbol: "فملی", name: "ملی صنایع مس", realNet: -124, legalNet: 121 },
];

/* ── Index impacts ──────────────────────────────────────────── */

export const INDEX_IMPACT_POSITIVE: ImpactRow[] = [
  { symbol: "فولاد", name: "فولاد مبارکه", impact: 87.4 },
  { symbol: "شستا", name: "س.تأمین اجتماعی", impact: 64.2 },
  { symbol: "پارسان", name: "پتروشیمی پارس", impact: 52.8 },
  { symbol: "خساپا", name: "سایپا", impact: 41.3 },
  { symbol: "وبملت", name: "بانک ملت", impact: 35.6 },
];

export const INDEX_IMPACT_NEGATIVE: ImpactRow[] = [
  { symbol: "فملی", name: "ملی صنایع مس", impact: -96.5 },
  { symbol: "کگل", name: "گل‌گهر", impact: -48.1 },
  { symbol: "وتجارت", name: "بانک تجارت", impact: -32.4 },
  { symbol: "خودرو", name: "ایران‌خودرو", impact: -21.7 },
  { symbol: "ذوب", name: "ذوب‌آهن", impact: -14.2 },
];

/* ── Value / Volume + Top5 (بورس و فرابورس) ─────────────────── */

export const VALUE_VOLUME = {
  tradeValueB: 12842.5,
  prevTradeValueB: 11867.2,
  volumeM: 11260,
  prevVolumeM: 10380,
  dealsK: 1284,
  avgChangePct: 2.06,
  breadth: { up: 284, down: 312, flat: 41 } as Breadth,
  totalCapB: 7486250,
  peRatio: 7.6,
  top5Tse: [
    { symbol: "فولاد", name: "فولاد مبارکه", tradeValueB: 1240.8, changePct: 2.31 },
    { symbol: "شستا", name: "س.تأمین اجتماعی", tradeValueB: 985.4, changePct: 1.85 },
    { symbol: "وبملت", name: "بانک ملت", tradeValueB: 872.1, changePct: 1.18 },
    { symbol: "خساپا", name: "سایپا", tradeValueB: 765.2, changePct: 3.08 },
    { symbol: "پارسان", name: "پتروشیمی پارس", tradeValueB: 720.6, changePct: 0.95 },
    { symbol: "شپنا", name: "پالایش نفت اصفهان", tradeValueB: 643.7, changePct: 1.42 },
    { symbol: "فملی", name: "ملی صنایع مس", tradeValueB: 431.9, changePct: 0.78 },
    { symbol: "خودرو", name: "ایران‌خودرو", tradeValueB: 388.4, changePct: 0.65 },
    { symbol: "وتجارت", name: "بانک تجارت", tradeValueB: 356.7, changePct: 0.54 },
    { symbol: "شتران", name: "پالایش نفت تهران", tradeValueB: 287.5, changePct: 0.41 },
  ] as Top5Symbol[],
  top5Otc: [
    { symbol: "کگل", name: "گل‌گهر", tradeValueB: 648.3, changePct: -2.15 },
    { symbol: "وسپهر", name: "س.سپهر", tradeValueB: 542.7, changePct: 1.34 },
    { symbol: "دی", name: "بانک دی", tradeValueB: 481.2, changePct: 2.6 },
    { symbol: "انرژی۳", name: "انرژی سه", tradeValueB: 432.9, changePct: 0.7 },
    { symbol: "فایرا", name: "آلومراد", tradeValueB: 394.5, changePct: -0.85 },
    { symbol: "غصینو", name: "سینا خلیج‌فارس", tradeValueB: 322.8, changePct: 1.12 },
    { symbol: "زمینی", name: "توسعه زمین و ساختمان", tradeValueB: 281.4, changePct: -0.42 },
    { symbol: "وثنو", name: "س.صنایع و معادن", tradeValueB: 254.9, changePct: 0.88 },
    { symbol: "کیسون", name: "کیسون", tradeValueB: 236.1, changePct: 2.1 },
    { symbol: "کرومیت", name: "توسعه معادن کرومیت", tradeValueB: 218.7, changePct: -1.3 },
  ] as Top5Symbol[],
};

/* ── Three coordinated charts ───────────────────────────────── */

export const CASHFLOW_BY_SECTOR: SectorFlowBar[] = [
  { name: "بانک‌ها", value: 420 },
  { name: "فلزات", value: 362 },
  { name: "پتروشیمی", value: 241 },
  { name: "نفتی", value: 118 },
  { name: "دارو", value: 76 },
  { name: "خودرو", value: -48 },
  { name: "مخابرات", value: -62 },
  { name: "کانی", value: -114 },
  { name: "سیمان", value: -151 },
  { name: "غذایی", value: -207 },
];

export const VALUE_LAST_DAYS: ValueDayBar[] = [
  { day: "شنبه", value: 8412 },
  { day: "یکشنبه", value: 9158 },
  { day: "دوشنبه", value: 7643 },
  { day: "سه‌شنبه", value: 10206 },
  { day: "چهارشنبه", value: 12843 },
];

export const OWNERSHIP_LAST_DAYS: OwnershipDayBar[] = [
  { day: "شنبه", real: 412, legal: -406 },
  { day: "یکشنبه", real: -183, legal: 180 },
  { day: "دوشنبه", real: 476, legal: -469 },
  { day: "سه‌شنبه", real: 689, legal: -682 },
  { day: "چهارشنبه", real: 290, legal: -284 },
];

/* ── Liquidity / Cash flow / Top performers blocks ──────────── */

export const LIQUIDITY = {
  totalB: 12842.5,
  deltaPct: 8.2,
  cashDistribution: [
    { label: "سهام خرد", value: 58, color: "#33486b" },
    { label: "صندوق‌ها", value: 24, color: "#718db0" },
    { label: "اختیار", value: 11, color: "#a3b7d2" },
    { label: "اوراق", value: 7, color: "#d97706" },
  ],
};

export const CASH_FLOW = {
  realNetInflowB: 1423.7,
  legalNetInflowB: -1388.2,
  queueBuy: 82,
  queueSell: 64,
};

export const TOP_PERFORMERS: TopStock[] = [
  { symbol: "خساپا", name: "سایپا", price: 620, changePct: 3.08, tradeValueB: 765.2 },
  { symbol: "فولاد", name: "فولاد مبارکه", price: 14850, changePct: 2.31, tradeValueB: 1240.8 },
  { symbol: "شستا", name: "س.تأمین اجتماعی", price: 1260, changePct: 1.85, tradeValueB: 985.4 },
  { symbol: "شپنا", name: "پالایش نفت اصفهان", price: 24350, changePct: 1.42, tradeValueB: 643.7 },
  { symbol: "وبملت", name: "بانک ملت", price: 980, changePct: 1.18, tradeValueB: 872.1 },
  { symbol: "پارسان", name: "پتروشیمی پارس", price: 27450, changePct: 1.05, tradeValueB: 520.3 },
  { symbol: "کگل", name: "گل‌گهر", price: 2340, changePct: 0.92, tradeValueB: 648.3 },
  { symbol: "فملی", name: "ملی صنایع مس", price: 9740, changePct: 0.78, tradeValueB: 431.9 },
  { symbol: "خودرو", name: "ایران‌خودرو", price: 4150, changePct: 0.65, tradeValueB: 388.4 },
  { symbol: "وتجارت", name: "بانک تجارت", price: 3120, changePct: 0.54, tradeValueB: 356.7 },
];

/* ── تقویم بازار ───────────────────────────────────────────── */

export const MARKET_EVENTS: MarketEvent[] = [
  { id: "e1", title: "مجمع عمومی عادی سالیانه فولاد مبارکه", date: "۱۴۰۵/۰۵/۲۰", day: "سه‌شنبه", type: "مجمع", symbol: "فولاد" },
  { id: "e2", title: "واریز سود نقدی بانک ملت", date: "۱۴۰۵/۰۵/۲۱", day: "چهارشنبه", type: "سود نقدی", symbol: "وبملت" },
  { id: "e3", title: "افزایش سرمایه شستا از محل تجدید ارزیابی", date: "۱۴۰۵/۰۵/۲۴", day: "شنبه", type: "افزایش سرمایه", symbol: "شستا" },
  { id: "e4", title: "اعلامیه EPS سالانه سایپا", date: "۱۴۰۵/۰۵/۲۶", day: "دوشنبه", type: "اعلامیه", symbol: "خساپا" },
  { id: "e5", title: "مجمع عادی به طور فوق‌العاده گل‌گهر", date: "۱۴۰۵/۰۵/۲۸", day: "چهارشنبه", type: "مجمع", symbol: "کگل" },
  { id: "e6", title: "واریز مرحله دوم سود سهام عدالت", date: "۱۴۰۵/۰۵/۳۰", day: "جمعه", type: "سود نقدی", symbol: "—" },
];

/* ── Symbol search index ────────────────────────────────────── */

export const SEARCH_SYMBOLS: SearchSymbol[] = [
  { symbol: "فولاد", name: "فولاد مبارکه", market: "بورس" },
  { symbol: "شستا", name: "س.تأمین اجتماعی", market: "بورس" },
  { symbol: "فملی", name: "ملی صنایع مس ایران", market: "بورس" },
  { symbol: "خساپا", name: "سایپا", market: "بورس" },
  { symbol: "وبملت", name: "بانک ملت", market: "بورس" },
  { symbol: "کگل", name: "گل‌گهر", market: "فرابورس" },
  { symbol: "پارسان", name: "پتروشیمی پارس", market: "بورس" },
  { symbol: "خودرو", name: "ایران‌خودرو", market: "بورس" },
  { symbol: "شپنا", name: "پالایش نفت اصفهان", market: "بورس" },
  { symbol: "ذوب", name: "ذوب‌آهن اصفهان", market: "بورس" },
  { symbol: "غصینو", name: "سینا خلیج‌فارس", market: "فرابورس" },
  { symbol: "وملت", name: "بانک ملت (سهام)", market: "بورس" },
  { symbol: "شتران", name: "پالایش نفت تهران", market: "بورس" },
  { symbol: "خودرو۱", name: "گواهی ایران‌خودرو", market: "بورس" },
];
