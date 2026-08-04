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
  };
  symbol?: string;
  method?: string;
  score?: number;
  validation_status?: "validated" | "rejected" | "pending";
  wf_result?: {
    validated: boolean;
    avg_is_return: number;
    avg_oos_return: number;
    avg_is_calmar: number;
    windows_tested: number;
    reason: string;
  };
}

interface CascadeResponse {
  strategies: StrategyResult[];
  stats: {
    total_generated: number;
    passed_6stage: number;
    passed_walk_forward: number;
    symbols: string[];
    period: string;
    engine_version: string;
  };
}

interface ProgressData {
  running: boolean;
  progress_pct: number;
  completed: number;
  total: number;
  found: number;
  phase?: string;
}

interface SymbolOption {
  symbol: string;
  name: string;
  bar_count?: number;
}

// ── Constants ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const STRATEGIES = [
  { id: "moving_average_cross", name: "تقاطع میانگین متحرک", cat: "trend", params: 2, combos: 70 },
  { id: "momentum", name: "مومنتوم قیمتی", cat: "momentum", params: 2, combos: 72 },
  { id: "mean_reversion", name: "بازگشت به میانگین", cat: "reversion", params: 3, combos: 120 },
  { id: "breakout", name: "شکست قیمت", cat: "momentum", params: 2, combos: 42 },
  { id: "rsi_reversion", name: "بازگشت RSI", cat: "reversion", params: 3, combos: 100 },
  { id: "volatility_breakout", name: "شکست نوسان", cat: "momentum", params: 2, combos: 30 },
  { id: "half_trend", name: "نیمه‌روند", cat: "trend", params: 2, combos: 25 },
  { id: "squeeze_momentum", name: "فشردگی مومنتوم", cat: "trend", params: 4, combos: 432 },
  { id: "support_resistance", name: "حمایت و مقاومت", cat: "technical", params: 2, combos: 30 },
];

const FEATURES = [
  { id: "technical", label: "تکنیکال", icon: "📊", items: ["RSI", "MACD", "ATR", "Bollinger", "EMA", "ADX"] },
  { id: "momentum", label: "مومنتوم", icon: "🚀", items: ["ROC", "Normalized Return", "Sector RS", "Price Momentum"] },
  { id: "volume", label: "حجم", icon: "📦", items: ["Volume Ratio", "OBV", "VWAP", "Smart Money"] },
  { id: "microstructure", label: "ریزساختار", icon: "🔬", items: ["IBP", "Buyer/Seller Ratio", "QPI", "Trade Value"] },
  { id: "macro", label: "کلان", icon: "🌍", items: ["USD Trend", "Commodity", "Index"] },
];

const CAT_COLORS: Record<string, string> = {
  trend: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30",
  momentum: "bg-accent-amber/15 text-accent-amber border-accent-amber/30",
  reversion: "bg-primary-600/15 text-primary-300 border-primary-500/30",
  technical: "bg-surface-700/50 text-surface-300 border-surface-600",
};

const PHASES: Record<string, string> = {
  initializing: "آماده‌سازی...",
  grid_search: "جستجوی شبکه‌ای",
  genetic_optimization: "بهینه‌سازی ژنتیک",
  walk_forward: "Walk-Forward",
  idle: "تمام",
};

