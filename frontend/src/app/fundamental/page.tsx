"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

export default function FundamentalPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [industry, setIndustry] = useState("فلزات اساسی");
  const [tab, setTab] = useState<"ratios" | "dcf" | "score" | "industry">("ratios");

  const { data: fundData, isLoading } = useQuery({
    queryKey: ["fundamental", symbol, tab, industry],
    queryFn: async () => {
      if (tab === "industry") {
        return await apiGet(`/fundamental/industry/${industry}`);
      }
      // For other tabs, we might need multiple calls or a single overview
      const [ratios, score, dcf] = await Promise.all([
        apiGet(`/fundamental/ratios/${symbol}`),
        apiGet(`/fundamental/score/${symbol}`),
        apiGet(`/fundamental/dcf/${symbol}`),
      ]);
      return { ratios, score, dcf };
    },
  });

  const infoRows = (data: any) => [
    { label: "نماد", value: data?.symbol },
    { label: "نام شرکت", value: data?.company_name },
    { label: "صنعت", value: data?.industry },
    { label: "قیمت", value: data?.last_price?.toLocaleString("fa") },
    { label: "ارزش بازار", value: data?.market_cap ? `${(data.market_cap / 1e12).toFixed(2)} تریلیون` : "" },
    { label: "P/E", value: data?.pe, color: data?.pe < 8 ? "text-emerald-400" : data?.pe < 15 ? "text-amber-400" : "text-rose-400" },
    { label: "P/B", value: data?.pb, color: data?.pb < 1 ? "text-emerald-400" : data?.pb < 3 ? "text-amber-400" : "text-rose-400" },
    { label: "ROE", value: data?.roe_pct ? `${data.roe_pct}%` : "", color: data?.roe_pct > 20 ? "text-emerald-400" : data?.roe_pct > 10 ? "text-amber-400" : "text-rose-400" },
    { label: "ROA", value: data?.roa_pct ? `${data.roa_pct}%` : "" },
    { label: "D/E", value: data?.debt_to_equity, color: data?.debt_to_equity < 0.5 ? "text-emerald-400" : data?.debt_to_equity < 1.5 ? "text-amber-400" : "text-rose-400" },
    { label: "EPS", value: data?.eps?.toLocaleString("fa") },
    { label: "BVPS", value: data?.bvps?.toLocaleString("fa") },
    { label: "حاشیه سود", value: data?.net_margin_pct ? `${data.net_margin_pct}%` : "" },
    { label: "سود نقدی", value: data?.dividend_yield_pct ? `${data.dividend_yield_pct}%` : "" },
    { label: "درآمد", value: data?.revenue ? `${(data.revenue / 1e12).toFixed(1)} تریلیون` : "" },
    { label: "سود خالص", value: data?.net_profit ? `${(data.net_profit / 1e12).toFixed(1)} تریلیون` : "" },
  ];

  const TAB_LABELS: Record<string, string> = { ratios: "نسبت‌های مالی", dcf: "ارزش‌گذاری DCF", score: "امتیازدهی", industry: "تحلیل صنعت" };

  return (
    <AppLayout title="تحلیل فاندامنتال">
      <div className="flex gap-2 mb-6">
        {["ratios", "dcf", "score", "industry"].map((t) => (
          <button key={t} onClick={() => setTab(t as any)} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${tab === t ? "bg-primary-600 text-white" : "bg-surface-800 text-gray-400 hover:text-white"}`}>
             {TAB_LABELS[t]}
          </button>
        ))}
      </div>

        {tab !== "industry" && (
          <div className="flex gap-4 items-end mb-6">
            <div>
              <label className="block text-sm text-gray-400 mb-1">نماد</label>
              <select value={symbol} onChange={e => setSymbol(e.target.value)} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white">
                {["فولاد", "فملی", "شپنا", "وبانک", "خودرو", "ذوب", "رمپنا", "اخابر", "کگل", "چادر"].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
        )}

        {tab === "industry" && (
          <div className="flex gap-4 items-end mb-6">
            <div>
              <label className="block text-sm text-gray-400 mb-1">صنعت</label>
              <select value={industry} onChange={e => setIndustry(e.target.value)} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white">
                {["فلزات اساسی", "فرآورده‌های نفتی", "بانک", "خودرو", "پتروشیمی", "سیمان", "دارویی"].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-64 w-full rounded-xl" />
          </div>
        ) : (
          <>
             {tab === "ratios" && (fundData as any)?.ratios && (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                 {infoRows((fundData as any).ratios).map((r) => (
                  <div key={r.label} className="glass-card p-3">
                    <p className="text-xs text-gray-500">{r.label}</p>
                    <p className={`text-lg font-semibold ${r.color || ""}`}>{r.value || "-"}</p>
                  </div>
                ))}
              </div>
            )}
             {tab === "dcf" && (fundData as any)?.dcf && (
              <div className="glass-card p-6">
                 <h2 className="text-lg font-semibold mb-4">ارزش‌گذاری DCF - {(fundData as any).dcf.symbol}</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-3 bg-surface-800 rounded-lg">
                    <p className="text-xs text-gray-500">قیمت فعلی</p>
                     <p className="text-lg font-semibold text-rose-400">{(fundData as any).dcf.current_price?.toLocaleString("fa")}</p>
                  </div>
                  <div className="p-3 bg-surface-800 rounded-lg">
                    <p className="text-xs text-gray-500">قیمت منصفانه</p>
                     <p className="text-lg font-semibold text-emerald-400">{(fundData as any).dcf.fair_price?.toLocaleString("fa")}</p>
                  </div>
                </div>
              </div>
            )}
             {tab === "score" && (fundData as any)?.score && (
              <div className="glass-card p-6">
                <div className="flex items-center justify-between mb-4">
                   <h2 className="text-lg font-semibold">امتیاز {(fundData as any).score.symbol}</h2>
                  <div className="text-center">
                     <p className="text-3xl font-bold gradient-text">{(fundData as any).score.total_score}</p>
                     <p className="text-xs text-gray-500">از {(fundData as any).score.max_score}</p>
                  </div>
                </div>
                 <div className="w-full bg-surface-800 rounded-full h-3 mb-4">
                   <div className="bg-primary-600 h-3 rounded-full transition-all" style={{ width: `${((fundData as any).score.total_score / (fundData as any).score.max_score) * 100}%` }} />
                 </div>
                 <p className="text-center text-lg font-semibold mb-4">تحلیل: {(fundData as any).score.rating_fa}</p>
              </div>
            )}
             {tab === "industry" && (fundData as any) && (
              <div className="glass-card p-4">
                 <h3 className="font-semibold mb-3">شرکت‌های هم‌صنعت ({(fundData as any).peers_count})</h3>
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 border-b border-surface-700">
                        <th className="text-right py-2 px-2">نماد</th>
                        <th className="text-right py-2 px-2">P/E</th>
                        <th className="text-right py-2 px-2">ROE</th>
                        <th className="text-right py-2 px-2">ارزش بازار</th>
                      </tr>
                    </thead>
                    <tbody>
                       {(fundData as any).peers?.map((p: any) => (
                        <tr key={p.symbol} className="border-b border-surface-800 hover:bg-surface-800/50">
                          <td className="py-2 px-2 font-medium">{p.symbol}</td>
                          <td className="py-2 px-2">{p.pe}</td>
                          <td className="py-2 px-2">{p.roe}%</td>
                          <td className="py-2 px-2">{(p.market_cap / 1e12).toFixed(1)}T</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
    </AppLayout>
  );
}
