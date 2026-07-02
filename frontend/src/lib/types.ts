// ------ Base Types ------------------------------------------------------------------------------------------------------------------------
export interface MarketStats {
  marketCap: number;
  totalVolume: number;
  totalTrades: number;
  indexValue: number;
}

export interface AIInsight {
  title: string;
  description: string;
  type: 'positive' | 'negative' | 'neutral';
  icon: string;
}

export interface ChartDataPoint {
  date: string;
  value: number;
  volume?: number;
  positive?: number;
  neutral?: number;
  negative?: number;
}

export interface NewsItem {
  id: string;
  title: string;
  summary?: string;
  source?: string;
  date?: string;
  published_at?: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  url?: string;
}

export interface ExpertOpinion {
  id: string;
  name: string;
  role: string;
  avatar: string;
  text: string;
  time: string;
  symbols: string[];
}

export interface SectorData {
  name: string;
  value: number;
  color?: string;
}

export interface Signal {
  id?: string;
  symbol: string;
  signal: 'buy' | 'sell' | 'neutral';
  strength: number;
  confidence: string;
  horizon?: string;
  price?: number;
  timestamp?: string;
  instrument_id?: string;
  strategy?: string;
  created_at?: string;
}

export interface OrderBookEntry {
  price: number;
  volume: number;
  count?: number;
}

export interface WatchlistItem {
  symbol: string;
  name?: string;
  price?: number;
  change?: number;
  // Enriched fields
  priceLowestAllowed?: number;
  priceHighestAllowed?: number;
  freeFloatPct?: number;
  price_yesterday?: number;
  eps?: number;
  peRatio?: number;
  groupPeRatio?: number;
  psRatio?: number;
  state?: string;
  sector?: string;
}

// ------ اضافه کردن تایپ‌های جدید ------------------------------------------------------------------------------
export interface MarketIndex {
  name: string;
  value: number;
  isUp: boolean;
  changePercent: number;
  icon: string;
}

export interface HeatmapCell {
  symbol: string;
  change: number;
  value?: number;
  volume?: number;
  // Enriched fields
  name?: string;
  price?: number;
  priceLowestAllowed?: number;
  priceHighestAllowed?: number;
  freeFloatPct?: number;
  eps?: number;
  peRatio?: number;
  state?: string;
  sector?: string;
  market?: string;
  board?: string;
}

export interface CandleDataPoint {
  date?: string;
  time?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  isUp?: boolean;
}

export interface PieChartData {
  name: string;
  value: number;
  color: string;
}

export interface SentimentPoint {
  date: string;
  positive: number;
  neutral: number;
  negative: number;
}

// ------ Mock Generators ------------------------------------------------------------------------------------------------------------

export function generateMockNews(count: number = 3): NewsItem[] {
  const titles = [
    'افزایش ۲ درصدی شاخص کل بورس تهران',
    'تصویب نرخ خوراک پتروشیمی‌ها در بودجه ۱۴۰۴',
    'رونق معاملات خودرو در بورس کالا',
    'کاهش نرخ بهره بین‌بانکی و تأثیر آن بر بازار',
    'گزارش مالی فولاد مبارکه منتشر شد',
  ];
  const sources = ['خبرگزاری فارس', 'تسنیم', 'اکوایران', 'باشگاه خبرنگاران'];
  const sentiments: ('positive' | 'negative' | 'neutral')[] = ['positive', 'negative', 'neutral'];

  return Array.from({ length: count }, (_, i) => ({
    id: `news-${i}`,
    title: titles[i % titles.length],
    summary: 'خلاصه‌ای از این خبر که نشان‌دهنده‌ی اهمیت آن در بازار سرمایه است...',
    source: sources[i % sources.length],
    date: new Date(Date.now() - i * 3600000).toLocaleDateString('fa-IR'),
    published_at: new Date(Date.now() - i * 3600000).toLocaleString('fa-IR'),
    sentiment: sentiments[i % sentiments.length],
  }));
}

