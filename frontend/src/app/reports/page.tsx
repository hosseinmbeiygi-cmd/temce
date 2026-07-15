"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";

// ------ Types -------------------------------------------------------------------------------------------------------------
interface MarketOverview {
  total_instruments: number;
  gainers: number;
  losers: number;
  avg_change_pct: number;
  total_value: number;
  total_volume: number;
}

interface QuoteSummary {
  symbol: string;
  price_last: number;
  price_change_pct: number;
  volume: number;
  value: number;
}

interface SectorItem {
  name: string;
  count: number;
  avg_change: number;
  total_value: number;
}

interface MarketReport {
  title: string;
  report_type: string;
  generated_at: string;
  date: string;
  overview: MarketOverview;
  top_gainers: QuoteSummary[];
  top_losers: QuoteSummary[];
  most_active: QuoteSummary[];
  sector_summary: SectorItem[];
}

interface QuoteRow {
  date: string;
  price_close: number;
  price_open: number;
  price_high: number;
  price_low: number;
  volume: number;
  price_change_pct: number;
}

interface SymbolReport {
  title: string;
  report_type: string;
  generated_at: string;
  symbol: string;
  instrument: Record<string, unknown>;
  recent_quotes: QuoteRow[];
  summary: Record<string, unknown>;
}

interface BacktestReportData {
  title: string;
  report_type: string;
  generated_at: string;
  strategy_name: string;
  initial_capital: number;
  final_capital: number;
  total_return: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  win_rate: number;
  metrics: Record<string, number>;
  completed_at: string;
}

type ReportTab = "market" | "symbol" | "backtest";

const TABS: { key: ReportTab; label: string; icon: string }[] = [
  { key: "market", label: "گزارش بازار", icon: "📊" },
  { key: "symbol", label: "گزارش نماد", icon: "📈" },
  { key: "backtest", label: "گزارش بک‌تست", icon: "📋" },
];

