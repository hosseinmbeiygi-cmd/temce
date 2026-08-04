"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

// ── All 30 Indicators Definition ──────────────────────────────────────────────

const ALL_INDICATORS: { id: string; name: string; group: string; groupFa: string; icon: string; params: Record<string, number[]> }[] = [
  { id:"rsi", name:"RSI", group:"momentum", groupFa:"مومنتوم", icon:"📊", params:{ period:[7,10,14,21] } },
  { id:"macd", name:"MACD", group:"momentum", groupFa:"مومنتوم", icon:"📊", params:{ fast:[8,12,16], slow:[21,26,30], signal:[7,9,12] } },
  { id:"squeeze_momentum", name:"Squeeze", group:"momentum", groupFa:"مومنتوم", icon:"📊", params:{ bb_period:[15,20,25], bb_std:[1.5,2,2.5], kc_period:[15,20,25], kc_mult:[1,1.5,2] } },
  { id:"stochastic", name:"Stochastic", group:"momentum", groupFa:"مومنتوم", icon:"📊", params:{ k_period:[9,14,21], d_period:[3,5], smooth:[3,5] } },
  { id:"williams_r", name:"Williams %R", group:"momentum", groupFa:"مومنتوم", icon:"📊", params:{ period:[10,14,21] } },
  { id:"cci", name:"CCI", group:"momentum", groupFa:"مومنتوم", icon:"📊", params:{ period:[14,20,28] } },
  { id:"ema_crossover", name:"EMA Cross", group:"trend", groupFa:"روند", icon:"📈", params:{ fast:[5,10,15], slow:[20,30,50] } },
  { id:"adx", name:"ADX", group:"trend", groupFa:"روند", icon:"📈", params:{ period:[14,20,28] } },
  { id:"half_trend", name:"Half-Trend", group:"trend", groupFa:"روند", icon:"📈", params:{ amplitude:[1,2,3,4,5], channel_deviation:[1,1.5,2,2.5,3] } },
  { id:"parabolic_sar", name:"Parabolic SAR", group:"trend", groupFa:"روند", icon:"📈", params:{ step:[0.01,0.02,0.03], max_af:[0.1,0.2,0.3] } },
  { id:"ichimoku", name:"Ichimoku", group:"trend", groupFa:"روند", icon:"📈", params:{ tenkan:[7,9,12], kijun:[22,26,30], senkou:[52,60] } },
  { id:"atr", name:"ATR", group:"volatility", groupFa:"نوسان", icon:"📉", params:{ period:[10,14,20,28] } },
  { id:"bollinger_bw", name:"Bollinger BW", group:"volatility", groupFa:"نوسان", icon:"📉", params:{ period:[15,20,25], std:[1.5,2,2.5] } },
  { id:"keltner_position", name:"Keltner", group:"volatility", groupFa:"نوسان", icon:"📉", params:{ period:[10,20,30], mult:[1.5,2,2.5] } },
  { id:"compression_ratio", name:"Compression", group:"volatility", groupFa:"نوسان", icon:"📉", params:{ short_p:[3,5,7], long_p:[15,20,25] } },
  { id:"normalized_volatility", name:"Norm Vol", group:"volatility", groupFa:"نوسان", icon:"📉", params:{ period:[10,14,20,28] } },
  { id:"relative_volume", name:"Rel Volume", group:"volume", groupFa:"حجم", icon:"📦", params:{ period:[10,15,20,30] } },
  { id:"obv", name:"OBV", group:"volume", groupFa:"حجم", icon:"📦", params:{ sma_p:[10,15,20,30] } },
  { id:"vwap", name:"VWAP", group:"volume", groupFa:"حجم", icon:"📦", params:{ period:[10,15,20,30] } },
  { id:"supply_dryness", name:"Supply Dryness", group:"volume", groupFa:"حجم", icon:"📦", params:{ period:[10,15,20,30] } },
  { id:"volume_zscore", name:"Vol Z-Score", group:"volume", groupFa:"حجم", icon:"📦", params:{ period:[10,15,20,30] } },
  { id:"clv", name:"CLV", group:"price", groupFa:"قیمت", icon:"💵", params:{} },
  { id:"recovery_ratio", name:"Recovery", group:"price", groupFa:"قیمت", icon:"💵", params:{} },
  { id:"support_resistance", name:"S/R Levels", group:"structure", groupFa:"ساختار", icon:"🏗️", params:{ lookback:[10,15,20,25,30] } },
  { id:"breakout_quality", name:"Breakout Q", group:"structure", groupFa:"ساختار", icon:"🏗️", params:{ period:[15,20,25,30] } },
  { id:"relative_strength", name:"Rel Strength", group:"relative", groupFa:"نسبی", icon:"⚖️", params:{ period:[10,15,20,30] } },
  { id:"amihud_illiquidity", name:"Amihud", group:"liquidity", groupFa:"نقدینگی", icon:"💧", params:{ period:[10,15,20,30] } },
];

