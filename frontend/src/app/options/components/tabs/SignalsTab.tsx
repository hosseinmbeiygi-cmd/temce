"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, Minus, Loader2, Target, ShieldAlert } from "lucide-react";
import { apiPost } from "@/lib/api";
import { PayoffDiagram, fmt, riskBg, riskColor, riskLabel, marketLabel } from "../helpers";
import type { StrategyAnalysis, StrategyInfo } from "../types";

type Market = "all" | "stock" | "commodity";

const CONDITIONS = [
  { id: "bullish", label: "صعودی" },
  { id: "bearish", label: "نزولی" },
  { id: "neutral", label: "خنثی" },
  { id: "volatile", label: "پرنوسان" },
];

function dirIcon(market: string) {
  if (market.includes("bull")) return <TrendingUp size={16} className="text-accent-emerald" />;
  if (market.includes("bear")) return <TrendingDown size={16} className="text-accent-rose" />;
  return <Minus size={16} className="text-accent-amber" />;
}

export default function SignalsTab() {
  const [condition, setCondition] = useState("neutral");
  const [market, setMarket] = useState<Market>("all");
  const [signals, setSignals] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<StrategyAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiPost<{ success: boolean; data: StrategyInfo[] }>(
        "/options/recommend",
        { market_condition: condition, risk_tolerance: 0.5 }
      );
      setSignals(r.success ? r.data ?? [] : []);
    } catch {
      setSignals([]);
    } finally {
      setLoading(false);
    }
  };

  const analyze = async (s: StrategyInfo) => {
    setAnalyzing(s.id);
    try {
      const r = await apiPost<{ success: boolean; data: StrategyAnalysis }>(
        "/options/analyze",
        { strategy: s.id, stock_price: 1000, strike: 1000, call_premium: 50, put_premium: 30 }
      );
      setAnalysis(r.success ? r.data : null);
    } catch {
      setAnalysis(null);
    } finally {
      setAnalyzing(null);
    }
  };

  const filtered = signals.filter(
    (s) => market === "all" || (s.market ?? "").toLowerCase().includes(market === "stock" ? "stock" : "commod")
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
          {CONDITIONS.map((c) => (
            <button
              key={c.id}
              onClick={() => setCondition(c.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                condition === c.id ? "bg-emerald-600 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
          {(["all", "stock", "commodity"] as Market[]).map((m) => (
            <button
              key={m}
              onClick={() => setMarket(m)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                market === m ? "bg-emerald-600 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {m === "all" ? "همه" : m === "stock" ? "سهام" : "کالا"}
            </button>
          ))}
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          دریافت سیگنال
        </button>
      </div>

      {filtered.length === 0 && !loading && (
        <div className="text-center text-slate-500 text-sm py-12">سیگنالی یافت نشد — شرایط بازار را انتخاب و دریافت بزنید.</div>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((s) => (
          <button
            key={s.id}
            onClick={() => analyze(s)}
            className="text-right bg-slate-900 border border-slate-800 rounded-2xl p-4 hover:border-emerald-600/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="flex items-center gap-2 font-bold text-sm text-slate-100">
                {dirIcon(s.market ?? "")}
                {s.name_fa || s.name}
              </span>
              {analyzing === s.id && <Loader2 size={14} className="animate-spin text-slate-400" />}
            </div>
            <div className="flex items-center gap-2 text-[11px]">
              <span className={`px-2 py-0.5 rounded-full border font-bold ${riskBg(s.risk)} ${riskColor(s.risk)}`}>
                ریسک {riskLabel(s.risk)}
              </span>
              <span className="text-slate-500">{marketLabel(s.market ?? "")}</span>
              {typeof s.score === "number" && (
                <span className="text-emerald-400 font-mono">امتیاز {s.score.toFixed(1)}</span>
              )}
            </div>
          </button>
        ))}
      </div>

      {analysis && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
          <h3 className="font-bold text-sm text-slate-100">{analysis.strategy_name_fa || analysis.strategy_name}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
            <div className="bg-slate-950 rounded-xl p-3">
              <div className="text-[10px] text-slate-500 flex items-center justify-center gap-1"><Target size={12} /> حد سود</div>
              <div className="font-mono font-bold text-emerald-400" dir="ltr">{fmt(analysis.max_profit)}</div>
            </div>
            <div className="bg-slate-950 rounded-xl p-3">
              <div className="text-[10px] text-slate-500 flex items-center justify-center gap-1"><ShieldAlert size={12} /> حد ضرر</div>
              <div className="font-mono font-bold text-rose-400" dir="ltr">{fmt(analysis.max_loss)}</div>
            </div>
            <div className="bg-slate-950 rounded-xl p-3">
              <div className="text-[10px] text-slate-500">سر‌به‌سر</div>
              <div className="font-mono font-bold text-amber-400" dir="ltr">{(analysis.break_even ?? []).map(fmt).join(" / ")}</div>
            </div>
            <div className="bg-slate-950 rounded-xl p-3">
              <div className="text-[10px] text-slate-500">هزینه اولیه</div>
              <div className="font-mono font-bold text-slate-200" dir="ltr">{fmt(analysis.initial_cost)}</div>
            </div>
          </div>
          <PayoffDiagram analysis={analysis} />
        </div>
      )}
    </div>
  );
}
