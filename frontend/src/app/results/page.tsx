"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

interface BacktestRun {
  id: string;
  name: string;
  status: string;
  progress_pct: number;
  message: string;
  completed_at?: string;
}

interface BacktestResult {
  id: string;
  name: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  final_value: number;
  initial_capital: number;
}

export default function ResultsPage() {
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: () => apiGet<BacktestRun[]>( "/backtests/runs"),
  });

  const { data: result, isLoading: loadingResult } = useQuery({
    queryKey: ["backtest-result", selectedRun],
    queryFn: () => apiGet<BacktestResult>( `/backtests/runs/${selectedRun}/result`),
    enabled: !!selectedRun,
  });

  return (
    <AppLayout title="مرکز نتایج و گزارشات" subtitle="بررسی عملکرد استراتژی‌ها و خروجی‌های شبیه‌سازی">
      <div className="grid lg:grid-cols-3 gap-6">
          {/* Runs List */}
          <div className="lg:col-span-1 space-y-3">
            <h3 className="text-xs font-bold text-surface-500 uppercase tracking-wider mb-3">تاریخچه اجراها</h3>
            {loadingRuns ? (
              <div className="space-y-2">
                {[1,2,3,4,5].map(i => <div key={i} className="h-16 bg-surface-800 animate-pulse rounded-xl" />)}
              </div>
            ) : runs?.map(run => (
              <div 
                key={run.id} 
                onClick={() => setSelectedRun(run.id)}
                className={`p-4 rounded-xl cursor-pointer transition-all border ${
                  selectedRun === run.id ? "bg-primary-600/20 border-primary-600 text-primary-100" : "bg-surface-900/50 border-surface-800 text-surface-400 hover:bg-surface-800"
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-bold text-sm truncate">{run.name}</div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    run.status === "completed" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"
                  }`}>
                    {run.status === "completed" ? "کامل" : "در جریان"}
                  </span>
                </div>
                <div className="text-xs opacity-60 truncate">{run.message}</div>
                {run.status === "completed" && (
                   <div className="mt-2 h-1 bg-surface-800 rounded-full overflow-hidden">
                     <div className="h-full bg-primary-500" style={{ width: `${run.progress_pct}%` }} />
                   </div>
                )}
              </div>
            )) || <div className="text-xs text-surface-600 text-center py-4">هیچ اجرای ثبت شده‌ای یافت نشد</div>}
          </div>

          {/* Result Detail */}
          <div className="lg:col-span-2 space-y-6">
            {!selectedRun ? (
              <div className="glass-card h-full flex flex-col items-center justify-center text-center p-12">
                <span className="text-4xl mb-4">📈</span>
                <h3 className="text-lg font-bold text-surface-200">نتیجه‌ای برای نمایش نیست</h3>
                <p className="text-sm text-surface-500 mt-2">یک اجرای بک‌تست را از لیست سمت راست انتخاب کنید تا تحلیل دقیق آن را مشاهده کنید.</p>
              </div>
            ) : loadingResult ? (
              <div className="space-y-6">
                <div className="h-32 bg-surface-800 animate-pulse rounded-2xl" />
                <div className="h-64 bg-surface-800 animate-pulse rounded-2xl" />
              </div>
            ) : result ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: "بازده کل", value: `${result.total_return_pct}%`, color: result.total_return_pct >= 0 ? "text-accent-emerald" : "text-accent-rose" },
                    { label: "نسبت شارپ", value: result.sharpe_ratio.toFixed(2), color: result.sharpe_ratio >= 1 ? "text-accent-emerald" : "text-accent-amber" },
                    { label: "بیشترین کاهش", value: `${result.max_drawdown_pct}%`, color: "text-accent-rose" },
                    { label: "نرخ برد", value: `${result.win_rate}%`, color: "text-accent-cyan" },
                  ].map((stat, i) => (
                    <div key={i} className="glass-card p-4 text-center">
                      <div className="text-xs text-surface-500 mb-1">{stat.label}</div>
                      <div className={`text-xl font-black ${stat.color}`}>{stat.value}</div>
                    </div>
                  ))}
                </div>

                <div className="glass-card p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="font-bold text-surface-200">تحلیل عملکرد {result.name}</h3>
                    <button className="text-xs bg-surface-800 hover:bg-surface-700 text-surface-300 px-3 py-1.5 rounded-lg border border-surface-700 transition">
                      دانلود گزارش PDF
                    </button>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div className="space-y-4">
                      <div className="flex justify-between items-center p-3 bg-surface-900/50 rounded-lg">
                        <span className="text-sm text-surface-400">سرمایه اولیه:</span>
                        <span className="font-mono text-surface-200">{result.initial_capital.toLocaleString()} ریال</span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-surface-900/50 rounded-lg">
                        <span className="text-sm text-surface-400">ارزش نهایی:</span>
                        <span className="font-mono text-surface-200">{result.final_value.toLocaleString()} ریال</span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-surface-900/50 rounded-lg">
                        <span className="text-sm text-surface-400">تعداد معاملات:</span>
                        <span className="font-mono text-surface-200">{result.total_trades} معامله</span>
                      </div>
                    </div>
                    <div className="bg-surface-900/30 p-4 rounded-xl border border-surface-800">
                      <h4 className="text-sm font-bold text-surface-300 mb-3">تفسیر تحلیلگر</h4>
                      <p className="text-xs text-surface-500 leading-relaxed">
                        {result.sharpe_ratio > 1.5 ? "این استراتژی بازدهی بسیار بهینه نسبت به ریسک دارد." : 
                         result.sharpe_ratio > 1 ? "عملکرد استراتژی رضایت‌بخش است و ریسک مدیریت شده است." : 
                         "ریسک این استراتژی بالا است و احتمال Drawdown شدید وجود دارد."}
                      </p>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-surface-500">نتایج برای این اجرا یافت نشد یا هنوز در حال پردازش است.</div>
            )}
          </div>
        </div>
    </AppLayout>
  );
}
