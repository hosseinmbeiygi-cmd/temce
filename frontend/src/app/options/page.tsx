"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost, extractArray } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StrategyLeg { side: string; type: string; strike?: number; premium?: number; quantity: number; }
interface CostResult { gross_pnl: number; commission: number; net_pnl: number; net_pnl_pct: number; breakeven: number; }
interface SizingResult { max_contracts: number; total_cost: number; pct_of_capital: number; }
interface StrategyInfo { id: string; name: string; name_fa: string; category: string; market: string; risk: string; legs: number; score?: number; }
interface StrategyAnalysis {
  strategy_name: string; strategy_name_fa: string; legs: StrategyLeg[];
  max_profit: number; max_loss: number; break_even: number[];
  initial_cost: number; market_condition: string; risk_level: string;
  description: string; description_fa: string; best_for: string; example: unknown;
  profit_at_expiry: { price: number; profit: number }[];
}
interface OptionContract { symbol: string; name: string; type: string; strike: number; price: number; volume: number; oi: number; days_to_expiry: number; underlying_price: number; bid: number; ask: number; open: number; high: number; low: number; trades: number; }
interface ChainData { calls: OptionContract[]; puts: OptionContract[]; underlying_price: number; analysis?: Record<string, unknown>; total_contracts?: number; }
interface LiveSymbol { symbol: string; contracts: number; volume: number; price: number; }
interface GlossaryItem { fa: string; en: string; desc: string; }
interface MistakeItem { mistake: string; solution: string; }

// ── Helpers ───────────────────────────────────────────────────────────────────

const riskColor = (r: string) => r === "low" ? "text-accent-emerald" : r === "medium" ? "text-accent-amber" : "text-accent-rose";
const riskLabel = (r: string) => ({ low: "کم", medium: "متوسط", high: "زیاد", very_high: "خیلی زیاد" }[r] || r);
const fmt = (n: number) => n?.toLocaleString("fa-IR") ?? "—";

// ── Payoff SVG Diagram ────────────────────────────────────────────────────────

