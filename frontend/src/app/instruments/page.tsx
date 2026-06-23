"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface Instrument {
  symbol: string;
  name: string;
  industry: string;
  lastPrice: number;
  change: number;
  volume: number;
  marketCap: number;
  peRatio: number;
  status: string;
}

const FALLBACK_INSTRUMENTS: Instrument[] = [
  { symbol: "فولاد", name: "فولاد مبارکه اصفهان", industry: "فلزات اساسی", lastPrice: 58920, change: 1.2, volume: 4520000, marketCap: 456000000000000, peRatio: 6.2, status: "active" },
  { symbol: "فملی", name: "ملی صنایع مس ایران", industry: "فلزات اساسی", lastPrice: 42500, change: 3.7, volume: 7800000, marketCap: 520000000000000, peRatio: 8.5, status: "active" },
  { symbol: "شپنا", name: "پالایش نفت اصفهان", industry: "پالایشی", lastPrice: 42150, change: 0.5, volume: 3100000, marketCap: 215000000000000, peRatio: 4.8, status: "active" },
  { symbol: "وبملت", name: "بانک ملت", industry: "بانکی", lastPrice: 12450, change: -0.8, volume: 8900000, marketCap: 180000000000000, peRatio: 7.1, status: "active" },
  { symbol: "خودرو", name: "ایران خودرو", industry: "خودرو", lastPrice: 8750, change: 2.5, volume: 12300000, marketCap: 95000000000000, peRatio: 0, status: "active" },
  { symbol: "کگل", name: "گل گهر", industry: "فلزات اساسی", lastPrice: 35680, change: -1.1, volume: 5600000, marketCap: 380000000000000, peRatio: 10.4, status: "active" },
  { symbol: "شتران", name: "پالایش نفت تهران", industry: "پالایشی", lastPrice: 8950, change: 0.3, volume: 5600000, marketCap: 140000000000000, peRatio: 5.2, status: "active" },
  { symbol: "وغدیر", name: "سرمایه گذاری غدیر", industry: "سرمایه‌گذاری", lastPrice: 31200, change: -0.5, volume: 3200000, marketCap: 280000000000000, peRatio: 7.8, status: "active" },
  { symbol: "تاپیکو", name: "سرمایه گذاری نفت و گاز تامین", industry: "سرمایه‌گذاری", lastPrice: 18500, change: 1.2, volume: 4500000, marketCap: 320000000000000, peRatio: 9.3, status: "active" },
  { symbol: "کچاد", name: "صنعتی و معدنی چادرملو", industry: "معدنی", lastPrice: 27800, change: 1.8, volume: 4100000, marketCap: 380000000000000, peRatio: 10.4, status: "active" },
];

export default function InstrumentsPage() {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  const { data: instruments, isLoading } = useQuery({
    queryKey: ["instruments"],
    queryFn: async () => {
      try {
        return await apiGet<any>("/symbols?page=1&page_size=100");
      } catch {}
      return FALLBACK_INSTRUMENTS;
    },
  });

  const industries = [...new Set((instruments || []).map((i: any) => i.industry))];

  const filtered = (instruments || []).filter((i: any) => {
    if (filter !== "all" && i.industry !== filter) return false;
    if (search) {
      const q = search.trim();
      return i.symbol.includes(q) || i.name.includes(q);
    }
    return true;
  });

  return (
    <AppLayout title="نمادها" subtitle="لیست نمادهای قابل معامله">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="جستجوی نماد یا نام..."
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-56" />
        <Link
          href="/instruments/import"
          data-testid="instruments-import-link"
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white text-sm rounded-lg transition-colors"
        >
          <span aria-hidden>📤</span>
          ورود فایل نمادها
        </Link>
      </div>

        <div className="flex gap-2 mb-4 flex-wrap">
          <button onClick={() => setFilter("all")}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === "all" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>همه</button>
          {industries.map((ind) => (
             <button key={ind as string} onClick={() => setFilter(ind as string)}
               className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === ind ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{ind as string}</button>
          ))}
        </div>

        <div className="glass-card overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700">
                <th className="pb-2 px-3 font-medium">نماد</th>
                <th className="pb-2 px-3 font-medium">نام</th>
                <th className="pb-2 px-3 font-medium">صنعت</th>
                <th className="pb-2 px-3 font-medium">قیمت</th>
                <th className="pb-2 px-3 font-medium">تغییر</th>
                <th className="pb-2 px-3 font-medium">حجم</th>
                <th className="pb-2 px-3 font-medium">P/E</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                [1,2,3,4,5,6,7,8,9,10].map(i => (
                  <tr key={i} className="border-b border-surface-800/50">
                    <td colSpan={7} className="py-4"><Skeleton className="h-4 w-full" /></td>
                  </tr>
                ))
              ) : filtered.map((inst: any) => (
                <tr key={inst.symbol} className="border-b border-surface-800/50 hover:bg-white/5">
                  <td className="py-2.5 px-3 font-bold text-surface-200">{inst.symbol}</td>
                  <td className="py-2.5 px-3 text-surface-300">{inst.name}</td>
                  <td className="py-2.5 px-3 text-surface-400 text-xs">{inst.industry}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-200">{inst.lastPrice?.toLocaleString()}</td>
                  <td className={`py-2.5 px-3 font-mono ${inst.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{inst.change >= 0 ? "+" : ""}{inst.change}%</td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.volume?.toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-400">{inst.peRatio > 0 ? inst.peRatio.toFixed(1) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {isLoading && <div className="text-center text-surface-500 text-sm mt-4">در حال بارگذاری...</div>}
    </AppLayout>
  );
}
