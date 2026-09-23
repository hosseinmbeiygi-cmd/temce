"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface StrategyResult {
  strategy: string;
  params: Record<string, unknown>;
  metrics: {
    total_return_pct: number;
    annualized_return_pct: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    win_rate: number;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    profit_factor: number;
    sortino_ratio: number;
    calmar_ratio: number;
  };
  symbol?: string;
  method?: string;
  score?: number;
}

interface GenerateStats {
  total_combinations: number;
  passed_filter: number;
  symbols: string[];
  period: string;
  filters: Record<string, number>;
  genetic_used: boolean;
}

interface GenerateResponse {
  strategies: StrategyResult[];
  stats: GenerateStats;
}

interface ProgressData {
  running: boolean;
  progress_pct: number;
  completed: number;
  total: number;
  found: number;
  phase?: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const STRATEGY_CATEGORIES = {
  trend: {
    label: "روند",
    icon: "📈",
    items: [
      { id: "moving_average_cross", name: "تقاطع میانگین متحرک", desc: "سیگنال از تقاطع MA کوتاه و بلند" },
      { id: "half_trend", name: "نیمه‌روند", desc: "تشخیص روند با اندیکاتور Half Trend" },
      { id: "squeeze_momentum", name: "فشردگی مومنتوم", desc: "شروع روند پس از فشردگی قیمت" },
    ],
  },
  momentum: {
    label: "مومنتوم",
    icon: "🚀",
    items: [
      { id: "momentum", name: "مومنتوم قیمتی", desc: "اندازه‌گیری قدرت حرکت قیمت" },
      { id: "breakout", name: "شکست قیمت", desc: "شکست سقف/کف محدوده نوسانی" },
      { id: "volatility_breakout", name: "شکست نوسان", desc: "شکست بر اساس ATR" },
    ],
  },
  reversion: {
    label: "بازگشت به میانگین",
    icon: "🔄",
    items: [
      { id: "mean_reversion", name: "بازگشت به میانگین", desc: "خرید در اشباع فروش با Z-Score" },
      { id: "rsi_reversion", name: "بازگشت RSI", desc: "سیگنال از اشباع خرید/فروش RSI" },
    ],
  },
  technical: {
    label: "تحلیل تکنیکال",
    icon: "📊",
    items: [
      { id: "support_resistance", name: "حمایت و مقاومت", desc: "شکست سطوح کلیدی با تأیید حجم" },
    ],
  },
  ml: {
    label: "یادگیری ماشین",
    icon: "🤖",
    items: [
      { id: "ml_signal", name: "سیگنال ML", desc: "پیش‌بینی با مدل XGBoost/RF" },
    ],
  },
  portfolio: {
    label: "مدیریت پرتفوی",
    icon: "💼",
    items: [
      { id: "equal_weight", name: "وزن مساوی", desc: "توزیع مساوی سرمایه" },
      { id: "max_sharpe", name: "حداکثر شارپ", desc: "بهینه‌سازی برای حداکثر نسبت شارپ" },
      { id: "minimum_variance", name: "حداقل واریانس", desc: "حداقل ریسک پرتفوی" },
      { id: "risk_parity", name: "ریسک پاریتی", desc: "توزیع ریسک مساوی" },
      { id: "tactical_allocation", name: "تخصیص تاکتیکی", desc: "تخصیص بر اساس روند بازار" },
    ],
  },
};

const FEATURE_OPTIONS = [
  { id: "technical", label: "اندیکاتورهای تکنیکال", desc: "RSI, MACD, ATR, Bollinger" },
  { id: "momentum", label: "مومنتوم", desc: "ROC, Return, Rate of Change" },
  { id: "volume", label: "حجم و ارزش معاملات", desc: "Volume Ratio, OBV, VWAP" },
  { id: "volatility", label: "نوسانات", desc: "ATR, Historical Vol, Bollinger Width" },
  { id: "trend", label: "روند", desc: "MA, EMA, ADX, Supertrend" },
];

const TEHRAN_FILTERS = [
  { id: "min_liquidity", label: "حداقل نقدشوندگی", desc: "ارزش معاملات روزانه (میلیارد تومان)", default: 10 },
  { id: "min_volume", label: "حداقل حجم معاملات", desc: "تعداد سهم معامله شده در روز", default: 1000000 },
  { id: "max_spread", label: "حداکثر اسپرد", desc: "تفاوت قیمت خرید و فروش (%)", default: 2 },
  { id: "exclude_suspended", label: "حذف نمادهای متوقف", desc: "حذف نمادهای با توقف بیش از ۵ روز", default: true },
  { id: "exclude_auction", label: "حذف نمادهای حراج", desc: "حذف نمادهای در وضعیت حراج", default: true },
  { id: "consider_price_limit", label: "دامنه نوسان", desc: "لحاظ کردن دامنه نوسان ۵٪ در محاسبات", default: true },
  { id: "consider_queue", label: "صف خرید/فروش", desc: "لحاظ کردن اثر صف در خرید/فروش", default: true },
  { id: "min_float", label: "حداقل شناوری", desc: "درصد سهام شناور آزاد", default: 10 },
];

const PHASE_LABELS: Record<string, string> = {
  initializing: "آماده‌سازی...",
  grid_search: "جستجوی شبکه‌ای",
  genetic_optimization: "بهینه‌سازی ژنتیک",
  walk_forward: "اعتبارسنجی Walk-Forward",
  idle: "تمام شد",
};

// ── Components ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function MetricBadge({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="text-center">
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
      <div className="text-[10px] text-surface-500">{label}</div>
    </div>
  );
}

