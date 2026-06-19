"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Sidebar from "@/components/Sidebar";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface Signal {
  id: string;
  symbol: string;
  signal: string;
  strength: number;
  horizon: string;
  confidence: string;
  strategy: string;
  created_at: string;
  price: number;
}

export default function SignalsPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [filter, setFilter] = useState<"all" | "خرید" | "فروش" | "خنثی">("all");

  const { data: signals, isLoading } = useQuery({
    queryKey: ["signals-full"],
    queryFn: async () => {
      const res = await fetch("/api/v1/signals?page=1&page_size=50");
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.data) return data.data;
      }
      return [
        { id: "1", symbol: "فولاد", signal: "خرید", strength: 0.82, horizon: "۱ روز", confidence: "بالا", strategy: "Momentum_v3", created_at: "۱۴۰۴/۰۳/۲۶ ۱۰:۳۰", price: 58920 },
        { id: "2", symbol: "وبملت", signal: "فروش", strength: 0.74, horizon: "۳ روز", confidence: "متوسط", strategy: "MeanReversion_v2", created_at: "۱۴۰۴/۰۳/۲۶ ۰۹:۴۵", price: 12450 },
        { id: "3", symbol: "خودرو", signal: "خنثی", strength: 0.12, horizon: "—", confidence: "پایین", strategy: "QueueImbalance_v1", created_at: "۱۴۰۴/۰۳/۲۵ ۱۴:۰۰", price: 8750 },
        { id: "4", symbol: "شپنا", signal: "خرید", strength: 0.91, horizon: "۱ ساعت", confidence: "بالا", strategy: "ML_Alpha_v5", created_at: "۱۴۰۴/۰۳/۲۶ ۱۱:۱۵", price: 42150 },
        { id: "5", symbol: "فملی", signal: "خرید", strength: 0.67, horizon: "۳۰ دقیقه", confidence: "متوسط", strategy: "ML_Alpha_v5", created_at: "۱۴۰۴/۰۳/۲۶ ۱۱:۰۰", price: 33800 },
      ],
    },
    refetchInterval: 30000,
  });

  const filtered = filter === "all" ? signals : signals?.filter((s: any) => s.signal === filter);

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">سیگنال‌ها</h1>
            <p className="text-sm text-surface-500 mt-1">سیگنال‌های تولید شده توسط استراتژی‌ها</p>
          </div>
          {isLoading && <span className="text-xs text-accent-amber">در حال بارگذاری...</span>}
        </div>

        <div className="flex gap-2 mb-4 flex-wrap">
          {(["all", "خرید", "فروش", "خنثی"] as const).map((t) => (
            <button key={t} onClick={() => setFilter(t)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === t ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}>{t === "all" ? "همه" : t}</button>
          ))}
        </div>

        <div className="grid gap-3">
          {isLoading ? (
            [1,2,3,4,5].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
          ) : filtered?.map((s: any) => (
            <div key={s.id} className="glass-card p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div>
                  <span className="font-bold text-surface-200">{s.symbol}</span>
                  <span className={`mr-2 text-xs px-2 py-0.5 rounded-full font-medium ${
                    s.signal === "خرید" ? "bg-accent-emerald/15 text-accent-emerald" :
                    s.signal === "فروش" ? "bg-accent-rose/15 text-accent-rose" :
                    "bg-surface-600/30 text-surface-400"
                  }`}>{s.signal}</span>
                </div>
                <div className="text-xs text-surface-400">
                  <span className="ml-3">{(s.strength * 100).toFixed(0)}%</span>
                  <span className="ml-3">{s.confidence}</span>
                  <span>{s.horizon}</span>
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs text-surface-500">
                <span>{s.strategy}</span>
                <span className="font-mono">{s.price.toLocaleString()}</span>
                <span>{s.created_at}</span>
              </div>
            </div>
          )) || <div className="text-center text-surface-500 py-8">هیچ سیگنالی یافت نشد</div>}
        </div>
      </main>
    </div>
  );
}
