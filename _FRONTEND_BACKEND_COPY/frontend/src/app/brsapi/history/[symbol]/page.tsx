"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import SymbolSelector from "@/components/SymbolSelector";
import TradingViewChart from "@/components/charts/TradingViewChart";
import { apiGet } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";
import { CandleDataPoint } from "@/lib/types";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------------
interface HistoryRecord {
  id: number;
  symbol: string;
  date: string;
  time: string | null;
  trade_count: number | null;
  trade_volume: number | null;
  trade_value: number | null;
  price_min: number | null;
  price_max: number | null;
  price_yesterday: number | null;
  price_first: number | null;
  price_last: number | null;
  price_last_change: number | null;
  price_last_change_pct: number | null;
  price_close: number | null;
  price_close_change: number | null;
  price_close_change_pct: number | null;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

type RangeKey = "1w" | "1m" | "3m" | "6m" | "1y" | "all";

const RANGE_DAYS: Record<RangeKey, number | null> = {
  "1w": 7,
  "1m": 30,
  "3m": 90,
  "6m": 180,
  "1y": 365,
  "all": null,
};

const RANGE_LABELS: Record<RangeKey, string> = {
  "1w": "۱ هفته",
  "1m": "۱ ماه",
  "3m": "۳ ماه",
  "6m": "۶ ماه",
  "1y": "۱ سال",
  "all": "همه",
};

// ------ Helpers ------------------------------------------------------------------------------------------------------------------------------------------------
function formatCurrency(val: number | null | undefined): string {
  if (val == null) return "—";
  if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(2) + "T";
  if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(2) + "B";
  if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(2) + "M";
  if (Math.abs(val) >= 1e3) return (val / 1e3).toFixed(1) + "K";
  return val.toLocaleString("fa-IR");
}

function formatPct(val: number | null | undefined): { text: string; color: string } {
  if (val == null) return { text: "—", color: "text-surface-500" };
  const fixed = val.toFixed(2);
  if (val > 0) return { text: `+${fixed}%`, color: "text-accent-emerald" };
  if (val < 0) return { text: `${fixed}%`, color: "text-accent-rose" };
  return { text: "0.00%", color: "text-surface-400" };
}

function getChangeColor(val: number | null | undefined): string {
  if (val == null) return "text-surface-400";
  if (val > 0) return "text-accent-emerald";
  if (val < 0) return "text-accent-rose";
  return "text-surface-400";
}

// ------ Mini Sparkline ---------------------------------------------------------------------------------------------------------------------------
function Sparkline({ data, width = 120, height = 36, color = "#22c55e" }: { data: number[]; width?: number; height?: number; color?: string }) {
  if (!data.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * height}`).join(" ");
  return (
    <svg width={width} height={height} className="shrink-0" viewBox={`0 0 ${width} ${height}`}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <defs>
        <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill={`url(#grad-${color.replace("#", "")})`}
      />
    </svg>
  );
}

// ------ Main Page Component ------------------------------------------------------------------------------------------------------------
export default function BrsapiHistoryPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = (params?.symbol as string) || "فولاد";
  const decodedSymbol = decodeURIComponent(symbol);

  const [data, setData] = useState<HistoryRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<RangeKey>("1y");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const maxDays = RANGE_DAYS[range];
      let start = dateStart;
      if (!start && maxDays != null) {
        const d = new Date();
        d.setDate(d.getDate() - maxDays);
        start = d.toISOString().split("T")[0];
      }
      const reqParams = new URLSearchParams({
        limit: String(pageSize),
        offset: String(page * pageSize),
      });
      if (start) reqParams.set("date_start", start);
      if (dateEnd) reqParams.set("date_end", dateEnd);

      const res = await apiGet<{ success: boolean; data: PaginatedResponse<HistoryRecord> }>(
        `/brsapi/history/${encodeURIComponent(decodedSymbol)}?${reqParams.toString()}`
      );

