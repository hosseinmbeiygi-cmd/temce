"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import MiniSparkline from "@/components/MiniSparkline";
import { apiGet, extractArray } from "@/lib/api";

interface Instrument {
  symbol: string;
  name: string;
  industry: string;
  lastPrice: number;
  change: number;
  volume: number;
  peRatio: number;
  eps: number;
  status: string;
}

function mapInstrument(raw: Record<string, unknown>): Instrument {
  return {
    symbol: String(raw.symbol ?? ""),
    name: String(raw.name ?? ""),
    industry: String(raw.sector ?? ""),
    lastPrice: Number(raw.price) || 0,
    change: Number(raw.change) || 0,
    volume: Number(raw.volume) || 0,
    peRatio: Number(raw.peRatio) || 0,
    eps: Number(raw.eps) || 0,
    status: String(raw.state ?? "active"),
  };
}

const FALLBACK_INSTRUMENTS: Instrument[] = [
  { symbol: "فولاد", name: "فولاد مبارکه اصفهان", industry: "فلزات اساسی", lastPrice: 58920, change: 1.2, volume: 4520000, peRatio: 6.2, eps: 9500, status: "active" },
  { symbol: "فملی", name: "ملی صنایع مس ایران", industry: "فلزات اساسی", lastPrice: 42500, change: 3.7, volume: 7800000, peRatio: 8.5, eps: 5000, status: "active" },
  { symbol: "شپنا", name: "پالایش نفت اصفهان", industry: "پالایشی", lastPrice: 42150, change: 0.5, volume: 3100000, peRatio: 4.8, eps: 8780, status: "active" },
  { symbol: "وبملت", name: "بانک ملت", industry: "بانکی", lastPrice: 12450, change: -0.8, volume: 8900000, peRatio: 7.1, eps: 1750, status: "active" },
  { symbol: "خودرو", name: "ایران خودرو", industry: "خودرو", lastPrice: 8750, change: 2.5, volume: 12300000, peRatio: 0, eps: -1200, status: "active" },
  { symbol: "کگل", name: "گل گهر", industry: "فلزات اساسی", lastPrice: 35680, change: -1.1, volume: 5600000, peRatio: 10.4, eps: 3430, status: "active" },
  { symbol: "شتران", name: "پالایش نفت تهران", industry: "پالایشی", lastPrice: 8950, change: 0.3, volume: 5600000, peRatio: 5.2, eps: 1720, status: "active" },
  { symbol: "وغدیر", name: "سرمایه گذاری غدیر", industry: "سرمایه‌گذاری", lastPrice: 31200, change: -0.5, volume: 3200000, peRatio: 7.8, eps: 4000, status: "active" },
  { symbol: "تاپیکو", name: "سرمایه گذاری نفت و گاز تامین", industry: "سرمایه‌گذاری", lastPrice: 18500, change: 1.2, volume: 4500000, peRatio: 9.3, eps: 1990, status: "active" },
  { symbol: "کچاد", name: "صنعتی و معدنی چادرملو", industry: "معدنی", lastPrice: 27800, change: 1.8, volume: 4100000, peRatio: 10.4, eps: 2670, status: "active" },
];

export default function InstrumentsPage() {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  const { data: instruments, isLoading } = useQuery({
    queryKey: ["instruments"],
    queryFn: async () => {
      try {
        const response = await apiGet<Record<string, unknown>>("/market/enriched-heatmap");
        const items = extractArray<Record<string, unknown>>(response);
        const mapped = items.length > 0 ? items.map(mapInstrument) : FALLBACK_INSTRUMENTS;
        return mapped;
      } catch {
        return FALLBACK_INSTRUMENTS;
      }
    },
  });

  const industries = [...new Set((instruments || []).map((i: Instrument) => i.industry))];

  // ── Batch sparkline data ──
  const displaySymbols = useMemo(() => {
    const filtered = (instruments || []).filter((i: Instrument) => {
      if (filter !== "all" && i.industry !== filter) return false;
      if (search) { const q = search.trim(); return i.symbol.includes(q) || i.name.includes(q); }
      return true;
    });
    return filtered;
  }, [instruments, filter, search]);

  const displayLimit = 30;
  const sparkQuery = useMemo(() => {
    const syms = displaySymbols.slice(0, displayLimit).map(i => i.symbol);
    return syms.join(",");
  }, [displaySymbols]);

  const { data: sparkMap } = useQuery({
    queryKey: ["instruments-spark", sparkQuery],
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

  return (
    <AppLayout title="نمادها" subtitle="لیست نمادهای قابل معامله">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="جستجوی نماد یا نام..."
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-56" />
        <Link
          href="/instruments/import"
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
             <button key={String(ind)} onClick={() => setFilter(String(ind))}
               className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === ind ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{String(ind)}</button>
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
                <th className="pb-2 px-3 font-medium">روند ۳۰ روزه</th>
                <th className="pb-2 px-3 font-medium">حجم</th>
                <th className="pb-2 px-3 font-medium">P/E</th>
                <th className="pb-2 px-3 font-medium">EPS</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                [1,2,3,4,5,6,7,8,9,10].map(i => (
                  <tr key={i} className="border-b border-surface-800/50">
                    <td colSpan={8} className="py-4"><Skeleton className="h-4 w-full" /></td>
                  </tr>
                ))
              ) : displaySymbols.slice(0, displayLimit).map((inst: Instrument, idx: number) => {
                const sparkData = sparkMap?.[inst.symbol];
                return (
                <tr key={`${inst.symbol}-${idx}`} className="border-b border-surface-800/50 hover:bg-white/5">
                  <td className="py-2.5 px-3 font-bold text-surface-200">{inst.symbol}</td>
                  <td className="py-2.5 px-3 text-surface-300">{inst.name}</td>
                  <td className="py-2.5 px-3 text-surface-400 text-xs">{inst.industry}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-200">{inst.lastPrice?.toLocaleString()}</td>
                  <td className={`py-2.5 px-3 font-mono ${inst.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{inst.change >= 0 ? "+" : ""}{inst.change}%</td>
                  <td className="py-2.5 px-3">
                    {sparkData && sparkData.length > 1
                      ? <MiniSparkline data={sparkData} width={72} height={24} />
                      : <span className="text-[10px] text-surface-600">—</span>
                    }
                  </td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.volume?.toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.peRatio > 0 ? inst.peRatio.toFixed(1) : "—"}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.eps > 0 ? inst.eps.toLocaleString() : "—"}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {isLoading && <div className="text-center text-surface-500 text-sm mt-4">در حال بارگذاری...</div>}
    </AppLayout>
  );
}