export function generateMockExperts(count: number = 3): ExpertOpinion[] {
  const names = ['احمد نادری', 'سارا محمدی', 'علی رضایی', 'مریم کریمی'];
  const roles = ['تحلیلگر ارشد بازار سرمایه', 'مدیر صندوق سرمایه‌گذاری', 'کارشناس بازار سهام'];
  const texts = [
    'با توجه به روند فعلی، به نظر می‌رسد بازار در کوتاه‌مدت اصلاحی خواهد بود. اما در میان‌مدت، صنایع صادراتی پتانسیل رشد دارند.',
    'تغییرات نرخ ارز و قیمت جهانی کامودیتی‌ها می‌تواند تأثیر قابل‌توجهی بر سودآوری شرکت‌های پتروشیمی داشته باشد.',
    'بازار در حال تثبیت است و احتمالاً در هفته‌های آینده شاهد رشد شاخص خواهیم بود. صنعت خودرو و فلزات اساسی جذاب به نظر می‌رسند.',
  ];
  const symbols = [['فولاد', 'خودرو'], ['پترول', 'شستا'], ['کالا', 'وغدیر', 'بانک']];

  return Array.from({ length: count }, (_, i) => ({
    id: `expert-${i}`,
    name: names[i % names.length],
    role: roles[i % roles.length],
    avatar: '👤',
    text: texts[i % texts.length],
    time: new Date(Date.now() - i * 7200000).toLocaleTimeString('fa-IR'),
    symbols: symbols[i % symbols.length] || [],
  }));
}

export function generateIndexHistory(days: number): ChartDataPoint[] {
  let value = 2100000;
  return Array.from({ length: days }, (_, i) => {
    const change = (Math.random() - 0.45) * 5000;
    value = Math.max(2000000, value + change);
    const date = new Date();
    date.setDate(date.getDate() - (days - i));
    return {
      date: date.toLocaleDateString('fa-IR'),
      value: Math.round(value),
    };
  });
}

export function generateVolumeData(days: number): ChartDataPoint[] {
  return Array.from({ length: days }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (days - i));
    return {
      date: date.toLocaleDateString('fa-IR'),
      value: Math.floor(100000 + Math.random() * 900000),
    };
  });
}

export function generateSectorPerformance(): SectorData[] {
  const sectors = [
    { name: 'فلزات اساسی', value: 28 },
    { name: 'پتروشیمی', value: 22 },
    { name: 'خودرو', value: 18 },
    { name: 'بانکی', value: 15 },
    { name: 'سایر', value: 17 },
  ];
  return sectors.map((s) => ({
    ...s,
    color: `hsl(${Math.random() * 360}, 70%, 50%)`,
  }));
}

export function generateSentimentHistory(days: number): ChartDataPoint[] {
  let positive = 45,
    neutral = 35,
    negative = 20;
  return Array.from({ length: days }, (_, i) => {
    positive += (Math.random() - 0.48) * 4;
    neutral += (Math.random() - 0.5) * 3;
    negative = 100 - positive - neutral;
    const total = positive + neutral + negative;
    positive = (positive / total) * 100;
    neutral = (neutral / total) * 100;
    negative = (negative / total) * 100;

    const date = new Date();
    date.setDate(date.getDate() - (days - i));
    return {
      date: date.toLocaleDateString('fa-IR'),
      positive: Math.round(positive),
      neutral: Math.round(neutral),
      negative: Math.round(negative),
      value: Math.round(positive - negative + 50),
    };
  });
}

export function generateMockSignals(count: number = 10): Signal[] {
  const symbols = ['فولاد', 'شپنا', 'وبملت', 'خودرو', 'فملی', 'کگل', 'پترول', 'مس', 'وغدیر', 'بانک'];
  const signals: ('buy' | 'sell' | 'neutral')[] = ['buy', 'sell', 'neutral'];
  const confidences = ['بالا', 'متوسط', 'پایین'];
  return Array.from({ length: count }, (_, i) => ({
    id: `sig-${i}`,
    symbol: symbols[i % symbols.length],
    signal: signals[i % signals.length],
    strength: 0.3 + Math.random() * 0.6,
    confidence: confidences[i % confidences.length],
    horizon: 'کوتاه‌مدت',
    price: Math.round(1000 + Math.random() * 50000),
    timestamp: new Date(Date.now() - i * 60000).toLocaleString('fa-IR'),
  }));
}

