"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiPost, apiGet } from "@/lib/api";

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

// API is handled by apiGet/apiPost from @/lib/api
const SYMBOLS = ["فولاد", "شپنا", "وبملت", "خودرو", "فملی", "ذوب", "کگل", "چادر"];

export default function BacktestPage() {
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [formData, setFormData] = useState({
    name: "بک‌تست جدید",
    symbols: ["فولاد"],
    strategyType: "moving_average_cross",
    startDate: (() => {
      const d = new Date(); d.setFullYear(d.getFullYear() - 1);
      return d.toISOString().split("T")[0];
    })(),
    endDate: new Date().toISOString().split("T")[0],
    capital: 1000000000,
  });

  const { data: strategies, isLoading: loadingStrats } = useQuery({
    queryKey: ["backtest-strategies"],
    queryFn: async () => {
      return await apiGet<any>('/backtests/strategies');
    },
  });

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: async () => {
      return await apiGet<any>('/backtests/runs');
    },
    refetchInterval: 5000,
  });

  const { data: result, isLoading: loadingResult } = useQuery({
    queryKey: ["backtest-result", selectedResult?.id],
    queryFn: async () => {
      if (!selectedResult?.id) return null;
      return await apiGet<any>(`/backtests/runs/${selectedResult.id}/result`);
    },
    enabled: !!selectedResult,
  });

  const runMutation = useMutation({
    mutationFn: async (data: any) => {
      return await apiPost<any>('/backtests/run', data);
    },
    onSuccess: () => {
      toast.success("بک‌تست با موفقیت شروع شد");
    },
    onError: (err: any) => toast.error(err.message),
  });

  function formatRials(v: number) {
    return new Intl.NumberFormat("fa-IR").format(Math.round(v));
  }

  return (
    <AppLayout title="بک‌تست استراتژی">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 glass-card p-5">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">تنظیمات بک‌تست</h2>

            <label className="block mb-2 text-sm text-gray-600">نام</label>
            <input className="w-full border rounded-lg px-3 py-2 mb-3 text-sm" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />

            <label className="block mb-2 text-sm text-gray-600">نمادها</label>
            <div className="flex flex-wrap gap-1 mb-3">
              {SYMBOLS.map(s => (
                <button key={s} onClick={() => setFormData(prev => ({...prev, symbols: prev.symbols.includes(s) ? prev.symbols.filter(x => x !== s) : [...prev.symbols, s]}))}
                  className={`px-3 py-1 text-xs rounded-full border ${formData.symbols.includes(s) ? "bg-blue-600 text-white border-blue-600" : "bg-gray-100 text-gray-600 border-gray-300"}`}>
                  {s}
                </button>
              ))}
            </div>

            <label className="block mb-2 text-sm text-gray-600">استراتژی</label>
            <select className="w-full border rounded-lg px-3 py-2 mb-3 text-sm" value={formData.strategyType} onChange={e => setFormData({...formData, strategyType: e.target.value})}>
              {strategies?.map((s: any) => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>

            <div className="grid grid-cols-2 gap-2 mb-3">
              <div>
                <label className="block mb-1 text-sm text-gray-600">از تاریخ</label>
                <input type="date" className="w-full border rounded-lg px-3 py-2 text-sm" value={formData.startDate} onChange={e => setFormData({...formData, startDate: e.target.value})} />
              </div>
              <div>
                <label className="block mb-1 text-sm text-gray-600">تا تاریخ</label>
                <input type="date" className="w-full border rounded-lg px-3 py-2 text-sm" value={formData.endDate} onChange={e => setFormData({...formData, endDate: e.target.value})} />
              </div>
            </div>

            <label className="block mb-2 text-sm text-gray-600">سرمایه اولیه (ریال)</label>
            <input type="number" className="w-full border rounded-lg px-3 py-2 mb-4 text-sm" value={formData.capital} onChange={e => setFormData({...formData, capital: Number(e.target.value)})} />

            <button onClick={() => runMutation.mutate({
              name: formData.name,
              symbols: formData.symbols,
              strategy_type: formData.strategyType,
              strategy_params: {},
              start_date: formData.startDate,
              end_date: formData.endDate,
              initial_capital: formData.capital,
            })} disabled={runMutation.isPending}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">
              {runMutation.isPending ? "در حال اجرا..." : "اجرای بک‌تست"}
            </button>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">بک‌تست‌های انجام شده</h2>
              {loadingRuns ? (
                <div className="space-y-2">
                  {[1,2,3].map(i => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}
                </div>
              ) : runs?.length === 0 ? (
                <p className="text-gray-400 text-sm">هنوز بک‌تستی اجرا نشده</p>
              ) : (
                <div className="space-y-2">
                  {runs?.map((run: any) => (
                    <div key={run.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="font-medium text-gray-700">{run.name}</p>
                        <p className="text-xs text-gray-400">{run.status} — {run.progress_pct}%</p>
                      </div>
                      <button onClick={() => setSelectedResult({ id: run.id } as any)} className="text-blue-600 text-sm hover:underline">
                        مشاهده نتیجه
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {loadingResult ? (
              <Skeleton className="h-96 w-full rounded-2xl" />
            ) : result ? (
              <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
                <h2 className="text-lg font-semibold text-gray-700 mb-4">نتیجه بک‌تست: {result.name}</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  {[
                    { label: "بازده کل", value: `${result.total_return_pct}%`, color: result.total_return_pct >= 0 ? "text-green-600" : "text-red-600" },
                    { label: "بازده سالانه", value: `${result.annualized_return_pct}%`, color: "text-gray-700" },
                    { label: "نسبت شارپ", value: result.sharpe_ratio.toFixed(2), color: result.sharpe_ratio >= 1 ? "text-green-600" : "text-yellow-600" },
                    { label: "بیشترین کاهش", value: `${result.max_drawdown_pct}%`, color: "text-red-600" },
                    { label: "درصد برندگی", value: `${result.win_rate}%`, color: result.win_rate >= 50 ? "text-green-600" : "text-red-600" },
                    { label: "تعداد معاملات", value: result.total_trades.toString(), color: "text-gray-700" },
                    { label: "سرمایه اولیه", value: `${formatRials(result.initial_capital)} ریال`, color: "text-gray-700" },
                    { label: "ارزش نهایی", value: `${formatRials(result.final_value)} ریال`, color: result.final_value >= result.initial_capital ? "text-green-600" : "text-red-600" },
                  ].map(item => (
                    <div key={item.label} className="bg-gray-50 rounded-lg p-3 text-center">
                      <p className="text-xs text-gray-500 mb-1">{item.label}</p>
                      <p className={`text-lg font-bold ${item.color}`}>{item.value}</p>
                    </div>
                  ))}
                </div>
                {/* ...Equity Curve and Trades table can be added here similarly to Portfolio page... */}
              </div>
            ) : null}
          </div>
        </div>
    </AppLayout>
  );
}