const INDICATOR_GROUPS = [...new Set(ALL_INDICATORS.map(i => i.group))].map(g => {
  const first = ALL_INDICATORS.find(i => i.group === g)!;
  return { id: g, label: first.groupFa, icon: first.icon };
});

// ── 6-Stage Filter Defaults ────────────────────────────────────────────────

const DEFAULT_FILTER = {
  stage1_min_return: 5.0,
  stage2_max_drawdown: 25.0,
  stage3_min_sharpe: 0.5,
  stage4_min_win_rate: 40.0,
  stage5_min_trades: 5,
  stage6_min_profit_factor: 1.2,
};

const FILTER_LABELS: Record<string, { label: string; unit: string }> = {
  stage1_min_return: { label: "حداقل بازده کل", unit: "%" },
  stage2_max_drawdown: { label: "حداکثر افت سرمایه", unit: "%" },
  stage3_min_sharpe: { label: "حداقل نسبت شارپ", unit: "" },
  stage4_min_win_rate: { label: "حداقل نرخ برد", unit: "%" },
  stage5_min_trades: { label: "حداقل تعداد معاملات", unit: "عدد" },
  stage6_min_profit_factor: { label: "حداقل عامل سود", unit: "" },
};

// ── Types ────────────────────────────────────────────────────────────────────

interface ScanResult {
  id: string; symbol: string; indicator: string; params: string;
  exit_condition: string; total_return_pct: number; sharpe_ratio: number;
  max_drawdown_pct: number; win_rate: number; profit_factor: number;
  total_trades: number; score: number; batch_id: string;
}

interface StrategyResult {
  strategy: string; params: Record<string, unknown>;
  metrics: { total_return_pct: number; sharpe_ratio: number; max_drawdown_pct: number; win_rate: number; total_trades: number; profit_factor: number; sortino_ratio: number; calmar_ratio: number; annualized_return_pct: number; winning_trades: number; losing_trades: number };
  symbol?: string; method?: string; score?: number;
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function FullScanPage() {
  // Symbol selection
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbolInput, setSymbolInput] = useState("");
  const [allDbSymbols, setAllDbSymbols] = useState<{ symbol: string; bar_count: number }[]>([]);

  // Indicator selection
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(ALL_INDICATORS.map(i => i.id));

  // 6-Stage Filter
  const [filters, setFilters] = useState({ ...DEFAULT_FILTER });

  // Genetic
  const [useGenetic, setUseGenetic] = useState(true);
  const [geneticGens, setGeneticGens] = useState(8);
  const [maxCombinations, setMaxCombinations] = useState(3000);

  // Phases
  const [runPhase1, setRunPhase1] = useState(true);
  const [runPhase2, setRunPhase2] = useState(true);

  // Date & Capital
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState(1_000_000_000);