export function generateCandleData(count: number = 60) {
  let close = 2000;
  return Array.from({ length: count }, (_, i) => {
    const change = (Math.random() - 0.48) * 120;
    const open = close;
    close = Math.max(1500, close + change);
    const high = Math.max(open, close) + Math.random() * 30;
    const low = Math.min(open, close) - Math.random() * 30;
    const date = new Date();
    date.setDate(date.getDate() - (count - i));
    return {
      date: date.toLocaleDateString('fa-IR'),
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
      volume: Math.floor(1000 + Math.random() * 10000),
    };
  });
}

// ------ توابع اضافه شده (یک بار تعریف) ------------------------------------------------------------------
export function generateMockWatchlist(): WatchlistItem[] {
  return [
    { symbol: 'فولاد', name: 'فولاد مبارکه', price: 12450, change: 2.34, priceLowestAllowed: 11828, priceHighestAllowed: 13073, freeFloatPct: 33, eps: 8520, peRatio: 4.5, groupPeRatio: 11.6, psRatio: 0.85, state: 'مجاز', sector: 'فلزات اساسی' },
    { symbol: 'شپنا', name: 'پالایش نفت اصفهان', price: 8760, change: -1.23, priceLowestAllowed: 8322, priceHighestAllowed: 9198, freeFloatPct: 20, eps: 14500, peRatio: 3.2, groupPeRatio: 8.4, psRatio: 1.20, state: 'مجاز', sector: 'فرآورده‌های نفتی' },
    { symbol: 'وبملت', name: 'بانک ملت', price: 5670, change: 0.0, priceLowestAllowed: 5387, priceHighestAllowed: 5954, freeFloatPct: 45, eps: 2100, peRatio: 6.8, groupPeRatio: 7.2, psRatio: 2.35, state: 'مجاز', sector: 'بانکداری' },
    { symbol: 'خودرو', name: 'ایران خودرو', price: 23890, change: 3.45, priceLowestAllowed: 22696, priceHighestAllowed: 25085, freeFloatPct: 15, eps: 3200, peRatio: 7.5, groupPeRatio: 14.8, psRatio: 0.45, state: 'مجاز', sector: 'خودرو' },
    { symbol: 'فملی', name: 'صنایع مس', price: 18230, change: 1.56, priceLowestAllowed: 17319, priceHighestAllowed: 19142, freeFloatPct: 10, eps: 6100, peRatio: 5.2, groupPeRatio: 10.3, psRatio: 1.65, state: 'مجاز', sector: 'استخراج کانه‌های فلزی' },
  ];
}

export function generateMockIndices(): MarketIndex[] {
  return [
    { name: 'شاخص کل', value: 2145678, isUp: true, changePercent: 1.2, icon: 'trending_up' },
    { name: 'شاخص هم‌وزن', value: 456789, isUp: true, changePercent: 0.8, icon: 'bar_chart' },
    { name: 'شاخص صنعت', value: 123456, isUp: true, changePercent: 2.1, icon: 'analytics' },
  ];
}

