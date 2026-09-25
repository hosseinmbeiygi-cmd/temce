"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Loader2 } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { PayoffDiagram, fmt, fmtPct } from "../helpers";
import type { StrategyAnalysis, StrategyInfo } from "../types";

export default function BacktestTab() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [strategy, setStrategy] = useState("");
  const [price, setPrice] = useState("1000");
  const [result, setResult] = useState<StrategyAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<{ success: boolean; data: StrategyInfo[] }>("/options/strategies")
      .then((r) => {
        const list = r.success ? r.data ?? [] : [];
        setStrategies(list);
        if (list.length) setStrategy(list[0].id);
      })
      .catch(() => setStrategies([]));
  }, []);

  const run = async () => {
    if (!strategy) return;
    setLoading(true);
    try {
      const r = await apiPost<{ success: boolean; data: StrategyAnalysis }>("/options/analyze", {
        strategy,
        stock_price: Number(price) || 1000,
        strike: Number(price) || 1000,
        call_premium: 50,
        put_premium: 30,
      });
      setResult(r.success ? r.data : null);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const curve = result?.profit_at_expiry ?? [];
  const rets = curve.length > 1 && result && result.initial_cost > 0
    ? (result.max_profit / result.initial_cost) * 100
    : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200"
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>{s.name_fa || s.name}</option>
          ))}
        </select>
        <input
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="قیمت مبنا"
          inputMode="decimal"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-32 font-mono"
          dir="ltr"
        />
        <button
          onClick={run}
          disabled={loading || !strategy}
          className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
          اجرای بک‌تست
        </button>
      </div>

      {!result && !loading && (
        <div className="text-center text-slate-500 text-sm py-12">استراتژی را انتخاب و بک‌تست را اجرا کنید.</div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3">
              <div className="text-[10px] text-slate-500">بیشترین سود</div>
              <div className="font-mono font-bold text-emerald-400" dir="ltr">{fmt(result.max_profit)}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3">
              <div className="text-[10px] text-slate-500">بیشترین ضرر</div>
              <div className="font-mono font-bold text-rose-400" dir="ltr">{fmt(result.max_loss)}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3">
              <div className="text-[10px] text-slate-500">بازده تاریخی</div>
              <div className="font-mono font-bold text-amber-400" dir="ltr">{fmtPct(rets)}</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3">
              <div className="text-[10px] text-slate-500">هزینه اولیه</div>
              <div className="font-mono font-bold text-slate-200" dir="ltr">{fmt(result.initial_cost)}</div>
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
            <h3 className="text-xs font-bold text-slate-300 mb-2">منحنی سود سررسید</h3>
            <PayoffDiagram analysis={result} />
          </div>
        </div>
      )}
    </div>
  );
}