// ── Components ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function SymbolPicker({ symbols, onAdd, onRemove, allDb, loadingDb }: {
  symbols: string[]; onAdd: (s: string) => void; onRemove: (s: string) => void;
  allDb: SymbolOption[]; loadingDb: boolean;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const { data: res = [], isLoading } = useQuery({
    queryKey: ["cascade-sym", q],
    queryFn: async (): Promise<SymbolOption[]> => {
      if (!q.trim()) return [];
      try {
        const r = await apiGet<{ success: boolean; data: { items: SymbolOption[] } }>(
          `/instruments/search?q=${encodeURIComponent(q)}&page_size=20`);
        return r?.data?.items || [];
      } catch { return []; }
    },
    enabled: open && q.trim().length > 0,
  });

  return (
    <div className="space-y-2" ref={ref}>
      {symbols.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {symbols.map(s => (
            <span key={s} className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-primary-600/15 text-primary-300 rounded-md">
              {s}<button onClick={() => onRemove(s)} className="text-primary-400 hover:text-primary-200">✕</button>
            </span>
          ))}
        </div>
      )}
      <div className="relative">
        <input type="text" value={q} onChange={e => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          onKeyDown={e => { if (e.key === "Enter" && res.length > 0) { onAdd(res[0].symbol); setQ(""); } if (e.key === "Escape") setOpen(false); }}
          className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 outline-none focus:border-primary-500"
          placeholder="جستجو و افزودن نماد..." />
        {open && q.trim().length > 0 && (
          <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-800 border border-surface-700 rounded-lg shadow-2xl max-h-48 overflow-y-auto">
            {isLoading && <div className="px-3 py-2 text-[10px] text-surface-500">جستجو...</div>}
            {!isLoading && res.length === 0 && <div className="px-3 py-2 text-[10px] text-surface-500">نتیجه‌ای یافت نشد</div>}
            {!isLoading && res.map(it => {
              const sel = symbols.includes(it.symbol);
              return (
                <button key={it.symbol} onClick={() => { if (sel) { onRemove(it.symbol); } else { onAdd(it.symbol); } setQ(""); setOpen(false); }}
                  className={`w-full text-right px-3 py-1.5 text-xs flex items-center justify-between transition-colors ${sel ? "bg-primary-600/20 text-primary-300" : "text-surface-200 hover:bg-surface-700"}`}>
                  <div className="flex items-center gap-1.5">{sel && <span className="text-primary-400">✓</span>}
                    <span className="font-mono font-bold">{it.symbol}</span></div>
                  <span className="text-[10px] text-surface-500 truncate ml-2 max-w-[120px]">{it.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <div className="flex gap-1" suppressHydrationWarning>
        <button onClick={() => onAdd(allDb.map(s => s.symbol).join(","))} disabled={loadingDb || allDb.length === 0}
          className="text-[9px] px-1.5 py-0.5 bg-primary-600/20 text-primary-300 rounded transition-colors font-bold">
          {loadingDb ? "..." : "همه (" + allDb.length + ")"}
        </button>
        <button onClick={() => symbols.forEach(s => onRemove(s))} disabled={symbols.length === 0}
          className="text-[9px] px-1.5 py-0.5 bg-accent-rose/20 text-accent-rose rounded transition-colors">پاک کردن</button>
      </div>
      {allDb.length > 0 && (
        <div className="max-h-32 overflow-y-auto border border-surface-700/50 rounded-lg">
          {allDb.slice(0, 30).map(s => (
            <button key={s.symbol} onClick={() => symbols.includes(s.symbol) ? onRemove(s.symbol) : onAdd(s.symbol)}
              className={`w-full text-right px-2 py-1 text-[10px] flex items-center justify-between border-b border-surface-700/20 transition-colors ${symbols.includes(s.symbol) ? "bg-primary-600/10 text-primary-300" : "text-surface-400 hover:bg-surface-800"}`}>
              <div className="flex items-center gap-1">{symbols.includes(s.symbol) && <span className="text-primary-400">✓</span>}
                <span className="font-mono font-bold">{s.symbol}</span></div>
              <span className="text-surface-600">{s.bar_count || "?"}r</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultCard({ item, rank, onSave }: { item: StrategyResult; rank: number; onSave: () => void }) {
  const m = item.metrics;
  const rc = m.total_return_pct > 0 ? "text-accent-emerald" : "text-accent-rose";
  const sc = m.sharpe_ratio > 1 ? "text-accent-emerald" : m.sharpe_ratio > 0.5 ? "text-accent-amber" : "text-accent-rose";
  const vc = item.validation_status === "validated" ? "text-accent-emerald" : item.validation_status === "rejected" ? "text-accent-rose" : "text-surface-500";
  const vl = item.validation_status === "validated" ? "✓ تأیید" : item.validation_status === "rejected" ? "✕ رد" : "...";

  return (
    <div className={`glass-card p-3 transition-all ${item.validation_status === "rejected" ? "opacity-50" : "hover:bg-surface-800/50"}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="w-5 h-5 rounded-full bg-primary-600/20 text-primary-300 flex items-center justify-center text-[9px] font-bold">{rank}</span>
          <div>
            <h4 className="font-bold text-surface-100 text-[11px]">{item.strategy}</h4>
            <div className="flex items-center gap-1 mt-0.5">
              {item.symbol && <span className="text-[8px] px-1 py-0.5 bg-primary-600/15 text-primary-300 rounded">{item.symbol}</span>}
              {item.method && <span className={`text-[8px] px-1 py-0.5 rounded ${item.method === "genetic" ? "bg-accent-amber/15 text-accent-amber" : "bg-surface-700 text-surface-400"}`}>{item.method}</span>}
              <span className={`text-[8px] ${vc}`}>{vl}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`text-[11px] px-1.5 py-0.5 rounded font-bold ${rc} bg-surface-800`}>{m.total_return_pct > 0 ? "+" : ""}{m.total_return_pct.toFixed(1)}%</span>
          <button onClick={onSave} className="text-[9px] px-1.5 py-0.5 bg-primary-600/20 text-primary-300 hover:bg-primary-600/30 rounded">💾</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-0.5 mb-1.5">
        {Object.entries(item.params).map(([k, v]) => (
          <span key={k} className="text-[7px] px-1 py-0.5 bg-surface-800 text-surface-500 rounded font-mono">{k}={String(v)}</span>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-1">
        {[
          { l: "بازده", v: `${m.total_return_pct.toFixed(1)}%`, c: rc },
          { l: "شارپ", v: m.sharpe_ratio.toFixed(2), c: sc },
          { l: "افت", v: `${m.max_drawdown_pct.toFixed(1)}%`, c: "text-accent-rose" },
          { l: "برد", v: `${m.win_rate.toFixed(0)}%`, c: "text-surface-200" },
        ].map((x, i) => (
          <div key={i} className="text-center p-1 bg-surface-800/30 rounded">
            <div className={`text-[11px] font-bold font-mono ${x.c}`}>{x.v}</div>
            <div className="text-[7px] text-surface-500">{x.l}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-1 mt-1">
        {[
          { l: "سود/زیان", v: m.profit_factor.toFixed(2) },
          { l: "سورتینو", v: m.sortino_ratio.toFixed(2) },
          { l: "کالمر", v: m.calmar_ratio.toFixed(2) },
          { l: "معاملات", v: String(m.total_trades) },
        ].map((x, i) => (
          <div key={i} className="text-center p-0.5 bg-surface-800/20 rounded">
            <div className="text-[9px] font-mono text-surface-300">{x.v}</div>
            <div className="text-[6px] text-surface-600">{x.l}</div>
          </div>
        ))}
      </div>
      {item.wf_result && (
        <div className="mt-1.5 p-1.5 bg-surface-800/20 rounded border border-surface-700/20">
          <div className="text-[7px] text-surface-500">WF: IS={item.wf_result.avg_is_return.toFixed(1)}% | OOS={item.wf_result.avg_oos_return.toFixed(1)}% | {item.wf_result.windows_tested} پنجره</div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function CascadePage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [allDb, setAllDb] = useState<SymbolOption[]>([]);
  const [loadingDb, setLoadingDb] = useState(false);
  const [selStrats, setSelStrats] = useState<string[]>(STRATEGIES.map(s => s.id));
  const [selFeatures, setSelFeatures] = useState<string[]>(["technical", "momentum", "volume", "microstructure"]);
  const [popSize, setPopSize] = useState(50);
  const [gens, setGens] = useState(12);
  const [mutRate, setMutRate] = useState(15);
  const [crossRate, setCrossRate] = useState(70);
  const [f1, setF1] = useState(5);
  const [f2, setF2] = useState(25);
  const [f3, setF3] = useState(0.5);
  const [f4, setF4] = useState(40);
  const [f5, setF5] = useState(5);
  const [f6, setF6] = useState(1.2);
  const [useWF, setUseWF] = useState(true);
  const [wfWin, setWfWin] = useState(5);
  const [wfTrain, setWfTrain] = useState(70);
  const [stopLoss, setStopLoss] = useState(8);
  const [trailStop] = useState(true);
  const [trailPct, setTrailPct] = useState(5);
  const [startDate, setStartDate] = useState("2021-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState(1000000000);
  const [tab, setTab] = useState<"sym" | "feat" | "ga" | "filter" | "wf">("sym");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [results, setResults] = useState<CascadeResponse | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoadingDb(true);
      try {
        const r = await apiGet<{ success: boolean; data: SymbolOption[] }>("/backtests/data/symbols");
        if (r?.data && Array.isArray(r.data)) setAllDb(r.data);
      } catch {}
      setLoadingDb(false);
    };
    load();
  }, []);

  useEffect(() => {
    if (!running) return;
    const iv = setInterval(async () => {
      try {
        const r = await apiGet<{ success: boolean; data: ProgressData }>("/backtests/cascade/status");
        if (r?.data) {
          setProgress(r.data);
          if (!r.data.running && r.data.completed > 0) {
            setRunning(false);
            const res = await apiGet<{ success: boolean; data: CascadeResponse }>("/backtests/cascade/results");
            if (res?.data) setResults(res.data);
          }
        }
      } catch {}
    }, 2000);
    return () => clearInterval(iv);
  }, [running]);

  const addSym = useCallback((s: string) => {
    if (s.includes(",")) {
      const newSyms = s.split(",").filter(x => x.trim() && !symbols.includes(x.trim())).map(x => x.trim());
      if (newSyms.length) setSymbols([...symbols, ...newSyms]);
    } else if (s && !symbols.includes(s)) setSymbols([...symbols, s]);
  }, [symbols]);
  const rmSym = useCallback((s: string) => setSymbols(symbols.filter(x => x !== s)), [symbols]);
  const toggleStrat = useCallback((id: string) => setSelStrats(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]), []);
  const toggleFeat = useCallback((id: string) => setSelFeatures(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]), []);

  const totalCombos = useMemo(() => {
    let t = 0;
    for (const sid of selStrats) {
      const st = STRATEGIES.find(s => s.id === sid);
      if (st) t += st.combos;
    }
    t *= symbols.length || 1;
    t += selStrats.length * popSize * gens * (symbols.length || 1);
    return t;
  }, [selStrats, symbols, popSize, gens]);

  const handleRun = useCallback(async () => {
    if (!symbols.length || !selStrats.length) return;
    setRunning(true);
    setResults(null);
    try {
      await apiPost("/backtests/cascade/run", {
        symbols, strategies: selStrats, features: selFeatures,
        start_date: startDate, end_date: endDate, capital,
        filters: { stage1_min_return: f1, stage2_max_drawdown: f2, stage3_min_sharpe: f3, stage4_min_win_rate: f4, stage5_min_trades: f5, stage6_min_profit_factor: f6 },
        use_genetic: true, genetic_generations: gens, population_size: popSize,
        mutation_rate: mutRate / 100, crossover_rate: crossRate / 100,
        use_walk_forward: useWF, walk_forward_windows: wfWin, walk_forward_train_ratio: wfTrain / 100,
        stop_loss: stopLoss, trailing_stop: trailStop, trailing_stop_pct: trailPct,
      });
    } catch { setRunning(false); }
  }, [symbols, selStrats, selFeatures, startDate, endDate, capital, f1, f2, f3, f4, f5, f6, gens, popSize, mutRate, crossRate, useWF, wfWin, wfTrain, stopLoss, trailStop, trailPct]);

  const handleSaveAll = useCallback(async () => {
    if (!results?.strategies?.length) return;
    setSaving(true);
    try {
      const r = await apiPost<{ success: boolean; data: { saved: number } }>("/backtests/generate/save", { strategies: results.strategies });
      if (r?.success) setSavedCount(r.data.saved);
    } catch {}
    setSaving(false);
  }, [results]);

  const handleSaveOne = useCallback(async (s: StrategyResult) => {
    try {
      await apiPost("/backtests/generate/save", { strategies: [s] });
      setSavedCount(c => c + 1);
    } catch {}
  }, []);

  const tabs = [
    { id: "sym" as const, icon: "💹", label: "نمادها", cnt: symbols.length },
    { id: "feat" as const, icon: "🔬", label: "ویژگی‌ها", cnt: selFeatures.length },
    { id: "ga" as const, icon: "🧬", label: "ژنتیک" },
    { id: "filter" as const, icon: "🎯", label: "فیلتر" },
    { id: "wf" as const, icon: "🔍", label: "WF" },
  ];

  return (
    <AppLayout title="موتور کاسکاد" subtitle="فیلتر آبشاری + ژنتیک + Walk-Forward + ذخیره">
      <div className="max-w-7xl mx-auto space-y-3">
        {/* Stats */}
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
          {[
            { v: symbols.length, l: "نماد", c: "text-primary-300" },
            { v: selStrats.length, l: "استراتژی", c: "text-accent-amber" },
            { v: selFeatures.length, l: "ویژگی", c: "text-accent-emerald" },
            { v: totalCombos.toLocaleString("en"), l: "ترکیب", c: "text-surface-100" },
            { v: results?.strategies?.length || 0, l: "نتیجه", c: "text-surface-200" },
            { v: savedCount, l: "ذخیره", c: "text-accent-emerald" },
          ].map((s, i) => (
            <div key={i} className="glass-card p-2 text-center">
              <div className={`text-base font-bold font-mono ${s.c}`}>{s.v}</div>
              <div className="text-[7px] text-surface-500">{s.l}</div>
            </div>
          ))}
        </div>

        {/* Tabs + Run */}
        <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1 items-center">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-1 px-2 py-1.5 rounded text-[10px] font-bold transition-colors whitespace-nowrap ${tab === t.id ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"}`}>
              {t.icon} {t.label}
              {t.cnt != null && t.cnt > 0 && <span className={`text-[7px] px-1 rounded ${tab === t.id ? "bg-white/20" : "bg-surface-700"}`}>{t.cnt}</span>}
            </button>
          ))}
          <div className="flex-1" />
          <button onClick={handleRun} disabled={running || !symbols.length || !selStrats.length}
            className={`px-4 py-1.5 rounded text-[10px] font-bold transition-colors ${running || !symbols.length || !selStrats.length ? "bg-surface-700 text-surface-400 cursor-not-allowed" : "bg-primary-600 hover:bg-primary-500 text-white"}`}>
            {running ? "⏳" : "🚀"} {running ? "در حال اجرا..." : "شروع"}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Left: Settings */}
          <div className="lg:col-span-1 space-y-3">
            {tab === "sym" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">💹 انتخاب نمادها</h3>
                <SymbolPicker symbols={symbols} onAdd={addSym} onRemove={rmSym} allDb={allDb} loadingDb={loadingDb} />
                <div className="mt-2 pt-2 border-t border-surface-700/50 space-y-1.5">
                  <div className="grid grid-cols-2 gap-1.5">
                    <div><label className="block text-[8px] text-surface-500">شروع</label>
                      <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-1.5 py-1 text-[9px] text-surface-100 font-mono outline-none" /></div>
                    <div><label className="block text-[8px] text-surface-500">پایان</label>
                      <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-1.5 py-1 text-[9px] text-surface-100 font-mono outline-none" /></div>
                  </div>
                  <div><label className="block text-[8px] text-surface-500">سرمایه</label>
                    <input type="number" value={capital} onChange={e => setCapital(parseInt(e.target.value) || 1e9)} className="w-full bg-surface-800 border border-surface-700 rounded px-1.5 py-1 text-[9px] text-surface-100 font-mono outline-none" /></div>
                </div>
              </div>
            )}

            {tab === "feat" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">🔬 ویژگی‌ها</h3>
                <div className="space-y-2">
                  {FEATURES.map(f => (
                    <div key={f.id}>
                      <button onClick={() => toggleFeat(f.id)}
                        className={`w-full text-right p-1.5 rounded border text-[10px] transition-all ${selFeatures.includes(f.id) ? "border-accent-emerald bg-accent-emerald/10 text-accent-emerald" : "border-surface-700/50 text-surface-500"}`}>
                        <span>{f.icon}</span> <span className="font-bold">{f.label}</span>
                        <span className="text-[8px] mr-1 opacity-60">({f.items.length})</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "ga" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">🧬 ژنتیک</h3>
                <div className="space-y-2">
                  {[{ l: "جمعیت", v: popSize, s: setPopSize, min: 10, max: 200 },
                    { l: "نسل", v: gens, s: setGens, min: 2, max: 50 },
                    { l: "جهش %", v: mutRate, s: setMutRate, min: 5, max: 50 },
                    { l: "تقاطع %", v: crossRate, s: setCrossRate, min: 30, max: 100 }
                  ].map((x, i) => (
                    <div key={i}>
                      <div className="flex justify-between"><label className="text-[8px] text-surface-500">{x.l}</label><span className="text-[8px] font-mono text-primary-300">{x.v}</span></div>
                      <input type="range" min={x.min} max={x.max} step={1} value={x.v} onChange={e => x.s(parseInt(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "filter" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">🎯 فیلتر ۶ مرحله</h3>
                <div className="space-y-2">
                  {[{ l: "۱. حداقل بازده", v: f1, s: setF1, u: "%", mx: 50 },
                    { l: "۲. حداکثر افت", v: f2, s: setF2, u: "%", mx: 50 },
                    { l: "۳. حداقل شارپ", v: f3, s: setF3, u: "", mx: 5 },
                    { l: "۴. حداقل نرخ برد", v: f4, s: setF4, u: "%", mx: 80 },
                    { l: "۵. حداقل معاملات", v: f5, s: setF5, u: "", mx: 30 },
                    { l: "۶. حداقل سود/زیان", v: f6, s: setF6, u: "", mx: 5 },
                  ].map((x, i) => (
                    <div key={i}>
                      <div className="flex justify-between"><label className="text-[8px] text-surface-400">{x.l}</label><span className="text-[8px] font-mono text-primary-300">{x.v}{x.u}</span></div>
                      <input type="range" min={0} max={x.mx} step={x.mx <= 5 ? 0.1 : 1} value={x.v} onChange={e => x.s(parseFloat(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
                    </div>
                  ))}
                </div>
                <div className="mt-2 p-1.5 bg-surface-800/30 rounded text-[7px] text-surface-500">
                  استراتژی‌هایی که هر ۶ فیلتر را رد کنند باقی می‌مانند
                </div>
              </div>
            )}

            {tab === "wf" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">🔍 Walk-Forward</h3>
                <label className="flex items-center gap-1.5 cursor-pointer mb-2">
                  <input type="checkbox" checked={useWF} onChange={e => setUseWF(e.target.checked)} className="w-3 h-3 accent-primary-500" />
                  <span className="text-[10px] text-surface-300">فعال</span>
                </label>
                {useWF && (
                  <div className="space-y-2">
                    <div><label className="block text-[8px] text-surface-500">پنجره‌ها: {wfWin}</label>
                      <input type="range" min={2} max={10} value={wfWin} onChange={e => setWfWin(parseInt(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" /></div>
                    <div><label className="block text-[8px] text-surface-500">آموزش: {wfTrain}%</label>
                      <input type="range" min={50} max={90} value={wfTrain} onChange={e => setWfTrain(parseInt(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" /></div>
                    <div className="p-1.5 bg-surface-800/30 rounded text-[7px] text-surface-500 space-y-0.5">
                      <div>• {wfWin} پنجره滚动 | {wfTrain}% آموزش + {100 - wfTrain}% تست</div>
                      <div>• فقط استراتژی‌های سودآور در هر دو دوره تأیید می‌شوند</div>
                    </div>
                  </div>
                )}
                <div className="mt-2 pt-2 border-t border-surface-700/50">
                  <h4 className="text-[9px] font-bold text-surface-400 mb-1">🛡️ ریسک</h4>
                  <div className="grid grid-cols-2 gap-1.5">
                    <div><label className="block text-[7px] text-surface-500">حد ضرر: {stopLoss}%</label>
                      <input type="range" min={2} max={20} value={stopLoss} onChange={e => setStopLoss(parseInt(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" /></div>
                    <div><label className="block text-[7px] text-surface-500">شناور: {trailPct}%</label>
                      <input type="range" min={1} max={15} value={trailPct} onChange={e => setTrailPct(parseInt(e.target.value))}
                        className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" /></div>
                  </div>
                </div>
              </div>
            )}

            {/* Strategy Selection (always visible) */}
            <div className="glass-card p-3">
              <h3 className="font-bold text-surface-200 text-[11px] mb-2">🎯 استراتژی‌ها ({selStrats.length}/{STRATEGIES.length})</h3>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {STRATEGIES.map(st => {
                  const sel = selStrats.includes(st.id);
                  return (
                    <button key={st.id} onClick={() => toggleStrat(st.id)}
                      className={`w-full text-right p-1.5 rounded border text-[9px] transition-all ${sel ? "border-primary-500 bg-primary-600/10" : "border-surface-700/50 hover:border-surface-500"}`}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1">
                          <div className={`w-2 h-2 rounded-full border ${sel ? "border-primary-500 bg-primary-500" : "border-surface-600"}`} />
                          <span className="font-bold text-surface-200">{st.name}</span>
                        </div>
                        <span className={`text-[7px] px-1 rounded border ${CAT_COLORS[st.cat]}`}>{st.cat}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right: Progress + Results */}
          <div className="lg:col-span-2 space-y-3">
            {running && progress && (
              <div className="glass-card p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] text-surface-300 font-bold">{PHASES[progress.phase || ""] || "..."}</span>
                  <span className="text-[11px] font-mono text-primary-300">{progress.progress_pct}%</span>
                </div>
                <div className="w-full h-1.5 bg-surface-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-primary-600 to-primary-400 rounded-full transition-all duration-300" style={{ width: `${progress.progress_pct}%` }} />
                </div>
                <div className="flex justify-between mt-1 text-[9px] text-surface-500">
                  <span>{progress.completed.toLocaleString("en")} / {progress.total.toLocaleString("en")}</span>
                  <span>{progress.found} یافت شد</span>
                </div>
              </div>
            )}

            {results && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
                  <div className="glass-card p-2 text-center"><div className="text-base font-bold text-surface-100">{results.stats.total_generated.toLocaleString("en")}</div><div className="text-[7px] text-surface-500">تولید</div></div>
                  <div className="glass-card p-2 text-center"><div className="text-base font-bold text-accent-emerald">{results.stats.passed_6stage}</div><div className="text-[7px] text-surface-500">فیلتر</div></div>
                  <div className="glass-card p-2 text-center"><div className="text-base font-bold text-primary-300">{results.stats.passed_walk_forward}</div><div className="text-[7px] text-surface-500">تأیید WF</div></div>
                  <div className="glass-card p-2 text-center"><div className="text-base font-bold text-surface-200">{results.strategies.length}</div><div className="text-[7px] text-surface-500">نهایی</div></div>
                  <div className="glass-card p-2 text-center">
                    <button onClick={handleSaveAll} disabled={saving} className="text-[10px] font-bold text-primary-300 hover:text-primary-200">
                      {saving ? "..." : "💾 ذخیره همه (" + results.strategies.length + ")"}
                    </button>
                  </div>
                </div>

                {results.strategies.length > 0 ? (
                  <div className="space-y-1.5">
                    <h3 className="text-[11px] font-bold text-surface-200">🏆 نتایج ({results.strategies.length})</h3>
                    {results.strategies.map((item, i) => (
                      <ResultCard key={`${item.strategy}-${item.symbol}-${i}`} item={item} rank={i + 1} onSave={() => handleSaveOne(item)} />
                    ))}
                  </div>
                ) : (
                  <div className="glass-card p-8 text-center text-surface-500">
                    <p className="text-3xl mb-2">🔍</p>
                    <p className="text-[11px]">هیچ استراتژی‌ای از فیلترها عبور نکرد</p>
                  </div>
                )}
              </>
            )}

            {!running && !results && (
              <div className="glass-card p-8 text-center text-surface-500">
                <p className="text-4xl mb-3">🌊</p>
                <p className="text-[11px] font-bold text-surface-300 mb-1">موتور کاسکاد فیلترینگ</p>
                <p className="text-[9px] max-w-md mx-auto leading-relaxed">
                  فیلترینگ آبشاری: از کل بازار تا نمادهای برتر. ژنتیک پارامترها را بهینه می‌کند،
                  فیلتر ۶ مرحله ضعیف‌ها را حذف می‌کند، و Walk-Forward overfitting را شناسایی می‌کند.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 text-[9px]">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">← بک‌تست</Link>
          <Link href="/backtest/engine" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">موتور استراتژی</Link>
          <Link href="/backtest/generate" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">تولید خودکار</Link>
        </div>
      </div>
    </AppLayout>
  );
}
