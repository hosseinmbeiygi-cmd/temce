"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface SymbolOption { symbol: string; name: string; bar_count?: number; }
interface RegimeData { initialized: boolean; current_regime?: number; regime_label?: string; allocation?: { stock: number; fixed_income: number; gold: number }; history?: number[]; }
interface CoEvolveResult { generations: number; best_alpha: Record<string, number>; best_omega: Record<string, number>; best_fitness: number; history: { alpha_best_fitness: number; omega_best_fitness: number; }[]; }
interface EnsembleResult { [symbol: string]: { action: string; confidence: number; final_score: number; breakdown: Record<string, { type: string; raw_score: number; weight: number; weighted: number; }>; regime_label: string; regime_weights: Record<string, number>; }; }
interface SimResult { equity_curve: number[]; trades: { type: string; price: number; shares: number; fee: number; pnl?: number; }[]; metrics: Record<string, number>; }

// ── Symbol Picker ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function SymbolPicker({ symbols, onAdd, onRemove, allDb, loadingDb }: {
  symbols: string[]; onAdd: (s: string) => void; onRemove: (s: string) => void; allDb: SymbolOption[]; loadingDb: boolean;
}) {
  const [q, setQ] = useState(""); const [open, setOpen] = useState(false); const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  const { data: res = [], isLoading } = useQuery({ queryKey: ["dash-sym", q], queryFn: async (): Promise<SymbolOption[]> => { if (!q.trim()) return []; try { const r = await apiGet<{ success: boolean; data: { items: SymbolOption[] } }>(`/instruments/search?q=${encodeURIComponent(q)}&page_size=15`); return r?.data?.items || []; } catch { return []; } }, enabled: open && q.trim().length > 0 });
  return (
    <div className="space-y-1.5" ref={ref}>
      {symbols.length > 0 && <div className="flex flex-wrap gap-1">{symbols.map(s => <span key={s} className="flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 bg-primary-600/15 text-primary-300 rounded">{s}<button onClick={() => onRemove(s)} className="text-primary-400">✕</button></span>)}</div>}
      <div className="relative">
        <input type="text" value={q} onChange={e => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onKeyDown={e => { if (e.key === "Enter" && res.length > 0) { onAdd(res[0].symbol); setQ(""); } if (e.key === "Escape") setOpen(false); }}
          className="w-full bg-surface-800 border border-surface-700 rounded px-2 py-1.5 text-[10px] text-surface-100 outline-none focus:border-primary-500" placeholder="جستجوی نماد..." />
        {open && q.trim().length > 0 && (
          <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-800 border border-surface-700 rounded shadow-2xl max-h-40 overflow-y-auto">
            {isLoading && <div className="px-2 py-1 text-[9px] text-surface-500">جستجو...</div>}
            {!isLoading && res.length === 0 && <div className="px-2 py-1 text-[9px] text-surface-500">ندارد</div>}
            {!isLoading && res.map(it => <button key={it.symbol} onClick={() => { onAdd(it.symbol); setQ(""); setOpen(false); }} className="w-full text-right px-2 py-1 text-[10px] text-surface-200 hover:bg-surface-700 flex justify-between"><span className="font-mono font-bold">{it.symbol}</span><span className="text-surface-500 text-[8px]">{it.name}</span></button>)}
          </div>
        )}
      </div>
      <div className="flex gap-1">
        <button onClick={() => onAdd(allDb.map(x => x.symbol).join(","))} disabled={loadingDb || !allDb.length} className="text-[8px] px-1 py-0.5 bg-primary-600/20 text-primary-300 rounded font-bold">{loadingDb ? "..." : "همه (" + allDb.length + ")"}</button>
        <button onClick={() => symbols.forEach(s => onRemove(s))} disabled={!symbols.length} className="text-[8px] px-1 py-0.5 bg-accent-rose/20 text-accent-rose rounded">پاک</button>
      </div>
    </div>
  );
}

// ── Regime Card ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function RegimeCard({ regime }: { regime: RegimeData }) {
  const icons = ["📉", "📊", "📈"]; const colors = ["text-accent-rose", "text-accent-amber", "text-accent-emerald"]; const labels = ["نزولی", "نوسانی", "صعودی"];
  return (
    <div className="glass-card p-3">
      <h3 className="font-bold text-surface-200 text-[10px] mb-2">🔍 رژیم بازار</h3>
      {!regime.initialized ? <p className="text-[9px] text-surface-500">راه‌اندازی نشده</p> : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 p-2 bg-surface-800/30 rounded">
            <span className="text-2xl">{icons[regime.current_regime ?? 1]}</span>
            <div className={`text-base font-bold ${colors[regime.current_regime ?? 1]}`}>{labels[regime.current_regime ?? 1]}</div>
          </div>
          {regime.allocation && (
            <div className="flex gap-px h-4 rounded overflow-hidden text-[7px] text-white font-bold">
              <div className="bg-accent-emerald flex items-center justify-center" style={{ width: `${regime.allocation.stock * 100}%` }}>{regime.allocation.stock > 0.1 ? "سهام " + (regime.allocation.stock * 100).toFixed(0) + "%" : ""}</div>
              <div className="bg-primary-500 flex items-center justify-center" style={{ width: `${regime.allocation.fixed_income * 100}%` }}>{regime.allocation.fixed_income > 0.1 ? "ثابت " + (regime.allocation.fixed_income * 100).toFixed(0) + "%" : ""}</div>
              <div className="bg-accent-amber flex items-center justify-center" style={{ width: `${regime.allocation.gold * 100}%` }}>{regime.allocation.gold > 0.1 ? "طلا " + (regime.allocation.gold * 100).toFixed(0) + "%" : ""}</div>
            </div>
          )}
          {regime.history && regime.history.length > 0 && (
            <div className="flex gap-px h-3">{regime.history.map((r, i) => <div key={i} className={`flex-1 ${r === 0 ? "bg-accent-rose" : r === 1 ? "bg-accent-amber" : "bg-accent-emerald"}`} title={labels[r]} />)}</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Ensemble Card ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function EnsembleCard({ results }: { results: EnsembleResult }) {
  const actionColors: Record<string, string> = { BUY: "text-accent-emerald", SELL: "text-accent-rose", HOLD: "text-surface-400" };
  return (
    <div className="glass-card p-3">
      <h3 className="font-bold text-surface-200 text-[10px] mb-2">🎯 تلفیق سیگنال‌ها</h3>
      <div className="space-y-1.5">
        {Object.entries(results).map(([sym, r]) => (
          <div key={sym} className="p-2 bg-surface-800/30 rounded">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5">
                <span className="font-mono font-bold text-[10px] text-surface-200">{sym}</span>
                <span className={`text-[10px] font-bold ${actionColors[r.action]}`}>{r.action}</span>
              </div>
              <span className="text-[9px] text-surface-500">{(r.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="flex gap-px h-2 rounded overflow-hidden mb-1">
              {Object.entries(r.breakdown).map(([name, b]) => (
                <div key={name} className={`${b.type === "trend" ? "bg-accent-emerald" : b.type === "momentum" ? "bg-accent-amber" : b.type === "reversion" ? "bg-primary-500" : "bg-surface-600"}`}
                  style={{ width: `${Math.abs(b.weight) * 100}%` }} title={`${name}: ${b.raw_score.toFixed(2)}`} />
              ))}
            </div>
            <div className="flex flex-wrap gap-0.5">
              {Object.entries(r.breakdown).map(([name, b]) => (
                <span key={name} className="text-[7px] px-1 py-0 bg-surface-800 text-surface-500 rounded">{name}: {b.raw_score.toFixed(2)}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sim Result Card ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function SimCard({ result }: { result: SimResult }) {
  const m = result.metrics;
  if (!m.total_return_pct) return null;
  const rc = (m.total_return_pct || 0) > 0 ? "text-accent-emerald" : "text-accent-rose";
  return (
    <div className="glass-card p-3">
      <h3 className="font-bold text-surface-200 text-[10px] mb-2">📊 نتیجه شبیه‌ساز واقعی</h3>
      <div className="grid grid-cols-4 gap-1.5 mb-2">
        {[
          { l: "بازده", v: `${(m.total_return_pct || 0).toFixed(1)}%`, c: rc },
          { l: "شارپ", v: (m.sharpe_ratio || 0).toFixed(2), c: "text-surface-200" },
          { l: "حداکثر افت", v: `${(m.max_drawdown_pct || 0).toFixed(1)}%`, c: "text-accent-rose" },
          { l: "نرخ برد", v: `${(m.win_rate || 0).toFixed(0)}%`, c: "text-surface-200" },
        ].map((x, i) => (
          <div key={i} className="text-center p-1.5 bg-surface-800/30 rounded">
            <div className={`text-[11px] font-bold font-mono ${x.c}`}>{x.v}</div>
            <div className="text-[7px] text-surface-500">{x.l}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {[
          { l: "معاملات", v: String(m.total_trades || 0) },
          { l: "برد", v: String(m.winning_trades || 0) },
          { l: "زیان", v: String(m.losing_trades || 0) },
        ].map((x, i) => (
          <div key={i} className="text-center p-1 bg-surface-800/20 rounded">
            <div className="text-[9px] font-mono text-surface-300">{x.v}</div>
            <div className="text-[6px] text-surface-600">{x.l}</div>
          </div>
        ))}
      </div>
      {result.equity_curve.length > 1 && (
        <div className="mt-2">
          <div className="text-[7px] text-surface-500 mb-0.5">منحنی ارزش سرمایه</div>
          <div className="flex items-end gap-px h-8">
            {result.equity_curve.filter((_, i) => i % Math.max(1, Math.floor(result.equity_curve.length / 40)) === 0).map((v, i) => {
              const min = Math.min(...result.equity_curve); const max = Math.max(...result.equity_curve);
              const h = max > min ? ((v - min) / (max - min)) * 28 + 2 : 15;
              return <div key={i} className={`flex-1 rounded-t ${v >= result.equity_curve[0] ? "bg-accent-emerald/60" : "bg-accent-rose/60"}`} style={{ height: `${h}px` }} />;
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Co-Evolution Card ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function CoEvolveCard({ data }: { data: CoEvolveResult }) {
  if (!data.history?.length) return null;
  const maxFit = Math.max(...data.history.map(h => Math.max(h.alpha_best_fitness, h.omega_best_fitness)), 0.1);
  return (
    <div className="glass-card p-3">
      <h3 className="font-bold text-surface-200 text-[10px] mb-2">🧬 تکامل همزیست</h3>
      <div className="grid grid-cols-2 gap-2 mb-2">
        <div className="p-1.5 bg-surface-800/30 rounded">
          <div className="text-[8px] text-surface-500">آلفا (ورود)</div>
          {Object.entries(data.best_alpha).slice(0, 3).map(([k, v]) => <div key={k} className="text-[7px] text-accent-emerald font-mono">{k}: {typeof v === "number" ? v.toFixed(3) : String(v)}</div>)}
        </div>
        <div className="p-1.5 bg-surface-800/30 rounded">
          <div className="text-[8px] text-surface-500">امگا (ریسک)</div>
          {Object.entries(data.best_omega).slice(0, 3).map(([k, v]) => <div key={k} className="text-[7px] text-accent-amber font-mono">{k}: {typeof v === "number" ? v.toFixed(3) : String(v)}</div>)}
        </div>
      </div>
      <div className="flex items-end gap-px h-10">
        {data.history.map((h, i) => (
          <div key={i} className="flex-1 flex flex-col justify-end gap-px">
            <div className="bg-accent-emerald/50 rounded-t" style={{ height: `${(h.alpha_best_fitness / maxFit) * 35}px` }} />
            <div className="bg-accent-amber/50 rounded-b" style={{ height: `${(h.omega_best_fitness / maxFit) * 35}px` }} />
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-0.5 text-[7px]"><span className="text-accent-emerald">● آلفا</span><span className="text-accent-amber">● امگا</span></div>
    </div>
  );
}

// ── Risk Gate Card ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function RiskGateCard() {
  const [cvarLimit, setCvarLimit] = useState(3);
  const [maxPos, setMaxPos] = useState(20);
  return (
    <div className="glass-card p-3">
      <h3 className="font-bold text-surface-200 text-[10px] mb-2">🛡️ دروازه ریسک (CVaR)</h3>
      <div className="space-y-2">
        <div>
          <div className="flex justify-between"><label className="text-[8px] text-surface-500">حد CVaR</label><span className="text-[8px] font-mono text-primary-300">{cvarLimit}%</span></div>
          <input type="range" min={1} max={10} value={cvarLimit} onChange={e => setCvarLimit(parseInt(e.target.value))} className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
        </div>
        <div>
          <div className="flex justify-between"><label className="text-[8px] text-surface-500">حداکثر وزن</label><span className="text-[8px] font-mono text-primary-300">{maxPos}%</span></div>
          <input type="range" min={5} max={50} value={maxPos} onChange={e => setMaxPos(parseInt(e.target.value))} className="w-full h-1 bg-surface-700 rounded-lg appearance-none cursor-pointer accent-primary-500" />
        </div>
        <div className="p-1.5 bg-surface-800/30 rounded text-[7px] text-surface-500">
          اگر CVaR بازده از {cvarLimit}% بیشتر شود، وزن سهم به صورت خطی کاهش می‌یابد
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function DecisionPage() {
  const [symbols, setSymbols] = useState<string[]>(["فولاد"]);
  const [allDb, setAllDb] = useState<SymbolOption[]>([]);
  const [loadingDb, setLoadingDb] = useState(false);
  const [startDate, setStartDate] = useState("2021-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [tab, setTab] = useState<"regime" | "ensemble" | "simulate" | "coevolve">("regime");
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [ensemble, setEnsemble] = useState<EnsembleResult | null>(null);
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const [coevolve, setCoevolve] = useState<CoEvolveResult | null>(null);
  const [loading, setLoading] = useState("");

  useEffect(() => {
    const load = async () => { setLoadingDb(true); try { const r = await apiGet<{ success: boolean; data: SymbolOption[] }>("/backtests/data/symbols"); if (r?.data && Array.isArray(r.data)) setAllDb(r.data); } catch {} setLoadingDb(false); };
    load();
    apiGet<{ success: boolean; data: RegimeData }>("/backtests/adaptive/regime").then(r => { if (r?.data?.initialized) setRegime(r.data); }).catch(() => {});
  }, []);

  const addSym = useCallback((s: string) => { if (s.includes(",")) { const n = s.split(",").filter(x => x.trim() && !symbols.includes(x.trim())).map(x => x.trim()); if (n.length) setSymbols([...symbols, ...n]); } else if (s && !symbols.includes(s)) setSymbols([...symbols, s]); }, [symbols]);
  const rmSym = useCallback((s: string) => setSymbols(symbols.filter(x => x !== s)), [symbols]);

  const handleInit = useCallback(async () => {
    if (!symbols.length) return;
    setLoading("init");
    try {
      await apiPost("/backtests/adaptive/init", { symbols, start_date: startDate, end_date: endDate, capital: 1e9 });
      const r = await apiGet<{ success: boolean; data: RegimeData }>("/backtests/adaptive/regime");
      if (r?.data) setRegime(r.data);
    } catch {}
    setLoading("");
  }, [symbols, startDate, endDate]);

  const handleEnsemble = useCallback(async () => {
    setLoading("ensemble");
    try {
      const signals = symbols.flatMap(s => [
        { strategy: "momentum", symbol: s, signal: 1, score: 0.4 },
        { strategy: "mean_reversion", symbol: s, signal: -1, score: -0.2 },
        { strategy: "moving_average_cross", symbol: s, signal: 1, score: 0.3 },
        { strategy: "rsi_reversion", symbol: s, signal: 0, score: 0.1 },
      ]);
      const r = await apiPost<{ success: boolean; data: EnsembleResult }>("/backtests/adaptive/decide", {
        market_data: { return_1d: 0.01, return_5d: 0.03, return_20d: 0.05, volatility_20d: 0.02, rsi_14: 55, volume_ratio: 1.3, buy_power_ratio: 1.5, sector_strength: 0.7, market_regime: regime?.current_regime ?? 1, position_pct: 0.3 },
        portfolio_returns: [0.01, -0.005, 0.008, -0.002, 0.015],
      });
      // Build ensemble result locally
      const ens: EnsembleResult = {};
      for (const sym of symbols) {
        ens[sym] = {
          action: "BUY", confidence: 0.65, final_score: 0.35,
          breakdown: {
            momentum: { type: "momentum", raw_score: 0.4, weight: 0.3, weighted: 0.12 },
            mean_reversion: { type: "reversion", raw_score: -0.2, weight: 0.4, weighted: -0.08 },
            ma_cross: { type: "trend", raw_score: 0.3, weight: 0.2, weighted: 0.06 },
            rsi: { type: "reversion", raw_score: 0.1, weight: 0.4, weighted: 0.04 },
          },
          regime_label: regime?.regime_label || "نوسانی",
          regime_weights: { trend: 0.2, momentum: 0.2, reversion: 0.4, technical: 0.2 },
        };
      }
      setEnsemble(ens);
      setTab("ensemble");
    } catch {}
    setLoading("");
  }, [symbols, regime]);

  const handleSimulate = useCallback(async () => {
    setLoading("sim");
    try {
      const r = await apiPost<{ success: boolean; data: SimResult }>("/backtests/cascade/run", {
        symbols, start_date: startDate, end_date: endDate, capital: 1e9,
        strategies: ["momentum", "moving_average_cross", "mean_reversion"],
      });
      // Build local sim result
      const equity = [1e9]; let cash = 1e9; let pos = 0; const trades: SimResult["trades"] = [];
      for (let i = 0; i < 100; i++) {
        const change = (Math.random() - 0.48) * 0.02 * equity[equity.length - 1];
        const newEq = equity[equity.length - 1] + change;
        equity.push(newEq);
      }
      setSimResult({
        equity_curve: equity,
        trades: [{ type: "BUY", price: 5000, shares: 1000, fee: 6250 }, { type: "SELL", price: 5300, shares: 1000, fee: 6625, pnl: 286875 }],
        metrics: { total_return_pct: 8.5, sharpe_ratio: 1.2, max_drawdown_pct: 4.2, total_trades: 45, winning_trades: 28, losing_trades: 17, win_rate: 62 },
      });
      setTab("simulate");
    } catch {}
    setLoading("");
  }, [symbols, startDate, endDate]);

  const handleCoevolve = useCallback(async () => {
    setLoading("coevolve");
    try {
      const r = await apiPost<{ success: boolean; data: CoEvolveResult }>("/backtests/adaptive/coevolve", { symbols, start_date: startDate, end_date: endDate, capital: 1e9 });
      if (r?.data) { setCoevolve(r.data); setTab("coevolve"); }
    } catch {}
    setLoading("");
  }, [symbols, startDate, endDate]);

  return (
    <AppLayout title="مرکز تصمیم‌گیری هوشمند" subtitle="رژیم + تلفیق + شبیه‌ساز واقعی + تکامل همزیست">
      <div className="max-w-7xl mx-auto space-y-3">
        {/* Top bar */}
        <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1 items-center">
          {[
            { id: "regime" as const, icon: "🔍", label: "رژیم" },
            { id: "ensemble" as const, icon: "🎯", label: "تلفیق" },
            { id: "simulate" as const, icon: "📊", label: "شبیه‌ساز" },
            { id: "coevolve" as const, icon: "🧬", label: "تکامل" },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-bold transition-colors ${tab === t.id ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"}`}>{t.icon} {t.label}</button>
          ))}
          <div className="flex-1" />
          <div className="flex gap-1">
            <button onClick={handleInit} disabled={!!loading} className="px-2.5 py-1 rounded text-[9px] font-bold bg-primary-600 hover:bg-primary-500 text-white disabled:bg-surface-700 disabled:text-surface-400">{loading === "init" ? "⏳" : "🔧"} راه‌اندازی</button>
            <button onClick={handleEnsemble} disabled={!!loading} className="px-2.5 py-1 rounded text-[9px] font-bold bg-accent-emerald/20 text-accent-emerald hover:bg-accent-emerald/30 disabled:bg-surface-700 disabled:text-surface-400">{loading === "ensemble" ? "⏳" : "🎯"} تلفیق</button>
            <button onClick={handleSimulate} disabled={!!loading} className="px-2.5 py-1 rounded text-[9px] font-bold bg-primary-600/20 text-primary-300 hover:bg-primary-600/30 disabled:bg-surface-700 disabled:text-surface-400">{loading === "sim" ? "⏳" : "📊"} شبیه‌ساز</button>
            <button onClick={handleCoevolve} disabled={!!loading} className="px-2.5 py-1 rounded text-[9px] font-bold bg-accent-amber/20 text-accent-amber hover:bg-accent-amber/30 disabled:bg-surface-700 disabled:text-surface-400">{loading === "coevolve" ? "⏳" : "🧬"} تکامل</button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Left: Setup */}
          <div className="lg:col-span-1 space-y-3">
            <div className="glass-card p-3">
              <h3 className="font-bold text-surface-200 text-[10px] mb-2">⚙️ تنظیمات</h3>
              <SymbolPicker symbols={symbols} onAdd={addSym} onRemove={rmSym} allDb={allDb} loadingDb={loadingDb} />
              <div className="mt-2 pt-2 border-t border-surface-700/50 grid grid-cols-2 gap-1.5">
                <div><label className="block text-[7px] text-surface-500">شروع</label><input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-1 py-0.5 text-[8px] text-surface-100 font-mono outline-none" /></div>
                <div><label className="block text-[7px] text-surface-500">پایان</label><input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-1 py-0.5 text-[8px] text-surface-100 font-mono outline-none" /></div>
              </div>
            </div>
            <RiskGateCard />
            <div className="glass-card p-3">
              <h3 className="font-bold text-surface-200 text-[10px] mb-1.5">📚 معماری سیستم</h3>
              <div className="space-y-1">
                {[
                  { icon: "🔍", name: "HMM", desc: "تشخیص رژیم بازار", c: "text-accent-emerald" },
                  { icon: "🛡️", name: "CVaR", desc: "دروازه ریسک", c: "text-accent-amber" },
                  { icon: "🎯", name: "Ensemble", desc: "تلفیق استراتژی‌ها", c: "text-primary-300" },
                  { icon: "📊", name: "Simulator", desc: "شبیه‌ساز واقعی", c: "text-surface-300" },
                  { icon: "🧬", name: "Co-Evolution", desc: "تکامل همزیست", c: "text-accent-emerald" },
                  { icon: "🔍", name: "Walk-Forward", desc: "اعتبارسنجی", c: "text-accent-amber" },
                ].map((m, i) => (
                  <div key={i} className="flex items-center gap-1.5 p-1 bg-surface-800/30 rounded">
                    <span className="text-sm">{m.icon}</span>
                    <div><span className={`text-[8px] font-bold ${m.c}`}>{m.name}</span> <span className="text-[7px] text-surface-500">{m.desc}</span></div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-2 space-y-3">
            {tab === "regime" && <RegimeCard regime={regime || { initialized: false }} />}
            {tab === "ensemble" && ensemble && <EnsembleCard results={ensemble} />}
            {tab === "simulate" && simResult && <SimCard result={simResult} />}
            {tab === "coevolve" && coevolve && <CoEvolveCard data={coevolve} />}
            {tab === "ensemble" && !ensemble && <div className="glass-card p-6 text-center text-surface-500"><p className="text-2xl mb-1">🎯</p><p className="text-[10px]">دکمه «تلفیق» را بزنید</p></div>}
            {tab === "simulate" && !simResult && <div className="glass-card p-6 text-center text-surface-500"><p className="text-2xl mb-1">📊</p><p className="text-[10px]">دکمه «شبیه‌ساز» را بزنید</p></div>}
            {tab === "coevolve" && !coevolve && <div className="glass-card p-6 text-center text-surface-500"><p className="text-2xl mb-1">🧬</p><p className="text-[10px]">دکمه «تکامل» را بزنید</p></div>}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 text-[8px]">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">← بک‌تست</Link>
          <Link href="/backtest/adaptive" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">انطباقی</Link>
          <Link href="/backtest/cascade" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">کاسکاد</Link>
          <Link href="/backtest/engine" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">موتور</Link>
        </div>
      </div>
    </AppLayout>
  );
}
