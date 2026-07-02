"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface CommodityPrice {
  symbol: string;
  name: string;
  price: number;
  change_value: number;
  change_percent: number;
  unit: string;
  category: string;
  date: string;
  time: string;
}

const CATEGORIES = [
  { key: "precious_metal", label: "فلزات گرانبها", icon: "💎" },
  { key: "base_metal", label: "فلزات پایه", icon: "⚙️" },
  { key: "energy", label: "انرژی", icon: "🛢️" },
  { key: "all", label: "همه", icon: "🌐" },
];

const CATEGORY_ICONS: Record<string, string> = {
  precious_metal: "🥇",
  base_metal: "⚙️",
  energy: "🛢️",
};

function getCommodityIcon(c: CommodityPrice): string {
  if (c.category && CATEGORY_ICONS[c.category]) return CATEGORY_ICONS[c.category];
  const symbolIcons: Record<string, string> = {
    XAUUSD: "🥇", XAGUSD: "🥈", XPTUSD: "💎", XPDUSD: "🔮",
    COPPER: "🪙", ALUMINUM: "🪶", ZINC: "⚡", LEAD: "🔋", NICKEL: "🧲",
    BRENT: "🛢️", WTI: "⛽", NATURAL_GAS: "🔥", GASOLINE: "⛽",
  };
  return symbolIcons[c.symbol] || "📊";
}

function CommodityCard({ c }: { c: CommodityPrice }) {
  const isPositive = c.change_percent >= 0;
  const icon = getCommodityIcon(c);

  return (
    <div className="glass-card p-4 group hover:scale-[1.02] transition-all duration-300">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <div>
            <h3 className="font-bold text-surface-200 text-sm">{c.name || c.symbol}</h3>
            <span className="text-xs text-surface-500 font-mono">{c.symbol}</span>
          </div>
        </div>
        {c.category && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-600/10 text-primary-300">
            {CATEGORIES.find((cat) => cat.key === c.category)?.label || c.category}
          </span>
        )}
      </div>

      <div className="flex items-end justify-between">
        <div>
          <div className="text-2xl font-bold font-mono text-surface-100">
            {c.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
          </div>
          <div className="text-xs text-surface-500 mt-1">{c.unit || "USD"}</div>
        </div>
        <div className="text-right">
          <div className={`text-lg font-bold font-mono ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
            {isPositive ? "+" : ""}{c.change_percent?.toFixed(2)}%
          </div>
          <div className={`text-xs font-mono ${isPositive ? "text-accent-emerald/70" : "text-accent-rose/70"}`}>
            {isPositive ? "+" : ""}{c.change_value?.toFixed(2)}
          </div>
        </div>
      </div>

      {c.time && (
        <div className="text-[10px] text-surface-600 mt-3 flex items-center gap-1 border-t border-surface-800/50 pt-2">
          <span className="material-icons text-xs">schedule</span>
          {c.date} {c.time}
        </div>
      )}
    </div>
  );
}

export default function CommoditiesPage() {
  const [category, setCategory] = useState("all");

  const { data: prices, isLoading, error } = useQuery({
    queryKey: ["brsapi-commodities", category],
    queryFn: async () => {
      const endpoint = category === "all"
        ? "/brsapi/commodities"
        : `/brsapi/commodities?category=${category}`;
      const res = await apiGet<{ success: boolean; data: CommodityPrice[] }>(endpoint);
      return res.data || [];
    },
    refetchInterval: 30_000,
  });

  return (
    <AppLayout title="🌍 قیمت‌های جهانی کامودیتی" subtitle="فلزات گرانبها، فلزات پایه و انرژی - به‌روزرسانی لحظه‌ای">
      {/* Category Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setCategory(cat.key)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              category === cat.key
                ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                : "bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700"
            }`}
          >
            <span>{cat.icon}</span>
            {cat.label}
          </button>
        ))}
      </div>

      {/* Stats Bar */}
      {prices && prices.length > 0 && (
        <div className="flex flex-wrap gap-4 mb-6 p-3 glass-card">
          <div className="text-xs text-surface-400">
            <span className="text-surface-300 font-bold">{prices.length}</span> آیتم
          </div>
          <div className="text-xs text-surface-400">
            به‌روزرسانی: {prices[0]?.time || "—"}
          </div>
          <div className="text-xs text-surface-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse" />
            لحظه‌ای
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 mb-4 bg-accent-rose/10 border border-accent-rose/20 rounded-lg text-accent-rose text-sm">
          خطا در دریافت داده‌ها. در حال نمایش داده‌های کش شده...
        </div>
      )}

      {/* Grid */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {isLoading
          ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)
          : prices?.map((c, i) => <CommodityCard key={`${c.symbol}-${i}`} c={c} />)
        }
      </div>

      {!isLoading && prices?.length === 0 && (
        <div className="text-center py-16 text-surface-600">
          <div className="text-4xl mb-3">📡</div>
          <p>داده‌ای برای نمایش وجود ندارد</p>
          <p className="text-xs mt-2">منتظر اولین همگام‌سازی داده باشید</p>
        </div>
      )}
    </AppLayout>
  );
}