function PayoffDiagram({ analysis, width = 600, height = 300 }: { analysis: StrategyAnalysis; width?: number; height?: number }) {
  if (!analysis?.profit_at_expiry?.length) return null;
  const data = analysis.profit_at_expiry;
  const prices = data.map(d => d.price);
  const profits = data.map(d => d.profit);
  const minP = Math.min(...profits); const maxP = Math.max(...profits);
  const minPrice = Math.min(...prices); const maxPrice = Math.max(...prices);
  const pad = 40; const w = width - pad * 2; const h = height - pad * 2;
  const xS = (p: number) => pad + ((p - minPrice) / (maxPrice - minPrice || 1)) * w;
  const yS = (p: number) => pad + ((maxP - p) / (maxP - minP || 1)) * h;
  const pts = data.map(d => `${xS(d.price)},${yS(d.profit)}`).join(" ");
  const zeroY = yS(0);

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="bg-surface-900 rounded-lg">
      <line x1={pad} y1={zeroY} x2={width - pad} y2={zeroY} stroke="#475569" strokeWidth={1} strokeDasharray="4" />
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#475569" strokeWidth={1} />
      <polyline points={pts} fill="none" stroke="#10b981" strokeWidth={2} />
      {data.map((d, i) => { if (i === 0) return null; const x1 = xS(data[i - 1].price), y1 = yS(data[i - 1].profit), x2 = xS(d.price), y2 = yS(d.profit); return <polygon key={i} points={`${x1},${y1} ${x2},${y2} ${x2},${zeroY} ${x1},${zeroY}`} fill={d.profit >= 0 ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)"} />; })}
      {analysis.break_even.map((be, i) => (<g key={i}><line x1={xS(be)} y1={pad} x2={xS(be)} y2={height - pad} stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="6,3" /><text x={xS(be)} y={pad - 5} textAnchor="middle" fill="#f59e0b" fontSize={10}>BE: {fmt(be)}</text></g>))}
      <text x={width / 2} y={height - 5} textAnchor="middle" fill="#94a3b8" fontSize={11}>قیمت دارایی پایه در سررسید</text>
      <text x={5} y={height / 2} textAnchor="middle" fill="#94a3b8" fontSize={11} transform={`rotate(-90, 12, ${height / 2})`}>سود/زیان (تومان)</text>
      <text x={width - pad + 5} y={zeroY + 4} fill="#64748b" fontSize={9}>0</text>
    </svg>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function OptionsPage() {
  const [tab, setTab] = useState<"strategies" | "chain" | "professional" | "learn">("strategies");
  const [selectedStrategy, setSelectedStrategy] = useState("covered_call");
  const [analysis, setAnalysis] = useState<StrategyAnalysis | null>(null);
  const [marketCondition, setMarketCondition] = useState("neutral");
  const [riskTolerance, setRiskTolerance] = useState(0.5);
  const [stockPrice, setStockPrice] = useState(1000);
  const [strike, setStrike] = useState(1000);
  const [callPremium, setCallPremium] = useState(50);
  const [putPremium, setPutPremium] = useState(30);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [chainData, setChainData] = useState<ChainData | null>(null);
  const [chainLoading, setChainLoading] = useState(false);

  // ── Queries with React Query ──
  const { data: strategies = [] } = useQuery({
    queryKey: ["options-strategies"],
    queryFn: async () => { const d = await apiGet<unknown>("/options/strategies"); return extractArray<StrategyInfo>(d); },
    staleTime: 300_000,
  });

  const { data: liveSymbols = [] } = useQuery({
    queryKey: ["options-live-symbols"],
    queryFn: async () => { const d = await apiGet<unknown>("/options/live/symbols"); return extractArray<LiveSymbol>(d); },
    refetchInterval: 60_000,
  });

  const { data: recommendations = [] } = useQuery({
    queryKey: ["options-recommend", marketCondition, riskTolerance],
    queryFn: async () => { const d = await apiPost<unknown>("/options/recommend", { market_condition: marketCondition, risk_tolerance: riskTolerance }); return extractArray<StrategyInfo>(d); },
    staleTime: 120_000,
  });

  const { data: glossary = [] } = useQuery({
    queryKey: ["options-glossary"],
    queryFn: async () => { const d = await apiGet<unknown>("/options/reference/glossary"); return extractArray<GlossaryItem>(d); },
    staleTime: 600_000,
  });

  const { data: mistakes = [] } = useQuery({
    queryKey: ["options-mistakes"],
    queryFn: async () => { const d = await apiGet<unknown>("/options/reference/mistakes"); return extractArray<MistakeItem>(d); },
    staleTime: 600_000,
  });

  const { data: formulas = {} } = useQuery({
    queryKey: ["options-formulas"],
    queryFn: async () => { const d = await apiGet<{ data: Record<string, string> }>("/options/reference/formulas"); return d?.data ?? {}; },
    staleTime: 600_000,
  });

  // ── Mutations ──
  const analyzeMutation = useMutation({
    mutationFn: async (params: { strategy: string; stock_price: number; strike: number; call_premium: number; put_premium: number }) => {
      const d = await apiPost<{ data: StrategyAnalysis }>("/options/analyze", params);
      return d.data;
    },
    onSuccess: (data) => setAnalysis(data),
  });

  const chainReqIdRef = useRef(0);
  const loadChain = useCallback(async (sym: string) => {
    const reqId = ++chainReqIdRef.current;
    setSelectedSymbol(sym);
    setChainLoading(true);
    try {
      const d = await apiGet<{ data: ChainData }>(`/options/live/chain/${encodeURIComponent(sym)}?limit=100`);
      if (reqId !== chainReqIdRef.current) return; // stale response guard
      setChainData(d.data);
      if (d.data?.underlying_price) setStockPrice(d.data.underlying_price);
    } catch (e) {
      if (reqId !== chainReqIdRef.current) return;
      console.error(e);
      toast.error("خطا در دریافت زنجیره اختیار");
    } finally {
      if (reqId === chainReqIdRef.current) setChainLoading(false);
    }
  }, []);

  const handleAnalyze = useCallback(() => {
    analyzeMutation.mutate({ strategy: selectedStrategy, stock_price: stockPrice, strike, call_premium: callPremium, put_premium: putPremium });
  }, [selectedStrategy, stockPrice, strike, callPremium, putPremium, analyzeMutation]);

  const handleQuickBuy = useCallback((type: string, strikePrice: number, qty: number) => {
    toast.info(`ثبت سفارش خرید ${type === "call" ? "اختیار خرید" : "اختیار فروش"} ${selectedSymbol} — اعمال: ${fmt(strikePrice)} — تعداد: ${qty} قرارداد`, { description: "این قابلیت فعلاً نمایشی است و به کارگزاری متصل نشده" });
  }, [selectedSymbol]);

  const tabs = [
    { id: "strategies" as const, label: "استراتژی‌ها", icon: "📊" },
    { id: "chain" as const, label: "زنجیره اختیار", icon: "🔗" },
    { id: "professional" as const, label: "ابزارهای حرفه‌ای", icon: "⚡" },
    { id: "learn" as const, label: "آموزش", icon: "📚" },
  ];

  return (
    <AppLayout title="📊 بازار اختیار معامله" subtitle="تحلیل، استراتژی و ابزارهای حرفه‌ای اختیار معامله">
      {/* Tabs */}
      <div className="flex gap-1 mb-5 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
        {tabs.map(t => (<button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${tab === t.id ? "bg-primary-600/30 text-primary-300 shadow-sm" : "text-surface-400 hover:text-surface-200"}`}>{t.icon} {t.label}</button>))}
      </div>

      {/* ═══════ TAB: Strategies ═══════ */}
      {tab === "strategies" && (
        <div className="space-y-4">
          {/* Market Condition */}
          <Card title="شرایط بازار">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
              {[{ v: "bullish", l: "صعودی 📈" }, { v: "bearish", l: "نزولی 📉" }, { v: "neutral", l: "خنثی ➡️" }, { v: "volatile", l: "پرنوسان 📊" }].map(mc => (
                <button key={mc.v} onClick={() => setMarketCondition(mc.v)} className={`p-2.5 rounded-xl text-xs font-bold transition-all ${marketCondition === mc.v ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{mc.l}</button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <label className="text-[10px] text-surface-500 shrink-0">ریسک:</label>
              <input type="range" min="0" max="1" step="0.1" value={riskTolerance} onChange={e => setRiskTolerance(Number(e.target.value))} className="flex-1 h-1.5 rounded-full appearance-none bg-surface-700 accent-primary-500" />
              <span className="text-[10px] text-surface-400 w-20 shrink-0">{riskTolerance < 0.3 ? "محافظه‌کار" : riskTolerance < 0.7 ? "متوسط" : "ریسک‌پذیر"}</span>
            </div>
          </Card>

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <Card title="پیشنهاد خودکار">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {recommendations.slice(0, 8).map(rec => (
                  <button key={rec.id} onClick={() => { setSelectedStrategy(rec.id); handleAnalyze(); }} className="bg-surface-800/50 rounded-xl p-3 text-right hover:bg-surface-700/50 transition-all border border-surface-700/30 hover:border-primary-600/30">
                    <p className="text-xs font-bold text-surface-200">{rec.name_fa}</p>
                    <p className="text-[10px] text-surface-500 mt-0.5">{rec.name}</p>
                    <span className={`text-[10px] mt-1 inline-block ${riskColor(rec.risk)}`}>ریسک: {riskLabel(rec.risk)}</span>
                  </button>
                ))}
              </div>
            </Card>
          )}

          {/* Strategy Builder + Analysis */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Builder */}
            <Card title="سازنده استراتژی">
              <select value={selectedStrategy} onChange={e => setSelectedStrategy(e.target.value)} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-3 py-2 text-xs text-surface-200 mb-3 focus:outline-none focus:border-primary-500">
                {strategies.map(s => <option key={s.id} value={s.id}>{s.name_fa}</option>)}
              </select>
              <div className="space-y-2">
                {[{ label: "قیمت سهم", val: stockPrice, set: setStockPrice }, { label: "قیمت اعمال", val: strike, set: setStrike }, { label: "پریمیوم Call", val: callPremium, set: setCallPremium }, { label: "پریمیوم Put", val: putPremium, set: setPutPremium }].map(f => (
                  <div key={f.label}>
                    <label className="text-[10px] text-surface-500">{f.label}</label>
                    <input type="number" value={f.val} onChange={e => f.set(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-3 py-1.5 text-xs text-surface-200 focus:outline-none focus:border-primary-500" />
                  </div>
                ))}
              </div>
              <button onClick={handleAnalyze} disabled={analyzeMutation.isPending} className="w-full mt-3 bg-primary-600 text-white py-2.5 rounded-xl text-xs font-bold hover:bg-primary-500 disabled:opacity-50 transition-all">
                {analyzeMutation.isPending ? "در حال تحلیل..." : "تحلیل استراتژی"}
              </button>
            </Card>

            {/* Analysis Result */}
            <div className="lg:col-span-2">
              {analyzeMutation.isPending ? (
                <Skeleton className="h-80 w-full rounded-2xl" />
              ) : analysis ? (
                <Card title={analysis.strategy_name_fa}>
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-[10px] px-2.5 py-1 rounded-full ${riskColor(analysis.risk_level)} bg-surface-800`}>ریسک: {riskLabel(analysis.risk_level)}</span>
                    <span className="text-[10px] text-surface-500">{analysis.market_condition}</span>
                  </div>
                  <p className="text-xs text-surface-400 mb-3">{analysis.description_fa}</p>

                  {/* Metrics */}
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    {[{ label: "حداکثر سود", val: analysis.max_profit, color: "text-accent-emerald" }, { label: "حداکثر زیان", val: analysis.max_loss, color: "text-accent-rose" }, { label: "هزینه اولیه", val: analysis.initial_cost, color: "text-surface-200" }].map(m => (
                      <div key={m.label} className="bg-surface-800/50 rounded-xl p-3 text-center">
                        <p className="text-[10px] text-surface-500">{m.label}</p>
                        <p className={`text-sm font-bold ${m.color}`}>{m.val === Infinity || m.val === -Infinity ? "∞" : fmt(m.val)}</p>
                      </div>
                    ))}
                  </div>

                  {/* Break Even */}
                  {analysis.break_even.length > 0 && (
                    <div className="bg-surface-800/30 rounded-xl p-3 mb-4">
                      <p className="text-[10px] text-surface-500 mb-1">نقاط سر به سر</p>
                      <div className="flex gap-2">{analysis.break_even.map((be, i) => <span key={i} className="text-xs font-mono text-accent-amber bg-accent-amber/10 px-2 py-0.5 rounded-full">{fmt(be)}</span>)}</div>
                    </div>
                  )}

                  {/* Payoff Diagram */}
                  <div className="mb-4">
                    <p className="text-[10px] text-surface-500 mb-1">نمودار سود/زیان</p>
                    <PayoffDiagram analysis={analysis} />
                  </div>

                  {/* Legs */}
                  <div className="mb-3">
                    <p className="text-[10px] text-surface-500 mb-1">اجزای استراتژی</p>
                    <div className="space-y-1">
                      {analysis.legs.map((leg: StrategyLeg, i: number) => (
                        <div key={i} className="flex items-center gap-1.5 text-[10px]">
                          <span className={`px-1.5 py-0.5 rounded-full ${leg.side === "buy" ? "bg-accent-emerald/20 text-accent-emerald" : "bg-accent-rose/20 text-accent-rose"}`}>{leg.side === "buy" ? "خرید" : "فروش"}</span>
                          <span className="text-surface-300">{leg.type === "stock" ? "سهام" : leg.type === "call" ? "Call" : "Put"}</span>
                          {leg.strike && <span className="text-surface-400">اعمال: {fmt(leg.strike)}</span>}
                          {leg.premium && <span className="text-surface-400">@{fmt(leg.premium)}</span>}
                          {leg.quantity > 1 && <span className="text-surface-500">×{leg.quantity}</span>}
                        </div>
                      ))}
                    </div>
                  </div>

                  {analysis.best_for && (
                    <div className="bg-primary-600/10 border border-primary-600/20 rounded-xl p-3">
                      <p className="text-[10px] text-primary-400">بهترین زمان استفاده: {analysis.best_for}</p>
                    </div>
                  )}
                </Card>
              ) : (
                <Card title="نتیجه تحلیل">
                  <div className="flex items-center justify-center h-64 text-surface-500 text-sm">یک استراتژی انتخاب و دکمه تحلیل را بزنید</div>
                </Card>
              )}
            </div>
          </div>

          {/* All Strategies */}
          <Card title={`تمام استراتژی‌ها (${strategies.length})`}>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {strategies.map(s => (
                <button key={s.id} onClick={() => { setSelectedStrategy(s.id); handleAnalyze(); }} className={`rounded-xl p-3 text-right transition-all border ${selectedStrategy === s.id ? "bg-primary-600/20 border-primary-600/40" : "bg-surface-800/30 border-surface-700/30 hover:bg-surface-800/50"}`}>
                  <p className="text-xs font-bold text-surface-200">{s.name_fa}</p>
                  <p className="text-[10px] text-surface-500 mt-0.5">{s.name}</p>
                  <span className={`text-[9px] mt-1 inline-block ${riskColor(s.risk)}`}>{riskLabel(s.risk)}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ═══════ TAB: Chain ═══════ */}
      {tab === "chain" && (
        <div className="space-y-4">
          {/* Symbol selector */}
          <Card title="انتخاب نماد پایه">
            {liveSymbols.length === 0 ? <Skeleton className="h-16 w-full" /> : (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {liveSymbols.map(s => (
                  <button key={s.symbol} onClick={() => loadChain(s.symbol)} className={`rounded-xl p-3 text-right transition-all border ${selectedSymbol === s.symbol ? "bg-primary-600 text-white border-primary-500" : "bg-surface-800 text-surface-300 hover:bg-surface-700 border-surface-700/30"}`}>
                    <p className="text-xs font-bold">{s.symbol}</p>
                    <p className="text-[10px] opacity-70 mt-0.5">{s.contracts} قرارداد | حجم: {(s.volume / 1e6).toFixed(0)}M</p>
                    <p className="text-[10px] opacity-70">قیمت: {fmt(s.price)}</p>
                  </button>
                ))}
              </div>
            )}
          </Card>

          {chainLoading && <Skeleton className="h-64 w-full rounded-2xl" />}

          {chainData && !chainLoading && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Quick Buy */}
              <div className="space-y-4">
                <QuickBuyPanel symbol={selectedSymbol} price={chainData.underlying_price} onBuy={handleQuickBuy} />
                {chainData.analysis && (
                  <Card title="تحلیل زنجیره">
                    <div className="space-y-2 text-xs">
                      {[{ k: "atm_strike", l: "ATM Strike" }, { k: "put_call_ratio", l: "Put-Call Ratio" }, { k: "max_pain", l: "Max Pain" }, { k: "pcr_interpretation", l: "سیگنال" }].map(({ k, l }) => (
                        <div key={k} className="flex justify-between"><span className="text-surface-500">{l}</span><span className="text-surface-200 font-mono">{String(chainData.analysis?.[k] ?? "—")}</span></div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>

              {/* Calls */}
              <Card title={`اختیار خرید (Call) — ${chainData.calls.length}`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px]">
                    <thead><tr className="border-b border-surface-700">
                      <th className="py-1.5 px-1 text-right text-surface-500">اعمال</th><th className="py-1.5 px-1 text-right text-surface-500">قیمت</th><th className="py-1.5 px-1 text-right text-surface-500">Bid</th><th className="py-1.5 px-1 text-right text-surface-500">Ask</th><th className="py-1.5 px-1 text-right text-surface-500">حجم</th><th className="py-1.5 px-1 text-right text-surface-500">OI</th><th className="py-1.5 px-1 text-right text-surface-500">وضعیت</th>
                    </tr></thead>
                    <tbody>{chainData.calls.map((c, i) => {
                      const m = c.strike < chainData.underlying_price ? "ITM" : c.strike > chainData.underlying_price ? "OTM" : "ATM";
                      return (<tr key={i} className="border-b border-surface-800/50 hover:bg-surface-800/30 cursor-pointer" onClick={() => { setStrike(c.strike); setCallPremium(c.price); setTab("strategies"); }}>
                        <td className="py-1.5 px-1 font-mono text-surface-200">{fmt(c.strike)}</td>
                        <td className="py-1.5 px-1 font-mono text-accent-emerald">{c.price}</td>
                        <td className="py-1.5 px-1 font-mono text-surface-400">{c.bid}</td>
                        <td className="py-1.5 px-1 font-mono text-surface-400">{c.ask}</td>
                        <td className="py-1.5 px-1 font-mono">{fmt(c.volume)}</td>
                        <td className="py-1.5 px-1 font-mono text-surface-500">{fmt(c.oi)}</td>
                        <td className={`py-1.5 px-1 font-bold ${m === "ITM" ? "text-accent-emerald" : m === "ATM" ? "text-accent-amber" : "text-surface-500"}`}>{m}</td>
                      </tr>);
                    })}</tbody>
                  </table>
                </div>
              </Card>

              {/* Puts */}
              <Card title={`اختیار فروش (Put) — ${chainData.puts.length}`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px]">
                    <thead><tr className="border-b border-surface-700">
                      <th className="py-1.5 px-1 text-right text-surface-500">اعمال</th><th className="py-1.5 px-1 text-right text-surface-500">قیمت</th><th className="py-1.5 px-1 text-right text-surface-500">Bid</th><th className="py-1.5 px-1 text-right text-surface-500">Ask</th><th className="py-1.5 px-1 text-right text-surface-500">حجم</th><th className="py-1.5 px-1 text-right text-surface-500">OI</th><th className="py-1.5 px-1 text-right text-surface-500">وضعیت</th>
                    </tr></thead>
                    <tbody>{chainData.puts.map((p, i) => {
                      const m = p.strike > chainData.underlying_price ? "ITM" : p.strike < chainData.underlying_price ? "OTM" : "ATM";
                      return (<tr key={i} className="border-b border-surface-800/50 hover:bg-surface-800/30 cursor-pointer" onClick={() => { setStrike(p.strike); setPutPremium(p.price); setTab("strategies"); }}>
                        <td className="py-1.5 px-1 font-mono text-surface-200">{fmt(p.strike)}</td>
                        <td className="py-1.5 px-1 font-mono text-accent-rose">{p.price}</td>
                        <td className="py-1.5 px-1 font-mono text-surface-400">{p.bid}</td>
                        <td className="py-1.5 px-1 font-mono text-surface-400">{p.ask}</td>
                        <td className="py-1.5 px-1 font-mono">{fmt(p.volume)}</td>
                        <td className="py-1.5 px-1 font-mono text-surface-500">{fmt(p.oi)}</td>
                        <td className={`py-1.5 px-1 font-bold ${m === "ITM" ? "text-accent-emerald" : m === "ATM" ? "text-accent-amber" : "text-surface-500"}`}>{m}</td>
                      </tr>);
                    })}</tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ═══════ TAB: Professional ═══════ */}
      {tab === "professional" && <ProfessionalTab />}

      {/* ═══════ TAB: Learn ═══════ */}
      {tab === "learn" && <LearnTab glossary={glossary} mistakes={mistakes} formulas={formulas} />}
    </AppLayout>
  );
}

// ── Quick Buy Panel ───────────────────────────────────────────────────────────

function QuickBuyPanel({ symbol, price, onBuy }: { symbol: string; price: number; onBuy: (type: string, strike: number, qty: number) => void }) {
  const [qty, setQty] = useState(1);
  const [selectedStrike, setSelectedStrike] = useState(price);
  return (
    <Card title={`خرید سریع — ${symbol}`}>
      <div className="space-y-2 mb-3">
        <div><label className="text-[10px] text-surface-500">قیمت سهم پایه</label><p className="text-sm font-mono text-surface-200">{fmt(price)}</p></div>
        <div><label className="text-[10px] text-surface-500">قیمت اعمال</label><input type="number" value={selectedStrike} onChange={e => setSelectedStrike(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-3 py-1.5 text-xs text-surface-200" /></div>
        <div><label className="text-[10px] text-surface-500">تعداد قرارداد</label><input type="number" value={qty} min={1} onChange={e => setQty(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-3 py-1.5 text-xs text-surface-200" /></div>
      </div>
      <div className="flex gap-2">
        <button onClick={() => onBuy("call", selectedStrike, qty)} className="flex-1 bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30 rounded-xl py-2 text-xs font-bold hover:bg-accent-emerald/30">خرید Call</button>
        <button onClick={() => onBuy("put", selectedStrike, qty)} className="flex-1 bg-accent-rose/20 text-accent-rose border border-accent-rose/30 rounded-xl py-2 text-xs font-bold hover:bg-accent-rose/30">خرید Put</button>
      </div>
    </Card>
  );
}

// ── Professional Tab ──────────────────────────────────────────────────────────

function ProfessionalTab() {
  const [costEntry, setCostEntry] = useState(500);
  const [costExit, setCostExit] = useState(800);
  const [costQty, setCostQty] = useState(1000);
  const [sizingCapital, setSizingCapital] = useState(100_000_000);
  const [sizingRisk, setSizingRisk] = useState(2);
  const [sizingLoss, setSizingLoss] = useState(500);

  const costMutation = useMutation({
    mutationFn: async () => { const d = await apiPost<{ data: CostResult }>("/options/professional/costs", { entry_price: costEntry, exit_price: costExit, quantity: costQty, is_option: true }); return d.data; },
  });

  const sizingMutation = useMutation({
    mutationFn: async () => { const d = await apiPost<{ data: SizingResult }>("/options/professional/position-sizing", { capital: sizingCapital, risk_per_trade_pct: sizingRisk, max_loss_per_contract: sizingLoss }); return d.data; },
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Cost Calculator */}
      <Card title="محاسبه هزینه واقعی">
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div><label className="text-[10px] text-surface-500">قیمت ورود</label><input type="number" value={costEntry} onChange={e => setCostEntry(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-2 py-1.5 text-xs text-surface-200" /></div>
            <div><label className="text-[10px] text-surface-500">قیمت خروج</label><input type="number" value={costExit} onChange={e => setCostExit(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-2 py-1.5 text-xs text-surface-200" /></div>
            <div><label className="text-[10px] text-surface-500">تعداد</label><input type="number" value={costQty} onChange={e => setCostQty(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-2 py-1.5 text-xs text-surface-200" /></div>
          </div>
          <button onClick={() => costMutation.mutate()} disabled={costMutation.isPending} className="w-full bg-primary-600 text-white py-2.5 rounded-xl text-xs font-bold hover:bg-primary-500 disabled:opacity-50">{costMutation.isPending ? "در حال محاسبه..." : "محاسبه"}</button>
          {costMutation.data && (
            <div className="bg-surface-800/50 rounded-xl p-3 space-y-1.5 text-xs">
              <div className="flex justify-between"><span className="text-surface-500">سود ناخالص</span><span className="text-accent-emerald">{fmt(costMutation.data.gross_pnl)} تومان</span></div>
              <div className="flex justify-between"><span className="text-surface-500">کارمزد</span><span className="text-accent-rose">{fmt(costMutation.data.commission)} تومان</span></div>
              <div className="flex justify-between"><span className="text-surface-500">سود خالص</span><span className="text-surface-200 font-bold">{fmt(costMutation.data.net_pnl)} ({costMutation.data.net_pnl_pct}%)</span></div>
              <div className="flex justify-between"><span className="text-surface-500">سر به سر</span><span className="text-accent-amber">{fmt(costMutation.data.breakeven)} تومان</span></div>
            </div>
          )}
        </div>
      </Card>

      {/* Position Sizing */}
      <Card title="اندازه موقعیت">
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div><label className="text-[10px] text-surface-500">سرمایه</label><input type="number" value={sizingCapital} onChange={e => setSizingCapital(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-2 py-1.5 text-xs text-surface-200" /></div>
            <div><label className="text-[10px] text-surface-500">ریسک %</label><input type="number" value={sizingRisk} onChange={e => setSizingRisk(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-2 py-1.5 text-xs text-surface-200" /></div>
            <div><label className="text-[10px] text-surface-500">زیان هر قرارداد</label><input type="number" value={sizingLoss} onChange={e => setSizingLoss(Number(e.target.value))} className="w-full bg-surface-900 border border-surface-700 rounded-xl px-2 py-1.5 text-xs text-surface-200" /></div>
          </div>
          <button onClick={() => sizingMutation.mutate()} disabled={sizingMutation.isPending} className="w-full bg-primary-600 text-white py-2.5 rounded-xl text-xs font-bold hover:bg-primary-500 disabled:opacity-50">{sizingMutation.isPending ? "در حال محاسبه..." : "محاسبه"}</button>
          {sizingMutation.data && (
            <div className="bg-surface-800/50 rounded-xl p-3 space-y-1.5 text-xs">
              <div className="flex justify-between"><span className="text-surface-500">حداکثر قرارداد</span><span className="text-surface-200 font-bold">{sizingMutation.data.max_contracts}</span></div>
              <div className="flex justify-between"><span className="text-surface-500">هزینه کل</span><span className="text-surface-200">{fmt(sizingMutation.data.total_cost)} تومان</span></div>
              <div className="flex justify-between"><span className="text-surface-500">درصد سرمایه</span><span className="text-surface-200">{sizingMutation.data.pct_of_capital}%</span></div>
            </div>
          )}
        </div>
      </Card>

      {/* Iran Rules */}
      <Card title="قوانین بازار ایران" className="md:col-span-2">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          {[{ l: "کارمزد خرید", v: "۰.۱۲۵٪" }, { l: "کارمزد فروش", v: "۰.۶۲۵٪ (شامل مالیات)" }, { l: "تسویه", v: "T+2" }, { l: "اندازه قرارداد", v: "۱,۰۰۰ سهم" }, { l: "محدودیت قیمت", v: "±۱۹٪ (اختیار)" }, { l: "سبک اعمال", v: "اروپایی" }, { l: "فروش فزاینده", v: "ممنوع" }, { l: "حداقل سرمایه", v: "۵۰ میلیون تومان" }].map(r => (
            <div key={r.l} className="bg-surface-800/50 rounded-xl p-2.5"><p className="text-surface-500 text-[10px]">{r.l}</p><p className="text-surface-200 mt-0.5">{r.v}</p></div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── Learn Tab ─────────────────────────────────────────────────────────────────

function LearnTab({ glossary, mistakes, formulas }: { glossary: GlossaryItem[]; mistakes: MistakeItem[]; formulas: Record<string, string> }) {
  const [learnTab, setLearnTab] = useState<"glossary" | "mistakes" | "formulas">("glossary");
  return (
    <div>
      <div className="flex gap-1 mb-4 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50">
        {[{ id: "glossary" as const, label: "📚 اصطلاحات" }, { id: "mistakes" as const, label: "❌ اشتباهات رایج" }, { id: "formulas" as const, label: "📐 فرمول‌ها" }].map(t => (
          <button key={t.id} onClick={() => setLearnTab(t.id)} className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${learnTab === t.id ? "bg-primary-600/30 text-primary-300" : "text-surface-400 hover:text-surface-200"}`}>{t.label}</button>
        ))}
      </div>
      {learnTab === "glossary" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">{glossary.map((g, i) => (
          <div key={i} className="glass-card p-3"><div className="flex items-center gap-2 mb-1"><span className="text-xs font-bold text-surface-200">{g.fa}</span><span className="text-[10px] text-primary-400">{g.en}</span></div><p className="text-[10px] text-surface-500">{g.desc}</p></div>
        ))}</div>
      )}
      {learnTab === "mistakes" && (
        <div className="space-y-2">{mistakes.map((m, i) => (
          <div key={i} className="glass-card p-3"><div className="flex items-start gap-2"><span className="text-accent-rose text-sm">❌</span><div><p className="text-xs font-bold text-surface-200">{m.mistake}</p><p className="text-[10px] text-accent-emerald mt-1">✅ {m.solution}</p></div></div></div>
        ))}</div>
      )}
      {learnTab === "formulas" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">{Object.entries(formulas).map(([key, val]) => (
          <div key={key} className="glass-card p-3"><p className="text-[10px] text-primary-400 mb-1">{key}</p><p className="text-xs font-mono text-surface-200" dir="ltr">{val}</p></div>
        ))}</div>
      )}
    </div>
  );
}