export function generateMockHeatmap(): HeatmapCell[] {
  const data = [
    { symbol: 'فولاد', name: 'فولاد مبارکه', change: 2.34, value: 45000000, volume: 1200000, price: 12450, priceLowestAllowed: 11828, priceHighestAllowed: 13073, freeFloatPct: 33, eps: 8520, peRatio: 4.5, state: 'مجاز', sector: 'فلزات اساسی', market: 'بورس', board: 'بازار اول' },
    { symbol: 'شپنا', name: 'پالایش نفت اصفهان', change: -1.23, value: 32000000, volume: 980000, price: 8760, priceLowestAllowed: 8322, priceHighestAllowed: 9198, freeFloatPct: 20, eps: 14500, peRatio: 3.2, state: 'مجاز', sector: 'فرآورده‌های نفتی', market: 'بورس', board: 'بازار اول' },
    { symbol: 'وبملت', name: 'بانک ملت', change: 0.0, value: 18000000, volume: 2100000, price: 5670, priceLowestAllowed: 5387, priceHighestAllowed: 5954, freeFloatPct: 45, eps: 2100, peRatio: 6.8, state: 'مجاز', sector: 'بانکداری', market: 'بورس', board: 'بازار اول' },
    { symbol: 'خودرو', name: 'ایران خودرو', change: 3.45, value: 52000000, volume: 3400000, price: 23890, priceLowestAllowed: 22696, priceHighestAllowed: 25085, freeFloatPct: 15, eps: 3200, peRatio: 7.5, state: 'مجاز', sector: 'خودرو', market: 'بورس', board: 'بازار دوم' },
    { symbol: 'فملی', name: 'صنایع مس', change: 1.56, value: 41000000, volume: 1800000, price: 18230, priceLowestAllowed: 17319, priceHighestAllowed: 19142, freeFloatPct: 10, eps: 6100, peRatio: 5.2, state: 'مجاز', sector: 'استخراج کانه‌های فلزی', market: 'بورس', board: 'بازار اول' },
    { symbol: 'کگل', name: 'گل گهر', change: -0.87, value: 29000000, volume: 1500000, price: 15320, priceLowestAllowed: 14554, priceHighestAllowed: 16086, freeFloatPct: 25, eps: 7800, peRatio: 3.8, state: 'مجاز', sector: 'استخراج کانه‌های فلزی', market: 'بورس', board: 'بازار اول' },
    { symbol: 'پترول', name: 'پتروشیمی خلیج فارس', change: 2.10, value: 68000000, volume: 2900000, price: 32500, priceLowestAllowed: 30875, priceHighestAllowed: 34125, freeFloatPct: 18, eps: 16200, peRatio: 3.0, state: 'مجاز', sector: 'محصولات شیمیایی', market: 'بورس', board: 'بازار اول' },
    { symbol: 'وغدیر', name: 'سرمایه‌گذاری غدیر', change: 1.12, value: 25000000, volume: 1100000, price: 14560, priceLowestAllowed: 13832, priceHighestAllowed: 15288, freeFloatPct: 30, eps: 5400, peRatio: 5.5, state: 'مجاز', sector: 'سرمایه‌گذاری', market: 'بورس', board: 'بازار دوم' },
    { symbol: 'مس', name: 'ملی مس', change: -0.45, value: 35000000, volume: 1600000, price: 19990, priceLowestAllowed: 18991, priceHighestAllowed: 20990, freeFloatPct: 10, eps: 6100, peRatio: 5.2, state: 'مجاز', sector: 'استخراج کانه‌های فلزی', market: 'بورس', board: 'بازار اول' },
    { symbol: 'فارس', name: 'صنایع پتروشیمی خلیج فارس', change: 1.80, value: 55000000, volume: 2200000, price: 28000, priceLowestAllowed: 26600, priceHighestAllowed: 29400, freeFloatPct: 22, eps: 14000, peRatio: 3.5, state: 'مجاز', sector: 'محصولات شیمیایی', market: 'بورس', board: 'بازار اول' },
  ];
  return data;
}

export function generateMockOrderBook() {
  const bids: OrderBookEntry[] = [];
  const asks: OrderBookEntry[] = [];
  const basePrice = 12000;
  for (let i = 1; i <= 10; i++) {
    bids.push({ price: basePrice - i * 50, volume: Math.floor(1000 + Math.random() * 5000) });
    asks.push({ price: basePrice + i * 50, volume: Math.floor(1000 + Math.random() * 5000) });
  }
  return { bids, asks, lastPrice: basePrice };
}