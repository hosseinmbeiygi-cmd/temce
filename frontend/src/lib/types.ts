// ── Market Index ──────────────────────────
export interface MarketIndex {
  name: string;
  value: string;
  change: number;
  changePercent: number;
  icon: string;
  isUp: boolean;
}

// ── Instrument / Symbol ───────────────────
export interface Instrument {
  symbol: string;
  name: string;
  industry: string;
  lastPrice: number;
  change: number;
  volume: number;
  marketCap: number;
  peRatio: number;
  eps: number;
  status: "active" | "inactive";
}

// ── Order Book ────────────────────────────
export interface OrderBookLevel {
  price: number;
  volume: number;
  count: number;
}

export interface OrderBook {
  symbol: string;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  lastPrice: number;
  spread: number;
}

// ── News ──────────────────────────────────
export interface NewsItem {
  id: string;
  title: string;
  summary: string;
  source: string;
  date: string;
  category: string;
  sentiment: "positive" | "negative" | "neutral";
  fullContent?: string;
  trending?: boolean;
}

// ── Expert Opinion ────────────────────────
export interface ExpertOpinion {
  id: string;
  name: string;
  role: string;
  avatar: string;
  text: string;
  symbols: string[];
  time: string;
}

// ── Signal ────────────────────────────────
export interface Signal {
  id: string;
  symbol: string;
  signal: "buy" | "sell" | "neutral";
  strength: number;
  horizon: string;
  confidence: "high" | "medium" | "low";
  strategy: string;
  created_at: string;
  price: number;
}

// ── Portfolio ─────────────────────────────
export interface PortfolioPosition {
  symbol: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  weightPct: number;
}

export interface Portfolio {
  id: string;
  name: string;
  initialCapital: number;
  currentValue: number;
  positions: PortfolioPosition[];
}

// ── Risk Metrics ──────────────────────────
export interface RiskMetric {
  label: string;
  value: string;
  status: "low" | "medium" | "high";
  description: string;
  progress: number;
}

// ── Technical Indicator ───────────────────
export interface TechnicalIndicator {
  name: string;
  value: string;
  status: "positive" | "negative" | "neutral";
  description: string;
}

// ── Financial Ratio ───────────────────────
export interface FinancialRatio {
  label: string;
  value: string;
  status: "positive" | "negative" | "neutral";
  description: string;
}

// ── AI Insight ────────────────────────────
export interface AIInsight {
  title: string;
  description: string;
  type: "positive" | "negative" | "neutral";
  icon: string;
}

// ── Heatmap Cell ──────────────────────────
export interface HeatmapCell {
  symbol: string;
  change: number;
  volume: number;
}

// ── Watchlist Item ────────────────────────
export interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
}

// ── Market Stats ──────────────────────────
export interface MarketStats {
  marketCap: number;
  totalVolume: number;
  totalTrades: number;
  indexValue: number;
}

// ── Sentiment ─────────────────────────────
export interface SentimentData {
  date: string;
  score: number;
  positive: number;
  negative: number;
  neutral: number;
}

// ── Candle Data for Charts ────────────────
export interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ── Prediction ────────────────────────────
export interface Prediction {
  symbol: string;
  predictions: number[];
  confidence: number;
  dates: string[];
}

// ── Paginated Response ────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ── Chart Data Types ───────────────────────
export interface ChartDataPoint {
  time: string;
  value: number;
  volume?: number;
}

export interface PieChartData {
  name: string;
  value: number;
  color: string;
}

export interface SentimentPoint {
  date: string;
  score: number;
  positive: number;
  negative: number;
  neutral: number;
}

export interface CandleDataPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  isUp: boolean;
}

// ── Mock Data Generators ──────────────────
import { createRng, FIXED_NOW } from "@/lib/rng";

