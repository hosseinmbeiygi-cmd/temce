"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import SymbolSelector from "@/components/SymbolSelector";
import { apiGet } from "@/lib/api";
import { formatTime } from "@/lib/dates";

// ------ Types -------------------------------------------------------------------------------------------------------------
interface TradeRecord {
  id: number | string;
  symbol: string;
  time: string;
  price: number;
  volume: number;
  value: number;
  side: string;
  canceled: boolean | null;
  trade_date: string;
}

interface PaginatedTrades {
  items: TradeRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ------ Constants ---------------------------------------------------------------------------------------------------------
const POPULAR_SYMBOLS = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران", "وغدیر", "پترول", "مس"];

type SideFilter = "all" | "buy" | "sell";

const SIDE_CONFIG: Record<string, { label: string; color: string }> = {
  buy: { label: "خرید", color: "bg-accent-emerald/15 text-accent-emerald" },
  sell: { label: "فروش", color: "bg-accent-rose/15 text-accent-rose" },
};

// ------ Helpers ------------------------------------------------------------------------------------------------------------

function getSideBadge(side: string | null | undefined) {
  const key = side?.toLowerCase() || "";
  const cfg = SIDE_CONFIG[key];
  if (!cfg) return null;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------------
export default function TradesPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [sideFilter, setSideFilter] = useState<SideFilter>("all");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  // Reset page when symbol changes
  const handleSymbolChange = (s: string) => {
    setSymbol(s);
    setPage(0);
  };

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["trades", symbol, page],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: PaginatedTrades }>(
        `/trades/${encodeURIComponent(symbol)}?limit=${pageSize}&offset=${page * pageSize}`
      );
      if (!res?.success) throw new Error("Failed to fetch trades");
      return res.data;
    },
    enabled: !!symbol,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  // Also fetch recent trades for the header summary
  const { data: recentData } = useQuery({
    queryKey: ["trades-recent", symbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: PaginatedTrades }>(
        `/trades/${encodeURIComponent(symbol)}/recent`
      );
      return res?.data?.items ?? [];
    },
    enabled: !!symbol,
    refetchInterval: 30_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Apply side filter
  const filtered = useMemo(() => {
    if (sideFilter === "all") return items;
    return items.filter(t => t.side?.toLowerCase() === sideFilter);
  }, [items, sideFilter]);

  // Statistics from filtered data
  const stats = useMemo(() => {
    if (!filtered.length) return null;
    const totalVolume = filtered.reduce((s, t) => s + (t.volume || 0), 0);
    const totalValue = filtered.reduce((s, t) => s + (t.value || 0), 0);
    const avgPrice = filtered.reduce((s, t) => s + (t.price || 0), 0) / filtered.length;
    const buyCount = filtered.filter(t => t.side?.toLowerCase() === "buy").length;
    const sellCount = filtered.filter(t => t.side?.toLowerCase() === "sell").length;
    const maxPrice = Math.max(...filtered.map(t => t.price || 0));
    const minPrice = Math.min(...filtered.map(t => t.price || 0));
    return { totalVolume, totalValue, avgPrice, buyCount, sellCount, maxPrice, minPrice, count: filtered.length };
  }, [filtered]);

  // Recent trades spark data
  const recentTrades = recentData ?? [];

  return (
    <AppLayout title="تاریخچه معاملات" subtitle={"نماد: " + symbol}>
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ── Header: Symbol Selector ── */}
        <div className="glass-card p-5">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-xs text-surface-500 mb-1.5">انتخاب نماد</label>
              <SymbolSelector value={symbol} onChange={handleSymbolChange} />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-surface-500 mb-1.5">نمادهای محبوب</label>
              <div className="flex flex-wrap gap-1">
                {POPULAR_SYMBOLS.map(s => (
                  <button key={s} onClick={() => handleSymbolChange(s)}
                    className={`text-xs px-2.5 py-1 rounded-lg transition-all ${
                      symbol === s ? "bg-primary-600/20 text-primary-400 border border-primary-600/20" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                    }`}>{s}</button>
                ))}
              </div>
            </div>
            <div className="text-xs text-surface-500">
              {total.toLocaleString("fa-IR")} معامله
              {!isLoading && " • " + filtered.length + " نمایش"}
            </div>
          </div>
        </div>

        {/* ── Stats Summary ── */}
        {stats && !isLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">تعداد</p>
              <p className="text-sm font-bold font-mono text-surface-200">{stats.count.toLocaleString("fa-IR")}</p>
            </div>
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">خرید</p>
              <p className="text-sm font-bold font-mono text-accent-emerald">{stats.buyCount.toLocaleString("fa-IR")}</p>
            </div>
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">فروش</p>
              <p className="text-sm font-bold font-mono text-accent-rose">{stats.sellCount.toLocaleString("fa-IR")}</p>
            </div>
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">میانگین قیمت</p>
              <p className="text-sm font-bold font-mono text-surface-200">{Math.round(stats.avgPrice).toLocaleString("fa-IR")}</p>
            </div>
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">بالاترین</p>
              <p className="text-sm font-bold font-mono text-accent-rose">{stats.maxPrice.toLocaleString("fa-IR")}</p>
            </div>
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">پایین‌ترین</p>
              <p className="text-sm font-bold font-mono text-accent-emerald">{stats.minPrice.toLocaleString("fa-IR")}</p>
            </div>
            <div className="glass-card p-2.5 text-center">
              <p className="text-xs text-surface-500">کل حجم</p>
              <p className="text-sm font-bold font-mono text-primary-300">{stats.totalVolume.toLocaleString("fa-IR")}</p>
            </div>
          </div>
        )}

        {/* ── Recent Trades Mini Card ── */}
        {recentTrades.length > 0 && (
          <div className="glass-card p-3 flex items-center gap-4 flex-wrap text-xs text-surface-500">
            <span className="material-icons text-sm text-primary-400">schedule</span>
            <span>آخرین معاملات {symbol}:</span>
            {recentTrades.slice(0, 5).map((t, i) => (
              <span key={i} className="inline-flex items-center gap-1.5 bg-surface-800/50 px-2 py-1 rounded-lg">
                <span className="font-mono text-surface-200">{t.price.toLocaleString("fa-IR")}</span>
                <span className="font-mono text-surface-500">{t.volume.toLocaleString("fa-IR")}</span>
                {getSideBadge(t.side)}
                <span className="text-surface-600">{formatTime(t.time)}</span>
              </span>
            ))}
          </div>
        )}

        {/* ── Filters ── */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-surface-500 ml-1">طرف:</span>
          {(["all", "buy", "sell"] as const).map(s => (
            <button key={s} onClick={() => setSideFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                sideFilter === s ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}>
              {s === "all" ? "همه" : s === "buy" ? "خرید" : "فروش"}
              {s !== "all" && ` (${stats ? (s === "buy" ? stats.buyCount : stats.sellCount).toLocaleString("fa-IR") : "—"})`}
            </button>
          ))}
          <div className="flex-1" />
          <button onClick={() => refetch()}
            className="p-1.5 rounded-lg bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
            title="بروزرسانی">
            <span className="material-icons text-sm">refresh</span>
          </button>
        </div>

        {/* ── Trade Table ── */}
        <Card
          title="📋 جزئیات معاملات"
          subtitle={"صفحه " + (page + 1) + " از " + totalPages}
        >
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          ) : isError ? (
            <div className="text-center py-10">
              <p className="text-4xl mb-3">⚠️</p>
              <p className="text-surface-500">خطا در دریافت داده</p>
              <button onClick={() => refetch()} className="mt-3 px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-200 rounded-lg text-sm transition-colors">
                تلاش مجدد
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-10 text-surface-500">
              <p className="text-4xl mb-3">📭</p>
              <p>هیچ معامله‌ای برای {symbol} یافت نشد</p>
              <p className="text-xs mt-2 text-surface-600">داده‌های معاملات از BrsApi دریافت می‌شود</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="pb-2 px-1.5">#</th>
                    <th className="pb-2 px-1.5">زمان</th>
                    <th className="pb-2 px-1.5">قیمت (ریال)</th>
                    <th className="pb-2 px-1.5">حجم</th>
                    <th className="pb-2 px-1.5">ارزش (ریال)</th>
                    <th className="pb-2 px-1.5">طرف</th>
                    <th className="pb-2 px-1.5">وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((t, i) => {
                    const tradeValue = t.value || (t.price * t.volume);
                    const isBuy = t.side?.toLowerCase() === "buy";
                    return (
                      <tr key={t.id ?? `${t.trade_date}-${t.time}-${i}`}
                        className="border-b border-surface-800/30 hover:bg-white/[0.03] transition-colors">
                        <td className="py-2 px-1.5 font-mono text-surface-500 text-[10px]">{page * pageSize + i + 1}</td>
                        <td className="py-2 px-1.5 font-mono text-surface-300">{formatTime(t.time)}</td>
                        <td className={`py-2 px-1.5 font-mono font-bold ${isBuy ? "text-accent-emerald" : "text-accent-rose"}`}>
                          {t.price.toLocaleString("fa-IR")}
                        </td>
                        <td className="py-2 px-1.5 font-mono text-surface-200">{t.volume.toLocaleString("fa-IR")}</td>
                        <td className="py-2 px-1.5 font-mono text-surface-400">{tradeValue.toLocaleString("fa-IR")}</td>
                        <td className="py-2 px-1.5">{getSideBadge(t.side)}</td>
                        <td className="py-2 px-1.5">
                          {t.canceled
                            ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-rose/10 text-accent-rose">لغو</span>
                            : <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-emerald/10 text-accent-emerald">عادی</span>
                          }
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Pagination ── */}
          {totalPages > 1 && !isLoading && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-800">
              <p className="text-xs text-surface-500">
                {total.toLocaleString("fa-IR")} معامله • صفحه {page + 1} از {totalPages}
              </p>
              <div className="flex gap-1">
                <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                  className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
                  ← قبلی
                </button>
                <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                  className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
                  بعدی →
                </button>
              </div>
            </div>
          )}
        </Card>

        {/* ── Quick Links ── */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href={`/symbol/${encodeURIComponent(symbol)}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← صفحه نماد {symbol}
          </Link>
          <Link href={`/brsapi/history/${encodeURIComponent(symbol)}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            📈 تاریخچه قیمت
          </Link>
          <Link href="/smart-money" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            🧠 پول هوشمند
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}
