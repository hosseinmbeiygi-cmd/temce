"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiPost, apiGet, extractArray } from "@/lib/api";

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

function toJalali(gy: number, gm: number, gd: number): string {
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let gy2 = gm > 2 ? gy + 1 : gy;
  let days = 355666 + (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) + gd + g_d_m[gm - 1];
  let jy = -1595 + (33 * Math.floor(days / 12053));
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
  let jm: number, jd: number;
  if (days < 186) { jm = 1 + Math.floor(days / 31); jd = 1 + (days % 31); }
  else { jm = 7 + Math.floor((days - 186) / 30); jd = 1 + ((days - 186) % 30); }
  return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
}

function gregorianToJalaliStr(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return toJalali(y, m, d);
}

function jalaliToDate(jalaliStr: string): string {
  const [jy, jm, jd] = jalaliStr.split("/").map(Number);
  let gy = jy + 1595;
  let days = -355668 + (365 * jy) + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4) + jd + (jm < 7 ? (jm - 1) * 31 : ((jm - 7) * 30 + 186));
  let gd = days % 365;
  if (gd < 0) { gy--; gd += 365; }
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let gm = 1;
  for (let i = 0; i < 12; i++) { if (gd < g_d_m[i]) break; gm = i + 1; }
  const gd2 = gd - (gm === 1 ? 0 : g_d_m[gm - 1]);
  return `${gy}-${String(gm).padStart(2, "0")}-${String(gd2).padStart(2, "0")}`;
}

