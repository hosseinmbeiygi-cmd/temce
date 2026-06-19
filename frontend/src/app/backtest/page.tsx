"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";

interface Strategy {
  name: string;
  type: string;
  params: { name: string; type: string; default: unknown }[];
}

interface BacktestRun {
  id: string;
  name: string;
  status: string;
  progress_pct: number;
  message: string;
}

interface BacktestResult {
  id: string;
  name: string;
  status: string;
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  initial_capital: number;
  final_value: number;
  equity_curve: { timestamp: string; nav: number }[];
  trades: { instrument_id: string; side: string; quantity: number; price: number; pnl: number }[];
  metrics: Record<string, number>;
  completed_at: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const SYMBOLS = ["فولاد", "شپنا", "وبملت", "خودرو", "فملی", "ذوب", "کگل", "چادر"];

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [resultLoading, setResultLoading] = useState(false);
  const [name, setName] = useState("بک‌تست جدید");
  const [symbols, setSymbols] = useState(["فولاد"]);
  const [strategyType, setStrategyType] = useState("moving_average_cross");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState(1000000000);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchStrategies();
    fetchRuns();
  }, []);

  async function fetchStrategies() {
    try {
      const res = await fetch(`${API}/backtests/strategies`);
      const json = await res.json();
      if (json.success) setStrategies(json.data);
    } catch { /* ignore */ }
  }

  async function fetchRuns() {
    try {
      const res = await fetch(`${API}/backtests/runs`);
      const json = await res.json();
      if (json.success) setRuns(json.data || []);
    } catch { /* ignore */ }
  }

  async function handleRun() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/backtests/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          symbols,
          strategy_type: strategyType,
          strategy_params: {},
          start_date: startDate,
          end_date: endDate,
          initial_capital: capital,
        }),
      });
      const json = await res.json();
      if (json.success) {
        await fetchRuns();
      } else {
        setError(json.error?.message || "خطا در اجرای بک‌تست");
      }
    } catch (e) {
      setError("خطا در ارتباط با سرور");
    }
    setLoading(false);
  }

  async function handleViewResult(runId: string) {
    setResultLoading(true);
    try {
      const res = await fetch(`${API}/backtests/runs/${runId}/result`);
      const json = await res.json();
      if (json.success) setSelectedResult(json.data as BacktestResult);
    } catch { /* ignore */ }
    setResultLoading(false);
  }

  function formatRials(v: number) {
    return new Intl.NumberFormat("fa-IR").format(Math.round(v));
  }

  return (
    <div className="min-h-screen flex bg-gray-50 font-sans" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">بک‌تست استراتژی</h1>

        {error && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">{error}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">تنظیمات بک‌تست</h2>

            <label className="block mb-2 text-sm text-gray-600">نام</label>
            <input className="w-full border rounded-lg px-3 py-2 mb-3 text-sm" value={name} onChange={e => setName(e.target.value)} />

            <label className="block mb-2 text-sm text-gray-600">نمادها</label>
            <div className="flex flex-wrap gap-1 mb-3">
              {SYMBOLS.map(s => (
                <button key={s} onClick={() => setSymbols(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])}
                  className={`px-3 py-1 text-xs rounded-full border ${symbols.includes(s) ? "bg-blue-600 text-white border-blue-600" : "bg-gray-100 text-gray-600 border-gray-300"}`}>
                  {s}
                </button>
              ))}
            </div>

            <label className="block mb-2 text-sm text-gray-600">استراتژی</label>
            <select className="w-full border rounded-lg px-3 py-2 mb-3 text-sm" value={strategyType} onChange={e => setStrategyType(e.target.value)}>
              {strategies.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>

            <div className="grid grid-cols-2 gap-2 mb-3">
              <div>
                <label className="block mb-1 text-sm text-gray-600">از تاریخ</label>
                <input type="date" className="w-full border rounded-lg px-3 py-2 text-sm" value={startDate} onChange={e => setStartDate(e.target.value)} />
              </div>
              <div>
                <label className="block mb-1 text-sm text-gray-600">تا تاریخ</label>
                <input type="date" className="w-full border rounded-lg px-3 py-2 text-sm" value={endDate} onChange={e => setEndDate(e.target.value)} />
              </div>
            </div>

            <label className="block mb-2 text-sm text-gray-600">سرمایه اولیه (ریال)</label>
            <input type="number" className="w-full border rounded-lg px-3 py-2 mb-4 text-sm" value={capital} onChange={e => setCapital(Number(e.target.value))} />

            <button onClick={handleRun} disabled={loading}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">
              {loading ? "در حال اجرا..." : "اجرای بک‌تست"}
            </button>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">بک‌تست‌های انجام شده</h2>
              {runs.length === 0 ? (
                <p className="text-gray-400 text-sm">هنوز بک‌تستی اجرا نشده</p>
              ) : (
                <div className="space-y-2">
                  {runs.map(run => (
                    <div key={run.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="font-medium text-gray-700">{run.name}</p>
                        <p className="text-xs text-gray-400">{run.status} — {run.progress_pct}%</p>
                      </div>
                      <button onClick={() => handleViewResult(run.id)} className="text-blue-600 text-sm hover:underline">
                        مشاهده نتیجه
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {resultLoading && <div className="text-center py-4 text-gray-500">در حال دریافت نتیجه...</div>}

            {selectedResult && (
              <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
                <h2 className="text-lg font-semibold text-gray-700 mb-4">نتیجه بک‌تست: {selectedResult.name}</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  {[
                    { label: "بازده کل", value: `${selectedResult.total_return_pct}%`, color: selectedResult.total_return_pct >= 0 ? "text-green-600" : "text-red-600" },
                    { label: "بازده سالانه", value: `${selectedResult.annualized_return_pct}%`, color: "text-gray-700" },
                    { label: "نسبت شارپ", value: selectedResult.sharpe_ratio.toFixed(2), color: selectedResult.sharpe_ratio >= 1 ? "text-green-600" : "text-yellow-600" },
                    { label: "بیشترین کاهش", value: `${selectedResult.max_drawdown_pct}%`, color: "text-red-600" },
                    { label: "درصد برندگی", value: `${selectedResult.win_rate}%`, color: selectedResult.win_rate >= 50 ? "text-green-600" : "text-red-600" },
                    { label: "تعداد معاملات", value: selectedResult.total_trades.toString(), color: "text-gray-700" },
                    { label: "سرمایه اولیه", value: `${formatRials(selectedResult.initial_capital)} ریال`, color: "text-gray-700" },
                    { label: "ارزش نهایی", value: `${formatRials(selectedResult.final_value)} ریال`, color: selectedResult.final_value >= selectedResult.initial_capital ? "text-green-600" : "text-red-600" },
                  ].map(item => (
                    <div key={item.label} className="bg-gray-50 rounded-lg p-3 text-center">
                      <p className="text-xs text-gray-500 mb-1">{item.label}</p>
                      <p className={`text-lg font-bold ${item.color}`}>{item.value}</p>
                    </div>
                  ))}
                </div>

                {selectedResult.equity_curve.length > 0 && (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-600 mb-2">منحنی سرمایه</h3>
                    <div className="bg-gray-50 rounded-lg p-3 h-48 flex items-end gap-0.5 overflow-x-auto">
                      {selectedResult.equity_curve.map((pt, i) => {
                        const maxNav = Math.max(...selectedResult.equity_curve.map(p => p.nav));
                        const minNav = Math.min(...selectedResult.equity_curve.map(p => p.nav));
                        const range = maxNav - minNav || 1;
                        const h = ((pt.nav - minNav) / range) * 100;
                        return <div key={i} className="w-2 bg-blue-500 rounded-t" style={{ height: `${Math.max(h, 1)}%` }} title={formatRials(pt.nav)} />;
                      })}
                    </div>
                  </div>
                )}

                {selectedResult.trades.length > 0 && (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-600 mb-2">معاملات</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-gray-100">
                            <th className="p-2 text-right">نماد</th>
                            <th className="p-2 text-right">طرف</th>
                            <th className="p-2 text-right">تعداد</th>
                            <th className="p-2 text-right">قیمت</th>
                            <th className="p-2 text-right">سود/زیان</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedResult.trades.map((t, i) => (
                            <tr key={i} className="border-b border-gray-100">
                              <td className="p-2">{t.instrument_id}</td>
                              <td className="p-2">{t.side === "BUY" ? "خرید" : "فروش"}</td>
                              <td className="p-2">{formatRials(t.quantity)}</td>
                              <td className="p-2">{formatRials(t.price)}</td>
                              <td className={`p-2 ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>{formatRials(t.pnl)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