  // State
  const [isRunning, setIsRunning] = useState(false);
  const [phase1Results, setPhase1Results] = useState<StrategyResult[]>([]);
  const [phase2Results, setPhase2Results] = useState<ScanResult[]>([]);
  const [phase2Progress, setPhase2Progress] = useState<{ progress_pct: number; total_passing: number } | null>(null);
  const [activeTab, setActiveTab] = useState<"config" | "results">("config");
  const [resultSortKey, setResultSortKey] = useState<string>("score");
  const [resultSortDir, setResultSortDir] = useState<"asc"|"desc">("desc");
  const [resultFilterSymbol, setResultFilterSymbol] = useState("");
  const [resultFilterIndicator, setResultFilterIndicator] = useState("");

  // Polling cleanup ref
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, []);

  // Load DB symbols
  useEffect(() => {
    apiGet<{ success: boolean; data: { symbol: string; bar_count: number }[] }>("/backtests/data/symbols")
      .then(r => { if (r?.data) setAllDbSymbols(r.data); })
      .catch(() => {});
  }, []);

  const addSymbol = (s: string) => { if (s && !symbols.includes(s)) setSymbols([...symbols, s]); };
  const removeSymbol = (s: string) => setSymbols(symbols.filter(x => x !== s));

  // Toggle indicator
  const toggleIndicator = (id: string) => {
    setSelectedIndicators(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };
  const selectAllIndicators = () => setSelectedIndicators(ALL_INDICATORS.map(i => i.id));
  const clearIndicators = () => setSelectedIndicators([]);
  const selectGroup = (group: string) => {
    const ids = ALL_INDICATORS.filter(i => i.group === group).map(i => i.id);
    setSelectedIndicators(prev => [...new Set([...prev, ...ids])]);
  };

  // Run full scan
  const handleRun = async () => {
    if (symbols.length === 0) { toast.error("حداقل یک نماد انتخاب کنید"); return; }
    // Clear any existing polling
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setIsRunning(true);
    setPhase1Results([]); setPhase2Results([]);
    setPhase2Progress(null);

    try {
      // Phase 1: Strategy Generator (synchronous — results returned directly)
      if (runPhase1) {
        toast.info("فاز ۱: جستجوی شبکه‌ای + ژنتیک + فیلتر ۶ مرحله‌ای در حال اجرا...");
        const res = await apiPost<{ success: boolean; data: { strategies: StrategyResult[]; stats: Record<string, unknown> } }>("/backtests/generate", {
          symbols, capital, max_combinations: maxCombinations,
          use_genetic: useGenetic, genetic_generations: geneticGens,
          start_date: startDate, end_date: endDate, filters,
        });
        if (res?.data?.strategies && mountedRef.current) {
          setPhase1Results(res.data.strategies);
          toast.success(`فاز ۱: ${res.data.strategies.length} استراتژی از فیلتر عبور کرد`);
        }
      }

      // Phase 2: Indicator Scan (fire-and-forget, then poll)
      if (runPhase2 && mountedRef.current) {
        toast.info("فاز ۲: اسکن ۲۶ اندیکاتور شروع شد");
        await apiPost("/backtests/scan-indicators", {
          symbols, indicator_ids: selectedIndicators,
          capital, start_date: startDate, end_date: endDate,
          filters, batch_size: 10, max_concurrent: 10,
        });

        let pollCount = 0;
        const maxPolls = 600;
        pollRef.current = setInterval(async () => {
          pollCount++;
          try {
            const statusRes = await apiGet<{ success: boolean; data: { running: boolean; progress_pct: number; total_passing: number } }>("/backtests/scan-indicators/status");
            if (statusRes?.data && mountedRef.current) setPhase2Progress(statusRes.data);
            if (!statusRes?.data?.running || pollCount >= maxPolls || !mountedRef.current) {
              if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
              const resultsRes = await apiGet<{ success: boolean; data: { results: ScanResult[] } }>("/backtests/scan-indicators/results");
              if (resultsRes?.data?.results && mountedRef.current) setPhase2Results(resultsRes.data.results);
              if (mountedRef.current) {
                setIsRunning(false);
                toast.success("اسکن کامل شد!");
                setActiveTab("results");
              }
            }
          } catch {
            if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
            if (mountedRef.current) setIsRunning(false);
          }
        }, 3000);
      } else if (mountedRef.current) {
        setIsRunning(false);
        toast.success("تولید کامل شد!");
        setActiveTab("results");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "خطا در اجرا";
      if (mountedRef.current) toast.error(msg);
      if (mountedRef.current) setIsRunning(false);
    }
  };

  // Combined & Sorted Results
  const allCombined = [
    ...phase1Results.map(r => ({
      id: `${r.strategy}-${r.symbol}`,
      symbol: r.symbol || "?",
      type: "استراتژی" as const,
      name: r.strategy,
      method: r.method || "grid",
      return_pct: r.metrics?.total_return_pct || 0,
      sharpe: r.metrics?.sharpe_ratio || 0,
      max_dd: r.metrics?.max_drawdown_pct || 0,
      win_rate: r.metrics?.win_rate || 0,
      profit_factor: r.metrics?.profit_factor || 0,
      total_trades: r.metrics?.total_trades || 0,
      sortino: r.metrics?.sortino_ratio || 0,
      calmar: r.metrics?.calmar_ratio || 0,
      score: r.score || 0,
    })),
    ...phase2Results.map(r => ({
      id: r.id,
      symbol: r.symbol,
      type: "اندیکاتور" as const,
      name: r.indicator,
      method: "signal",
      return_pct: r.total_return_pct || 0,
      sharpe: r.sharpe_ratio || 0,
      max_dd: r.max_drawdown_pct || 0,
      win_rate: r.win_rate || 0,
      profit_factor: r.profit_factor || 0,
      total_trades: r.total_trades || 0,
      sortino: 0,
      calmar: 0,
      score: r.score || 0,
    })),
  ];

  const filtered = allCombined.filter(r => {
    if (resultFilterSymbol && r.symbol !== resultFilterSymbol) return false;
    if (resultFilterIndicator && r.name !== resultFilterIndicator) return false;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    const key = resultSortKey as keyof typeof a;
    const aVal = (a[key] as number) ?? 0;
    const bVal = (b[key] as number) ?? 0;
    return resultSortDir === "asc" ? aVal - bVal : bVal - aVal;
  });

  const uniqueSymbols = [...new Set(allCombined.map(r => r.symbol))];
  const uniqueNames = [...new Set(allCombined.map(r => r.name))];

  // Helpers
  const colorReturn = (v: number) => v >= 0 ? "text-accent-emerald" : "text-accent-rose";
  const colorSharpe = (v: number) => v >= 1 ? "text-accent-emerald" : v >= 0.5 ? "text-accent-amber" : "text-accent-rose";

  return (
    <AppLayout title="اسکن کامل — تمام اندیکاتورها + ژنتیک + فیلتر ۶ مرحله‌ای" subtitle="Phase 1: Strategy Generator + Phase 2: All 30 Indicators">
      <div className="max-w-7xl mx-auto space-y-4">

        {/* Header Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-primary-300">{symbols.length}</div>
            <div className="text-[10px] text-surface-500">نماد</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-accent-amber">{selectedIndicators.length}/{ALL_INDICATORS.length}</div>
            <div className="text-[10px] text-surface-500">اندیکاتور</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-accent-emerald">{allCombined.length}</div>
            <div className="text-[10px] text-surface-500">نتیجه</div>
          </div>
          <div className="glass-card p-3 text-center col-span-2">
            <button onClick={handleRun} disabled={isRunning || symbols.length === 0}
              className={`w-full py-3 rounded-lg text-sm font-bold transition-colors ${
                isRunning || symbols.length === 0
                  ? "bg-surface-700 text-surface-400 cursor-not-allowed"
                  : "bg-gradient-to-r from-primary-600 to-accent-purple text-white hover:from-primary-500 hover:to-accent-purple/80"
              }`}>
              {isRunning ? "⏳ در حال اجرا..." : "🚀 شروع اسکن کامل"}
            </button>
            {isRunning && phase2Progress && (
              <div className="mt-2">
                <div className="flex justify-between text-[9px] text-surface-500 mb-1">
                  <span>فاز ۲: اسکن اندیکاتورها</span>
                  <span className="font-mono">{phase2Progress.progress_pct}% · {phase2Progress.total_passing} عبور</span>
                </div>
                <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-primary-500 to-accent-purple rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, phase2Progress.progress_pct))}%` }} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1">
          {[
            { id: "config" as const, label: "⚙️ تنظیمات" },
            { id: "results" as const, label: `📊 نتایج (${allCombined.length})` },
          ].map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`flex-1 text-sm py-2 rounded-md transition-colors ${
                activeTab === t.id ? "bg-primary-600 text-white font-bold" : "text-surface-400 hover:text-surface-200"
              }`}>{t.label}</button>
          ))}
        </div>

        {/* ── Config Tab ── */}
        {activeTab === "config" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Symbols */}
            <div className="glass-card p-4">
              <h3 className="text-sm font-bold text-surface-200 mb-3">💹 نمادها</h3>
              <div className="flex gap-2 mb-2">
                <input value={symbolInput} onChange={e => setSymbolInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") { addSymbol(symbolInput); setSymbolInput(""); } }}
                  className="flex-1 bg-surface-800 border border-surface-700 rounded px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500"
                  placeholder="جستجوی نماد..." />
                <button onClick={() => { addSymbol(symbolInput); setSymbolInput(""); }}
                  className="px-3 py-2 bg-primary-600 text-white rounded text-sm">+</button>
              </div>
              <div className="flex flex-wrap gap-1 mb-2 max-h-20 overflow-y-auto">
                {symbols.map(s => (
                  <span key={s} className="flex items-center gap-1 text-xs px-2 py-0.5 bg-primary-600/15 text-primary-300 rounded-full">
                    {s} <button onClick={() => removeSymbol(s)} className="text-primary-400 hover:text-primary-200">✕</button>
                  </span>
                ))}
              </div>
              <div className="flex gap-1 flex-wrap">
                <button onClick={() => setSymbols(allDbSymbols.slice(0, 100).map(s => s.symbol))}
                  className="text-[10px] px-2 py-0.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-full">
                  همه ({Math.min(allDbSymbols.length, 100)})
                </button>
                <button onClick={() => setSymbols([])}
                  className="text-[10px] px-2 py-0.5 bg-accent-rose/20 text-accent-rose rounded-full">پاک کردن</button>
              </div>
            </div>

            {/* Phases & Dates */}
            <div className="glass-card p-4">
              <h3 className="text-sm font-bold text-surface-200 mb-3">📅 فازها و تاریخ</h3>
              <div className="space-y-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={runPhase1} onChange={e => setRunPhase1(e.target.checked)}
                    className="w-4 h-4 accent-primary-500 rounded" />
                  <span className="text-xs text-surface-300">فاز ۱: تولید استراتژی (Grid + Genetic + 6-stage)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={runPhase2} onChange={e => setRunPhase2(e.target.checked)}
                    className="w-4 h-4 accent-accent-amber rounded" />
                  <span className="text-xs text-surface-300">فاز ۲: اسکن ۳۰ اندیکاتور</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-surface-500">شروع</label>
                    <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                      className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-100 font-mono outline-none" />
                  </div>
                  <div>
                    <label className="text-[10px] text-surface-500">پایان</label>
                    <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                      className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-100 font-mono outline-none" />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] text-surface-500">سرمایه (ریال)</label>
                  <input type="number" value={capital} onChange={e => setCapital(Number(e.target.value))}
                    className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-100 font-mono outline-none" />
                </div>
              </div>
            </div>

            {/* Genetic */}
            <div className="glass-card p-4">
              <h3 className="text-sm font-bold text-surface-200 mb-3">🧬 الگوریتم ژنتیک</h3>
              <label className="flex items-center gap-2 cursor-pointer mb-3">
                <input type="checkbox" checked={useGenetic} onChange={e => setUseGenetic(e.target.checked)}
                  className="w-4 h-4 accent-primary-500 rounded" />
                <span className="text-xs text-surface-300">فعال‌سازی بهینه‌سازی ژنتیک</span>
              </label>
              {useGenetic && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-surface-500">نسل‌ها</label>
                    <input type="number" value={geneticGens} onChange={e => setGeneticGens(Number(e.target.value))}
                      className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-100 font-mono outline-none" />
                  </div>
                  <div>
                    <label className="text-[10px] text-surface-500">حداکثر ترکیب</label>
                    <input type="number" value={maxCombinations} onChange={e => setMaxCombinations(Number(e.target.value))}
                      className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-100 font-mono outline-none" />
                  </div>
                </div>
              )}
            </div>

            {/* 6-Stage Filter */}
            <div className="glass-card p-4">
              <h3 className="text-sm font-bold text-surface-200 mb-3">🔍 فیلتر ۶ مرحله‌ای</h3>
              <div className="space-y-2">
                {Object.entries(FILTER_LABELS).map(([key, { label, unit }]) => (
                  <div key={key} className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-surface-400 w-32 truncate">{label}</span>
                    <input type="number" step={key.includes("sharpe") || key.includes("profit") ? 0.1 : 1}
                      value={(filters as Record<string, number>)[key]} onChange={e => setFilters({ ...filters, [key]: Number(e.target.value) })}
                      className="w-20 bg-surface-800 border border-surface-700 rounded px-2 py-1 text-xs text-surface-100 font-mono outline-none focus:border-primary-500" />
                    <span className="text-[10px] text-surface-600 w-5">{unit}</span>
                  </div>
                ))}
              </div>
              <button onClick={() => setFilters({...DEFAULT_FILTER})}
                className="mt-3 text-[10px] px-2 py-1 bg-surface-800 text-surface-400 hover:text-surface-200 rounded">↩ ریست</button>
            </div>

            {/* All 30 Indicators */}
            <div className="lg:col-span-3 glass-card p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-surface-200">📡 تمام ۳۰ اندیکاتور ({selectedIndicators.length}/{ALL_INDICATORS.length})</h3>
                <div className="flex gap-2">
                  <button onClick={selectAllIndicators} className="text-[10px] px-2 py-1 bg-surface-800 text-surface-400 hover:text-surface-200 rounded">انتخاب همه</button>
                  <button onClick={clearIndicators} className="text-[10px] px-2 py-1 bg-accent-rose/20 text-accent-rose rounded">حذف همه</button>
                </div>
              </div>
              <div className="space-y-3">
                {INDICATOR_GROUPS.map(group => {
                  const items = ALL_INDICATORS.filter(i => i.group === group.id);
                  const selected = items.filter(i => selectedIndicators.includes(i.id));
                  return (
                    <div key={group.id}>
                      <button onClick={() => selectGroup(group.id)}
                        className="flex items-center gap-2 mb-2 text-xs font-bold text-surface-400 hover:text-surface-200">
                        {group.icon} {group.label}
                        <span className="text-[10px] text-surface-600">({selected.length}/{items.length})</span>
                      </button>
                      <div className="flex flex-wrap gap-1.5">
                        {items.map(ind => {
                          const sel = selectedIndicators.includes(ind.id);
                          return (
                            <button key={ind.id} onClick={() => toggleIndicator(ind.id)}
                              className={`text-[10px] px-2 py-1 rounded-full border transition-all ${
                                sel ? "border-primary-500 bg-primary-600/15 text-primary-300" : "border-surface-700 text-surface-500 hover:border-surface-500"
                              }`}>{ind.name}</button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── Results Tab ── */}
        {activeTab === "results" && (
          <div className="space-y-4">
            {/* Filter Controls */}
            <div className="glass-card p-3 flex flex-wrap gap-3 items-center">
              <span className="text-xs text-surface-400 font-bold">فیلتر:</span>
              <select value={resultFilterSymbol} onChange={e => setResultFilterSymbol(e.target.value)}
                className="bg-surface-800 border border-surface-700 rounded px-2 py-1 text-xs text-surface-200">
                <option value="">همه نمادها</option>
                {uniqueSymbols.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <select value={resultFilterIndicator} onChange={e => setResultFilterIndicator(e.target.value)}
                className="bg-surface-800 border border-surface-700 rounded px-2 py-1 text-xs text-surface-200">
                <option value="">همه</option>
                {uniqueNames.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
              <span className="text-[10px] text-surface-500">{filtered.length} از {allCombined.length}</span>
            </div>

            {/* Results Table */}
            <div className="glass-card overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-surface-700 text-surface-400">
                    {[
                      { k:"symbol", l:"نماد" }, { k:"type", l:"نوع" }, { k:"name", l:"نام" },
                      { k:"return_pct", l:"بازده %" }, { k:"sharpe", l:"شارپ" }, { k:"max_dd", l:"MaxDD%" },
                      { k:"win_rate", l:"Win%" }, { k:"profit_factor", l:"PF" }, { k:"total_trades", l:"معاملات" },
                      { k:"score", l:"Score" },
                    ].map(c => (
                      <th key={c.k} className="py-2 px-2 text-right cursor-pointer hover:text-surface-200"
                        onClick={() => { setResultSortKey(c.k); setResultSortDir(prev => resultSortKey === c.k ? (prev === "asc" ? "desc" : "asc") : "desc"); }}>
                        {c.l}{resultSortKey === c.k ? (resultSortDir === "asc" ? " ▲" : " ▼") : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.slice(0, 200).map((r, i) => (
                    <tr key={r.id || i} className={`border-b border-surface-800/50 hover:bg-surface-800/30 ${i % 2 === 0 ? "bg-surface-800/10" : ""}`}>
                      <td className="py-2 px-2 font-mono text-surface-200 font-bold">{r.symbol}</td>
                      <td className="py-2 px-2">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${r.type === "استراتژی" ? "bg-primary-600/15 text-primary-300" : "bg-accent-amber/15 text-accent-amber"}`}>{r.type}</span>
                      </td>
                      <td className="py-2 px-2 text-surface-300">{r.name}</td>
                      <td className={`py-2 px-2 font-mono font-bold ${colorReturn(r.return_pct)}`}>
                        {r.return_pct > 0 ? "+" : ""}{r.return_pct.toFixed(1)}%
                      </td>
                      <td className={`py-2 px-2 font-mono ${colorSharpe(r.sharpe)}`}>{r.sharpe.toFixed(2)}</td>
                      <td className="py-2 px-2 font-mono text-accent-rose">{r.max_dd.toFixed(1)}%</td>
                      <td className="py-2 px-2 font-mono">{r.win_rate.toFixed(0)}%</td>
                      <td className="py-2 px-2 font-mono">{r.profit_factor.toFixed(2)}</td>
                      <td className="py-2 px-2 font-mono text-surface-400">{r.total_trades}</td>
                      <td className="py-2 px-2 font-mono text-primary-400 font-bold">{r.score.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {sorted.length === 0 && (
                <div className="p-12 text-center text-surface-500">
                  <p className="text-4xl mb-3">🔍</p>
                  <p>هنوز نتیجه‌ای موجود نیست — اسکن را اجرا کنید</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Quick Links */}
        <div className="flex flex-wrap gap-2 text-xs border-t border-surface-700/50 pt-4">
          <Link href="/backtest/generate" className="text-surface-500 hover:text-surface-200 px-2 py-1">🚀 تولید خودکار</Link>
          <Link href="/backtest/compose" className="text-surface-500 hover:text-surface-200 px-2 py-1">🔬 ترکیب استراتژی</Link>
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 px-2 py-1">← بک‌تست ساده</Link>
        </div>
      </div>
    </AppLayout>
  );
}
