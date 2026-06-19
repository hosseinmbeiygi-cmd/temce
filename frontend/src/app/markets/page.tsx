"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Sidebar from "@/components/Sidebar";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface Market {
  id: string;
  name: string;
  en: string;
  icon: string;
  instruments: number;
  status: string;
  change: string;
  desc: string;
  features: string[];
}

function MarketCard({ m }: { m: Market }) {
  return (
    <div className="glass-card p-5 group">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{m.icon}</span>
          <div>
            <h3 className="font-bold text-surface-200">{m.name}</h3>
            <span className="text-xs text-surface-500 font-mono">{m.en}</span>
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          m.status === "live" ? "bg-accent-emerald/15 text-accent-emerald" :
          m.status === "delayed" ? "bg-accent-amber/15 text-accent-amber" :
          "bg-surface-600/30 text-surface-400"
        }`}>{m.status === "live" ? "فعال" : m.status === "delayed" ? "تأخیر" : "در راه"}</span>
      </div>
      <p className="text-xs text-surface-400 mb-3">{m.desc}</p>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-surface-400">{m.instruments} نماد</span>
        <span className={`text-sm font-mono font-bold ${m.change.startsWith("+") ? "text-accent-emerald" : "text-accent-rose"}`}>{m.change}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {m.features.map((f) => (
          <span key={f} className="text-xs px-2 py-0.5 rounded-md bg-primary-600/10 text-primary-300">{f}</span>
        ))}
      </div>
    </div>
  );
}

export default function MarketsPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [filter, setFilter] = useState("all");

  const { data: markets, isLoading } = useQuery({
    queryKey: ["markets-full"],
    queryFn: async () => {
      const response = await fetch('/api/v1/market/overview');
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data && data.data.markets) {
          return data.data.markets;
        }
      }
      // Fallback to mock
      return [
        { id: "tse", name: "بورس تهران", en: "TSE", icon: "📈", instruments: 786, status: "live", change: "+۰.۸%", desc: "بزرگترین بازار سرمایه ایران", features: ["صف خرید/فروش", "حراج", "قیمت‌گذاری ۵٪"] },
        { id: "ifb", name: "فرابورس", en: "IFB", icon: "📊", instruments: 342, status: "live", change: "-۰.۳%", desc: "بازار اوراق بدهی و سهام", features: ["صف", "حراج", "قیمت‌گذاری ۳٪"] },
        { id: "crypto", name: "کریپتو", en: "Crypto", icon: "₿", instruments: 12, status: "live", change: "+۲.۱%", desc: "بازار ۲۴/۷ رمزارزها", features: ["Orderbook کامل", "تأثیر بازار", "اسپرد متغیر"] },
      ];
    },
    refetchInterval: 60000,
  });

  const filtered = filter === "all" ? markets : markets?.filter((m: any) => m.status === filter);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="flex flex-wrap items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">📈 بازارها</h1>
            <p className="text-sm text-surface-500 mt-1">مدیریت بازارهای پشتیبانی شده</p>
          </div>
          {isLoading && <span className="text-xs text-accent-amber">در حال بارگذاری...</span>}
        </div>
        <div className="flex gap-2 mb-6 flex-wrap">
          {[
            { key: "all", label: "همه" },
            { key: "live", label: "فعال" },
            { key: "delayed", label: "تأخیر" },
            { key: "coming", label: "در راه" },
          ].map((t) => (
            <button key={t.key} onClick={() => setFilter(t.key)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === t.key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}>{t.label}</button>
          ))}
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {isLoading ? (
            [1,2,3].map(i => <Skeleton key={i} className="h-48 w-full" />)
          ) : filtered?.map((m: any) => <MarketCard key={m.id} m={m} />) || <div className="text-center col-span-full py-8 text-surface-600">بازاری یافت نشد</div>}
        </div>
      </main>
    </div>
  );
}