// ── Generate candlestick data ─────────────
export function generateCandleData(days: number = 60): CandleDataPoint[] {
  const rng = createRng(42);
  const data: CandleDataPoint[] = [];
  let price = 12450;
  const now = new Date(FIXED_NOW);

  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    // Skip weekends (Friday=5, Saturday=6 in Iran)
    if (d.getDay() === 5 || d.getDay() === 6) continue;

    const change = price * (rng() - 0.48) * 0.025;
    const open = price;
    const close = Math.round(price + change);
    const candleHigh = Math.max(open, close) + Math.round(rng() * price * 0.01);
    const candleLow = Math.min(open, close) - Math.round(rng() * price * 0.01);
    const volume = Math.round(500000 + rng() * 5000000);

    data.push({
      time: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      open,
      high: candleHigh,
      low: Math.max(candleLow, 1),
      close,
      volume,
      isUp: close >= open,
    });

    price = close;
  }
  return data;
}

export function generateIndexHistory(days: number = 180): ChartDataPoint[] {
  const rng = createRng(days * 1000 + 7);
  const data: ChartDataPoint[] = [];
  let value = 2100000;
  const now = new Date(FIXED_NOW);

  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    // Skip weekends (Friday=5, Saturday=6 in Iran)
    const day = d.getDay();
    if (day === 5 || day === 6) continue;

    const change = value * (rng() - 0.48) * 0.008;
    value = Math.max(value + change, 1800000);

    data.push({
      time: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      value: Math.round(value),
      volume: Math.round(5000000 + rng() * 15000000),
    });
  }
  return data;
}

export function generateSentimentHistory(days: number = 30): SentimentPoint[] {
  const rng = createRng(days * 3000 + 13);
  const data: SentimentPoint[] = [];
  const now = new Date(FIXED_NOW);

  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    if (d.getDay() === 5 || d.getDay() === 6) continue;

    const total = 100;
    const positive = Math.round(20 + rng() * 40);
    const negative = Math.round(10 + rng() * 30);
    const neutral = total - positive - negative;
    const score = positive - negative;

    data.push({
      date: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      score,
      positive,
      negative,
      neutral,
    });
  }
  return data;
}

export function generateSectorPerformance(): PieChartData[] {
  return [
    { name: "فلزات اساسی", value: 28, color: "#0891b2" },
    { name: "فرآورده‌های نفتی", value: 18, color: "#00b4d8" },
    { name: "بانکی", value: 15, color: "#7c3aed" },
    { name: "خودرو", value: 12, color: "#db2777" },
    { name: "پتروشیمی", value: 10, color: "#f59e0b" },
    { name: "سیمان", value: 8, color: "#10b981" },
    { name: "دارویی", value: 5, color: "#6366f1" },
    { name: "سایر", value: 4, color: "#64748b" },
  ];
}

export function generateVolumeData(days: number = 30): ChartDataPoint[] {
  const rng = createRng(days * 5000 + 29);
  const data: ChartDataPoint[] = [];
  const now = new Date(FIXED_NOW);
  let baseVolume = 12000000000;

  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    if (d.getDay() === 5 || d.getDay() === 6) continue;

    const volume = Math.round(baseVolume + (rng() - 0.5) * 8000000000);
    const sign = rng() > 0.5 ? 1 : -1;
    const change = Math.round((rng() * 3 + 0.1) * 100) / 100;

    data.push({
      time: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      value: Math.max(volume, 2000000000),
      volume: sign * change,
    });
  }
  return data;
}

export function generateMockIndices(): MarketIndex[] {
  return [
    { name: "شاخص کل بورس", value: "2,145,678", change: 1.24, changePercent: 1.24, icon: "trending_up", isUp: true },
    { name: "شاخص کل هم‌وزن", value: "8,765", change: 0.87, changePercent: 0.87, icon: "account_balance", isUp: true },
    { name: "طلای ۱۸ عیار", value: "2,345,000", change: -0.32, changePercent: -0.32, icon: "monetization_on", isUp: false },
    { name: "دلار آمریکا", value: "59,800", change: 0.15, changePercent: 0.15, icon: "currency_exchange", isUp: true },
    { name: "یورو", value: "64,500", change: 0.28, changePercent: 0.28, icon: "euro", isUp: true },
    { name: "سکه امامی", value: "48,200,000", change: -0.45, changePercent: -0.45, icon: "local_gas_station", isUp: false },
    { name: "نفت برنت", value: "$82.45", change: 0.67, changePercent: 0.67, icon: "oil_barrel", isUp: true },
  ];
}

