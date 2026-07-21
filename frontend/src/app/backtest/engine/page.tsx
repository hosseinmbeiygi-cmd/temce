"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
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
    total_return_pct_oos?: number;
    max_drawdown_pct_oos?: number;
  };
  symbol?: string;
  method?: string;
  score?: number;
  validation_status?: "validated" | "rejected" | "pending";
}

interface GenerateResponse {
  strategies: StrategyResult[];
  stats: {
    total_generated: number;
    passed_6stage: number;
    passed_walk_forward: number;
    symbols: string[];
    period: string;
  };
}

interface ProgressData {
  running: boolean;
  progress_pct: number;
  completed: number;
  total: number;
  found: number;
  phase?: string;
  current_symbol?: string;
  strategies_per_second?: number;
}

interface SymbolOption {
  symbol: string;
  name: string;
  bar_count?: number;
}

interface SavedStrategy {
  id: string;
  symbol: string;
  strategy: string;
  params: Record<string, unknown>;
  metrics: Record<string, number>;
  score: number;
  created_at: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const STRATEGY_TYPES = [
  { id: "moving_average_cross", name: "تقاطع میانگین متحرک", category: "trend", desc: "سیگنال از تقاطع MA کوتاه و بلند" },
  { id: "momentum", name: "مومنتوم قیمتی", category: "momentum", desc: "اندازه‌گیری قدرت حرکت قیمت" },
  { id: "mean_reversion", name: "بازگشت به میانگین", category: "reversion", desc: "خرید در اشباع فروش با Z-Score" },
  { id: "breakout", name: "شکست قیمت", category: "momentum", desc: "شکست سقف/کف محدوده نوسانی" },
  { id: "rsi_reversion", name: "بازگشت RSI", category: "reversion", desc: "سیگنال از اشباع خرید/فروش RSI" },
  { id: "volatility_breakout", name: "شکست نوسان", category: "momentum", desc: "شکست بر اساس ATR" },
  { id: "half_trend", name: "نیمه‌روند", category: "trend", desc: "تشخیص روند با اندیکاتور Half Trend" },
  { id: "squeeze_momentum", name: "فشردگی مومنتوم", category: "trend", desc: "شروع روند پس از فشردگی قیمت" },
  { id: "support_resistance", name: "حمایت و مقاومت", category: "technical", desc: "شکست سطوح کلیدی با تأیید حجم" },
];

const PARAM_RANGES: Record<string, Record<string, number[]>> = {
  moving_average_cross: { fast_period: [3, 5, 7, 10, 12, 15], slow_period: [15, 20, 25, 30, 40, 50, 60] },
  momentum: { lookback: [5, 10, 15, 20, 25, 30, 40], threshold_pct: [1, 2, 3, 4, 5, 6, 8] },
  mean_reversion: { lookback: [10, 15, 20, 25, 30], entry_z: [1.5, 2, 2.5, 3], exit_z: [0, 0.3, 0.5, 0.8] },
  breakout: { lookback: [10, 15, 20, 25, 30, 40], breakout_pct: [0, 0.5, 1, 1.5, 2] },
  rsi_reversion: { period: [7, 10, 14, 21], oversold: [20, 25, 30, 35], overbought: [65, 70, 75, 80] },
  volatility_breakout: { lookback: [10, 15, 20, 25, 30], multiplier: [1, 1.5, 2, 2.5, 3] },
  half_trend: { amplitude: [1, 2, 3, 4, 5], channel_deviation: [1, 1.5, 2, 2.5, 3] },
  squeeze_momentum: { bb_period: [15, 20, 25], bb_std: [1.5, 2, 2.5], kc_period: [15, 20, 25], kc_mult: [1, 1.5, 2] },
  support_resistance: { lookback: [10, 15, 20, 25, 30], vol_threshold: [1, 1.3, 1.5, 2, 2.5] },
};

const FEATURE_CATEGORIES = {
  technical: {
    label: "اندیکاتورهای تکنیکال",
    icon: "📊",
    items: [
      { id: "rsi", name: "RSI", desc: "شاخص قدرت نسبی" },
      { id: "macd", name: "MACD", desc: "واگرایی میانگین متحرک" },
      { id: "atr", name: "ATR", desc: "میانگین محدوده واقعی" },
      { id: "bollinger", name: "Bollinger Bands", desc: "باندهای بولینگر" },
      { id: "ema", name: "EMA", desc: "میانگین متحرک نمایی" },
      { id: "adx", name: "ADX", desc: "شاخص جهت میانگین" },
    ],
  },
  momentum: {
    label: "مومنتوم",
    icon: "🚀",
    items: [
      { id: "roc", name: "ROC", desc: "نرخ تغییر قیمت" },
      { id: "normalized_return", name: "بازده نرمال‌شده", desc: "Normalized Return by ATR" },
      { id: "sector_rs", name: "قدرت نسبی صنعت", desc: "Sector Relative Strength" },
      { id: "price_momentum", name: "مومنتوم قیمتی", desc: "بازده ۲۰ روزه" },
    ],
  },
  volume: {
    label: "حجم و ارزش معاملات",
    icon: "📦",
    items: [
      { id: "volume_ratio", name: "نسبت حجم", desc: "Volume Ratio" },
      { id: "obv", name: "OBV", desc: "حجم تعادلی" },
      { id: "vwap", name: "VWAP", desc: "میانگین موزون حجمی" },
      { id: "smart_money", name: "پول هوشمند", desc: "Smart Money Inflow Rate" },
    ],
  },
  microstructure: {
    label: "ریزساختار بازار",
    icon: "🔬",
    items: [
      { id: "ibp", name: "قدرت خرید حقیقی", desc: "Individual Buyer Power (IBP)" },
      { id: "buyer_seller_ratio", name: "نسبت خریدار/فروشنده", desc: "Buyer/Seller Strength Ratio" },
      { id: "qpi", name: "فشار صف", desc: "Queue Pressure Index" },
      { id: "trade_value_avg", name: "ارزش معاملات", desc: "میانگین ارزش معاملات ماهانه" },
    ],
  },
  macro: {
    label: "متغیرهای کلان",
    icon: "🌍",
    items: [
      { id: "usd_trend", name: "روند دلار", desc: "تغییرات نرخ ارز" },
      { id: "commodity_trend", name: "روند کامودیتی", desc: "قیمت جهانی" },
      { id: "index_trend", name: "روند شاخص", desc: "شاخص کل بورس" },
    ],
  },
};

const PHASE_LABELS: Record<string, string> = {
  initializing: "آماده‌سازی موتور...",
  grid_search: "جستجوی شبکه‌ای",
  genetic_optimization: "بهینه‌سازی ژنتیک",
  walk_forward: "اعتبارسنجی Walk-Forward",
  idle: "تمام شد",
};

// ── Symbol Search ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function SymbolSearch({ symbols, onAdd, onRemove, onClearAll, onSelectAll, allDbSymbols, loadingDb }: {
  symbols: string[];
  onAdd: (s: string) => void;
  onRemove: (s: string) => void;
  onClearAll: () => void;
  onSelectAll: () => void;
  allDbSymbols: SymbolOption[];
  loadingDb: boolean;
}) {
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
    queryKey: ["eng-sym", input],
    queryFn: async (): Promise<SymbolOption[]> => {
      if (!input.trim()) return [];
      try {
        const res = await apiGet<{ success: boolean; data: { items: SymbolOption[] } }>(
          `/instruments/search?q=${encodeURIComponent(input)}&page_size=20`
        );
        return res?.data?.items || [];
      } catch { return []; }
    },
    enabled: open && input.trim().length > 0,
  });

  return (
    <div className="space-y-2">
      {symbols.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {symbols.map(s => (
            <span key={s} className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-primary-600/15 text-primary-300 rounded-md">
              {s}
              <button onClick={() => onRemove(s)} className="text-primary-400 hover:text-primary-200">✕</button>
            </span>
          ))}
        </div>
      )}
      <div className="relative" ref={ref}>
        <input type="text" value={input} onChange={e => { setInput(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          onKeyDown={e => { if (e.key === "Enter" && results.length > 0) { onAdd(results[0].symbol); setInput(""); } if (e.key === "Escape") setOpen(false); }}
          className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 outline-none focus:border-primary-500"
          placeholder="جستجوی نماد..." />
        {open && input.trim().length > 0 && (
          <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-800 border border-surface-700 rounded-lg shadow-2xl max-h-48 overflow-y-auto">
            {isLoading && <div className="px-3 py-2 text-[10px] text-surface-500">در حال جستجو...</div>}
            {!isLoading && results.length === 0 && <div className="px-3 py-2 text-[10px] text-surface-500">نتیجه‌ای یافت نشد</div>}
            {!isLoading && results.map(item => {
              const sel = symbols.includes(item.symbol);
              return (
                <button key={item.symbol} onClick={() => { sel ? onRemove(item.symbol) : onAdd(item.symbol); setInput(""); setOpen(false); }}
                  className={`w-full text-right px-3 py-1.5 text-xs flex items-center justify-between transition-colors ${sel ? "bg-primary-600/20 text-primary-300" : "text-surface-200 hover:bg-surface-700"}`}>
                  <div className="flex items-center gap-1.5">
                    {sel && <span className="text-primary-400">✓</span>}
                    <span className="font-mono font-bold">{item.symbol}</span>
                  </div>
                  <span className="text-[10px] text-surface-500 truncate ml-2 max-w-[120px]">{item.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-1" suppressHydrationWarning>
        <button onClick={onSelectAll} disabled={loadingDb || allDbSymbols.length === 0}
          className="text-[9px] px-1.5 py-0.5 bg-primary-600/20 text-primary-300 hover:bg-primary-600/30 rounded transition-colors font-bold">
          {loadingDb ? "..." : "همه (" + allDbSymbols.length + ")"}
        </button>
        <button onClick={onClearAll} disabled={symbols.length === 0}
          className="text-[9px] px-1.5 py-0.5 bg-accent-rose/20 text-accent-rose hover:bg-accent-rose/30 rounded transition-colors">
          پاک کردن
        </button>
      </div>
      {allDbSymbols.length > 0 && (
        <div className="max-h-36 overflow-y-auto border border-surface-700/50 rounded-lg">
          {allDbSymbols.slice(0, 40).map(s => (
            <button key={s.symbol} onClick={() => symbols.includes(s.symbol) ? onRemove(s.symbol) : onAdd(s.symbol)}
              className={`w-full text-right px-2 py-1 text-[10px] flex items-center justify-between border-b border-surface-700/20 transition-colors ${symbols.includes(s.symbol) ? "bg-primary-600/10 text-primary-300" : "text-surface-400 hover:bg-surface-800"}`}>
              <div className="flex items-center gap-1">
                {symbols.includes(s.symbol) && <span className="text-primary-400">✓</span>}
                <span className="font-mono font-bold">{s.symbol}</span>
              </div>
              <span className="text-surface-600">{s.bar_count || "?"} روز</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Strategy Result Card ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

function StrategyCard({ item, rank, onSave, isSaved }: { item: StrategyResult; rank: number; onSave: () => void; isSaved: boolean }) {
  const m = item.metrics;
  const returnColor = m.total_return_pct > 0 ? "text-accent-emerald" : "text-accent-rose";
  const sharpeColor = m.sharpe_ratio > 1 ? "text-accent-emerald" : m.sharpe_ratio > 0.5 ? "text-accent-amber" : "text-accent-rose";

  return (
    <div className={`glass-card p-4 transition-all ${item.validation_status === "rejected" ? "opacity-50" : "hover:bg-surface-800/50"}`}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-primary-600/20 text-primary-300 flex items-center justify-center text-[10px] font-bold">{rank}</span>
          <div>
            <h4 className="font-bold text-surface-100 text-xs">{item.strategy}</h4>
            <div className="flex items-center gap-1.5 mt-0.5">
              {item.symbol && <span className="text-[9px] px-1.5 py-0.5 bg-primary-600/15 text-primary-300 rounded-full">{item.symbol}</span>}
              {item.method && <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${item.method === "genetic" ? "bg-accent-amber/15 text-accent-amber" : "bg-surface-700 text-surface-400"}`}>{item.method === "genetic" ? "ژنتیک" : "شبکه‌ای"}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${returnColor} bg-surface-800`}>
            {m.total_return_pct > 0 ? "+" : ""}{m.total_return_pct.toFixed(1)}%
          </span>
          <button onClick={onSave} disabled={isSaved}
            className={`text-[10px] px-2 py-1 rounded transition-colors ${isSaved ? "bg-accent-emerald/20 text-accent-emerald cursor-default" : "bg-primary-600/20 text-primary-300 hover:bg-primary-600/30"}`}>
            {isSaved ? "✓ ذخیره شده" : "💾 ذخیره"}
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        {Object.entries(item.params).map(([k, v]) => (
          <span key={k} className="text-[8px] px-1 py-0.5 bg-surface-800 text-surface-500 rounded font-mono">{k}={String(v)}</span>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-1.5">
        <div className="text-center p-1.5 bg-surface-800/30 rounded"><div className={`text-sm font-bold font-mono ${returnColor}`}>{m.total_return_pct.toFixed(1)}%</div><div className="text-[8px] text-surface-500">بازده</div></div>
        <div className="text-center p-1.5 bg-surface-800/30 rounded"><div className={`text-sm font-bold font-mono ${sharpeColor}`}>{m.sharpe_ratio.toFixed(2)}</div><div className="text-[8px] text-surface-500">شارپ</div></div>
        <div className="text-center p-1.5 bg-surface-800/30 rounded"><div className="text-sm font-bold font-mono text-accent-rose">{m.max_drawdown_pct.toFixed(1)}%</div><div className="text-[8px] text-surface-500">افت</div></div>
        <div className="text-center p-1.5 bg-surface-800/30 rounded"><div className="text-sm font-bold font-mono text-surface-200">{m.win_rate.toFixed(0)}%</div><div className="text-[8px] text-surface-500">برد</div></div>
      </div>
      <div className="grid grid-cols-4 gap-1.5 mt-1.5">
        <div className="text-center p-1 bg-surface-800/20 rounded"><div className="text-xs font-mono text-surface-300">{m.profit_factor.toFixed(2)}</div><div className="text-[7px] text-surface-600">سود/زیان</div></div>
        <div className="text-center p-1 bg-surface-800/20 rounded"><div className="text-xs font-mono text-surface-300">{m.sortino_ratio.toFixed(2)}</div><div className="text-[7px] text-surface-600">سورتینو</div></div>
        <div className="text-center p-1 bg-surface-800/20 rounded"><div className="text-xs font-mono text-surface-300">{m.calmar_ratio.toFixed(2)}</div><div className="text-[7px] text-surface-600">کالمر</div></div>
        <div className="text-center p-1 bg-surface-800/20 rounded"><div className="text-xs font-mono text-surface-300">{m.total_trades}</div><div className="text-[7px] text-surface-600">معاملات</div></div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function EnginePage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [allDbSymbols, setAllDbSymbols] = useState<SymbolOption[]>([]);
  const [loadingDb, setLoadingDb] = useState(false);
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(STRATEGY_TYPES.map(s => s.id));
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(["rsi", "macd", "atr", "ema", "volume_ratio", "ibp", "smart_money"]);
  const [populationSize, setPopulationSize] = useState(50);
  const [generations, setGenerations] = useState(12);
  const [mutationRate, setMutationRate] = useState(15);
  const [crossoverRate, setCrossoverRate] = useState(70);
  const [filter1, setFilter1] = useState(5);
  const [filter2, setFilter2] = useState(25);
  const [filter3, setFilter3] = useState(0.5);
  const [filter4, setFilter4] = useState(40);
  const [filter5, setFilter5] = useState(5);
  const [filter6, setFilter6] = useState(1.2);
  const [useWalkForward, setUseWalkForward] = useState(true);
  const [wfWindows, setWfWindows] = useState(5);
  const [wfTrainRatio, setWfTrainRatio] = useState(70);
  const [stopLoss, setStopLoss] = useState(8);
  const [trailingStop, setTrailingStop] = useState(true);
  const [trailingStopPct, setTrailingStopPct] = useState(5);
  const [startDate, setStartDate] = useState("2021-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState(1000000000);
  const [activeTab, setActiveTab] = useState<"symbols" | "features" | "genetic" | "filter" | "walkforward" | "risk" | "saved">("symbols");
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [results, setResults] = useState<GenerateResponse | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [savingStrategies, setSavingStrategies] = useState(false);

  // Load DB symbols
  useEffect(() => {
    const load = async () => {
      setLoadingDb(true);
      try {
        const res = await apiGet<{ success: boolean; data: SymbolOption[] }>("/backtests/data/symbols");
        if (res?.data && Array.isArray(res.data)) setAllDbSymbols(res.data);
      } catch {}
      setLoadingDb(false);
    };
    load();
  }, []);

  // Load saved strategies
  const { data: savedData, refetch: refetchSaved } = useQuery({
    queryKey: ["engine-saved"],
    queryFn: async (): Promise<SavedStrategy[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: { strategies: SavedStrategy[] } }>("/backtests/generate/saved?limit=200");
        return res?.data?.strategies || [];
      } catch { return []; }
    },
  });

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
            const r = await apiGet<{ success: boolean; data: GenerateResponse }>("/backtests/generate/results");
            if (r?.data) setResults(r.data);
          }
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [isGenerating]);

  const addSymbol = useCallback((s: string) => { if (s && !symbols.includes(s)) setSymbols([...symbols, s]); }, [symbols]);
  const removeSymbol = useCallback((s: string) => { setSymbols(symbols.filter(x => x !== s)); }, [symbols]);
  const toggleStrategy = useCallback((id: string) => { setSelectedStrategies(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]); }, []);
  const toggleFeature = useCallback((id: string) => { setSelectedFeatures(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]); }, []);

  const totalCombinations = useMemo(() => {
    let total = 0;
    for (const sid of selectedStrategies) {
      const ranges = PARAM_RANGES[sid];
      if (!ranges) continue;
      let combos = 1;
      for (const vals of Object.values(ranges)) combos *= vals.length;
      total += combos;
    }
    total *= symbols.length || 1;
    total += selectedStrategies.length * populationSize * generations * (symbols.length || 1);
    return total;
  }, [selectedStrategies, symbols, populationSize, generations]);

  const handleGenerate = useCallback(async () => {
    if (symbols.length === 0 || selectedStrategies.length === 0) return;
    setIsGenerating(true);
    setResults(null);
    setSavedIds(new Set());
    try {
      await apiPost("/backtests/generate", {
        symbols, strategies: selectedStrategies, features: selectedFeatures,
        start_date: startDate, end_date: endDate, capital,
        max_combinations: totalCombinations, use_genetic: true,
        genetic_generations: generations, population_size: populationSize,
        mutation_rate: mutationRate / 100, crossover_rate: crossoverRate / 100,
        filters: { stage1_min_return: filter1, stage2_max_drawdown: filter2, stage3_min_sharpe: filter3, stage4_min_win_rate: filter4, stage5_min_trades: filter5, stage6_min_profit_factor: filter6 },
        use_walk_forward: useWalkForward, walk_forward_windows: wfWindows, train_ratio: wfTrainRatio / 100,
        stop_loss: stopLoss, trailing_stop: trailingStop, trailing_stop_pct: trailingStopPct,
      });
    } catch { setIsGenerating(false); }
  }, [symbols, selectedStrategies, selectedFeatures, startDate, endDate, capital, totalCombinations, generations, populationSize, mutationRate, crossoverRate, filter1, filter2, filter3, filter4, filter5, filter6, useWalkForward, wfWindows, wfTrainRatio, stopLoss, trailingStop, trailingStopPct]);

  const handleSaveStrategies = useCallback(async (strats: StrategyResult[]) => {
    setSavingStrategies(true);
    try {
      const res = await apiPost<{ success: boolean; data: { saved: number } }>("/backtests/generate/save", { strategies: strats });
      if (res?.success) {
        const newIds = new Set(savedIds);
        strats.forEach(s => newIds.add(`${s.strategy}-${s.symbol}`));
        setSavedIds(newIds);
        refetchSaved();
      }
    } catch {}
    setSavingStrategies(false);
  }, [savedIds, refetchSaved]);

  const handleSaveOne = useCallback(async (strat: StrategyResult) => {
    await handleSaveStrategies([strat]);
  }, [handleSaveStrategies]);

  const handleExport = useCallback(() => { window.open("/api/v1/backtests/generate/export", "_blank"); }, []);

  const tabs = [
    { id: "symbols" as const, icon: "💹", label: "نمادها", count: symbols.length },
    { id: "features" as const, icon: "🔬", label: "ویژگی‌ها", count: selectedFeatures.length },
    { id: "genetic" as const, icon: "🧬", label: "ژنتیک" },
    { id: "filter" as const, icon: "🎯", label: "فیلتر" },
    { id: "walkforward" as const, icon: "🔍", label: "WF" },
    { id: "risk" as const, icon: "🛡️", label: "ریسک" },
    { id: "saved" as const, icon: "💾", label: "ذخیره‌شده", count: savedData?.length || 0 },
  ];

  return (
    <AppLayout title="موتور کشف استراتژی" subtitle="تولید میلیون‌ها ترکیب + ژنتیک + Walk-Forward + ذخیره استراتژی">
      <div className="max-w-7xl mx-auto space-y-4">

        {/* Stats Bar */}
        <div className="grid grid-cols-3 sm:grid-cols-7 gap-2">
          {[
            { v: symbols.length, l: "نماد", c: "text-primary-300" },
            { v: selectedStrategies.length, l: "استراتژی", c: "text-accent-amber" },
            { v: selectedFeatures.length, l: "ویژگی", c: "text-accent-emerald" },
            { v: totalCombinations.toLocaleString("en"), l: "ترکیب", c: "text-surface-100" },
            { v: populationSize, l: "جمعیت", c: "text-surface-200" },
            { v: generations, l: "نسل", c: "text-surface-200" },
            { v: savedData?.length || 0, l: "ذخیره", c: "text-accent-emerald" },
          ].map((s, i) => (
            <div key={i} className="glass-card p-2 text-center">
              <div className={`text-base font-bold font-mono ${s.c}`}>{s.v}</div>
              <div className="text-[8px] text-surface-500">{s.l}</div>
            </div>
          ))}
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1 overflow-x-auto">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[10px] font-bold transition-colors whitespace-nowrap ${
                activeTab === tab.id ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"
              }`}>
              <span>{tab.icon}</span>{tab.label}
              {tab.count != null && tab.count > 0 && <span className={`text-[8px] px-1 rounded ${activeTab === tab.id ? "bg-white/20" : "bg-surface-700"}`}>{tab.count}</span>}
            </button>
          ))}
          <div className="flex-1" />
          <button onClick={handleGenerate} disabled={isGenerating || symbols.length === 0 || selectedStrategies.length === 0}
            className={`flex items-center gap-1 px-4 py-1.5 rounded-md text-[11px] font-bold transition-colors ${
              isGenerating || symbols.length === 0 || selectedStrategies.length === 0 ? "bg-surface-700 text-surface-400 cursor-not-allowed" : "bg-primary-600 hover:bg-primary-500 text-white"
            }`}>
            {isGenerating ? "⏳" : "🚀"} {isGenerating ? "در حال تولید..." : "شروع تولید"}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: Settings */}
          <div className="lg:col-span-1 space-y-4">

            {activeTab === "symbols" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">💹 انتخاب نمادها</h3>
                <SymbolSearch symbols={symbols} onAdd={addSymbol} onRemove={removeSymbol}
                  onClearAll={() => setSymbols([])} onSelectAll={() => setSymbols(allDbSymbols.map(s => s.symbol))}
                  allDbSymbols={allDbSymbols} loadingDb={loadingDb} />
                <div className="mt-3 pt-3 border-t border-surface-700/50 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div><label className="block text-[9px] text-surface-500 mb-0.5">شروع</label>
                      <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                    <div><label className="block text-[9px] text-surface-500 mb-0.5">پایان</label>
                      <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                  </div>
                  <div><label className="block text-[9px] text-surface-500 mb-0.5">سرمایه (تومان)</label>
                    <input type="number" value={capital} onChange={e => setCapital(parseInt(e.target.value) || 1e9)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                </div>
              </div>
            )}

            {activeTab === "features" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">🔬 موتور ویژگی</h3>
                <div className="space-y-3">
                  {Object.entries(FEATURE_CATEGORIES).map(([catId, cat]) => (
                    <div key={catId}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="text-xs">{cat.icon}</span>
                        <span className="text-[10px] font-bold text-surface-300">{cat.label}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-1">
                        {cat.items.map(f => {
                          const sel = selectedFeatures.includes(f.id);
                          return (
                            <button key={f.id} onClick={() => toggleFeature(f.id)}
                              className={`text-right p-1.5 rounded border text-[10px] transition-all ${sel ? "border-accent-emerald bg-accent-emerald/10 text-accent-emerald" : "border-surface-700/50 text-surface-500 hover:border-surface-500"}`}>
                              <div className="flex items-center gap-1">
                                <div className={`w-2 h-2 rounded-full border ${sel ? "border-accent-emerald bg-accent-emerald" : "border-surface-600"}`} />
                                <span className="font-bold">{f.name}</span>
                              </div>
                              <p className="text-[8px] opacity-60 mr-3">{f.desc}</p>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "genetic" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">🧬 الگوریتم ژنتیک</h3>
                <div className="space-y-2.5">
                  {[{ l: "جمعیت", v: populationSize, s: setPopulationSize }, { l: "نسل‌ها", v: generations, s: setGenerations },
                   { l: "نرخ جهش (%)", v: mutationRate, s: setMutationRate }, { l: "نرخ تقاطع (%)", v: crossoverRate, s: setCrossoverRate }
                  ].map((item, i) => (
                    <div key={i}>
                      <div className="flex justify-between mb-0.5"><label className="text-[9px] text-surface-500">{item.l}</label><span className="text-[9px] font-mono text-primary-300">{item.v}</span></div>
                      <input type="range" min={item.l.includes("نرخ") ? 10 : 10} max={item.l.includes("نرخ") ? 100 : 100} step={item.l.includes("نرخ") ? 5 : 5}
                        value={item.v} onChange={e => item.s(parseInt(e.target.value))} className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
                    </div>
                  ))}
                  <div className="p-2 bg-surface-800/30 rounded text-[9px] text-surface-500">
                    جمعیت × نسل × استراتژی × نماد = {(populationSize * generations * selectedStrategies.length * (symbols.length || 1)).toLocaleString("en")} ارزیابی ژنتیک
                  </div>
                </div>
              </div>
            )}

            {activeTab === "filter" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">🎯 فیلتر ۶ مرحله‌ای</h3>
                <div className="space-y-2.5">
                  {[
                    { l: "۱. حداقل بازده", v: filter1, s: setFilter1, u: "%", max: 100 },
                    { l: "۲. حداکثر افت", v: filter2, s: setFilter2, u: "%", max: 100 },
                    { l: "۳. حداقل شارپ", v: filter3, s: setFilter3, u: "", max: 5 },
                    { l: "۴. حداقل نرخ برد", v: filter4, s: setFilter4, u: "%", max: 100 },
                    { l: "۵. حداقل معاملات", v: filter5, s: setFilter5, u: "", max: 50 },
                    { l: "۶. حداقل عامل سود", v: filter6, s: setFilter6, u: "", max: 5 },
                  ].map((f, i) => (
                    <div key={i}>
                      <div className="flex justify-between mb-0.5">
                        <label className="text-[9px] text-surface-400">{f.l}</label>
                        <span className="text-[9px] font-mono text-primary-300">{f.v}{f.u}</span>
                      </div>
                      <input type="range" min={0} max={f.max} step={f.max <= 5 ? 0.1 : 1} value={f.v} onChange={e => f.s(parseFloat(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "walkforward" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">🔍 Walk-Forward</h3>
                <div className="space-y-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={useWalkForward} onChange={e => setUseWalkForward(e.target.checked)} className="w-3.5 h-3.5 accent-primary-500" />
                    <span className="text-[10px] text-surface-300">فعال‌سازی Walk-Forward</span>
                  </label>
                  {useWalkForward && (
                    <div className="grid grid-cols-2 gap-2">
                      <div><label className="block text-[9px] text-surface-500 mb-0.5">پنجره‌ها</label>
                        <input type="number" value={wfWindows} onChange={e => setWfWindows(parseInt(e.target.value) || 5)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                      <div><label className="block text-[9px] text-surface-500 mb-0.5">آموزش (%)</label>
                        <input type="number" value={wfTrainRatio} onChange={e => setWfTrainRatio(parseInt(e.target.value) || 70)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                    </div>
                  )}
                  <div className="p-2 bg-surface-800/30 rounded text-[8px] text-surface-500 space-y-0.5">
                    <div>• داده‌ها به {wfWindows} پنجره تقسیم می‌شوند</div>
                    <div>• هر پنجره: {wfTrainRatio}% آموزش + {100 - wfTrainRatio}% تست</div>
                    <div>• فقط استراتژی‌های مطلوب در هر دو دوره تأیید می‌شوند</div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "risk" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">🛡️ مدیریت ریسک</h3>
                <div className="space-y-2.5">
                  <div className="grid grid-cols-2 gap-2">
                    <div><label className="block text-[9px] text-surface-500 mb-0.5">حداکثر افت (%)</label>
                      <input type="number" value={filter2} onChange={e => setFilter2(parseInt(e.target.value) || 25)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                    <div><label className="block text-[9px] text-surface-500 mb-0.5">حد ضرر (%)</label>
                      <input type="number" value={stopLoss} onChange={e => setStopLoss(parseInt(e.target.value) || 8)} className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 font-mono outline-none focus:border-primary-500" /></div>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={trailingStop} onChange={e => setTrailingStop(e.target.checked)} className="w-3.5 h-3.5 accent-primary-500" />
                    <span className="text-[10px] text-surface-300">حد ضرر شناور ({trailingStopPct}%)</span>
                  </label>
                  {trailingStop && (
                    <input type="range" min={1} max={15} step={0.5} value={trailingStopPct} onChange={e => setTrailingStopPct(parseFloat(e.target.value))}
                      className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
                  )}
                </div>
              </div>
            )}

            {activeTab === "saved" && (
              <div className="glass-card p-4">
                <h3 className="font-bold text-surface-200 text-xs mb-3">💾 استراتژی‌های ذخیره شده ({savedData?.length || 0})</h3>
                {(!savedData || savedData.length === 0) ? (
                  <p className="text-[10px] text-surface-500">هنوز استراتژی ذخیره نشده</p>
                ) : (
                  <div className="space-y-1.5 max-h-[500px] overflow-y-auto">
                    {savedData?.map(s => (
                      <div key={s.id} className="p-2 bg-surface-800/30 rounded border border-surface-700/30">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-[10px] font-bold text-surface-200">{s.strategy}</span>
                            <span className="text-[9px] text-primary-300 mr-1">{s.symbol}</span>
                          </div>
                          <span className={`text-[9px] font-mono ${(s.metrics.total_return_pct || 0) > 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                            {(s.metrics.total_return_pct || 0).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex gap-2 mt-0.5 text-[8px] text-surface-500">
                          <span>شارپ: {(s.metrics.sharpe_ratio || 0).toFixed(2)}</span>
                          <span>افت: {(s.metrics.max_drawdown_pct || 0).toFixed(1)}%</span>
                          <span>س: {s.created_at?.split("T")[0]}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: Progress & Results */}
          <div className="lg:col-span-2 space-y-4">
            {isGenerating && progress && (
              <div className="glass-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-surface-300 font-bold">{PHASE_LABELS[progress.phase || ""] || "پردازش..."}</span>
                  <div className="flex items-center gap-3">
                    {progress.current_symbol && <span className="text-[10px] text-surface-500">{progress.current_symbol}</span>}
                    {progress.strategies_per_second && <span className="text-[10px] text-primary-300 font-mono">{progress.strategies_per_second.toFixed(0)} str/s</span>}
                    <span className="text-xs font-mono text-primary-300">{progress.progress_pct}%</span>
                  </div>
                </div>
                <div className="w-full h-2 bg-surface-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-primary-600 to-primary-400 rounded-full transition-all duration-300" style={{ width: `${progress.progress_pct}%` }} />
                </div>
                <div className="flex justify-between mt-2 text-[10px] text-surface-500">
                  <span>{progress.completed.toLocaleString("en")} از {progress.total.toLocaleString("en")}</span>
                  <span>{progress.found} استراتژی یافت شد</span>
                </div>
              </div>
            )}

            {results && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  <div className="glass-card p-2.5 text-center"><div className="text-lg font-bold text-surface-100">{results.stats.total_generated.toLocaleString("en")}</div><div className="text-[9px] text-surface-500">تولید شده</div></div>
                  <div className="glass-card p-2.5 text-center"><div className="text-lg font-bold text-accent-emerald">{results.stats.passed_6stage}</div><div className="text-[9px] text-surface-500">فیلتر</div></div>
                  <div className="glass-card p-2.5 text-center"><div className="text-lg font-bold text-primary-300">{results.stats.passed_walk_forward}</div><div className="text-[9px] text-surface-500">تأیید WF</div></div>
                  <div className="glass-card p-2.5 text-center"><div className="text-lg font-bold text-surface-200">{results.strategies.length}</div><div className="text-[9px] text-surface-500">نهایی</div></div>
                  <div className="glass-card p-2.5 text-center flex flex-col gap-1">
                    <button onClick={handleExport} className="text-sm font-bold text-accent-amber hover:text-accent-amber/80">📥 CSV</button>
                    <button onClick={() => handleSaveStrategies(results.strategies)} disabled={savingStrategies}
                      className="text-[10px] font-bold text-primary-300 hover:text-primary-200 disabled:text-surface-500">
                      {savingStrategies ? "..." : "💾 ذخیره همه (" + results.strategies.length + ")"}
                    </button>
                  </div>
                </div>

                {results.strategies.length > 0 ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-bold text-surface-200">🏆 استراتژی‌های تأیید شده</h3>
                    {results.strategies.map((item, i) => (
                      <StrategyCard key={`${item.strategy}-${item.symbol}-${i}`} item={item} rank={i + 1}
                        onSave={() => handleSaveOne(item)} isSaved={savedIds.has(`${item.strategy}-${item.symbol}`)} />
                    ))}
                  </div>
                ) : (
                  <div className="glass-card p-10 text-center text-surface-500">
                    <p className="text-4xl mb-3">🔍</p>
                    <p className="text-sm">هیچ استراتژی‌ای از فیلترها عبور نکرد</p>
                  </div>
                )}
              </>
            )}

            {!isGenerating && !results && (
              <div className="glass-card p-10 text-center text-surface-500">
                <p className="text-5xl mb-4">🧬</p>
                <p className="text-sm font-bold text-surface-300 mb-2">موتور کشف استراتژی</p>
                <p className="text-[10px] max-w-lg mx-auto leading-relaxed">
                  نمادها، ویژگی‌ها و استراتژی‌ها را انتخاب کنید. موتور میلیون‌ها ترکیب را با الگوریتم ژنتیک بهینه‌سازی کرده
                  و فقط استراتژی‌هایی که از فیلتر ۶ مرحله‌ای و Walk-Forward عبور کنند را نمایش می‌دهد. نتایج قابل ذخیره و مقایسه هستند.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-[10px]">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 px-2 py-1">← بک‌تست</Link>
          <Link href="/backtest/generate" className="text-surface-500 hover:text-surface-200 px-2 py-1">تولید خودکار</Link>
        </div>
      </div>
    </AppLayout>
  );
}