export default function BacktestPage() {
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [symbolSearch, setSymbolSearch] = useState("");
  const [startDateJalali, setStartDateJalali] = useState(() => {
    const now = new Date();
    now.setFullYear(now.getFullYear() - 1);
    return toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
  });
  const [endDateJalali, setEndDateJalali] = useState(() => {
    const now = new Date();
    return toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
  });

  const [formData, setFormData] = useState({
    name: "بک‌تست جدید",
    symbols: ["فولاد"],
    strategyType: "moving_average_cross",
    capital: 1000000000,
  });

  // Load symbols from instruments table
  const { data: symbolsData } = useQuery({
    queryKey: ["backtest-symbols"],
    queryFn: async () => {
      try {
        const res = await apiGet<unknown>("/instruments?page=1&page_size=2000");
        const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: { symbol: string; name: string }[] } }).data : null;
        return d?.items || [];
      } catch { return []; }
    },
  });

  const allSymbols: { symbol: string; name: string }[] = symbolsData || [];
  const filteredSymbols = symbolSearch
    ? allSymbols.filter(s => s.symbol.includes(symbolSearch) || s.name.includes(symbolSearch)).slice(0, 30)
    : allSymbols.slice(0, 30);

  const { data: strategies } = useQuery({
    queryKey: ["backtest-strategies"],
    queryFn: async () => {
      const res = await apiGet<unknown>('/backtests/strategies');
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: Record<string, unknown>[] } }).data : null;
      return d?.items || [];
    },
  });

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: async () => {
      const res = await apiGet<unknown>('/backtests/runs');
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: Record<string, unknown>[] } }).data : null;
      return d?.items || [];
    },
    refetchInterval: 5000,
  });

  const { data: result, isLoading: loadingResult } = useQuery({
    queryKey: ["backtest-result", selectedResult?.id],
    queryFn: async () => {
      if (!selectedResult?.id) return null;
      const res = await apiGet<unknown>(`/backtests/runs/${selectedResult.id}/result`);
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: Record<string, unknown> }).data : null;
      return d;
    },
    enabled: !!selectedResult,
  });

  const runMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      return await apiPost<Record<string, unknown>>('/backtests/run', data);
    },
    onSuccess: () => toast.success("بک‌تست با موفقیت شروع شد"),
    onError: (err: Error) => toast.error(err.message),
  });

  function formatRials(v: number) {
    return new Intl.NumberFormat("fa-IR").format(Math.round(v));
  }

  return (
    <AppLayout title="بک‌تست استراتژی" subtitle="تست استراتژی روی داده‌های واقعی تاریخی">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 glass-card p-5">
          <h2 className="text-base font-bold text-surface-200 mb-4">تنظیمات بک‌تست</h2>

          <label className="block mb-2 text-sm text-surface-400 font-bold">نام</label>
          <input className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 mb-3 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
            value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />

          <label className="block mb-2 text-sm text-surface-400 font-bold">نمادها ({formData.symbols.length} انتخاب شده)</label>
          <input type="text" value={symbolSearch} onChange={e => setSymbolSearch(e.target.value)}
            placeholder="جستجوی نماد..." className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 mb-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500" />
          <div className="flex flex-wrap gap-1 mb-3 max-h-32 overflow-y-auto">
            {filteredSymbols.map(s => (
              <button key={s.symbol} onClick={() => setFormData(prev => ({...prev, symbols: prev.symbols.includes(s.symbol) ? prev.symbols.filter(x => x !== s.symbol) : [...prev.symbols, s.symbol]}))}
                className={`px-2 py-1 text-xs rounded-full border font-bold ${formData.symbols.includes(s.symbol) ? "bg-primary-600 text-white border-primary-600" : "bg-surface-800 text-surface-300 border-surface-700 hover:border-surface-500"}`}>
                {s.symbol}
              </button>
            ))}
          </div>

          <label className="block mb-2 text-sm text-surface-400 font-bold">استراتژی</label>
          <select className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 mb-3 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
            value={formData.strategyType} onChange={e => setFormData({...formData, strategyType: e.target.value})}>
            {strategies?.map((s: Record<string, unknown>, i: number) => (
              <option key={`${s.name}-${i}`} value={String(s.name ?? "")}>{String(s.name ?? "")}</option>
            ))}
          </select>

          <div className="grid grid-cols-2 gap-2 mb-3">
            <div>
              <label className="block mb-1 text-sm text-surface-400 font-bold">از تاریخ (شمسی)</label>
              <input type="text" dir="ltr" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
                value={startDateJalali} onChange={e => setStartDateJalali(e.target.value)} placeholder="1403/01/01" />
              <div className="text-[10px] text-surface-600 mt-1">{gregorianToJalaliStr(jalaliToDate(startDateJalali) || "2024-01-01")}</div>
            </div>
            <div>
              <label className="block mb-1 text-sm text-surface-400 font-bold">تا تاریخ (شمسی)</label>
              <input type="text" dir="ltr" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
                value={endDateJalali} onChange={e => setEndDateJalali(e.target.value)} placeholder="1404/04/01" />
              <div className="text-[10px] text-surface-600 mt-1">{gregorianToJalaliStr(jalaliToDate(endDateJalali) || "2025-01-01")}</div>
            </div>
          </div>

          <label className="block mb-2 text-sm text-surface-400 font-bold">سرمایه اولیه (ریال)</label>
          <input type="number" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 mb-4 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
            value={formData.capital} onChange={e => setFormData({...formData, capital: Number(e.target.value)})} />

          <button onClick={() => runMutation.mutate({
            name: formData.name,
            symbols: formData.symbols,
            strategy_type: formData.strategyType,
            strategy_params: {},
            start_date: jalaliToDate(startDateJalali),
            end_date: jalaliToDate(endDateJalali),
            initial_capital: formData.capital,
          })} disabled={runMutation.isPending || formData.symbols.length === 0}
            className="w-full bg-primary-600 text-white py-2.5 rounded-lg font-bold hover:bg-primary-500 disabled:opacity-50 transition-colors">
            {runMutation.isPending ? "در حال اجرا..." : "اجرای بک‌تست"}
          </button>
          {formData.symbols.length === 0 && <p className="text-xs text-accent-rose mt-2">حداقل یک نماد انتخاب کنید</p>}
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="glass-card p-5">
            <h2 className="text-base font-bold text-surface-200 mb-4">بک‌تست‌های انجام شده</h2>
            {loadingRuns ? (
              <div className="space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}</div>
            ) : runs?.length === 0 ? (
              <p className="text-surface-500 text-sm">هنوز بک‌تستی اجرا نشده</p>
            ) : (
              <div className="space-y-2">
                {runs?.map((run: Record<string, unknown>, i: number) => (
                  <div key={String(run.id ?? i)} className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg hover:bg-surface-800 transition-colors">
                    <div>
                      <p className="font-bold text-surface-200">{String(run.name ?? "")}</p>
                      <p className="text-xs text-surface-500">{String(run.status ?? "")} — {String(run.progress_pct ?? "")}%</p>
                    </div>
                    <button onClick={() => setSelectedResult({ id: String(run.id) } as BacktestResult)}
                      className="text-primary-400 text-sm font-bold hover:text-primary-300">مشاهده نتیجه</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {loadingResult ? (
            <Skeleton className="h-96 w-full rounded-2xl" />
          ) : result ? (
            <div className="glass-card p-5">
              <h2 className="text-base font-bold text-surface-200 mb-4">نتیجه: {String(result.name ?? "")}</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {[
                  { label: "بازده کل", value: `${String(result.total_return_pct ?? "")}%`, color: Number(result.total_return_pct) >= 0 ? "text-accent-emerald" : "text-accent-rose" },
                  { label: "بازده سالانه", value: `${String(result.annualized_return_pct ?? "")}%`, color: "text-surface-200" },
                  { label: "شارپ", value: Number(result.sharpe_ratio || 0).toFixed(2), color: Number(result.sharpe_ratio) >= 1 ? "text-accent-emerald" : "text-accent-amber" },
                  { label: "Max DD", value: `${String(result.max_drawdown_pct ?? "")}%`, color: "text-accent-rose" },
                  { label: "Win Rate", value: `${String(result.win_rate ?? "")}%`, color: Number(result.win_rate) >= 50 ? "text-accent-emerald" : "text-accent-rose" },
                  { label: "معاملات", value: String(result.total_trades ?? ""), color: "text-surface-200" },
                  { label: "سرمایه اولیه", value: `${formatRials(Number(result.initial_capital) || 0)}`, color: "text-surface-200" },
                  { label: "ارزش نهایی", value: `${formatRials(Number(result.final_value) || 0)}`, color: Number(result.final_value) >= Number(result.initial_capital) ? "text-accent-emerald" : "text-accent-rose" },
                ].map(item => (
                  <div key={item.label} className="bg-surface-800/50 rounded-lg p-3 text-center">
                    <p className="text-xs text-surface-500 mb-1">{item.label}</p>
                    <p className={`text-sm font-bold font-mono ${item.color}`}>{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </AppLayout>
  );
}