// ------ Helpers ------------------------------------------------------------------------------------------------------------
function formatCurrency(v: number): string {
  if (v >= 1e12) return (v / 1e12).toFixed(2) + "T";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function formatPct(v: number): { text: string; color: string; icon: string } {
  if (v > 0) return { text: `+${v.toFixed(2)}%`, color: "text-accent-emerald", icon: "trending_up" };
  if (v < 0) return { text: `${v.toFixed(2)}%`, color: "text-accent-rose", icon: "trending_down" };
  return { text: "0.00%", color: "text-surface-400", icon: "remove" };
}

// ------ Market Report Tab --------------------------------------------------------------------------------------------------
function MarketReportTab({ data, loading }: { data: MarketReport | null; loading: boolean }) {
  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}</div>;
  if (!data) return <EmptyState icon="📊" message="گزارش بازار در دسترس نیست" sub="برای تولید گزارش، از endpoint /reports/market استفاده کنید" />;

  const fmt = formatPct(data.overview?.avg_change_pct ?? 0);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="glass-card p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <p className="text-xs text-surface-500">تولید شده در</p>
          <p className="text-sm font-mono text-surface-300">{formatDateShamsi(data.generated_at)}</p>
        </div>
        <div className="flex items-center gap-4 text-xs text-surface-500">
          <span>گزارش: {data.title}</span>
          <span className="material-icons text-surface-600">description</span>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="glass-card p-3 text-center">
          <p className="text-2xl font-bold text-surface-100">{data.overview?.total_instruments ?? "—"}</p>
          <p className="text-xs text-surface-500">کل نمادها</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-2xl font-bold text-accent-emerald">{data.overview?.gainers ?? "—"}</p>
          <p className="text-xs text-surface-500">مثبت</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-2xl font-bold text-accent-rose">{data.overview?.losers ?? "—"}</p>
          <p className="text-xs text-surface-500">منفی</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className={`text-2xl font-bold ${fmt.color}`}>{fmt.text}</p>
          <p className="text-xs text-surface-500">میانگین تغییر</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-2xl font-bold text-primary-300">{formatCurrency(data.overview?.total_value ?? 0)}</p>
          <p className="text-xs text-surface-500">کل ارزش</p>
        </div>
      </div>

      {/* Gainers + Losers */}
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="🏆 بیشترین رشد" subtitle={data.top_gainers?.length ? data.top_gainers.length + " نماد" : ""}>
          {data.top_gainers?.length ? (
            <div className="space-y-1">
              {data.top_gainers.map((q, i) => (
                <div key={`${q.symbol}-${i}`} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface-800/50">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-500 font-mono w-5">{i + 1}</span>
                    <span className="font-bold text-surface-200 text-sm">{q.symbol}</span>
                  </div>
                  <span className="text-sm font-bold font-mono text-accent-emerald">+{q.price_change_pct?.toFixed(2)}%</span>
                </div>
              ))}
            </div>
          ) : <p className="text-surface-500 text-sm text-center py-4">داده‌ای موجود نیست</p>}
        </Card>

        <Card title="📉 بیشترین کاهش">
          {data.top_losers?.length ? (
            <div className="space-y-1">
              {data.top_losers.map((q, i) => (
                <div key={`${q.symbol}-${i}`} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface-800/50">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-500 font-mono w-5">{i + 1}</span>
                    <span className="font-bold text-surface-200 text-sm">{q.symbol}</span>
                  </div>
                  <span className="text-sm font-bold font-mono text-accent-rose">{q.price_change_pct?.toFixed(2)}%</span>
                </div>
              ))}
            </div>
          ) : <p className="text-surface-500 text-sm text-center py-4">داده‌ای موجود نیست</p>}
        </Card>
      </div>

      {/* Most Active */}
      <Card title="⚡ پرمعامله‌ترین‌ها">
        {data.most_active?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="pb-2 px-3">#</th>
                  <th className="pb-2 px-3">نماد</th>
                  <th className="pb-2 px-3">قیمت</th>
                  <th className="pb-2 px-3">تغییر</th>
                  <th className="pb-2 px-3">حجم</th>
                  <th className="pb-2 px-3">ارزش</th>
                </tr>
              </thead>
              <tbody>
                {data.most_active.map((q, i) => {
                  const ch = formatPct(q.price_change_pct ?? 0);
                  return (
                    <tr key={`${q.symbol}-${i}`} className="border-b border-surface-800/50 hover:bg-white/5">
                      <td className="py-2.5 px-3 text-surface-500 font-mono text-xs">{i + 1}</td>
                      <td className="py-2.5 px-3 font-bold text-surface-200">{q.symbol}</td>
                      <td className="py-2.5 px-3 font-mono text-surface-200">{q.price_last?.toLocaleString("fa-IR")}</td>
                      <td className={`py-2.5 px-3 font-mono ${ch.color}`}>{ch.text}</td>
                      <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{q.volume?.toLocaleString("fa-IR")}</td>
                      <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{formatCurrency(q.value ?? 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <p className="text-surface-500 text-sm text-center py-4">داده‌ای موجود نیست</p>}
      </Card>

      {/* Sector Summary */}
      {data.sector_summary?.length > 0 && (
        <Card title="🏭 خلاصه صنایع">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.sector_summary.map((s, si) => (
              <div key={`${s.name}-${si}`} className="bg-surface-800/30 rounded-xl p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-bold text-surface-200">{s.name}</span>
                  <span className="text-xs text-surface-500">{s.count} نماد</span>
                </div>
                <div className={`text-lg font-bold font-mono ${s.avg_change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {s.avg_change >= 0 ? "+" : ""}{s.avg_change?.toFixed(2)}%
                </div>
                <div className="text-xs text-surface-500 mt-1">ارزش: {formatCurrency(s.total_value)}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ------ Symbol Report Tab --------------------------------------------------------------------------------------------------
const POPULAR_SYMBOLS = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران", "وغدیر"];

function SymbolReportTab() {
  const [symbol, setSymbol] = useState("فولاد");
  const [inputVal, setInputVal] = useState("فولاد");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["symbol-report", symbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: SymbolReport }>(`/reports/symbol/${encodeURIComponent(symbol)}`);
      return res?.data ?? null;
    },
    enabled: !!symbol,
  });

  const ch = data?.recent_quotes?.length
    ? formatPct(data.recent_quotes[data.recent_quotes.length - 1]?.price_change_pct ?? 0)
    : null;

  return (
    <div className="space-y-5">
      {/* Search */}
      <div className="glass-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-surface-500 mb-1.5">نام نماد</label>
            <input value={inputVal} onChange={e => setInputVal(e.target.value)}
              onKeyDown={e => e.key === "Enter" && setSymbol(inputVal)}
              placeholder="مثال: فولاد"
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500" />
          </div>
          <button onClick={() => setSymbol(inputVal)}
            className="px-5 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-1.5">
            <span className="material-icons text-sm">search</span>
            تولید گزارش
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          <span className="text-[10px] text-surface-600 mt-0.5 ml-1">سریع:</span>
          {POPULAR_SYMBOLS.map(s => (
            <button key={s} onClick={() => { setInputVal(s); setSymbol(s); }}
              className={`text-xs px-2.5 py-1 rounded-lg transition-all ${symbol === s ? "bg-primary-600/20 text-primary-400" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{s}</button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">{[1,2,3].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>
      ) : isError || !data ? (
        <EmptyState icon="📈" message={"داده‌ای برای " + symbol + " یافت نشد"} sub="از صحیح بودن نام نماد اطمینان حاصل کنید" onRetry={() => refetch()} />
      ) : (
        <>
          {/* Header */}
          <div className="glass-card p-4 flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="flex items-center gap-3">
                <span className="text-2xl font-black text-surface-100">{data.symbol}</span>
                <span className="text-xs text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full">{data.instrument?.name as string || ""}</span>
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-surface-500">
                <span>تولید: {formatDateShamsi(data.generated_at)}</span>
                <span>{data.recent_quotes?.length ?? 0} رکورد</span>
              </div>
            </div>
            <div className="text-right">
              {data.recent_quotes?.length > 0 && (
                <>
                  <p className="text-2xl font-black font-mono text-surface-100">
                    {data.recent_quotes[data.recent_quotes.length - 1]?.price_close?.toLocaleString("fa-IR")}
                  </p>
                  <p className={`text-sm font-bold font-mono ${ch?.color ?? ""}`}>{ch?.text ?? ""}</p>
                </>
              )}
            </div>
          </div>

          {/* Instrument Info */}
          {data.instrument && Object.keys(data.instrument).length > 0 && (
            <Card title="📋 اطلاعات نماد">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(data.instrument).filter(([k]) => !["id", "symbol", "created_at", "updated_at"].includes(k)).slice(0, 12).map(([k, v]) => (
                  <div key={k} className="bg-surface-800/30 rounded-xl p-3">
                    <p className="text-[10px] text-surface-500 mb-0.5">{k}</p>
                    <p className="text-sm font-mono font-bold text-surface-200 truncate">{String(v ?? "—")}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Recent Quotes Table */}
          {data.recent_quotes?.length > 0 && (
            <Card title="📅 آخرین قیمت‌ها" subtitle={data.recent_quotes.length + " روز"}>
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="pb-2 px-2">تاریخ</th>
                      <th className="pb-2 px-2">بسته</th>
                      <th className="pb-2 px-2">باز</th>
                      <th className="pb-2 px-2">بالاترین</th>
                      <th className="pb-2 px-2">پایین‌ترین</th>
                      <th className="pb-2 px-2">تغییر</th>
                      <th className="pb-2 px-2">حجم</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_quotes.slice().reverse().map((q, i) => {
                      const pct = formatPct(q.price_change_pct ?? 0);
                      return (
                        <tr key={i} className="border-b border-surface-800/30 hover:bg-white/5">
                          <td className="py-2 px-2 font-mono text-surface-400">{formatDateShamsi(q.date) || "—"}</td>
                          <td className="py-2 px-2 font-mono text-surface-200">{q.price_close?.toLocaleString("fa-IR")}</td>
                          <td className="py-2 px-2 font-mono text-surface-300">{q.price_open?.toLocaleString("fa-IR")}</td>
                          <td className="py-2 px-2 font-mono text-accent-emerald">{q.price_high?.toLocaleString("fa-IR")}</td>
                          <td className="py-2 px-2 font-mono text-accent-rose">{q.price_low?.toLocaleString("fa-IR")}</td>
                          <td className={`py-2 px-2 font-mono ${pct.color}`}>{pct.text}</td>
                          <td className="py-2 px-2 font-mono text-surface-400">{q.volume?.toLocaleString("fa-IR")}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ------ Backtest Report Tab ------------------------------------------------------------------------------------------------
function BacktestReportTab() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: runs } = useQuery({
    queryKey: ["reports-backtest-runs"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: { items: { id: string; name: string; status: string }[] } }>("/backtests/runs");
      return res?.data?.items ?? [];
    },
  });

  const { data, isLoading } = useQuery({
    queryKey: ["backtest-report", selectedId],
    queryFn: async () => {
      if (!selectedId) return null;
      const res = await apiGet<{ success: boolean; data: BacktestReportData }>(`/reports/backtest/${selectedId}`);
      return res?.data ?? null;
    },
    enabled: !!selectedId,
  });

  return (
    <div className="grid lg:grid-cols-3 gap-5">
      {/* Sidebar: backtest list */}
      <div className="lg:col-span-1">
        <Card title="بک‌تست‌ها">
          {!runs?.length ? (
            <p className="text-surface-500 text-sm text-center py-4">بک‌تستی یافت نشد</p>
          ) : (
            <div className="space-y-1">
              {runs.map(run => (
                <button key={run.id} onClick={() => setSelectedId(run.id)}
                  className={`w-full text-right p-3 rounded-lg text-sm transition-all border ${
                    selectedId === run.id
                      ? "bg-primary-600/20 border-primary-600/50 text-primary-300"
                      : "bg-surface-800/30 border-transparent text-surface-400 hover:bg-surface-800"
                  }`}>
                  <div className="font-bold">{run.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      run.status === "completed" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-amber/15 text-accent-amber"
                    }`}>{run.status === "completed" ? "کامل" : run.status}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Content */}
      <div className="lg:col-span-2">
        {!selectedId ? (
          <EmptyState icon="📋" message="یک بک‌تست را انتخاب کنید" sub="از لیست سمت راست یک بک‌تست را برای مشاهده گزارش انتخاب کنید" />
        ) : isLoading ? (
          <div className="space-y-4">{[1,2,3,4].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
        ) : !data ? (
          <EmptyState icon="📋" message="گزارش بک‌تست در دسترس نیست" sub="بک‌تست ممکن است هنوز کامل نشده باشد" />
        ) : (
          <div className="space-y-5">
            {/* Header */}
            <div className="glass-card p-4 flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="font-bold text-surface-100 text-lg">{data.strategy_name}</p>
                <p className="text-xs text-surface-500 mt-0.5">تکمیل: {formatDateShamsi(data.completed_at)}</p>
              </div>
              <div className={`text-right ${(data.total_return_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                <p className="text-2xl font-black">{(data.total_return_pct ?? 0) >= 0 ? "+" : ""}{(data.total_return_pct ?? 0).toFixed(2)}%</p>
                <p className="text-xs">بازده کل</p>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: "سرمایه اولیه", value: formatCurrency(data.initial_capital ?? 0), color: "text-surface-200" },
                { label: "ارزش نهایی", value: formatCurrency(data.final_capital ?? 0), color: (data.final_capital ?? 0) >= (data.initial_capital ?? 0) ? "text-accent-emerald" : "text-accent-rose" },
                { label: "بازده کل (ریال)", value: formatCurrency(data.total_return ?? 0), color: (data.total_return ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose" },
                { label: "نسبت شارپ", value: (data.sharpe_ratio ?? 0).toFixed(2), color: (data.sharpe_ratio ?? 0) >= 1 ? "text-accent-emerald" : (data.sharpe_ratio ?? 0) >= 0 ? "text-accent-amber" : "text-accent-rose" },
                { label: "بیشترین کاهش", value: `${(data.max_drawdown ?? 0).toFixed(1)}%`, color: "text-accent-rose" },
                { label: "نرخ برد", value: `${(data.win_rate ?? 0).toFixed(1)}%`, color: (data.win_rate ?? 0) >= 50 ? "text-accent-emerald" : "text-accent-rose" },
                { label: "تعداد معاملات", value: String(data.total_trades ?? 0), color: "text-surface-200" },
                { label: "سود هر معامله", value: data.total_trades ? formatCurrency((data.total_return ?? 0) / (data.total_trades ?? 1)) : "—", color: (data.total_return ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose" },
              ].map((s, i) => (
                <div key={i} className="bg-surface-800/30 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500 mb-0.5">{s.label}</p>
                  <p className={`text-sm font-bold font-mono ${s.color}`}>{s.value}</p>
                </div>
              ))}
            </div>

            {/* Extra Metrics */}
            {data.metrics && Object.keys(data.metrics).length > 0 && (
              <Card title="📊 معیارهای اضافی">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(data.metrics).map(([k, v]) => (
                    <div key={k} className="bg-surface-800/30 rounded-xl p-3 text-center">
                      <p className="text-[10px] text-surface-500 mb-0.5">{k}</p>
                      <p className="text-sm font-bold font-mono text-surface-200">{typeof v === "number" ? v.toFixed(2) : String(v)}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ------ Empty State Component ---------------------------------------------------------------------------------------------
function EmptyState({ icon, message, sub, onRetry }: { icon: string; message: string; sub?: string; onRetry?: () => void }) {
  return (
    <div className="glass-card p-12 text-center">
      <p className="text-5xl mb-3">{icon}</p>
      <p className="text-surface-300 font-bold">{message}</p>
      {sub && <p className="text-surface-500 text-sm mt-1">{sub}</p>}
      {onRetry && (
        <button onClick={onRetry} className="mt-4 px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-200 rounded-lg text-sm transition-colors">
          تلاش مجدد
        </button>
      )}
    </div>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------------
export default function ReportsPage() {
  const [tab, setTab] = useState<ReportTab>("market");

  const { data: marketReportRaw, isLoading: loadingMarket } = useQuery({
    queryKey: ["market-report"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: MarketReport }>("/reports/market");
      return res?.data ?? null;
    },
    enabled: tab === "market",
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  // Convert undefined → null to match component prop types
  const marketReport: MarketReport | null = marketReportRaw ?? null;

  return (
    <AppLayout title="مرکز گزارشات" subtitle="تولید و مشاهده گزارش‌های بازار، نمادها و بک‌تست‌ها">
      {/* Tab Navigation */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              tab === t.key ? "bg-primary-600 text-white shadow-lg" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}>
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "market" && <MarketReportTab data={marketReport} loading={loadingMarket} />}
      {tab === "symbol" && <SymbolReportTab />}
      {tab === "backtest" && <BacktestReportTab />}
    </AppLayout>
  );
}