      if (res?.success && res.data) {
        setData(res.data.items ?? []);
        setTotal(res.data.total ?? 0);
      } else {
        setData([]);
        setTotal(0);
        throw new Error((res as { error?: string })?.error || "داده‌ای یافت نشد");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در دریافت داده");
      setData([]);
    }
    setLoading(false);
  }, [decodedSymbol, range, dateStart, dateEnd, page]);

  // Reset page when filters change
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter change
    setPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decodedSymbol, range, dateStart, dateEnd]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter change
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchData]);

  // Derived data for chart
  const candleData: CandleDataPoint[] = useMemo(() => {
    // Reverse to chronological order for chart
    return [...data].reverse().map((r) => ({
      date: r.date ?? undefined,
      time: r.date ?? undefined,
      open: r.price_first ?? r.price_close ?? 0,
      high: r.price_max ?? r.price_close ?? 0,
      low: r.price_min ?? r.price_close ?? 0,
      close: r.price_close ?? 0,
      volume: r.trade_volume ?? 0,
      isUp: (r.price_close ?? 0) >= (r.price_yesterday ?? 0),
    }));
  }, [data]);

  const closePrices = useMemo(() => data.map((r) => r.price_close ?? 0).reverse(), [data]);

  const latest = data[0];

  const pctDisplay = latest ? formatPct(latest.price_last_change_pct) : { text: "—", color: "text-surface-500" };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <AppLayout
      title={`دیتای تاریخی ${decodedSymbol}`}
      subtitle={`brsapi_historical_daily • ${total.toLocaleString("fa-IR")} روز`}
    >
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ------ Header Bar ------------------------------------------------------------------------------------------------------ */}
        <div className="glass-card p-5 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <SymbolSelector value={decodedSymbol} onChange={(s) => router.push(`/brsapi/history/${s}`)} />
            {latest && (
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-black text-surface-100 font-mono">
                    {(latest.price_close ?? 0).toLocaleString("fa-IR")}
                  </span>
                  <span className={`text-lg font-bold font-mono ${pctDisplay.color}`}>
                    {pctDisplay.text}
                  </span>
                </div>
                <div className="flex items-center gap-4 mt-1 text-xs text-surface-500">
                  <span>آخرین: {formatDateShamsi(latest.date)}</span>
                  <span>بازه: {data.length > 0 ? `${formatDateShamsi(data[data.length - 1]?.date)} تا ${formatDateShamsi(latest.date)}` : "—"}</span>
                </div>
              </div>
            )}
          </div>

          {/* Sparkline */}
          <Sparkline data={closePrices} width={160} height={40} color={latest?.price_last_change_pct != null && latest.price_last_change_pct >= 0 ? "#22c55e" : "#ef4444"} />
        </div>

        {/* ------ Range Selector --------------------------------------------------------------------------------------------- */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex gap-1">
            {(Object.keys(RANGE_DAYS) as RangeKey[]).map((key) => (
              <button
                key={key}
                onClick={() => { setRange(key); setDateStart(""); setDateEnd(""); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  range === key
                    ? "bg-primary-600 text-white shadow-lg"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700"
                }`}
              >
                {RANGE_LABELS[key]}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                showFilters ? "bg-primary-600/20 text-primary-300" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              📅 بازه دلخواه
            </button>
            <Link
              href={`/symbol/${decodedSymbol}`}
              className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 transition-all"
            >
              ← صفحه نماد
            </Link>
          </div>
        </div>

        {/* ------ Date Range Filters --------------------------------------------------------------------------------- */}
        {showFilters && (
          <div className="glass-card p-4 flex items-center gap-3 flex-wrap">
            <span className="text-xs text-surface-500">از تاریخ:</span>
            <input
              type="date"
              value={dateStart}
              onChange={(e) => setDateStart(e.target.value)}
              className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-primary-500"
            />
            <span className="text-xs text-surface-500">تا تاریخ:</span>
            <input
              type="date"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-primary-500"
            />
            <button
              onClick={() => { setDateStart(""); setDateEnd(""); setRange("1y"); }}
              className="px-2 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200"
            >
              پاک کردن
            </button>
          </div>
        )}

        {/* ------ Candlestick Chart --------------------------------------------------------------------------------- */}
        <TradingViewChart
          title="📈 نمودار قیمت شمعی (از دیتای تاریخی BrsApi)"
          data={candleData}
          symbol={decodedSymbol}
          height={420}
          showVolume={true}
        />

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="glass-card p-8 text-center">
            <p className="text-4xl mb-3">⚠️</p>
            <p className="text-surface-500">{error}</p>
          </div>
        ) : data.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <p className="text-4xl mb-3">📭</p>
            <p className="text-surface-500">داده‌ای برای {decodedSymbol} در جدول brsapi_historical_daily یافت نشد.</p>
            <p className="text-xs text-surface-600 mt-2">ابتدا داده‌ها را با endpoint POST /brsapi/manage/sync/history-price?symbol={decodedSymbol} دریافت کنید.</p>
          </div>
        ) : (
          <>
            {/* ------ Summary Cards ------------------------------------------------------------------------------------------ */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Card title="بالاترین قیمت" className="!p-4">
                <p className="text-lg font-bold font-mono text-accent-rose">
                  {formatCurrency(Math.max(...data.map((r) => r.price_max ?? 0)))}
                </p>
                <p className="text-xs text-surface-500 mt-1">بیشترین قیمت در این بازه</p>
              </Card>
              <Card title="پایین‌ترین قیمت" className="!p-4">
                <p className="text-lg font-bold font-mono text-accent-emerald">
                  {formatCurrency(Math.min(...data.map((r) => r.price_min ?? Infinity)))}
                </p>
                <p className="text-xs text-surface-500 mt-1">کمترین قیمت در این بازه</p>
              </Card>
              <Card title="میانگین حجم" className="!p-4">
                <p className="text-lg font-bold font-mono text-surface-100">
                  {formatCurrency(data.reduce((s, r) => s + (r.trade_volume ?? 0), 0) / data.length)}
                </p>
                <p className="text-xs text-surface-500 mt-1">میانگین حجم روزانه</p>
              </Card>
              <Card title="تعداد روز" className="!p-4">
                <p className="text-lg font-bold font-mono text-primary-300">
                  {data.length.toLocaleString("fa-IR")}
                </p>
                <p className="text-xs text-surface-500 mt-1">روز معاملاتی</p>
              </Card>
            </div>

            {/* ------ Details Table --------------------------------------------------------------------------------------------- */}
            <Card
              title="📋 جزئیات کامل دیتای تاریخی"
              subtitle={`${total.toLocaleString("fa-IR")} رکورد • صفحه ${page + 1} از ${totalPages}`}
            >
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs whitespace-nowrap" dir="rtl">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="pb-2 px-2 font-medium">#</th>
                      <th className="pb-2 px-2 font-medium">تاریخ</th>
                      <th className="pb-2 px-2 font-medium">زمان</th>
                      <th className="pb-2 px-2 font-medium">ق. پایانی</th>
                      <th className="pb-2 px-2 font-medium">اولین</th>
                      <th className="pb-2 px-2 font-medium">آخرین</th>
                      <th className="pb-2 px-2 font-medium">بیشترین</th>
                      <th className="pb-2 px-2 font-medium">کمترین</th>
                      <th className="pb-2 px-2 font-medium">دیروز</th>
                      <th className="pb-2 px-2 font-medium">∆ آخرین</th>
                      <th className="pb-2 px-2 font-medium">∆% آخرین</th>
                      <th className="pb-2 px-2 font-medium">∆ پایانی</th>
                      <th className="pb-2 px-2 font-medium">∆% پایانی</th>
                      <th className="pb-2 px-2 font-medium">تعداد</th>
                      <th className="pb-2 px-2 font-medium">حجم</th>
                      <th className="pb-2 px-2 font-medium">ارزش</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((r, i) => (
                      <tr
                        key={r.id ?? i}
                        className="border-b border-surface-800/30 hover:bg-white/[0.03] transition-colors"
                      >
                        <td className="py-2.5 px-2 font-mono text-surface-500 text-[10px]">
                          {page * pageSize + i + 1}
                        </td>
                        <td className="py-2.5 px-2 font-mono font-medium text-surface-200">
                          {formatDateShamsi(r.date)}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-400">
                          {r.time?.substring(0, 5) || "—"}
                        </td>
                        <td className="py-2.5 px-2 font-mono font-bold text-surface-100">
                          {(r.price_close ?? 0).toLocaleString("fa-IR")}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-300">
                          {(r.price_first ?? 0).toLocaleString("fa-IR")}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-300">
                          {(r.price_last ?? 0).toLocaleString("fa-IR")}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-accent-rose">
                          {(r.price_max ?? 0).toLocaleString("fa-IR")}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-accent-emerald">
                          {(r.price_min ?? 0).toLocaleString("fa-IR")}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-400">
                          {(r.price_yesterday ?? 0).toLocaleString("fa-IR")}
                        </td>
                        <td className={`py-2.5 px-2 font-mono ${getChangeColor(r.price_last_change)}`}>
                          {r.price_last_change != null ? (r.price_last_change >= 0 ? "+" : "") + r.price_last_change.toLocaleString("fa-IR") : "—"}
                        </td>
                        <td className={`py-2.5 px-2 font-mono ${getChangeColor(r.price_last_change_pct)}`}>
                          {r.price_last_change_pct != null
                            ? (r.price_last_change_pct >= 0 ? "+" : "") + r.price_last_change_pct.toFixed(2) + "%"
                            : "—"}
                        </td>
                        <td className={`py-2.5 px-2 font-mono ${getChangeColor(r.price_close_change)}`}>
                          {r.price_close_change != null ? (r.price_close_change >= 0 ? "+" : "") + r.price_close_change.toLocaleString("fa-IR") : "—"}
                        </td>
                        <td className={`py-2.5 px-2 font-mono ${getChangeColor(r.price_close_change_pct)}`}>
                          {r.price_close_change_pct != null
                            ? (r.price_close_change_pct >= 0 ? "+" : "") + r.price_close_change_pct.toFixed(2) + "%"
                            : "—"}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-300">
                          {r.trade_count?.toLocaleString("fa-IR") ?? "—"}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-200">
                          {r.trade_volume?.toLocaleString("fa-IR") ?? "—"}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-200">
                          {r.trade_value != null ? formatCurrency(r.trade_value) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* ------ Pagination ------------------------------------------------------------------------------------------------ */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-800">
                  <p className="text-xs text-surface-500">
                    {total.toLocaleString("fa-IR")} رکورد • صفحه {page + 1} از {totalPages}
                  </p>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setPage(Math.max(0, page - 1))}
                      disabled={page === 0}
                      className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                    >
                      ← قبلی
                    </button>
                    <button
                      onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                      disabled={page >= totalPages - 1}
                      className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                    >
                      بعدی →
                    </button>
                  </div>
                </div>
              )}
            </Card>
          </>
        )}

        {/* ------ Quick Links ------------------------------------------------------------------------------------------------------ */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/brsapi" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← BrsApi Dashboard</Link>
          <Link href={`/symbol/${decodedSymbol}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">جزئیات نماد</Link>
          <Link href="/instruments" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">همه نمادها</Link>
        </div>
      </div>
    </AppLayout>
  );
}
