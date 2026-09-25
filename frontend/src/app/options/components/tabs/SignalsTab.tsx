"use client";

import { useState } from "react";
import {
  Loader2,
  Target,
  ShieldAlert,
  TrendingUp,
  TrendingDown,
  Minus,
  Percent,
} from "lucide-react";
import {
  fetchOptionsSignals,
  type OptionSignal,
  type SignalsResponse,
} from "@/lib/options-api";
import { fmt } from "../helpers";
import { CardSkeletonGrid } from "./Skeleton";

type Market = "all" | "stock" | "commodity";

const CONDITIONS = [
  { id: "bullish", label: "صعودی" },
  { id: "bearish", label: "نزولی" },
  { id: "neutral", label: "خنثی" },
  { id: "volatile", label: "پرنوسان" },
];

const IV_LEVELS = [
  { id: "50", label: "IV متوسط" },
  { id: "80", label: "IV بالا (فروش پریمیوم)" },
  { id: "20", label: "IV پایین (خرید پریمیوم)" },
];

function dirIcon(bias: string) {
  const b = (bias || "").toLowerCase();
  if (b.includes("bull") || b.includes("up")) return <TrendingUp size={16} className="text-emerald-400" />;
  if (b.includes("bear") || b.includes("down")) return <TrendingDown size={16} className="text-rose-400" />;
  return <Minus size={16} className="text-amber-400" />;
}

function Confidence({ score }: { score: number }) {
  // 0..100 → colored chip
  const tone = score >= 70 ? "text-emerald-400 border-emerald-600/40" : score >= 45 ? "text-amber-400 border-amber-600/40" : "text-slate-400 border-slate-700";
  return (
    <span className={`px-2 py-0.5 rounded-full border font-bold font-mono text-[11px] ${tone}`} dir="ltr">
      {score.toFixed(0)}%
    </span>
  );
}

export default function SignalsTab() {
  const [condition, setCondition] = useState("neutral");
  const [ivRank, setIvRank] = useState("50");
  const [market, setMarket] = useState<Market>("all");
  const [payload, setPayload] = useState<SignalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetchOptionsSignals({
        market_condition: condition,
        iv_rank: Number(ivRank) || 50,
        guarded: true,
      });
      setPayload(r);
    } catch {
      setError("اتصال به سرور برقرار نشد");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  const signals = (payload?.signals ?? []).filter((s: OptionSignal) => {
    if (market === "all") return true;
    const bias = String(s.market_bias ?? "").toLowerCase();
    return market === "stock" ? !bias.includes("commod") : bias.includes("commod");
  });

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
        <select
          value={ivRank}
          onChange={(e) => setIvRank(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200"
        >
          {IV_LEVELS.map((v) => (
            <option key={v.id} value={v.id}>{v.label}</option>
          ))}
        </select>
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

      {error && (
        <div className="text-center text-rose-400 text-xs bg-rose-500/10 border border-rose-500/30 rounded-2xl py-3">{error}</div>
      )}

      {loading && <CardSkeletonGrid />}

      {signals.length === 0 && !loading && !error && (
        <div className="text-center text-slate-500 text-sm py-12">
          سیگنالی یافت نشد — شرایط بازار را انتخاب و دریافت بزنید. (فیلتر نقدشوندگی فعال است: نمادهای قفل‌شده حذف می‌شوند)
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {signals.map((s, i) => (
          <div
            key={`${s.strategy_id}-${i}`}
            className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-emerald-600/50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-bold text-sm text-slate-100">
                {dirIcon(s.market_bias)}
                {s.strategy_name_fa || s.strategy_id}
              </span>
              <Confidence score={s.confidence} />
            </div>

            <div className="flex items-center gap-2 text-[11px]">
              <span
                className={`px-2 py-0.5 rounded-full border font-bold ${
                  s.direction === "credit"
                    ? "text-amber-400 border-amber-600/40 bg-amber-500/10"
                    : "text-emerald-400 border-emerald-600/40 bg-emerald-500/10"
                }`}
              >
                {s.direction === "credit" ? "فروش پریمیوم" : "خرید پریمیوم"}
              </span>
              <span className="text-slate-500 font-mono" dir="ltr">{s.underlying || "—"}</span>
              {typeof s.iv_rank === "number" && (
                <span className="flex items-center gap-1 text-slate-500">
                  <Percent size={10} />
                  IV {s.iv_rank.toFixed(0)}
                </span>
              )}
            </div>

            <div className="grid grid-cols-4 gap-1.5 text-center">
              <div className="bg-slate-950 rounded-lg p-1.5">
                <div className="text-[9px] text-slate-500">ورود</div>
                <div className="font-mono text-[11px] font-bold text-slate-200" dir="ltr">{fmt(s.entry_price)}</div>
              </div>
              <div className="bg-slate-950 rounded-lg p-1.5">
                <div className="text-[9px] text-slate-500 flex items-center justify-center gap-0.5"><Target size={9} /> حد سود</div>
                <div className="font-mono text-[11px] font-bold text-emerald-400" dir="ltr">{fmt(s.take_profit)}</div>
              </div>
              <div className="bg-slate-950 rounded-lg p-1.5">
                <div className="text-[9px] text-slate-500 flex items-center justify-center gap-0.5"><ShieldAlert size={9} /> حد ضرر</div>
                <div className="font-mono text-[11px] font-bold text-rose-400" dir="ltr">{fmt(s.stop_loss)}</div>
              </div>
              <div className="bg-slate-950 rounded-lg p-1.5">
                <div className="text-[9px] text-slate-500">R/R</div>
                <div className="font-mono text-[11px] font-bold text-amber-400" dir="ltr">{s.risk_reward?.toFixed?.(2) ?? "—"}</div>
              </div>
            </div>

            {(s.iran_notes ?? []).length > 0 && (
              <div className="text-[10px] text-slate-500 leading-4">{s.iran_notes[0]}</div>
            )}
          </div>
        ))}
      </div>

      {payload && (
        <div className="text-[10px] text-slate-600 text-center">{payload.legal_disclaimer}</div>
      )}
    </div>
  );
}