export function generateMockNews(): NewsItem[] {
  return [
    { id: "1", title: "افزایش قیمت فولاد در بازارهای جهانی", summary: "قیمت فولاد در بازارهای جهانی با رشد قابل توجهی همراه شد.", source: "خبرگزاری اقتصاد", date: "۱۰ دقیقه پیش", category: "market", sentiment: "positive" },
    { id: "2", title: "کاهش سودآوری شرکت خودروسازی", summary: "شرکت خودروسازی از کاهش سودآوری در فصل جاری خبر داد.", source: "خبرگزاری بورس", date: "۲۵ دقیقه پیش", category: "companies", sentiment: "negative" },
    { id: "3", title: "افزایش سرمایه شرکت پتروشیمی", summary: "شرکت پتروشیمی برنامه افزایش سرمایه را اعلام کرد.", source: "خبرگزاری مالی", date: "۴۵ دقیقه پیش", category: "companies", sentiment: "positive" },
    { id: "4", title: "ثبات قیمت طلا در بازار جهانی", summary: "قیمت طلا پس از نوسانات هفته گذشته به ثبات رسید.", source: "خبرگزاری ارز", date: "۱ ساعت پیش", category: "economic", sentiment: "neutral" },
  ];
}

export function generateMockExperts(): ExpertOpinion[] {
  return [
    { id: "1", name: "دکتر محمدرضا حسنی", role: "تحلیل‌گر ارشد بازار سرمایه", avatar: "م", text: "با توجه به تحلیل تکنیکال و بنیادی، صنعت فولاد همچنان جذابیت خود را حفظ کرده است. انتظار می‌رود با بهبود شرایط جهانی، قیمت‌ها در ماه آینده رشد قابل توجهی داشته باشند.", symbols: ["فولاد", "فملی"], time: "۱ ساعت پیش" },
    { id: "2", name: "سارا محمدی", role: "مدیر تحلیل شرکت‌های پتروشیمی", avatar: "س", text: "گزارش‌های مالی شرکت‌های پتروشیمی نشان از افزایش حاشیه سود دارد. با توجه به کاهش هزینه‌های تولید و افزایش قیمت محصولات، چشم‌انداز این صنعت مثبت ارزیابی می‌شود.", symbols: ["پترول", "پخش"], time: "۲ ساعت پیش" },
    { id: "3", name: "علی رضایی", role: "استراتژیست بازار", avatar: "ع", text: "با توجه به تحلیل جریان پول و حجم معاملات، بازار در کوتاه‌مدت با اصلاح مواجه خواهد شد. توصیه می‌شود در سطوح بالای مقاومت، ریسک‌های خود را کاهش دهید.", symbols: ["شاخص کل"], time: "۳ ساعت پیش" },
    { id: "4", name: "دکتر رضا کریمی", role: "رئیس بخش تحقیقات بازار سرمایه", avatar: "ر", text: "تحلیل ساختار بازار نشان‌دهنده ورود پول هوشمند به نمادهای بنیادی است. با توجه به گزارش‌های مالی فصل جدید، انتظار می‌رود بازار در میان‌مدت روند صعودی خود را ادامه دهد.", symbols: ["فولاد", "پترول", "مس"], time: "۵ ساعت پیش" },
  ];
}

export function generateMockSignals(): Signal[] {
  return [
    { id: "1", symbol: "فولاد", signal: "buy", strength: 0.82, horizon: "۱ روز", confidence: "high", strategy: "Momentum_v3", created_at: "۱۴۰۴/۰۳/۲۶ ۱۰:۳۰", price: 58920 },
    { id: "2", symbol: "وبملت", signal: "sell", strength: 0.74, horizon: "۳ روز", confidence: "medium", strategy: "MeanReversion_v2", created_at: "۱۴۰۴/۰۳/۲۶ ۰۹:۴۵", price: 12450 },
    { id: "3", symbol: "خودرو", signal: "neutral", strength: 0.12, horizon: "—", confidence: "low", strategy: "QueueImbalance_v1", created_at: "۱۴۰۴/۰۳/۲۵ ۱۴:۰۰", price: 8750 },
    { id: "4", symbol: "شپنا", signal: "buy", strength: 0.91, horizon: "۱ ساعت", confidence: "high", strategy: "ML_Alpha_v5", created_at: "۱۴۰۴/۰۳/۲۶ ۱۱:۱۵", price: 42150 },
    { id: "5", symbol: "فملی", signal: "buy", strength: 0.67, horizon: "۳۰ دقیقه", confidence: "medium", strategy: "ML_Alpha_v5", created_at: "۱۴۰۴/۰۳/۲۶ ۱۱:۰۰", price: 33800 },
  ];
}

