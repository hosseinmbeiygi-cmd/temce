"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";

interface PriceItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  value: number;
  sector: string;
  market: string;
  state: string;
}

function PriceRow({ item }: { item: PriceItem }) {
  const isPositive = item.change_pct >= 0;
  return (
    <div className="flex items-center justify-between px-4 py-3 rounded-lg bg-surface-800/30 hover:bg-surface-800/60 transition-colors border border-transparent hover:border-surface-700">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-1 h-10 rounded-full bg-surface-700" />
        <div>
          <p className="font-bold text-surface-200 text-sm">{item.symbol}</p>
          <p className="text-xs text-surface-500 truncate max-w-40">{item.name || "—"}</p>
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="text-right">
          <p className="font-mono font-bold text-surface-200 text-sm">
            {item.price.toLocaleString("fa-IR")}
          </p>
          <p className="text-xs text-surface-500">ریال</p>
        </div>
        <div className={`text-right ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
          <p className="font-mono font-bold text-sm" dir="ltr">
            {isPositive ? "+" : ""}{item.change_pct.toFixed(2)}%
          </p>
          <p className="text-xs opacity-70" dir="ltr">
            {isPositive ? "+" : ""}{item.change.toLocaleString("fa-IR")}
          </p>
        </div>
        <div className="text-right hidden md:block">
          <p className="font-mono text-xs text-surface-400">
            {item.volume?.toLocaleString("fa-IR") || "0"}
          </p>
          <p className="text-[10px] text-surface-600">حجم</p>
        </div>
        <div className={`px-2 py-0.5 rounded text-[10px] ${
          item.state === "مجاز" ? "bg-accent-emerald/10 text-accent-emerald" :
          item.state === "ممنوع" ? "bg-accent-rose/10 text-accent-rose" :
          "bg-surface-700/30 text-surface-500"
        }`}>
          {item.state || "—"}
        </div>
      </div>
    </div>
  );
}

export default function QuotesPage() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"change_pct" | "volume" | "price">("change_pct");
  const [marketFilter, setMarketFilter] = useState<string>("all");

  const { data: prices, isLoading } = useQuery({
    queryKey: ["live-prices"],
    queryFn: async () => {
      const data = await apiGet<{ success: boolean; data: Record<string, unknown>[] }>("/market/enriched-heatmap");
      if (data?.success && Array.isArray(data.data)) {
        return data.data.map((item) => ({
          symbol: String(item.symbol || ""),
          name: String(item.name || ""),
          price: Number(item.price || 0),
          change: Number(item.change || 0),        // price_last_change_pct
          change_pct: Number(item.change || 0),     // same field = percentage
          volume: Number(item.volume || 0),
          value: Number(item.value || 0),
          sector: String(item.sector || ""),
          market: String(item.market || ""),
          state: String(item.state || ""),
        })) as PriceItem[];
      }
      return [] as PriceItem[];
    },
    refetchInterval: 30000,
  });

  // Apply filters
  const filtered = (prices || [])
    .filter((p) => {
      if (search) {
        const q = search.trim().toLowerCase();
        if (!p.symbol.toLowerCase().includes(q) && !p.name.toLowerCase().includes(q)) return false;
      }
      if (marketFilter !== "all" && p.market !== marketFilter) return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "volume") return (b.volume || 0) - (a.volume || 0);
      if (sortBy === "price") return (b.price || 0) - (a.price || 0);
      return Math.abs(b.change_pct || 0) - Math.abs(a.change_pct || 0);
    });

  // Market stats
  const gainers = (prices || []).filter((p) => p.change_pct > 0).length;
  const losers = (prices || []).filter((p) => p.change_pct < 0).length;
  const unchanged = (prices || []).filter((p) => p.change_pct === 0).length;

  const markets = [...new Set((prices || []).map((p) => p.market).filter(Boolean))];

  return (
    <AppLayout title="قیمت‌های لحظه‌ای" subtitle="آخرین قیمت‌ها و تغییرات نمادهای بورس تهران">
      {/* Summary Bar */}
      {!isLoading && prices && (
        <div className="flex flex-wrap gap-3 mb-6">
          <div className="glass-card px-4 py-2.5 flex items-center gap-2">
            <span className="material-icons text-primary-400 text-sm">analytics</span>
            <span className="text-xs text-surface-400">
              <span className="font-bold text-surface-200">{prices.length}</span> نماد
            </span>
          </div>
          <div className="glass-card px-4 py-2.5 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-emerald" />
            <span className="text-xs text-surface-400">
              <span className="font-bold text-accent-emerald">{gainers}</span> مثبت
            </span>
          </div>
          <div className="glass-card px-4 py-2.5 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-rose" />
            <span className="text-xs text-surface-400">
              <span className="font-bold text-accent-rose">{losers}</span> منفی
            </span>
          </div>
          <div className="glass-card px-4 py-2.5 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-surface-600" />
            <span className="text-xs text-surface-400">
              <span className="font-bold text-surface-400">{unchanged}</span> بدون تغییر
            </span>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جستجوی نماد..."
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-48"
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value="change_pct">بر اساس تغییر</option>
          <option value="volume">بر اساس حجم</option>
          <option value="price">بر اساس قیمت</option>
        </select>
        <select
          value={marketFilter}
          onChange={(e) => setMarketFilter(e.target.value)}
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value="all">همه بازارها</option>
          {markets.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        {isLoading && <span className="text-xs text-accent-amber animate-pulse">در حال بروزرسانی...</span>}
      </div>

      {/* Price List */}
      <div className="space-y-1">
        {isLoading ? (
          Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))
        ) : filtered.length > 0 ? (
          filtered.map((item) => <PriceRow key={item.symbol} item={item} />)
        ) : (
          <div className="glass-card p-8 text-center text-surface-500">
            <div className="text-4xl mb-3">📊</div>
            <p>نماندی یافت نشد</p>
            {search && <p className="text-xs mt-1">برای {search} نتیجه‌ای پیدا نشد</p>}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-6 p-4 glass-card text-xs text-surface-500">
        <p>📡 داده‌ها از BrsApi دریافت و در دیتابیس ذخیره می‌شوند. بروزرسانی خودکار هر ۳۰ ثانیه.</p>
      </div>
    </AppLayout>
  );
}
