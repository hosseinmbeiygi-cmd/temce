"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface SymbolOption { symbol: string; name: string; bar_count?: number; }

interface RegimeData {
  initialized: boolean;
  current_regime?: number;
  regime_label?: string;
  allocation?: { stock: number; fixed_income: number; gold: number };
  history?: number[];
}

interface CoEvolveResult {
  generations: number;
  best_alpha: Record<string, number>;
  best_omega: Record<string, number>;
  best_fitness: number;
  history: {
    alpha_best_fitness: number;
    omega_best_fitness: number;
    alpha_avg_fitness: number;
    omega_avg_fitness: number;
  }[];
}

interface Decision {
  action: number;
  action_label: string;
  regime: number;
  regime_label: string;
  allocation: { stock: number; fixed_income: number; gold: number };
  risk_check: string;
}

// ── Symbol Search ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

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
    queryKey: ["adapt-sym", q],
    queryFn: async (): Promise<SymbolOption[]> => {
      if (!q.trim()) return [];
      try { const r = await apiGet<{ success: boolean; data: { items: SymbolOption[] } }>(`/instruments/search?q=${encodeURIComponent(q)}&page_size=20`); return r?.data?.items || []; } catch { return []; }
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
          placeholder="جستجوی نماد..." />
        {open && q.trim().length > 0 && (
          <div className="absolute top-full mt-1 left-0 right-0 z-50 bg-surface-800 border border-surface-700 rounded-lg shadow-2xl max-h-48 overflow-y-auto">
            {isLoading && <div className="px-3 py-2 text-[10px] text-surface-500">جستجو...</div>}
            {!isLoading && res.length === 0 && <div className="px-3 py-2 text-[10px] text-surface-500">نتیجه‌ای یافت نشد</div>}
            {!isLoading && res.map(it => (
              <button key={it.symbol} onClick={() => { onAdd(it.symbol); setQ(""); setOpen(false); }}
                className="w-full text-right px-3 py-1.5 text-xs text-surface-200 hover:bg-surface-700 flex items-center justify-between">
                <span className="font-mono font-bold">{it.symbol}</span>
                <span className="text-[10px] text-surface-500 truncate ml-2 max-w-[120px]">{it.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex gap-1" suppressHydrationWarning>
        <button onClick={() => { const s = allDb.map(x => x.symbol).join(","); onAdd(s); }} disabled={loadingDb || allDb.length === 0}
          className="text-[9px] px-1.5 py-0.5 bg-primary-600/20 text-primary-300 rounded font-bold">
          {loadingDb ? "..." : "همه (" + allDb.length + ")"}
        </button>
        <button onClick={() => symbols.forEach(s => onRemove(s))} disabled={symbols.length === 0}
          className="text-[9px] px-1.5 py-0.5 bg-accent-rose/20 text-accent-rose rounded">پاک کردن</button>
      </div>
    </div>
  );
}

// ── Regime Visualization ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

function RegimeDisplay({ regime }: { regime: RegimeData }) {
  const regimeColors = ["text-accent-rose", "text-accent-amber", "text-accent-emerald"];
  const regimeLabels = ["نزولی", "نوسانی", "صعودی"];
  const regimeIcons = ["📉", "📊", "📈"];
  const allocColors = { stock: "bg-accent-emerald", fixed_income: "bg-primary-500", gold: "bg-accent-amber" };
  const allocLabels = { stock: "سهام", fixed_income: "درآمد ثابت", gold: "طلا" };

  return (
    <div className="glass-card p-4">
      <h3 className="font-bold text-surface-200 text-xs mb-3">🔍 وضعیت فعلی بازار</h3>
      {!regime.initialized ? (
        <p className="text-[10px] text-surface-500">سیستم هنوز راه‌اندازی نشده</p>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-3 bg-surface-800/30 rounded-lg">
            <span className="text-3xl">{regimeIcons[regime.current_regime ?? 1]}</span>
            <div>
              <div className={`text-lg font-bold ${regimeColors[regime.current_regime ?? 1]}`}>
                {regimeLabels[regime.current_regime ?? 1]}
              </div>
              <div className="text-[9px] text-surface-500">رژیم فعلی بازار</div>
            </div>
          </div>
          {regime.allocation && (
            <div>
              <div className="text-[9px] text-surface-500 mb-1">تخصیص پیشنهادی</div>
              <div className="flex gap-1 h-6 rounded overflow-hidden">
                {Object.entries(regime.allocation).map(([k, v]) => (
                  <div key={k} className={`${allocColors[k as keyof typeof allocColors]} flex items-center justify-center text-[8px] text-white font-bold`}
                    style={{ width: `${v * 100}%` }}>
                    {v > 0.1 && `${allocLabels[k as keyof typeof allocLabels]} ${(v * 100).toFixed(0)}%`}
                  </div>
                ))}
              </div>
            </div>
          )}
          {regime.history && regime.history.length > 0 && (
            <div>
              <div className="text-[9px] text-surface-500 mb-1">تاریخچه رژیم (۵۰ روز اخیر)</div>
              <div className="flex gap-px h-4">
                {regime.history.map((r, i) => (
                  <div key={i} className={`flex-1 rounded-sm ${r === 0 ? "bg-accent-rose" : r === 1 ? "bg-accent-amber" : "bg-accent-emerald"}`}
                    title={regimeLabels[r]} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Decision Display ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function DecisionDisplay({ decision }: { decision: Decision }) {
  const actionColors = ["text-accent-rose", "text-surface-400", "text-accent-emerald"];
  const actionIcons = ["🔴", "⚪", "🟢"];
  return (
    <div className="glass-card p-4">
      <h3 className="font-bold text-surface-200 text-xs mb-3">🤖 تصمیم عامل</h3>
      <div className="grid grid-cols-2 gap-2">
        <div className="p-3 bg-surface-800/30 rounded-lg text-center">
          <span className="text-2xl">{actionIcons[decision.action]}</span>
          <div className={`text-sm font-bold mt-1 ${actionColors[decision.action]}`}>{decision.action_label}</div>
          <div className="text-[8px] text-surface-500">اکشن</div>
        </div>
        <div className="p-3 bg-surface-800/30 rounded-lg text-center">
          <span className={`text-lg font-bold ${decision.risk_check === "SAFE" ? "text-accent-emerald" : "text-accent-amber"}`}>
            {decision.risk_check === "SAFE" ? "✓ ایمن" : "⚠ احتیاط"}
          </span>
          <div className="text-[8px] text-surface-500 mt-1">وضعیت ریسک (CVaR)</div>
        </div>
      </div>
    </div>
  );
}

// ── Co-Evolution Chart ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

function CoEvolutionChart({ data }: { data: CoEvolveResult }) {
  if (!data.history?.length) return null;
  const maxFit = Math.max(...data.history.map(h => Math.max(h.alpha_best_fitness, h.omega_best_fitness)), 0.1);
  return (
    <div className="glass-card p-4">
      <h3 className="font-bold text-surface-200 text-xs mb-3">🧬 نتیجه تکامل همزیست</h3>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="p-2 bg-surface-800/30 rounded">
          <div className="text-[9px] text-surface-500">بهترین آلفا (ورود)</div>
          <div className="text-[10px] font-mono text-accent-emerald">fitness: {data.best_fitness.toFixed(3)}</div>
          <div className="space-y-0.5 mt-1">
            {Object.entries(data.best_alpha).slice(0, 4).map(([k, v]) => (
              <div key={k} className="text-[8px] text-surface-400">{k}: {typeof v === "number" ? v.toFixed(3) : String(v)}</div>
            ))}
          </div>
        </div>
        <div className="p-2 bg-surface-800/30 rounded">
          <div className="text-[9px] text-surface-500">بهترین امگا (ریسک)</div>
          <div className="text-[10px] font-mono text-accent-amber">fitness: {data.best_fitness.toFixed(3)}</div>
          <div className="space-y-0.5 mt-1">
            {Object.entries(data.best_omega).slice(0, 4).map(([k, v]) => (
              <div key={k} className="text-[8px] text-surface-400">{k}: {typeof v === "number" ? v.toFixed(3) : String(v)}</div>
            ))}
          </div>
        </div>
      </div>
      <div className="text-[9px] text-surface-500 mb-1">منحنی تکامل ({data.generations} نسل)</div>
      <div className="flex items-end gap-px h-16">
        {data.history.map((h, i) => (
          <div key={i} className="flex-1 flex flex-col justify-end gap-px">
            <div className="bg-accent-emerald/60 rounded-t" style={{ height: `${(h.alpha_best_fitness / maxFit) * 60}px` }} title={`Alpha: ${h.alpha_best_fitness.toFixed(3)}`} />
            <div className="bg-accent-amber/60 rounded-b" style={{ height: `${(h.omega_best_fitness / maxFit) * 60}px` }} title={`Omega: ${h.omega_best_fitness.toFixed(3)}`} />
          </div>
        ))}
      </div>
      <div className="flex gap-3 mt-1 text-[8px]">
        <span className="text-accent-emerald">● آلفا (ورود)</span>
        <span className="text-accent-amber">● امگا (ریسک)</span>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function AdaptivePage() {
  const [symbols, setSymbols] = useState<string[]>(["فولاد"]);
  const [allDb, setAllDb] = useState<SymbolOption[]>([]);
  const [loadingDb, setLoadingDb] = useState(false);
  const [startDate, setStartDate] = useState("2021-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [initLoading, setInitLoading] = useState(false);
  const [decideLoading, setDecideLoading] = useState(false);
  const [coevolveLoading, setCoevolveLoading] = useState(false);
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [coevolve, setCoevolve] = useState<CoEvolveResult | null>(null);
  const [tab, setTab] = useState<"setup" | "regime" | "decision" | "coevolve">("setup");

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
    // Load regime if already initialized
    apiGet<{ success: boolean; data: RegimeData }>("/backtests/adaptive/regime").then(r => {
      if (r?.data?.initialized) setRegime(r.data);
    }).catch(() => {});
  }, []);

  const addSym = useCallback((s: string) => {
    if (s.includes(",")) {
      const n = s.split(",").filter(x => x.trim() && !symbols.includes(x.trim())).map(x => x.trim());
      if (n.length) setSymbols([...symbols, ...n]);
    } else if (s && !symbols.includes(s)) setSymbols([...symbols, s]);
  }, [symbols]);
  const rmSym = useCallback((s: string) => setSymbols(symbols.filter(x => x !== s)), [symbols]);

  const handleInit = useCallback(async () => {
    if (!symbols.length) return;
    setInitLoading(true);
    try {
      const r = await apiPost<{ success: boolean; data: { data_points: number } }>("/backtests/adaptive/init", {
        symbols, start_date: startDate, end_date: endDate, capital: 1e9,
      });
      if (r?.success) {
        const regimeR = await apiGet<{ success: boolean; data: RegimeData }>("/backtests/adaptive/regime");
        if (regimeR?.data) setRegime(regimeR.data);
        setTab("regime");
      }
    } catch {}
    setInitLoading(false);
  }, [symbols, startDate, endDate]);

  const handleDecide = useCallback(async () => {
    setDecideLoading(true);
    try {
      const r = await apiPost<{ success: boolean; data: Decision }>("/backtests/adaptive/decide", {
        market_data: { return_1d: 0.01, return_5d: 0.03, return_20d: 0.05, volatility_20d: 0.02, rsi_14: 55, volume_ratio: 1.3, buy_power_ratio: 1.5, sector_strength: 0.7, market_regime: regime?.current_regime ?? 1, position_pct: 0.3 },
        portfolio_returns: [0.01, -0.005, 0.008, -0.002, 0.015, -0.001, 0.003],
      });
      if (r?.data) { setDecision(r.data); setTab("decision"); }
    } catch {}
    setDecideLoading(false);
  }, [regime]);

  const handleCoevolve = useCallback(async () => {
    if (!symbols.length) return;
    setCoevolveLoading(true);
    try {
      const r = await apiPost<{ success: boolean; data: CoEvolveResult }>("/backtests/adaptive/coevolve", {
        symbols, start_date: startDate, end_date: endDate, capital: 1e9,
      });
      if (r?.data) { setCoevolve(r.data); setTab("coevolve"); }
    } catch {}
    setCoevolveLoading(false);
  }, [symbols, startDate, endDate]);

  const tabs = [
    { id: "setup" as const, icon: "⚙️", label: "تنظیمات" },
    { id: "regime" as const, icon: "🔍", label: "رژیم بازار" },
    { id: "decision" as const, icon: "🤖", label: "تصمیم‌گیری" },
    { id: "coevolve" as const, icon: "🧬", label: "تکامل همزیست" },
  ];

  return (
    <AppLayout title="سیستم معاملاتی انطباق‌پذیر" subtitle="Safe RL + HMM + Co-evolutionary Optimization">
      <div className="max-w-6xl mx-auto space-y-3">
        {/* Tabs */}
        <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1 items-center">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-bold transition-colors ${tab === t.id ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"}`}>
              {t.icon} {t.label}
            </button>
          ))}
          <div className="flex-1" />
          <div className="flex gap-1">
            <button onClick={handleInit} disabled={initLoading || !symbols.length}
              className={`px-3 py-1.5 rounded text-[10px] font-bold ${initLoading ? "bg-surface-700 text-surface-400" : "bg-primary-600 hover:bg-primary-500 text-white"}`}>
              {initLoading ? "⏳" : "🔧"} راه‌اندازی
            </button>
            <button onClick={handleDecide} disabled={decideLoading}
              className={`px-3 py-1.5 rounded text-[10px] font-bold ${decideLoading ? "bg-surface-700 text-surface-400" : "bg-accent-emerald/20 text-accent-emerald hover:bg-accent-emerald/30"}`}>
              {decideLoading ? "⏳" : "🤖"} تصمیم
            </button>
            <button onClick={handleCoevolve} disabled={coevolveLoading || !symbols.length}
              className={`px-3 py-1.5 rounded text-[10px] font-bold ${coevolveLoading ? "bg-surface-700 text-surface-400" : "bg-accent-amber/20 text-accent-amber hover:bg-accent-amber/30"}`}>
              {coevolveLoading ? "⏳" : "🧬"} تکامل
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Left: Setup */}
          <div className="lg:col-span-1 space-y-3">
            <div className="glass-card p-3">
              <h3 className="font-bold text-surface-200 text-[11px] mb-2">⚙️ تنظیمات</h3>
              <SymbolPicker symbols={symbols} onAdd={addSym} onRemove={rmSym} allDb={allDb} loadingDb={loadingDb} />
              <div className="mt-2 pt-2 border-t border-surface-700/50 space-y-1.5">
                <div className="grid grid-cols-2 gap-1.5">
                  <div><label className="block text-[8px] text-surface-500">شروع</label>
                    <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-1.5 py-1 text-[9px] text-surface-100 font-mono outline-none" /></div>
                  <div><label className="block text-[8px] text-surface-500">پایان</label>
                    <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded px-1.5 py-1 text-[9px] text-surface-100 font-mono outline-none" /></div>
                </div>
              </div>
            </div>

            {/* Module Info */}
            <div className="glass-card p-3 space-y-2">
              <h3 className="font-bold text-surface-200 text-[11px]">📚 ماژول‌ها</h3>
              {[
                { icon: "🛡️", name: "Safe RL", desc: "عامل یادگیری تقویتی با قید ایمنی CVaR", color: "text-accent-emerald" },
                { icon: "🔍", name: "HMM Regime", desc: "تشخیص رژیم بازار (صعودی/نزولی/نوسانی)", color: "text-accent-amber" },
                { icon: "🧬", name: "Co-Evolution", desc: "تکامل همزیست آلفا و امگا", color: "text-primary-300" },
              ].map((m, i) => (
                <div key={i} className="flex items-center gap-2 p-2 bg-surface-800/30 rounded">
                  <span className="text-lg">{m.icon}</span>
                  <div>
                    <div className={`text-[10px] font-bold ${m.color}`}>{m.name}</div>
                    <div className="text-[8px] text-surface-500">{m.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-2 space-y-3">
            {tab === "setup" && (
              <div className="glass-card p-8 text-center text-surface-500">
                <p className="text-5xl mb-4">🧠</p>
                <p className="text-sm font-bold text-surface-300 mb-2">سیستم معاملاتی انطباق‌پذیر</p>
                <p className="text-[10px] max-w-lg mx-auto leading-relaxed">
                  ترکیب یادگیری تقویتی ایمن، تشخیص رژیم بازار با مارکوف پنهان، و بهینه‌سازی تکاملی همزیست.
                  ابتدا نمادها را انتخاب و سیستم را راه‌اندازی کنید.
                </p>
              </div>
            )}

            {tab === "regime" && regime && <RegimeDisplay regime={regime} />}
            {tab === "regime" && !regime && (
              <div className="glass-card p-6 text-center text-surface-500">
                <p className="text-2xl mb-2">🔍</p>
                <p className="text-[10px]">ابتدا سیستم را راه‌اندازی کنید</p>
              </div>
            )}

            {tab === "decision" && decision && <DecisionDisplay decision={decision} />}
            {tab === "decision" && !decision && (
              <div className="glass-card p-6 text-center text-surface-500">
                <p className="text-2xl mb-2">🤖</p>
                <p className="text-[10px]">ابتدا سیستم را راه‌اندازی و سپس تصمیم بگیرید</p>
              </div>
            )}

            {tab === "coevolve" && coevolve && <CoEvolutionChart data={coevolve} />}
            {tab === "coevolve" && !coevolve && (
              <div className="glass-card p-6 text-center text-surface-500">
                <p className="text-2xl mb-2">🧬</p>
                <p className="text-[10px]">برای شروع تکامل همزیست دکمه «تکامل» را بزنید</p>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 text-[9px]">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">← بک‌تست</Link>
          <Link href="/backtest/engine" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">موتور استراتژی</Link>
          <Link href="/backtest/cascade" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">کاسکاد</Link>
        </div>
      </div>
    </AppLayout>
  );
}
