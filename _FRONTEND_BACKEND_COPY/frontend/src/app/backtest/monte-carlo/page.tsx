"use client";

import { useState, useCallback } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { apiPost } from "@/lib/api";
import Link from "next/link";

interface MCResult {
  simulations: number;
  initial_capital: number;
  confidence_intervals: Record<number, number>;
  prob_profit: number;
  prob_ruin: number;
  expected_return: number;
  worst_case: number;
  best_case: number;
  avg_final_capital: number;
  avg_max_drawdown: number;
  avg_max_drawdown_pct: number;
  median_final: number;
}

const STRATEGIES = [
  { value: "moving_average_cross", label: "تقاطع میانگین متحرک" },
  { value: "momentum", label: "مومنتوم" },
  { value: "mean_reversion", label: "بازگشت به میانگین" },
  { value: "breakout", label: "شکست قیمت" },
  { value: "rsi_reversion", label: "بازگشت RSI" },
  { value: "volatility_breakout", label: "شکست نوسان" },
];

function formatCurrency(n: number): string {
  if (n >= 1e12) return (n / 1e12).toFixed(1) + "T";
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  return n.toLocaleString();
}

export default function MonteCarloPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [strategy, setStrategy] = useState("moving_average_cross");
  const [nSimulations, setNSimulations] = useState(1000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MCResult | null>(null);
  const [error, setError] = useState("");

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await apiPost<{ success: boolean; data: MCResult; error?: { message: string } }>("/backtests/monte-carlo", {
        symbol,
        strategy,
        strategy_params: {},
        n_simulations: nSimulations,
      });
      if (res?.success && res.data) {
        setResult(res.data);
      } else {
        setError(res?.error?.message || "خطا در اجرای شبیه‌سازی");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در اتصال به سرور");
    }
    setLoading(false);
  }, [symbol, strategy, nSimulations]);

  return (
    <AppLayout title="شبیه‌سازی Monte Carlo" subtitle="بازه اطمینان عملکرد استراتژی">
      <div className="max-w-5xl mx-auto space-y-5">

        {/* Config */}
        <div className="glass-card p-5">
          <h2 className="font-bold text-surface-200 mb-4">⚙️ تنظیمات</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs text-surface-500 mb-1">نماد</label>
              <input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500" />
            </div>
            <div>
              <label className="block text-xs text-surface-500 mb-1">استراتژی</label>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500">
                {STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-surface-500 mb-1">تعداد شبیه‌سازی</label>
              <input type="number" value={nSimulations} onChange={(e) => setNSimulations(parseInt(e.target.value) || 1000)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 font-mono outline-none focus:border-primary-500"
                min={100} max={10000} />
            </div>
            <div className="flex items-end">
              <button onClick={handleRun} disabled={loading}
                className={`w-full px-5 py-2 rounded-lg text-sm font-medium transition-colors ${loading ? "bg-surface-700 text-surface-400" : "bg-primary-600 hover:bg-primary-500 text-white"}`}>
                {loading ? "در حال شبیه‌سازی..." : "🎲 اجرای Monte Carlo"}
              </button>
            </div>
          </div>
        </div>

        {error && <div className="glass-card p-4 text-accent-rose text-sm">{error}</div>}

        {/* Results */}
        {result && (
          <>
            {/* Key Metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="glass-card p-3 text-center">
                <div className={`text-2xl font-bold ${result.prob_profit > 60 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {result.prob_profit}%
                </div>
                <div className="text-xs text-surface-500">احتمال سود</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className={`text-2xl font-bold ${result.prob_ruin < 10 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {result.prob_ruin}%
                </div>
                <div className="text-xs text-surface-500">احتمال ورشکستگی</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-primary-300">{result.expected_return}%</div>
                <div className="text-xs text-surface-500">بازده مورد انتظار</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-accent-amber">{result.avg_max_drawdown_pct}%</div>
                <div className="text-xs text-surface-500">حداکثر افت میانگین</div>
              </div>
            </div>

            {/* Confidence Intervals */}
            <div className="glass-card p-4">
              <h3 className="font-bold text-surface-200 mb-3">📊 بازه‌های اطمینان</h3>
              <div className="space-y-3">
                {Object.entries(result.confidence_intervals).sort(([a], [b]) => Number(a) - Number(b)).map(([level, value]) => {
                  const pct = Number(level);
                  const barWidth = ((value - result.worst_case) / (result.best_case - result.worst_case)) * 100;
                  return (
                    <div key={level} className="flex items-center gap-3">
                      <span className="text-xs text-surface-400 w-16 text-left">%{pct}</span>
                      <div className="flex-1 h-6 bg-surface-800 rounded-full overflow-hidden relative">
                        <div className="h-full rounded-full transition-all" style={{
                          width: `${Math.max(5, barWidth)}%`,
                          background: pct >= 75 ? "#22c55e" : pct >= 25 ? "#f59e0b" : "#ef4444",
                          opacity: 0.7,
                        }} />
                      </div>
                      <span className="text-xs font-mono text-surface-200 w-24 text-left">{formatCurrency(value)}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Worst/Best/Expected */}
            <div className="grid grid-cols-3 gap-3">
              <div className="glass-card p-4 text-center">
                <div className="text-xs text-surface-500 mb-1">🔴 بدترین حالت</div>
                <div className="text-lg font-bold text-accent-rose font-mono">{formatCurrency(result.worst_case)}</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-xs text-surface-500 mb-1">📊 میانه</div>
                <div className="text-lg font-bold text-surface-200 font-mono">{formatCurrency(result.median_final)}</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-xs text-surface-500 mb-1">🟢 بهترین حالت</div>
                <div className="text-lg font-bold text-accent-emerald font-mono">{formatCurrency(result.best_case)}</div>
              </div>
            </div>

            {/* Interpretation */}
            <div className="glass-card p-4">
              <h3 className="font-bold text-surface-200 mb-2">📝 تفسیر</h3>
              <div className="text-sm text-surface-400 space-y-1">
                <p>• در <span className="font-bold text-surface-200">{result.simulations.toLocaleString()}</span> شبیه‌سازی اجرا شد</p>
                <p>• احتمال سوددهی: <span className={`font-bold ${result.prob_profit > 60 ? "text-accent-emerald" : "text-accent-rose"}`}>{result.prob_profit}%</span></p>
                <p>• احتمال از دست دادن بیش از ۵۰٪ سرمایه: <span className={`font-bold ${result.prob_ruin < 10 ? "text-accent-emerald" : "text-accent-rose"}`}>{result.prob_ruin}%</span></p>
                <p>• بازده مورد انتظار: <span className="font-bold text-surface-200">{result.expected_return}%</span></p>
              </div>
            </div>
          </>
        )}

        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← بک تست ساده</Link>
          <Link href="/backtest/walk-forward" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">Walk-Forward</Link>
          <Link href="/backtest/generate" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">تولید خودکار</Link>
        </div>
      </div>
    </AppLayout>
  );
}
