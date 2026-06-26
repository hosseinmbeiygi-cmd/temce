"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";

interface MajorHolder {
  rank: number;
  name: string;
  shares: number;
  percentage: number;
  monthlyChange: number;
}

interface InsiderTrade {
  date: string;
  type: "buy" | "sell";
  count: number;
  price: number;
}

const IRANIAN_SYMBOLS = [
  { code: "فولاد", name: "فولاد مبارکه اصفهان" },
  { code: "شپنا", name: "پالایش نفت اصفهان" },
  { code: "وبملت", name: "بانک ملت" },
  { code: "خودرو", name: "ایران خودرو" },
  { code: "فملی", name: "ملی صنایع مس ایران" },
  { code: "تاپیکو", name: "سرمایه‌گذاری نفت و گاز تامین" },
  { code: "وغدیر", name: "سرمایه‌گذاری غدیر" },
  { code: "شتران", name: "پالایش نفت تهران" },
];

function formatShares(n: number): string {
  if (n >= 1000000000) return (n / 1000000000).toFixed(2) + " میلیارد";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + " میلیون";
  if (n >= 1000) return (n / 1000).toFixed(1) + " هزار";
  return n.toLocaleString("fa-IR");
}

function formatPrice(n: number): string {
  return n.toLocaleString("fa-IR");
}

export default function HoldersPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [searchSymbol, setSearchSymbol] = useState("فولاد");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const { data: holdersData, isLoading: loadingHolders } = useQuery({
    queryKey: ["holders", symbol],
    queryFn: async () => {
      const response = await apiGet<any>(`/codal/${symbol}/holders`);
      return extractArray(response);
    },
  });

  const { data: insiderData, isLoading: loadingInsider } = useQuery({
    queryKey: ["insider", symbol],
    queryFn: async () => {
      const response = await apiGet<any>(`/codal/${symbol}/insider`);
      return extractArray(response);
    },
  });

  const handleSearch = () => {
    if (searchSymbol.trim()) {
      setSymbol(searchSymbol.trim());
      setShowSuggestions(false);
    }
  };

  const filteredSymbols = searchSymbol.trim()
    ? IRANIAN_SYMBOLS.filter((s) => s.code.includes(searchSymbol) || s.name.includes(searchSymbol))
    : IRANIAN_SYMBOLS;

  return (
    <AppLayout title="سهامداران عمده و معاملات داخلی" subtitle="اطلاعات سهامداران عمده و معاملات داخلی شرکت‌ها">
        <div className="flex flex-wrap items-center justify-between mb-6">
          <div className="flex items-center gap-2 relative">
            <div className="relative">
              <input
                type="text"
                value={searchSymbol}
                onChange={(e) => { setSearchSymbol(e.target.value); setShowSuggestions(true); }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="جستجوی نماد..."
                className="px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-40"
              />
              {showSuggestions && searchSymbol.trim() && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-surface-800 border border-surface-700 rounded-lg shadow-xl z-10 max-h-48 overflow-y-auto">
                  {filteredSymbols.map((s) => (
                    <button key={s.code} onClick={() => { setSearchSymbol(s.code); setSymbol(s.code); setShowSuggestions(false); }}
                      className="w-full text-right px-3 py-2 text-sm text-surface-200 hover:bg-surface-700 transition-colors">
                      <span className="font-mono font-bold">{s.code}</span>
                      <span className="text-surface-500 text-xs mr-2">{s.name}</span>
                    </button>
                  ))}
                  {filteredSymbols.length === 0 && (
                    <div className="px-3 py-2 text-sm text-surface-500">نمادی یافت نشد</div>
                  )}
                </div>
              )}
            </div>
            <button onClick={handleSearch}
              className="px-3 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded text-sm transition-colors">جستجو</button>
            {(loadingHolders || loadingInsider) && <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />}
          </div>
        </div>

        <div className="glass-card p-5 mb-6">
          <h2 className="font-bold text-surface-200 mb-4">
            سهامداران عمده — <span className="font-mono text-primary-300">{symbol}</span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 font-medium">رتبه</th>
                  <th className="pb-2 font-medium">نام سهامدار</th>
                  <th className="pb-2 font-medium">تعداد سهام</th>
                  <th className="pb-2 font-medium">درصد مالکیت</th>
                  <th className="pb-2 font-medium">تغییر ماه</th>
                </tr>
              </thead>
              <tbody>
                {loadingHolders ? (
                  [1,2,3,4,5].map(i => <tr key={i} className="border-b border-surface-800/50"><td colSpan={5} className="py-4"><Skeleton className="h-4 w-full" /></td></tr>)
                ) : holdersData?.map((h: MajorHolder) => (
                  <tr key={h.rank} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 font-mono text-surface-400">{h.rank}</td>
                    <td className="py-2.5 text-surface-200 text-xs">{h.name}</td>
                    <td className="py-2.5 font-mono text-surface-200">{formatShares(h.shares)}</td>
                    <td className="py-2.5 font-mono text-accent-cyan">{h.percentage.toFixed(1)}%</td>
                    <td className="py-2.5">
                      <span className={`font-mono text-xs ${
                        h.monthlyChange > 0 ? "text-accent-emerald" : h.monthlyChange < 0 ? "text-accent-rose" : "text-surface-400"
                      }`}>
                        {h.monthlyChange > 0 ? "+" : ""}{h.monthlyChange.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                )) || <tr><td colSpan={5} className="py-6 text-center text-surface-500">داده‌ای یافت نشد</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <div className="glass-card p-5">
          <h2 className="font-bold text-surface-200 mb-4">
            معاملات داخلی اخیر — <span className="font-mono text-primary-300">{symbol}</span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 font-medium">تاریخ</th>
                  <th className="pb-2 font-medium">نوع معامله</th>
                  <th className="pb-2 font-medium">تعداد</th>
                  <th className="pb-2 font-medium">قیمت</th>
                </tr>
              </thead>
              <tbody>
                {loadingInsider ? (
                  [1,2,3,4,5].map(i => <tr key={i} className="border-b border-surface-800/50"><td colSpan={4} className="py-4"><Skeleton className="h-4 w-full" /></td></tr>)
                ) : insiderData?.map((t: InsiderTrade, i: number) => (
                  <tr key={i} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 text-surface-400 text-xs">{t.date}</td>
                    <td className="py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        t.type === "buy" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
                      }`}>{t.type === "buy" ? "خرید" : "فروش"}</span>
                    </td>
                    <td className="py-2.5 font-mono text-surface-200">{formatShares(t.count)}</td>
                    <td className="py-2.5 font-mono text-surface-200">{formatPrice(t.price)}</td>
                  </tr>
                )) || <tr><td colSpan={4} className="py-6 text-center text-surface-500">داده‌ای یافت نشد</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
    </AppLayout>
  );
}