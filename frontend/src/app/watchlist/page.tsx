"use client";

import { useState, useMemo, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import MiniSparkline from "@/components/MiniSparkline";
import { apiGet, apiPost, apiDelete, extractArray } from "@/lib/api";
import { toast } from "sonner";

// ------ Types -------------------------------------------------------------------------------------------------------

interface WatchlistItemData {
  symbol: string;
  name?: string;
  price?: number;
  change?: number;
  priceLowestAllowed?: number;
  priceHighestAllowed?: number;
  freeFloatPct?: number;
  price_yesterday?: number;
  eps?: number;
  peRatio?: number;
  groupPeRatio?: number;
  psRatio?: number;
  state?: string;
  sector?: string;
  order?: number;
}

// ------ Components ------------------------------------------------------------------------------------------------

function PriceRangeBar({ low, high, current }: { low?: number; high?: number; current?: number }) {
  if (low == null || high == null || high <= low || current == null) return null;
  const pct = Math.max(2, Math.min(98, ((current - low) / (high - low)) * 100));
  const distToFloor = ((current - low) / (high - low)) * 100;
  const distToCeiling = 100 - distToFloor;
  const [hovered, setHovered] = useState(false);
  return (
    <div dir="ltr" className="flex items-center gap-1.5 w-full relative">
      <span className="text-[10px] text-surface-500 min-w-[48px] text-left font-mono">{low.toLocaleString()}</span>
      <div className="flex-1 h-1 rounded bg-gradient-to-r from-red-500/30 via-purple-500/30 to-blue-500/30 relative">
        <div
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          className="absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-surface-50 border-2 border-primary-500 cursor-crosshair transition-all duration-200"
          style={{ left: `${pct}%`, transform: `translate(-50%, -50%) scale(${hovered ? 1.8 : 1})`, boxShadow: hovered ? "0 0 12px rgba(99,102,241,0.6)" : "none" }}
        />
        {hovered && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 pointer-events-none">
            <div className="bg-surface-900 border border-surface-700 rounded-xl px-3 py-2 shadow-2xl text-xs whitespace-nowrap">
              <div className="flex justify-between gap-3">
                <span className="text-surface-500">فاصله از کف:</span>
                <span className="font-mono font-bold text-accent-emerald">{distToFloor.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3 mt-1">
                <span className="text-surface-500">فاصله از سقف:</span>
                <span className="font-mono font-bold text-accent-rose">{distToCeiling.toFixed(1)}%</span>
              </div>
            </div>
            <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-surface-700" />
          </div>
        )}
      </div>
      <span className="text-[10px] text-surface-500 min-w-[48px] text-right font-mono">{high.toLocaleString()}</span>
    </div>
  );
}

function AddSymbolDialog({ onAdd, onClose }: { onAdd: (symbol: string) => void; onClose: () => void }) {
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);

  const { data: suggestions, isLoading } = useQuery({
    queryKey: ["symbol-search", search],
    queryFn: async () => {
      if (!search || search.length < 1) return [];
      const res = await apiGet<{ success: boolean; data: { items: { symbol: string; name: string }[] } }>(
        `/instruments/search?q=${encodeURIComponent(search)}`
      );
      return res?.data?.items ?? [];
    },
    enabled: search.length >= 1,
    staleTime: 30000,
  });

  const handleAdd = useCallback(async (symbol: string) => {
    setAdding(true);
    try {
      await apiPost("/watchlist", { symbol });
      onAdd(symbol);
      toast.success("نماد " + symbol + " به لیست پیگیری اضافه شد");
    } catch {
      toast.error("خطا در افزودن نماد");
    }
    setAdding(false);
  }, [onAdd]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-900 border border-surface-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-surface-100">➕ افزودن نماد به لیست پیگیری</h3>
          <button onClick={onClose} className="text-surface-500 hover:text-surface-200 transition-colors">
            <span className="material-icons">close</span>
          </button>
        </div>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="نام یا نماد را تایپ کنید..."
          className="w-full bg-surface-800 border border-surface-700 rounded-xl px-4 py-3 text-sm text-surface-100 placeholder-surface-500 outline-none focus:border-primary-500 mb-4"
          autoFocus
        />
        <div className="max-h-60 overflow-y-auto space-y-1">
          {isLoading ? (
            <div className="space-y-2 p-2">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}
            </div>
          ) : suggestions && suggestions.length > 0 ? (
            suggestions.map((s: { symbol: string; name: string }) => (
              <button
                key={s.symbol}
                onClick={() => handleAdd(s.symbol)}
                disabled={adding}
                className="w-full flex items-center justify-between px-4 py-3 rounded-xl hover:bg-surface-800 transition-colors text-right disabled:opacity-50"
              >
                <div>
                  <span className="font-bold text-surface-100">{s.symbol}</span>
                  {s.name && <span className="text-xs text-surface-500 mr-2">{s.name}</span>}
                </div>
                <span className="material-icons text-primary-400 text-sm">add_circle</span>
              </button>
            ))
          ) : search.length >= 1 ? (
            <div className="text-center py-8 text-surface-500">
              <span className="material-icons text-3xl mb-2">search_off</span>
              <p className="text-sm">نتیجه‌ای برای &quot;{search}&quot; یافت نشد</p>
              <button
                onClick={() => handleAdd(search)}
                disabled={adding}
                className="mt-3 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                افزودن &quot;{search}&quot;
              </button>
            </div>
          ) : (
            <div className="text-center py-8 text-surface-500">
              <span className="material-icons text-3xl mb-2">search</span>
              <p className="text-sm">جستجو را شروع کنید</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------

export default function WatchlistPage() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  // ── Fetch watchlist from API ──
  const { data: items = [], isLoading, refetch } = useQuery({
    queryKey: ["watchlist"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: WatchlistItemData[] }>("/watchlist");
        return extractArray<WatchlistItemData>(res);
      } catch {
        return [];
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ── Batch sparkline data ──
  const sparkQuery = useMemo(() => items.map(i => i.symbol).join(","), [items]);
  const { data: sparkMap } = useQuery({
    queryKey: ["watchlist-spark", sparkQuery],
    queryFn: async () => {
      if (!sparkQuery) return {};
      try {
        const res = await apiGet<{ success: boolean; data: Record<string, number[]> }>(
          `/market/sparklines?symbols=${encodeURIComponent(sparkQuery)}&limit=30`
        );
        return res?.data ?? {};
      } catch { return {}; }
    },
    enabled: !!sparkQuery,
    staleTime: 120_000,
  });

  // ── Remove symbol ──
  const removeSymbol = useCallback(async (symbol: string) => {
    setRemoving(symbol);
    try {
      await apiDelete(`/watchlist/${encodeURIComponent(symbol)}`);
      toast.success("نماد " + symbol + " از لیست حذف شد");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    } catch {
      toast.error("خطا در حذف نماد");
    }
    setRemoving(null);
  }, [queryClient]);

  // ── Add symbol callback ──
  const handleAdd = useCallback((symbol: string) => {
    setShowAdd(false);
    queryClient.invalidateQueries({ queryKey: ["watchlist"] });
  }, [queryClient]);

  return (
    <AppLayout title="📋 دیده‌بان" subtitle="نمادهای تحت نظر شما با داده‌های زنده">
      <div className="max-w-4xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-surface-100">
              لیست پیگیری
              {items.length > 0 && (
                <span className="text-sm font-normal text-surface-500 mr-2">({items.length} نماد)</span>
              )}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              className="px-3 py-2 text-xs bg-surface-800 hover:bg-surface-700 text-surface-400 rounded-lg transition-colors flex items-center gap-1"
            >
              <span className="material-icons text-sm">refresh</span>
              تازه‌سازی
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 shadow-lg shadow-primary-600/20"
            >
              <span className="material-icons text-sm">add</span>
              افزودن نماد
            </button>
          </div>
        </div>

        {/* Watchlist Cards */}
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="glass-card p-5">
                <div className="flex items-center gap-4">
                  <Skeleton className="h-10 w-20 rounded-lg" />
                  <Skeleton className="h-10 w-full rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <span className="material-icons text-5xl text-surface-600 mb-4">star_border</span>
            <p className="text-surface-400 text-lg font-medium mb-2">لیست پیگیری شما خالی است</p>
            <p className="text-surface-500 text-sm mb-6">برای شروع، نمادهای مورد نظر خود را اضافه کنید</p>
            <button
              onClick={() => setShowAdd(true)}
              className="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-sm font-bold transition-all"
            >
              + افزودن اولین نماد
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item, i) => {
              const sd = sparkMap?.[item.symbol];
              const change = item.change ?? 0;
              const changeColor = change >= 0 ? "text-accent-emerald" : "text-accent-rose";
              const changeIcon = change >= 0 ? "arrow_upward" : "arrow_downward";

              return (
                <div key={`${item.symbol}-${i}`} className="glass-card p-4 hover:bg-surface-800/50 transition-all group">
                  {/* Row 1: Symbol + Sparkline + Price + Remove */}
                  <div className="flex items-center gap-3">
                    {/* Symbol + Name */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-base font-bold text-surface-100">{item.symbol}</span>
                        {item.name && item.name !== "شرکت " + item.symbol && (
                          <span className="text-xs text-surface-500 truncate hidden sm:inline">{item.name}</span>
                        )}
                      </div>
                      {item.sector && (
                        <span className="text-[10px] text-surface-600">{item.sector}</span>
                      )}
                    </div>

                    {/* Sparkline */}
                    {sd && sd.length > 1 && (
                      <div className="hidden sm:block">
                        <MiniSparkline data={sd} width={72} height={24} />
                      </div>
                    )}

                    {/* Price */}
                    <div className="text-left min-w-[100px]">
                      <div className={`text-base font-bold font-mono ${changeColor}`}>
                        {item.price?.toLocaleString() ?? "—"}
                      </div>
                      {item.change != null && (
                        <div className={`flex items-center gap-0.5 text-xs font-mono ${changeColor}`}>
                          <span className="material-icons text-sm">{changeIcon}</span>
                          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                        </div>
                      )}
                    </div>

                    {/* Badge row */}
                    <div className="hidden md:flex flex-wrap gap-1 max-w-[200px]">
                      {item.state && (
                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                          item.state === "مجاز" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
                        }`}>{item.state}</span>
                      )}
                      {item.freeFloatPct != null && item.freeFloatPct > 0 && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">شناور {item.freeFloatPct.toFixed(0)}%</span>
                      )}
                      {item.eps != null && item.eps !== 0 && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">EPS {item.eps.toLocaleString()}</span>
                      )}
                      {item.peRatio != null && item.peRatio !== 0 && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">P/E {item.peRatio.toFixed(1)}</span>
                      )}
                    </div>

                    {/* Remove button */}
                    <button
                      onClick={() => removeSymbol(item.symbol)}
                      disabled={removing === item.symbol}
                      className="opacity-0 group-hover:opacity-100 transition-opacity w-8 h-8 flex items-center justify-center rounded-full bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 disabled:opacity-50"
                      title="حذف از لیست"
                    >
                      <span className="material-icons text-sm">close</span>
                    </button>
                  </div>

                  {/* Row 2: Price Range Bar */}
                  <div className="mt-2">
                    <PriceRangeBar
                      low={item.priceLowestAllowed}
                      high={item.priceHighestAllowed}
                      current={item.price}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Add Symbol Dialog */}
        {showAdd && (
          <AddSymbolDialog onAdd={handleAdd} onClose={() => setShowAdd(false)} />
        )}
      </div>
    </AppLayout>
  );
}