export function generateMockWatchlist(): WatchlistItem[] {
  return [
    { symbol: "فولاد", name: "فولاد مبارکه", price: 12450, change: 2.34, changePercent: 2.34 },
    { symbol: "پترول", name: "", price: 23890, change: 3.45, changePercent: 3.45 },
    { symbol: "مس", name: "ملی مس", price: 25680, change: 1.56, changePercent: 1.56 },
    { symbol: "خودرو", name: "ایران خودرو", price: 8760, change: -1.23, changePercent: -1.23 },
    { symbol: "بانک", name: "بانک ملت", price: 5670, change: 0.00, changePercent: 0.00 },
    { symbol: "فملی", name: "ملی صنایع مس", price: 33800, change: -1.05, changePercent: -1.05 },
  ];
}

export function generateMockHeatmap(): HeatmapCell[] {
  return [
    { symbol: "فولاد", change: 7.34, volume: 5000000 },
    { symbol: "پترول", change: 6.12, volume: 2000000 },
    { symbol: "مس", change: 3.45, volume: 1500000 },
    { symbol: "وغدیر", change: 2.78, volume: 3000000 },
    { symbol: "کالا", change: 2.12, volume: 1000000 },
    { symbol: "بانک", change: 0.00, volume: 1500000 },
    { symbol: "سپا", change: -0.23, volume: 800000 },
    { symbol: "خودرو", change: -1.23, volume: 3000000 },
    { symbol: "سیمان", change: -1.87, volume: 1200000 },
    { symbol: "دارو", change: -2.45, volume: 900000 },
    { symbol: "قند", change: -4.56, volume: 600000 },
    { symbol: "چدن", change: 2.34, volume: 400000 },
    { symbol: "روال", change: 1.89, volume: 700000 },
    { symbol: "غشهد", change: 0.12, volume: 500000 },
    { symbol: "خگستر", change: 5.67, volume: 2500000 },
    { symbol: "وبملت", change: 3.21, volume: 1800000 },
    { symbol: "پخش", change: -0.45, volume: 1200000 },
    { symbol: "ساترا", change: -2.34, volume: 900000 },
    { symbol: "تپکو", change: 2.89, volume: 600000 },
    { symbol: "شبندر", change: 0.34, volume: 1100000 },
    { symbol: "پارس", change: -1.67, volume: 800000 },
    { symbol: "رهآور", change: -3.78, volume: 400000 },
    { symbol: "فملی", change: -1.05, volume: 7800000 },
    { symbol: "کگل", change: 1.80, volume: 5600000 },
  ];
}

export function generateMockOrderBook(): OrderBook {
  return {
    symbol: "فولاد",
    lastPrice: 12450,
    spread: 10,
    bids: [
      { price: 12450, volume: 85000, count: 120 },
      { price: 12440, volume: 70000, count: 95 },
      { price: 12430, volume: 60000, count: 82 },
      { price: 12420, volume: 50000, count: 68 },
      { price: 12410, volume: 40000, count: 55 },
      { price: 12400, volume: 30000, count: 41 },
      { price: 12390, volume: 20000, count: 28 },
    ],
    asks: [
      { price: 12460, volume: 25000, count: 35 },
      { price: 12470, volume: 35000, count: 48 },
      { price: 12480, volume: 45000, count: 62 },
      { price: 12490, volume: 55000, count: 75 },
      { price: 12500, volume: 65000, count: 88 },
      { price: 12510, volume: 75000, count: 102 },
      { price: 12520, volume: 90000, count: 125 },
    ],
  };
}