function StrategyCard({ item, rank }: { item: StrategyResult; rank: number }) {
  const m = item.metrics;
  const returnColor = m.total_return_pct > 0 ? "text-accent-emerald" : "text-accent-rose";
  const sharpeColor = m.sharpe_ratio > 1 ? "text-accent-emerald" : m.sharpe_ratio > 0.5 ? "text-accent-amber" : "text-accent-rose";

  return (
    <div className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-full bg-primary-600/20 text-primary-300 flex items-center justify-center text-xs font-bold">
            {rank}
          </span>
          <div>
            <h3 className="font-bold text-surface-100 text-sm">{item.strategy}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              {item.symbol && <span className="text-[10px] px-1.5 py-0.5 bg-primary-600/15 text-primary-300 rounded-full">{item.symbol}</span>}
              {item.method && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${item.method === "genetic" ? "bg-accent-amber/15 text-accent-amber" : "bg-surface-700 text-surface-400"}`}>
                  {item.method === "genetic" ? "ژنتیک" : "شبکه‌ای"}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="text-left">
          <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${returnColor} bg-surface-800`}>
            {m.total_return_pct > 0 ? "+" : ""}{m.total_return_pct.toFixed(1)}%
          </span>
          {item.score != null && (
            <div className="text-[10px] text-surface-600 mt-1">score: {item.score.toFixed(2)}</div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mb-3">
        {Object.entries(item.params).map(([k, v]) => (
          <span key={k} className="text-[9px] px-1.5 py-0.5 bg-surface-800 text-surface-400 rounded-full font-mono">
            {k}: {String(v)}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-4 gap-2 p-2 bg-surface-800/30 rounded-lg">
        <MetricBadge label="بازده کل" value={`${m.total_return_pct.toFixed(1)}%`} color={returnColor} />
        <MetricBadge label="شارپ" value={m.sharpe_ratio.toFixed(2)} color={sharpeColor} />
        <MetricBadge label="حداکثر افت" value={`${m.max_drawdown_pct.toFixed(1)}%`} color="text-accent-rose" />
        <MetricBadge label="نرخ برد" value={`${m.win_rate.toFixed(0)}%`} color="text-surface-200" />
      </div>

      <div className="grid grid-cols-4 gap-2 mt-2">
        <MetricBadge label="سود/زیان" value={m.profit_factor.toFixed(2)} color="text-surface-300" />
        <MetricBadge label="سورتینو" value={m.sortino_ratio.toFixed(2)} color="text-surface-300" />
        <MetricBadge label="کالمر" value={m.calmar_ratio.toFixed(2)} color="text-surface-300" />
        <MetricBadge label="معاملات" value={String(m.total_trades)} color="text-surface-300" />
      </div>
    </div>
  );
}

function SectionCard({ title, icon, children, defaultOpen = true }: { title: string; icon: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-800/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <h3 className="font-bold text-surface-200 text-sm">{title}</h3>
        </div>
        <span className="text-surface-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && <div className="px-4 pb-4 border-t border-surface-700/50">{children}</div>}
    </div>
  );
}

function SymbolSearchInput({ symbols, onAdd, onRemove }: { symbols: string[]; onAdd: (s: string) => void; onRemove: (s: string) => void }) {
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const { data: results = [], isLoading } = useQuery({
    queryKey: ["gen-sym-search", input],
    queryFn: async (): Promise<{ symbol: string; name: string }[]> => {
      if (!input.trim()) return [];
      try {
        const res = await apiGet<{ success: boolean; data: { items: { symbol: string; name: string }[] } }>(
          `/instruments/search?q=${encodeURIComponent(input)}&page_size=20`
        );
        return res?.data?.items || [];
      } catch {
        return [];
      }
    },
    enabled: open && input.trim().length > 0,
  });

  return (
    <div className="relative" ref={ref}>
      <input
        type="text"
        value={input}
        onChange={(e) => { setInput(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && results.length > 0) { onAdd(results[0].symbol); setInput(""); }
          if (e.key === "Escape") setOpen(false);
        }}
        className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500"
        placeholder="جستجوی نماد (مثلاً فولاد، موج، خودرو)..."
      />
      {open && input.trim().length > 0 && (
        <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-800 border border-surface-700 rounded-lg shadow-2xl max-h-64 overflow-y-auto">
          {isLoading && <div className="px-3 py-2 text-xs text-surface-500">در حال جستجو...</div>}
          {!isLoading && results.length === 0 && <div className="px-3 py-2 text-xs text-surface-500">نتیجه‌ای یافت نشد</div>}
          {!isLoading && results.map((item) => {
            const selected = symbols.includes(item.symbol);
            return (
              <button
                key={item.symbol}
                onClick={() => {
                  if (selected) onRemove(item.symbol);
                  else onAdd(item.symbol);
                  setInput(""); setOpen(false);
                }}
                className={`w-full text-right px-3 py-2 text-sm flex items-center justify-between transition-colors ${
                  selected ? "bg-primary-600/20 text-primary-300" : "text-surface-200 hover:bg-surface-700"
                }`}
              >
                <div className="flex items-center gap-2">
                  {selected && <span className="text-primary-400">✓</span>}
                  <span className="font-mono font-bold">{item.symbol}</span>
                </div>
                <span className="text-xs text-surface-500 truncate ml-2 max-w-[150px]">{item.name}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function GeneratePage() {
  const [mounted, setMounted] = useState(false);
  // Symbol selection
  const [symbols, setSymbols] = useState<string[]>([]);
  const [allDbSymbols, setAllDbSymbols] = useState<{ symbol: string; bar_count: number }[]>([]);
  const [loadingDbSymbols, setLoadingDbSymbols] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setMounted(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  // Strategy selection
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([
    "moving_average_cross", "momentum", "mean_reversion", "breakout", "rsi_reversion",
  ]);

  // Feature selection
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(["technical", "momentum", "volume"]);

  // Data settings
  const [startDate, setStartDate] = useState("2022-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState(1000000000);

  // Risk management
  const [maxDrawdown, setMaxDrawdown] = useState(25);
  const [stopLoss, setStopLoss] = useState(8);
  const [trailingStop, setTrailingStop] = useState(true);
  const [trailingStopPct, setTrailingStopPct] = useState(5);
  const [maxPositionPct, setMaxPositionPct] = useState(20);

  // Genetic algorithm
  const [useGenetic, setUseGenetic] = useState(true);
  const [geneticGens, setGeneticGens] = useState(8);
  const [populationSize, setPopulationSize] = useState(30);
  const [maxCombinations, setMaxCombinations] = useState(5000);

  // Walk-forward
  const [useWalkForward, setUseWalkForward] = useState(true);
  const [walkForwardWindows, setWalkForwardWindows] = useState(5);
  const [trainRatio, setTrainRatio] = useState(70);

  // Tehran filters
  const [tehranFilters, setTehranFilters] = useState<Record<string, number | boolean>>(
    Object.fromEntries(TEHRAN_FILTERS.map(f => [f.id, f.default]))
  );

  // UI state
  const [activeTab, setActiveTab] = useState<"strategies" | "features" | "risk" | "tehran" | "advanced">("strategies");
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [results, setResults] = useState<GenerateResponse | null>(null);

  // Load all DB symbols on mount
  useEffect(() => {
    const load = async () => {
      setLoadingDbSymbols(true);
      try {
        const res = await apiGet<{ success: boolean; data: { symbol: string; bar_count: number }[] }>("/backtests/data/symbols");
        if (res?.data && Array.isArray(res.data)) setAllDbSymbols(res.data);
      } catch {}
      setLoadingDbSymbols(false);
    };
    load();
  }, []);

  // Poll progress
  useEffect(() => {
    if (!isGenerating) return;
    const interval = setInterval(async () => {
      try {
        const res = await apiGet<{ success: boolean; data: ProgressData }>("/backtests/generate/status");
        if (res?.data) {
          setProgress(res.data);
          if (!res.data.running && res.data.completed > 0) {
            setIsGenerating(false);
            const resultsRes = await apiGet<{ success: boolean; data: GenerateResponse }>("/backtests/generate/results");
            if (resultsRes?.data) setResults(resultsRes.data);
          }
        }
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [isGenerating]);

  const addSymbol = useCallback((s: string) => {
    if (s && !symbols.includes(s)) setSymbols([...symbols, s]);
  }, [symbols]);

  const removeSymbol = useCallback((s: string) => {
    setSymbols(symbols.filter(x => x !== s));
  }, [symbols]);

  const toggleStrategy = useCallback((id: string) => {
    setSelectedStrategies(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }, []);

  const toggleFeature = useCallback((id: string) => {
    setSelectedFeatures(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }, []);

  const updateTehranFilter = useCallback((id: string, value: number | boolean) => {
    setTehranFilters(prev => ({ ...prev, [id]: value }));
  }, []);

  const handleGenerate = useCallback(async () => {
    if (symbols.length === 0 || selectedStrategies.length === 0) return;
    setIsGenerating(true);
    setResults(null);
    try {
      await apiPost("/backtests/generate", {
        symbols,
        strategies: selectedStrategies,
        features: selectedFeatures,
        start_date: startDate,
        end_date: endDate,
        capital,
        max_drawdown: maxDrawdown,
        stop_loss: stopLoss,
        trailing_stop: trailingStop,
        trailing_stop_pct: trailingStopPct,
        max_position_pct: maxPositionPct,
        use_genetic: useGenetic,
        genetic_generations: geneticGens,
        population_size: populationSize,
        max_combinations: maxCombinations,
        use_walk_forward: useWalkForward,
        walk_forward_windows: walkForwardWindows,
        train_ratio: trainRatio / 100,
        tehran_filters: tehranFilters,
      });
    } catch {
      setIsGenerating(false);
    }
  }, [
    symbols, selectedStrategies, selectedFeatures, startDate, endDate, capital,
    maxDrawdown, stopLoss, trailingStop, trailingStopPct, maxPositionPct,
    useGenetic, geneticGens, populationSize, maxCombinations,
    useWalkForward, walkForwardWindows, trainRatio, tehranFilters,
  ]);

  const handleExport = useCallback(() => {
    window.open("/api/v1/backtests/generate/export", "_blank");
  }, []);

  const selectedCount = selectedStrategies.length;
  const totalCombinations = selectedStrategies.length * maxCombinations;

  return (
    <AppLayout title="تولید خودکار استراتژی" subtitle="موتور تولید، تست و پایش استراتژی برای بورس تهران">
      <div className="max-w-7xl mx-auto space-y-5">

        {/* ── Header Stats ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-primary-300">{symbols.length}</div>
            <div className="text-xs text-surface-500">نماد انتخاب شده</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-accent-amber">{selectedCount}</div>
            <div className="text-xs text-surface-500">نوع استراتژی</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-accent-emerald">{totalCombinations.toLocaleString("en-US")}</div>
            <div className="text-xs text-surface-500">ترکیب تقریبی</div>
          </div>
          <div className="glass-card p-3 text-center">
            <button onClick={handleGenerate} disabled={isGenerating || symbols.length === 0 || selectedCount === 0}
              className={`w-full px-4 py-2 rounded-lg text-sm font-bold transition-colors ${
                isGenerating || symbols.length === 0 || selectedCount === 0
                  ? "bg-surface-700 text-surface-400 cursor-not-allowed"
                  : "bg-primary-600 hover:bg-primary-500 text-white"
              }`}>
              {isGenerating ? "در حال تولید..." : "🚀 شروع تولید"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

          {/* ── Left Column: Symbol Selection ── */}
          <div className="lg:col-span-1 space-y-4">
            <SectionCard title="انتخاب نمادها" icon="💹">
              <div className="space-y-3">
                <SymbolSearchInput symbols={symbols} onAdd={addSymbol} onRemove={removeSymbol} />

                {/* Selected chips */}
                {symbols.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {symbols.map(s => (
                      <span key={s} className="flex items-center gap-1 text-xs px-2 py-1 bg-primary-600/15 text-primary-300 rounded-lg">
                        {s}
                        <button onClick={() => removeSymbol(s)} className="text-primary-400 hover:text-primary-200">✕</button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Quick actions */}
                <div className="flex flex-wrap gap-1" suppressHydrationWarning>
                  <button onClick={() => setSymbols(allDbSymbols.map(s => s.symbol))} disabled={!mounted || loadingDbSymbols || allDbSymbols.length === 0}
                    className="text-[10px] px-2 py-0.5 bg-primary-600/20 text-primary-300 hover:bg-primary-600/30 rounded-full transition-colors font-bold">
                    {loadingDbSymbols ? "..." : "همه (" + allDbSymbols.length + ")"}
                  </button>
                  <button onClick={() => setSymbols([])} disabled={symbols.length === 0}
                    className="text-[10px] px-2 py-0.5 bg-accent-rose/20 text-accent-rose hover:bg-accent-rose/30 rounded-full transition-colors">
                    پاک کردن
                  </button>
                </div>

                {/* DB symbols list */}
                {mounted && allDbSymbols.length > 0 && (
                  <div className="max-h-48 overflow-y-auto border border-surface-700 rounded-lg">
                    {allDbSymbols.slice(0, 50).map(s => (
                      <button key={s.symbol} onClick={() => symbols.includes(s.symbol) ? removeSymbol(s.symbol) : addSymbol(s.symbol)}
                        className={`w-full text-right px-2 py-1.5 text-xs flex items-center justify-between border-b border-surface-700/30 transition-colors ${
                          symbols.includes(s.symbol) ? "bg-primary-600/10 text-primary-300" : "text-surface-300 hover:bg-surface-800"
                        }`}>
                        <div className="flex items-center gap-1.5">
                          {symbols.includes(s.symbol) && <span className="text-primary-400">✓</span>}
                          <span className="font-mono font-bold">{s.symbol}</span>
                        </div>
                        <span className="text-surface-500">{s.bar_count} روز</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </SectionCard>

            {/* Data Settings */}
            <SectionCard title="تنظیمات داده" icon="📅">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-surface-500 mb-1">تاریخ شروع</label>
                  <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                    className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                </div>
                <div>
                  <label className="block text-[10px] text-surface-500 mb-1">تاریخ پایان</label>
                  <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                    className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                </div>
                <div className="col-span-2">
                  <label className="block text-[10px] text-surface-500 mb-1">سرمایه اولیه (تومان)</label>
                  <input type="number" value={capital} onChange={e => setCapital(parseInt(e.target.value) || 1000000000)}
                    className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                </div>
              </div>
            </SectionCard>
          </div>

          {/* ── Right Column: Strategy & Filter Settings ── */}
          <div className="lg:col-span-2 space-y-4">

            {/* Tab navigation */}
            <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1">
              {[
                { id: "strategies" as const, label: "استراتژی‌ها", icon: "🎯" },
                { id: "features" as const, label: "ویژگی‌ها", icon: "📊" },
                { id: "risk" as const, label: "مدیریت ریسک", icon: "🛡️" },
                { id: "tehran" as const, label: "فیلتر تهران", icon: "🇮🇷" },
                { id: "advanced" as const, label: "تنظیمات پیشرفته", icon: "⚙️" },
              ].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className={`flex-1 text-xs py-2 rounded-md transition-colors ${
                    activeTab === tab.id ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"
                  }`}>
                  {tab.icon} {tab.label}
                </button>
              ))}
            </div>

            {/* ── Tab: Strategies ── */}
            {activeTab === "strategies" && (
              <SectionCard title="انتخاب استراتژی‌ها" icon="🎯">
                <div className="space-y-4">
                  {Object.entries(STRATEGY_CATEGORIES).map(([catId, cat]) => (
                    <div key={catId}>
                      <div className="flex items-center gap-2 mb-2">
                        <span>{cat.icon}</span>
                        <span className="text-xs font-bold text-surface-300">{cat.label}</span>
                        <span className="text-[10px] text-surface-600">
                          ({cat.items.filter(i => selectedStrategies.includes(i.id)).length}/{cat.items.length})
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {cat.items.map(item => {
                          const selected = selectedStrategies.includes(item.id);
                          return (
                            <button key={item.id} onClick={() => toggleStrategy(item.id)}
                              className={`text-right p-2.5 rounded-lg border transition-all ${
                                selected
                                  ? "border-primary-500 bg-primary-600/10 text-primary-200"
                                  : "border-surface-700 bg-surface-800/50 text-surface-400 hover:border-surface-500"
                              }`}>
                              <div className="flex items-center gap-2">
                                <div className={`w-3 h-3 rounded-full border-2 flex items-center justify-center ${
                                  selected ? "border-primary-500 bg-primary-500" : "border-surface-600"
                                }`}>
                                  {selected && <span className="text-[8px] text-white">✓</span>}
                                </div>
                                <span className="text-xs font-bold">{item.name}</span>
                              </div>
                              <p className="text-[10px] mt-1 opacity-70 mr-5">{item.desc}</p>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}

                  <div className="flex gap-2 pt-2 border-t border-surface-700/50">
                    <button onClick={() => setSelectedStrategies(Object.values(STRATEGY_CATEGORIES).flatMap(c => c.items.map(i => i.id)))}
                      className="text-[10px] px-2 py-1 bg-surface-800 text-surface-400 hover:text-surface-200 rounded transition-colors">
                      انتخاب همه
                    </button>
                    <button onClick={() => setSelectedStrategies([])}
                      className="text-[10px] px-2 py-1 bg-surface-800 text-surface-400 hover:text-surface-200 rounded transition-colors">
                      حذف همه
                    </button>
                    <span className="text-[10px] text-surface-600 self-center mr-2">{selectedCount} استراتژی انتخاب شده</span>
                  </div>
                </div>
              </SectionCard>
            )}

            {/* ── Tab: Features ── */}
            {activeTab === "features" && (
              <SectionCard title="موتور ویژگی" icon="📊">
                <p className="text-[10px] text-surface-500 mb-3">ویژگی‌هایی که برای تولید سیگنال استفاده می‌شوند:</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {FEATURE_OPTIONS.map(f => {
                    const selected = selectedFeatures.includes(f.id);
                    return (
                      <button key={f.id} onClick={() => toggleFeature(f.id)}
                        className={`text-right p-3 rounded-lg border transition-all ${
                          selected
                            ? "border-accent-emerald bg-accent-emerald/10 text-accent-emerald"
                            : "border-surface-700 bg-surface-800/50 text-surface-400 hover:border-surface-500"
                        }`}>
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full border-2 flex items-center justify-center ${
                            selected ? "border-accent-emerald bg-accent-emerald" : "border-surface-600"
                          }`}>
                            {selected && <span className="text-[8px] text-white">✓</span>}
                          </div>
                          <span className="text-xs font-bold">{f.label}</span>
                        </div>
                        <p className="text-[10px] mt-1 opacity-70 mr-5">{f.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </SectionCard>
            )}

            {/* ── Tab: Risk Management ── */}
            {activeTab === "risk" && (
              <SectionCard title="مدیریت ریسک" icon="🛡️">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[10px] text-surface-500 mb-1">حداکثر افت سرمایه (%)</label>
                    <input type="number" value={maxDrawdown} onChange={e => setMaxDrawdown(parseInt(e.target.value) || 25)}
                      className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                  </div>
                  <div>
                    <label className="block text-[10px] text-surface-500 mb-1">حد ضرر (%)</label>
                    <input type="number" value={stopLoss} onChange={e => setStopLoss(parseInt(e.target.value) || 8)}
                      className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                  </div>
                  <div>
                    <label className="block text-[10px] text-surface-500 mb-1">حداکثر وزن هر سهم (%)</label>
                    <input type="number" value={maxPositionPct} onChange={e => setMaxPositionPct(parseInt(e.target.value) || 20)}
                      className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={trailingStop} onChange={e => setTrailingStop(e.target.checked)} className="w-4 h-4 accent-primary-500" />
                      <span className="text-xs text-surface-300">حد ضرر شناور</span>
                    </label>
                  </div>
                  {trailingStop && (
                    <div>
                      <label className="block text-[10px] text-surface-500 mb-1">درصد حد ضرر شناور (%)</label>
                      <input type="number" value={trailingStopPct} onChange={e => setTrailingStopPct(parseInt(e.target.value) || 5)}
                        className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                    </div>
                  )}
                </div>

                <div className="mt-4 p-3 bg-surface-800/30 rounded-lg">
                  <h4 className="text-[10px] font-bold text-surface-400 mb-2">فیلتر ۶ مرحله‌ای</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[10px]">
                    <div className="text-surface-500">۱. حداقل بازده: <span className="text-surface-300">۵٪</span></div>
                    <div className="text-surface-500">۲. حداکثر افت: <span className="text-surface-300">{maxDrawdown}٪</span></div>
                    <div className="text-surface-500">۳. حداقل شارپ: <span className="text-surface-300">۰.۵</span></div>
                    <div className="text-surface-500">۴. حداقل نرخ برد: <span className="text-surface-300">۴۰٪</span></div>
                    <div className="text-surface-500">۵. حداقل معاملات: <span className="text-surface-300">۵</span></div>
                    <div className="text-surface-500">۶. حداقل عامل سود: <span className="text-surface-300">۱.۲</span></div>
                  </div>
                </div>
              </SectionCard>
            )}

            {/* ── Tab: Tehran Filters ── */}
            {activeTab === "tehran" && (
              <SectionCard title="فیلترهای مخصوص بورس تهران" icon="🇮🇷">
                <p className="text-[10px] text-surface-500 mb-3">فیلترهایی که مخصوص شرایط بازار تهران طراحی شده‌اند:</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {TEHRAN_FILTERS.map(f => (
                    <div key={f.id} className="p-2.5 bg-surface-800/50 rounded-lg border border-surface-700/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-surface-300">{f.label}</span>
                        {typeof f.default === "boolean" ? (
                          <label className="flex items-center gap-1.5 cursor-pointer">
                            <input type="checkbox" checked={tehranFilters[f.id] as boolean}
                              onChange={e => updateTehranFilter(f.id, e.target.checked)}
                              className="w-3.5 h-3.5 accent-primary-500" />
                          </label>
                        ) : null}
                      </div>
                      <p className="text-[10px] text-surface-500 mb-1">{f.desc}</p>
                      {typeof f.default === "number" && (
                        <input type="number" value={tehranFilters[f.id] as number}
                          onChange={e => updateTehranFilter(f.id, parseFloat(e.target.value) || 0)}
                          className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" />
                      )}
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* ── Tab: Advanced ── */}
            {activeTab === "advanced" && (
              <div className="space-y-4">
                {/* Genetic Algorithm */}
                <SectionCard title="الگوریتم ژنتیک" icon="🧬">
                  <div className="space-y-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={useGenetic} onChange={e => setUseGenetic(e.target.checked)} className="w-4 h-4 accent-primary-500" />
                      <span className="text-sm text-surface-300">فعال‌سازی بهینه‌سازی ژنتیک</span>
                    </label>
                    {useGenetic && (
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className="block text-[10px] text-surface-500 mb-1">نسل‌ها</label>
                          <input type="number" value={geneticGens} onChange={e => setGeneticGens(parseInt(e.target.value) || 8)}
                            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                        </div>
                        <div>
                          <label className="block text-[10px] text-surface-500 mb-1">جمعیت</label>
                          <input type="number" value={populationSize} onChange={e => setPopulationSize(parseInt(e.target.value) || 30)}
                            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                        </div>
                        <div>
                          <label className="block text-[10px] text-surface-500 mb-1">حداکثر ترکیب</label>
                          <input type="number" value={maxCombinations} onChange={e => setMaxCombinations(parseInt(e.target.value) || 5000)}
                            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                        </div>
                      </div>
                    )}
                  </div>
                </SectionCard>

                {/* Walk-Forward */}
                <SectionCard title="اعتبارسنجی Walk-Forward" icon="🔍">
                  <div className="space-y-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={useWalkForward} onChange={e => setUseWalkForward(e.target.checked)} className="w-4 h-4 accent-primary-500" />
                      <span className="text-sm text-surface-300">فعال‌سازی اعتبارسنجی Walk-Forward</span>
                    </label>
                    {useWalkForward && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[10px] text-surface-500 mb-1">تعداد پنجره‌ها</label>
                          <input type="number" value={walkForwardWindows} onChange={e => setWalkForwardWindows(parseInt(e.target.value) || 5)}
                            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                        </div>
                        <div>
                          <label className="block text-[10px] text-surface-500 mb-1">نسبت آموزش (%)</label>
                          <input type="number" value={trainRatio} onChange={e => setTrainRatio(parseInt(e.target.value) || 70)}
                            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                        </div>
                      </div>
                    )}
                    <div className="p-2 bg-surface-800/30 rounded text-[10px] text-surface-500">
                      Walk-Forward تست استراتژی روی بازه‌های آینده‌نگر را امکان‌پذیر می‌کند و از overfitting جلوگیری می‌کند.
                    </div>
                  </div>
                </SectionCard>
              </div>
            )}
          </div>
        </div>

        {/* ── Progress ── */}
        {isGenerating && progress && (
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-surface-300">{PHASE_LABELS[progress.phase || ""] || "در حال پردازش..."}</span>
              <span className="text-sm font-mono text-primary-300">{progress.progress_pct}%</span>
            </div>
            <div className="w-full h-2 bg-surface-700 rounded-full overflow-hidden">
              <div className="h-full bg-primary-500 rounded-full transition-all duration-300" style={{ width: `${progress.progress_pct}%` }} />
            </div>
            <div className="flex justify-between mt-2 text-xs text-surface-500">
              <span>{progress.completed} از {progress.total} ترکیب</span>
              <span>{progress.found} استراتژی یافت شد</span>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {results && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-surface-100">{results.stats.total_combinations.toLocaleString("en-US")}</div>
                <div className="text-xs text-surface-500">ترکیب اجرا شده</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-accent-emerald">{results.stats.passed_filter}</div>
                <div className="text-xs text-surface-500">از فیلتر عبور کرده</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-primary-300">{results.stats.symbols.join(", ")}</div>
                <div className="text-xs text-surface-500">نمادها</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-surface-200">{results.strategies.length}</div>
                <div className="text-xs text-surface-500">بهترین استراتژی</div>
              </div>
              <div className="glass-card p-3 text-center">
                <button onClick={handleExport} className="text-2xl font-bold text-accent-amber hover:text-accent-amber/80 transition-colors" title="دانلود CSV">
                  📥
                </button>
                <div className="text-xs text-surface-500">خروجی اکسل</div>
              </div>
            </div>

            {results.strategies.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-surface-200">🏆 بهترین استراتژی‌ها</h2>
                  <button onClick={handleExport} className="text-xs text-primary-400 hover:text-primary-300 transition-colors px-3 py-1 rounded-lg bg-primary-600/10">
                    📥 دانلود CSV
                  </button>
                </div>
                {results.strategies.map((item, i) => (
                  <StrategyCard key={`${item.strategy}-${item.symbol}-${i}`} item={item} rank={i + 1} />
                ))}
              </div>
            ) : (
              <div className="glass-card p-12 text-center text-surface-500">
                <p className="text-5xl mb-4">🔍</p>
                <p className="text-lg">هیچ استراتژی‌ای از فیلتر ۶ مرحله‌ای عبور نکرد</p>
                <p className="text-sm mt-1">تعداد ترکیب‌ها را افزایش دهید یا نماد دیگری امتحان کنید</p>
              </div>
            )}
          </>
        )}

        {/* Quick Links */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← بک تست ساده</Link>
          <Link href="/backtest/walk-forward" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">Walk-Forward</Link>
          <Link href="/backtest/monte-carlo" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">Monte Carlo</Link>
        </div>
      </div>
    </AppLayout>
  );
}
