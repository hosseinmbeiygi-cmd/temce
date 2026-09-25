"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Loader2, TrendingDown, TrendingUp } from "lucide-react";
import { apiGet } from "@/lib/api";
import { runOptionsBacktest, type BacktestResponse } from "@/lib/options-api";
import { fmt } from "../helpers";
import { ChartSkeleton } from "./Skeleton";
import type { StrategyInfo } from "../types";

function MetricCard({ label, value, tone }: { label: string; value: string; tone: "emerald" | "rose" | "amber" | "slate" }) {
  const color = { emerald: "text-emerald-400", rose: "text-rose-400", amber: "text-amber-400", slate: "text-slate-200" }[tone];
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={`font-mono font-bold ${color} text-lg`} dir="ltr">{value}</div>
    </div>
  );
}

/** Equity curve as a sparkline SVG (mission phase 1 — tab 4). */
function EquityCurve({ curve, dates }: { curve: number[]; dates: string[] }) {
  if (curve.length < 2) return null;
  const lo = Math.min(...curve);
  const hi = Math.max(...curve);
  const x = (i: number) => (i / (curve.length - 1)) * 560;
  const y = (v: number) => 100 - ((v - lo) / (hi - lo || 1)) * 90;
  const points = curve.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const up = curve[curve.length - 1] >= curve[0];
  return (
    <div>
      <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
        <span dir="ltr">{dates[0]}</span>
        <span>{up ? <TrendingUp size={12} className="inline text-emerald-400" /> : <TrendingDown size={12} className="inline text-rose-400" />} منحنی سرمایه</span>
        <span dir="ltr">{dates[dates.length - 1]}</span>
      </div>
      <svg viewBox="0 0 600 110" className="w-full bg-slate-950 rounded-xl" style={{ direction: "ltr" }}>
        <polyline points={points} fill="none" stroke={up ? "#10b981" : "#f43f5e"} strokeWidth={2} />
      </svg>
    </div>
  );
}

export default function BacktestTab() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [strategy, setStrategy] = useState("momentum");
  const [symbol, setSymbol] = useState("فولاد");
  const [dte, setDte] = useState("30");
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<{ success: boolean; data: StrategyInfo[] }>("/options/strategies")
      .then((r) => setStrategies(r.success ? r.data ?? [] : []))
      .catch(() => setStrategies([]));
  }, []);

  const run = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError("");
    try {
      const r = await runOptionsBacktest({
        symbol: symbol.trim(),
        strategy,
        days_to_expiry: Math.max(1, Math.min(365, Number(dte) || 30)),
        limit: 1000,
      });
      if (r.success && r.data) setResult(r.data);
      else {
        setResult(null);
        setError(r.error?.message ?? "بک‌تست ناموفق بود");
      }
    } catch {
      setResult(null);
      setError("اتصال به سرور برقرار نشد");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="نماد پایه (مثلاً فولاد)"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-40"
        />
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200"
        >
          <option value="momentum">مومنتوم (۰۰–۲۰ روزه)</option>
          <option value="always">همه دوره‌ها</option>
        </select>
        <input
          value={dte}
          onChange={(e) => setDte(e.target.value)}
          placeholder="روز تا سررسید"
          inputMode="numeric"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-28 font-mono"
          dir="ltr"
        />
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
          اجرای بک‌تست
        </button>
      </div>

      {error && (
        <div className="text-center text-rose-400 text-xs bg-rose-500/10 border border-rose-500/30 rounded-2xl py-3">{error}</div>
      )}

      {loading && <ChartSkeleton />}

      {!result && !loading && !error && (
        <div className="text-center text-slate-500 text-sm py-12">
          نماد و استراتژی را انتخاب کنید — بک‌تست روی دادهٔ تاریخی واقعی با کارمزد ایران اجرا می‌شود.
        </div>
      )}

      {m && result && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MetricCard label="نرخ برد" value={`${m.win_rate.toFixed(1)}%`} tone="emerald" />
            <MetricCard label="Profit Factor" value={m.profit_factor.toFixed(2)} tone="amber" />
            <MetricCard label="بیشترین افت سرمایه" value={`${m.max_drawdown_pct.toFixed(1)}%`} tone="rose" />
            <MetricCard label="نسبت شارپ" value={m.sharpe_ratio.toFixed(2)} tone="slate" />
            <MetricCard label="بازده سالانه" value={`${m.annualized_return_pct.toFixed(1)}%`} tone={m.annualized_return_pct >= 0 ? "emerald" : "rose"} />
            <MetricCard label="تعداد معاملات" value={String(m.n_trades)} tone="slate" />
            <MetricCard label="میانگین برد" value={fmt(Math.round(m.avg_win))} tone="emerald" />
            <MetricCard label="میانگین ضرر" value={fmt(Math.round(m.avg_loss))} tone="rose" />
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
            <EquityCurve curve={result.equity_curve} dates={result.equity_dates} />
          </div>

          {result.trades.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="px-4 py-2 text-xs font-bold text-slate-300">معاملات ({result.trades.length})</div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs" dir="ltr">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-800">
                      <th className="px-3 py-2 font-normal">Entry</th>
                      <th className="px-3 py-2 font-normal">Exit</th>
                      <th className="px-3 py-2 font-normal">Reason</th>
                      <th className="px-3 py-2 font-normal">PnL</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {result.trades.slice(-15).reverse().map((t, i) => (
                      <tr key={i} className="border-b border-slate-800/50 text-slate-200">
                        <td className="px-3 py-1.5">{t.entry_date}</td>
                        <td className="px-3 py-1.5">{t.exit_date}</td>
                        <td className={`px-3 py-1.5 ${t.exit_reason === "stop" ? "text-rose-400" : t.exit_reason === "target" ? "text-emerald-400" : "text-slate-400"}`}>
                          {t.exit_reason}
                        </td>
                        <td className={`px-3 py-1.5 font-bold ${t.pnl_net >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {fmt(Math.round(t.pnl_net))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="text-[10px] text-slate-600 text-center">{result.legal_disclaimer}</div>
        </div>
      )}
    </div>
  );
}
