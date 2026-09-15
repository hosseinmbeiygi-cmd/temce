"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface Commodity {
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
  { key: "all", label: "همه", icon: "🌐" },
  { key: "precious_metal", label: "فلزات گرانبها", icon: "💎" },
  { key: "base_metal", label: "فلزات پایه", icon: "⚙️" },
  { key: "energy", label: "انرژی", icon: "🛢️" },
];

const CATEGORY_LABEL: Record<string, string> = {
  precious_metal: "فلزات گرانبها",
  base_metal: "فلزات پایه",
  energy: "انرژی",
  agriculture: "کشاورزی",
};

const SYMBOL_ICONS: Record<string, string> = {
  XAUUSD: "🥇", XAGUSD: "🥈", XPTUSD: "💠", XPDUSD: "🔮",
  COPPER: "🪙", ALUMINUM: "🪶", ZINC: "⚡", LEAD: "🔋", NICKEL: "🧲",
  BRENT: "🛢️", WTI: "⛽", NATURAL_GAS: "🔥", GASOLINE: "⛽",
};

function getIcon(c: Commodity): string {
  if (c.category && CATEGORY_LABEL[c.category]) {
    return CATEGORIES.find((cat) => cat.key === c.category)?.icon || "📊";
  }
  return SYMBOL_ICONS[c.symbol] || "📊";
}

function fmtNum(n: number, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function CommodityCard({ c }: { c: Commodity }) {
  const positive = (c.change_percent ?? 0) >= 0;
  const icon = getIcon(c);

  return (
    <div className="glass-card p-4 hover:scale-[1.01] transition-all duration-200">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <div>
            <h3 className="font-bold text-surface-200 text-sm">{c.name || c.symbol}</h3>
            <span className="text-[10px] text-surface-500 font-mono">{c.symbol}</span>
          </div>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-700 text-surface-300">
          {CATEGORY_LABEL[c.category] || c.category || "—"}
        </span>
      </div>

      <div className="flex items-end justify-between mb-3">
        <div>
          <div className="text-xl font-bold font-mono text-surface-100">{fmtNum(c.price)}</div>
          <div className="text-[10px] text-surface-500 font-mono">{c.unit || "USD"}</div>
        </div>
        <div className="text-right">
          <div className={`text-sm font-bold font-mono ${positive ? "text-accent-emerald" : "text-accent-rose"}`}>
            {positive ? "+" : ""}{fmtNum(c.change_percent)}%
          </div>
          <div className={`text-[10px] font-mono ${positive ? "text-accent-emerald/70" : "text-accent-rose/70"}`}>
            {positive ? "+" : ""}{fmtNum(c.change_value)}
          </div>
        </div>
      </div>

      {c.time && (
        <div className="text-[10px] text-surface-600 mt-2 flex items-center gap-1 border-t border-surface-800/50 pt-2">
          <span className="material-icons text-[10px]">schedule</span>
          <span className="font-mono">{c.date} {c.time}</span>
        </div>
      )}
    </div>
  );
}

export default function CommoditiesMarketPage() {
  const [category, setCategory] = useState("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["brsapi-commodities", category],
    queryFn: async () => {
      const endpoint = category === "all"
        ? "/brsapi/commodities"
        : `/brsapi/commodities?category=${category}`;
      const res = await apiGet<{ success: boolean; data: Commodity[] }>(endpoint);
      return res.data || [];
    },
    refetchInterval: 30_000,
  });

  const filtered = data ?? [];

  const summary = useMemo(() => {
    const total = filtered.length;
    const up = filtered.filter((c) => (c.change_percent ?? 0) >= 0).length;
    const down = total - up;
    const avgChange = total === 0 ? 0 : filtered.reduce((s, c) => s + (c.change_percent ?? 0), 0) / total;
    const sorted = [...filtered].sort((a, b) => (b.change_percent ?? 0) - (a.change_percent ?? 0));
    const topGainer = sorted[0];
    const topLoser = sorted[sorted.length - 1];
    return { total, up, down, avgChange, topGainer, topLoser };
  }, [filtered]);

  const date = filtered[0]?.date;
  const time = filtered[0]?.time;

  return (
    <AppLayout title="بازار کالا" subtitle="قیمت جهانی کامودیتی‌ها - فلزات، انرژی و محصولات کشاورزی">
      <div className="flex flex-wrap gap-2 mb-5">
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

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <div className="glass-card p-3">
          <div className="text-[10px] text-surface-500">تعداد آیتم</div>
          <div className="text-lg font-bold font-mono text-surface-200">{summary.total}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-[10px] text-surface-500">صعودی</div>
          <div className="text-lg font-bold font-mono text-accent-emerald">{summary.up}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-[10px] text-surface-500">نزولی</div>
          <div className="text-lg font-bold font-mono text-accent-rose">{summary.down}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-[10px] text-surface-500">میانگین تغییر</div>
          <div className={`text-lg font-bold font-mono ${summary.avgChange >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
            {summary.avgChange >= 0 ? "+" : ""}{fmtNum(summary.avgChange)}%
          </div>
        </div>
        <div className="glass-card p-3">
          <div className="text-[10px] text-surface-500">به‌روزرسانی</div>
          <div className="text-xs font-mono text-surface-200 mt-1">{date || "—"}</div>
          <div className="text-[10px] font-mono text-surface-400">{time || ""}</div>
        </div>
      </div>

      {summary.topGainer && summary.topLoser && summary.total > 1 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
          <div className="glass-card p-3 border-r-4 border-accent-emerald flex items-center justify-between">
            <div>
              <div className="text-[10px] text-surface-500 mb-1">بیشترین رشد</div>
              <div className="text-sm font-bold text-surface-200">{summary.topGainer.name || summary.topGainer.symbol}</div>
              <div className="text-[10px] text-surface-500 font-mono">{summary.topGainer.symbol}</div>
            </div>
            <div className="text-xl font-bold font-mono text-accent-emerald">
              +{fmtNum(summary.topGainer.change_percent)}%
            </div>
          </div>
          <div className="glass-card p-3 border-r-4 border-accent-rose flex items-center justify-between">
            <div>
              <div className="text-[10px] text-surface-500 mb-1">بیشترین افت</div>
              <div className="text-sm font-bold text-surface-200">{summary.topLoser.name || summary.topLoser.symbol}</div>
              <div className="text-[10px] text-surface-500 font-mono">{summary.topLoser.symbol}</div>
            </div>
            <div className="text-xl font-bold font-mono text-accent-rose">
              {fmtNum(summary.topLoser.change_percent)}%
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 mb-4 bg-accent-rose/10 border border-accent-rose/20 rounded-lg text-accent-rose text-sm">
          خطا در دریافت داده‌ها. در حال نمایش داده‌های کش شده...
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {isLoading
          ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)
          : filtered.map((c, i) => <CommodityCard key={`${c.symbol}-${i}`} c={c} />)
        }
      </div>

      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-16 text-surface-600">
          <div className="text-4xl mb-3">📡</div>
          <p>داده‌ای برای نمایش وجود ندارد</p>
          <p className="text-xs mt-2">منتظر اولین همگام‌سازی داده باشید</p>
        </div>
      )}
    </AppLayout>
  );
}