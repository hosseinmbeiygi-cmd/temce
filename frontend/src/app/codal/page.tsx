"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";

interface CodalCompany {
  code: string;
  name: string;
  industry: string;
  lastPrice: number;
  change: number;
  volume: number;
  marketCap: number;
  peRatio: number;
  eps: number;
  status: "active" | "inactive";
}

interface CompanyProfile {
  code: string;
  name: string;
  industry: string;
  subIndustry: string;
  website: string;
  established: string;
  employees: number;
  description: string;
}

interface FinancialReport {
  quarter: string;
  revenue: number;
  netProfit: number;
  eps: number;
  date: string;
}

interface DividendItem {
  date: string;
  perShare: number;
  total: number;
}

interface ShareholderItem {
  name: string;
  shares: number;
  percentage: number;
}

interface InsiderTrade {
  date: string;
  type: "buy" | "sell";
  count: number;
  price: number;
}

function formatPrice(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatLarge(n: number): string {
  if (n >= 1000000000000000) return (n / 1000000000000000).toFixed(1) + " همت";
  if (n >= 1000000000000) return (n / 1000000000000).toFixed(1) + " میلیارد";
  if (n >= 1000000000) return (n / 1000000000).toFixed(1) + " میلیارد";
  return formatPrice(n);
}

function formatVolume(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + " میلیون";
  if (n >= 1000) return (n / 1000).toFixed(1) + " هزار";
  return formatPrice(n);
}

export default function CodalPage() {
  const [filter, setFilter] = useState<"all" | "active" | "inactive">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);

  const { data: companies, isLoading: loadingCompanies } = useQuery({
    queryKey: ["codal-companies"],
    queryFn: async () => {
      try {
        const response = await apiGet<any>("/codal");
        const items = extractArray(response);
        if (items.length > 0) return items;
      } catch {}
      return [
        { code: "فولاد", name: "فولاد مبارکه اصفهان", industry: "فلزات اساسی", lastPrice: 35840, change: 2.3, volume: 125000000, marketCap: 456000000000000, peRatio: 6.2, eps: 5780, status: "active" },
        { code: "شپنا", name: "پالایش نفت اصفهان", industry: "پالایشی", lastPrice: 12750, change: -1.5, volume: 89000000, marketCap: 215000000000000, peRatio: 4.8, eps: 2650, status: "active" },
      ];
    },
    refetchInterval: 60000,
  });

  const { data: detail, isLoading: loadingDetail } = useQuery({
    queryKey: ["codal-detail", selectedCode],
    queryFn: async () => {
      if (!selectedCode) return null;
      const [profile, financials, dividends, holders, insider] = await Promise.all([
        apiGet<CompanyProfile>(`/codal/${selectedCode}/profile`),
        apiGet<FinancialReport[]>(`/codal/${selectedCode}/financials`),
        apiGet<DividendItem[]>(`/codal/${selectedCode}/dividends`),
        apiGet<ShareholderItem[]>(`/codal/${selectedCode}/holders`),
        apiGet<InsiderTrade[]>(`/codal/${selectedCode}/insider`),
      ]);
      return { profile, financials, dividends, holders, insider };
    },
    enabled: !!selectedCode,
  });

  const filtered = companies?.filter((c: any) => {
    if (filter === "active" && c.status !== "active") return false;
    if (filter === "inactive" && c.status !== "inactive") return false;
    if (searchQuery) {
      const q = searchQuery.trim();
      return c.code.includes(q) || c.name.includes(q);
    }
    return true;
  });

  const selectedCompany = selectedCode ? companies?.find((c: any) => c.code === selectedCode) : null;

  return (
    <AppLayout title="اطلاعات شرکت‌ها (کدال)" subtitle="مشاهده اطلاعات شرکت‌های پذیرفته شده در بورس و فرابورس">
      <div className="flex flex-wrap items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">اطلاعات شرکت‌ها (کدال)</h1>
            <p className="text-sm text-surface-500 mt-1">مشاهده اطلاعات شرکت‌های پذیرفته شده در بورس و فرابورس</p>
          </div>
          <div className="flex items-center gap-2 mt-3 sm:mt-0">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجوی نماد یا نام شرکت..."
              className="px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-56"
            />
            {loadingCompanies && <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />}
          </div>
        </div>

        <div className="flex gap-2 mb-4 flex-wrap">
          {["all", "active", "inactive"].map((key) => (
            <button key={key} onClick={() => setFilter(key as any)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}>{key === "all" ? "همه" : key === "active" ? "فعال" : "راکد"}</button>
          ))}
        </div>

        <div className="glass-card p-5 mb-6 overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700">
                <th className="pb-2 font-medium">کد</th>
                <th className="pb-2 font-medium">نام شرکت</th>
                <th className="pb-2 font-medium">صنعت</th>
                <th className="pb-2 font-medium">آخرین قیمت</th>
                <th className="pb-2 font-medium">تغییر</th>
                <th className="pb-2 font-medium">حجم</th>
                <th className="pb-2 font-medium">ارزش بازار</th>
                <th className="pb-2 font-medium">P/E</th>
                <th className="pb-2 font-medium">EPS</th>
                <th className="pb-2 font-medium">وضعیت</th>
              </tr>
            </thead>
            <tbody>
              {loadingCompanies ? (
                [1,2,3,4,5].map(i => <tr key={i} className="border-b border-surface-800/50"><td colSpan={10} className="py-4"><Skeleton className="h-4 w-full" /></td></tr>)
              ) : filtered?.map((c: any) => (
                <tr key={c.code} onClick={() => setSelectedCode(selectedCode === c.code ? null : c.code)}
                  className={`border-b border-surface-800/50 hover:bg-white/5 cursor-pointer transition-all ${
                    selectedCode === c.code ? "bg-primary-600/10" : ""
                  }`}>
                  <td className="py-2.5 font-mono text-surface-200 font-bold">{c.code}</td>
                  <td className="py-2.5 text-surface-200">{c.name}</td>
                  <td className="py-2.5 text-surface-400 text-xs">{c.industry}</td>
                  <td className="py-2.5 font-mono text-surface-200">{formatPrice(c.lastPrice)}</td>
                  <td className={`py-2.5 font-mono ${c.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {c.change >= 0 ? "+" : ""}{c.change.toFixed(1)}%
                  </td>
                  <td className="py-2.5 font-mono text-surface-400 text-xs">{formatVolume(c.volume)}</td>
                  <td className="py-2.5 font-mono text-surface-200 text-xs">{formatLarge(c.marketCap)}</td>
                  <td className="py-2.5 font-mono text-surface-400">{c.peRatio > 0 ? c.peRatio.toFixed(1) : "—"}</td>
                  <td className="py-2.5 font-mono text-surface-400">{c.eps > 0 ? formatPrice(c.eps) : "—"}</td>
                  <td className="py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      c.status === "active" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
                    }`}>{c.status === "active" ? "فعال" : "راکد"}</span>
                  </td>
                </tr>
              )) || <tr><td colSpan={10} className="py-6 text-center text-surface-500">هیچ شرکتی یافت نشد</td></tr>}
            </tbody>
          </table>
        </div>

        {selectedCompany && (
          <div className="space-y-4">
            {loadingDetail ? (
              <div className="space-y-4">
                <Skeleton className="h-32 w-full rounded-2xl" />
                <Skeleton className="h-48 w-full rounded-2xl" />
              </div>
            ) : detail ? (
              <>
                <div className="glass-card p-5">
                  <h2 className="font-bold text-surface-200 mb-4">پروفایل شرکت — {selectedCompany.name}</h2>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><span className="text-surface-500">نماد:</span> <span className="text-surface-200 font-mono">{detail.profile?.code}</span></div>
                    <div><span className="text-surface-500">نام:</span> <span className="text-surface-200">{detail.profile?.name}</span></div>
                    <div><span className="text-surface-500">صنعت:</span> <span className="text-surface-200">{detail.profile?.industry}</span></div>
                    <div><span className="text-surface-500">زیرصنعت:</span> <span className="text-surface-200">{detail.profile?.subIndustry}</span></div>
                  </div>
                  <p className="mt-3 text-xs text-surface-400 leading-relaxed">{detail.profile?.description}</p>
                </div>
                <div className="glass-card p-5">
                  <h2 className="font-bold text-surface-200 mb-4">گزارش‌های مالی</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-right text-sm">
                      <thead>
                        <tr className="text-surface-500 border-b border-surface-700">
                          <th className="pb-2 font-medium">فصل</th>
                          <th className="pb-2 font-medium">درآمد</th>
                          <th className="pb-2 font-medium">سود خالص</th>
                          <th className="pb-2 font-medium">EPS</th>
                          <th className="pb-2 font-medium">تاریخ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.financials?.map((f: any, i: number) => (
                          <tr key={i} className="border-b border-surface-800/50">
                            <td className="py-2.5 text-surface-200">{f.quarter}</td>
                            <td className="py-2.5 font-mono text-surface-200">{formatLarge(f.revenue)}</td>
                            <td className="py-2.5 font-mono text-surface-200">{formatLarge(f.netProfit)}</td>
                            <td className="py-2.5 font-mono text-accent-emerald">{formatPrice(f.eps)}</td>
                            <td className="py-2.5 text-surface-400 text-xs">{f.date}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : <div className="text-center py-12 text-surface-500">جزئیات یافت نشد</div>}
          </div>
        )}
    </AppLayout>
  );
}