"use client";

import { useState, useCallback } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { apiPost } from "@/lib/api";
import Link from "next/link";

interface OOSResult {
  window: number;
  return_pct: number;
  sharpe: number;
  max_dd: number;
  win_rate: number;
  trades: number;
  params: Record<string, unknown>;
}

interface WalkForwardResult {
  strategy: string;
  best_params: Record<string, unknown>;
  oos_results: OOSResult[];
  avg_oos_return: number;
  avg_oos_sharpe: number;
  consistency: number;
  overfitting_score: number;
  windows_tested: number;
}

const STRATEGIES = [
  { value: "moving_average_cross", label: "تقاطع میانگین متحرک" },
  { value: "momentum", label: "مومنتوم" },
  { value: "mean_reversion", label: "بازگشت به میانگین" },
  { value: "breakout", label: "شکست قیمت" },
  { value: "rsi_reversion", label: "بازگشت RSI" },
  { value: "volatility_breakout", label: "شکست نوسان" },
];

export default function WalkForwardPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [strategy, setStrategy] = useState("moving_average_cross");
  const [windows, setWindows] = useState(5);
  const [trainRatio, setTrainRatio] = useState(70);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WalkForwardResult | null>(null);
  const [error, setError] = useState("");

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await apiPost<{ success: boolean; data: WalkForwardResult; error?: { message: string } }>("/backtests/walk-forward", {
        symbol,
        strategy,
        windows,
        train_ratio: trainRatio / 100,
      });
      if (res?.success && res.data) {
        setResult(res.data);
      } else {
        setError(res?.error?.message || "خطا در اجرای بهینه‌سازی");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در اتصال به سرور");
    }
    setLoading(false);
  }, [symbol, strategy, windows, trainRatio]);

  return (
    <AppLayout title="بهینه‌سازی Walk-Forward" subtitle="جلوگیری از overfitting با اعتبارسنجی متقاطع">
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
              <label className="block text-xs text-surface-500 mb-1">تعداد پنجره‌ها: {windows}</label>
              <input type="range" min={3} max={10} value={windows} onChange={(e) => setWindows(parseInt(e.target.value))}
                className="w-full accent-primary-500" />
            </div>
            <div>
              <label className="block text-xs text-surface-500 mb-1">آموزش: {trainRatio}% | تست: {100 - trainRatio}%</label>
              <input type="range" min={50} max={90} value={trainRatio} onChange={(e) => setTrainRatio(parseInt(e.target.value))}
                className="w-full accent-primary-500" />
            </div>
          </div>
          <button onClick={handleRun} disabled={loading}
            className={`mt-4 px-5 py-2 rounded-lg text-sm font-medium transition-colors ${loading ? "bg-surface-700 text-surface-400" : "bg-primary-600 hover:bg-primary-500 text-white"}`}>
            {loading ? "در حال اجرا..." : "🚀 اجرای Walk-Forward"}
          </button>
        </div>

        {error && <div className="glass-card p-4 text-accent-rose text-sm">{error}</div>}

        {/* Results */}
        {result && (
          <>
            {/* Summary */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="glass-card p-3 text-center">
                <div className={`text-2xl font-bold ${result.avg_oos_return > 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {result.avg_oos_return > 0 ? "+" : ""}{result.avg_oos_return}%
                </div>
                <div className="text-xs text-surface-500">میانگین بازده OOS</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className="text-2xl font-bold text-primary-300">{result.avg_oos_sharpe}</div>
                <div className="text-xs text-surface-500">میانگین شارپ OOS</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className={`text-2xl font-bold ${result.consistency > 60 ? "text-accent-emerald" : result.consistency > 40 ? "text-accent-amber" : "text-accent-rose"}`}>
                  {result.consistency}%
                </div>
                <div className="text-xs text-surface-500">ثبات عملکرد</div>
              </div>
              <div className="glass-card p-3 text-center">
                <div className={`text-2xl font-bold ${result.overfitting_score < 30 ? "text-accent-emerald" : result.overfitting_score < 60 ? "text-accent-amber" : "text-accent-rose"}`}>
                  {result.overfitting_score}
                </div>
                <div className="text-xs text-surface-500">امتیاز Overfitting</div>
              </div>
            </div>

            {/* Best Params */}
            <div className="glass-card p-4">
              <h3 className="font-bold text-surface-200 mb-2"> بهترین پارامترها</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(result.best_params).map(([k, v]) => (
                  <span key={k} className="text-xs px-2 py-1 bg-primary-600/15 text-primary-300 rounded-lg font-mono">
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            </div>

            {/* Window Results */}
            <div className="glass-card p-4">
              <h3 className="font-bold text-surface-200 mb-3">📊 نتایج هر پنجره</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="text-right py-2 px-2">پنجره</th>
                      <th className="text-right py-2 px-2">بازده</th>
                      <th className="text-right py-2 px-2">شارپ</th>
                      <th className="text-right py-2 px-2">حداکثر افت</th>
                      <th className="text-right py-2 px-2">نرخ برد</th>
                      <th className="text-right py-2 px-2">معاملات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.oos_results.map((r) => (
                      <tr key={r.window} className="border-b border-surface-800/50">
                        <td className="py-2 px-2 font-mono text-surface-300">{r.window}</td>
                        <td className={`py-2 px-2 font-mono font-bold ${r.return_pct > 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                          {r.return_pct > 0 ? "+" : ""}{r.return_pct}%
                        </td>
                        <td className="py-2 px-2 font-mono text-surface-300">{r.sharpe}</td>
                        <td className="py-2 px-2 font-mono text-accent-rose">{r.max_dd}%</td>
                        <td className="py-2 px-2 font-mono text-surface-300">{r.win_rate}%</td>
                        <td className="py-2 px-2 font-mono text-surface-300">{r.trades}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Interpretation */}
            <div className="glass-card p-4">
              <h3 className="font-bold text-surface-200 mb-2">📝 تفسیر</h3>
              <div className="text-sm text-surface-400 space-y-1">
                <p>• ثبات عملکرد <span className={`font-bold ${result.consistency > 60 ? "text-accent-emerald" : "text-accent-rose"}`}>{result.consistency}%</span> — {result.consistency > 60 ? "عملکرد پایدار" : "نیاز به بهبود"}</p>
                <p>• امتیاز overfitting <span className={`font-bold ${result.overfitting_score < 30 ? "text-accent-emerald" : "text-accent-rose"}`}>{result.overfitting_score}</span> — {result.overfitting_score < 30 ? "کمترین احتمال overfitting" : "احتمال overfitting بالا"}</p>
                <p>• میانگین بازده خارج از نمونه <span className="font-bold text-surface-200">{result.avg_oos_return}%</span></p>
              </div>
            </div>
          </>
        )}

        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← بک تست ساده</Link>
          <Link href="/backtest/generate" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">تولید خودکار</Link>
        </div>
      </div>
    </AppLayout>
  );
}
