"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import MiniSparkline from "@/components/MiniSparkline";
import { DonutChart } from "@/components/DonutChart";
import { Card } from "@/components/ui/Card";
import { apiGet, extractArray } from "@/lib/api";
import { useSectorCounts } from "@/hooks/useSectorCounts";
import { SECTOR_HEX_COLORS, sectorBadge } from "@/lib/sectors";

interface Instrument {
  symbol: string;
  name: string;
  industry: string;
  sector?: string;
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
    industry: String(raw.industry ?? ""),
    sector: String(raw.sector ?? "") || undefined,
    lastPrice: Number(raw.price) || 0,
    change: Number(raw.change) || 0,
    volume: Number(raw.volume) || 0,
    peRatio: Number(raw.peRatio) || 0,
    eps: Number(raw.eps) || 0,
    status: String(raw.state ?? "active"),
  };
}


export default function InstrumentsPage() {
  const [filter, setFilter] = useState("all");
  const [sectorFilter, setSectorFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data: instruments, isLoading, isError } = useQuery({
    queryKey: ["instruments"],
    queryFn: async () => {
      // Real snapshot only: the old hard-coded price/P/E table is gone.
      const response = await apiGet<Record<string, unknown>>("/market/enriched-heatmap");
      const items = extractArray<Record<string, unknown>>(response);
      return items.map(mapInstrument);
    },
  });

  // ── Sector distribution (from GET /symbols/sectors) ──
  const { sectors: sectorSummary } = useSectorCounts();

  const sectorSlices = useMemo(() => {
    const total = sectorSummary.reduce((s, r) => s + r.count, 0);
    if (!total) return [];
    return sectorSummary.map((r) => ({
      label: r.sector,
      value: r.count,
      color: SECTOR_HEX_COLORS[r.sector] || "#64748b",
    }));
  }, [sectorSummary]);

  const industries = [...new Set((instruments || []).map((i: Instrument) => i.industry))];

  // ── Market sector filter tabs ──

  const MARKETS = [
    { key: "", label: "همه" },
    { key: "سهام", label: "سهام" },
    { key: "طلا و سکه", label: "طلا و سکه" },
    { key: "ارز", label: "ارز" },
    { key: "رمزارز", label: "رمزارز" },
    { key: "کامودیتی", label: "کامودیتی" },
    { key: "بورس کالا", label: "بورس کالا" },
    { key: "صندوق", label: "صندوق" },
  ];

  // ── Batch sparkline data ──
  const displaySymbols = useMemo(() => {
    const filtered = (instruments || []).filter((i: Instrument) => {
      if (filter !== "all" && i.industry !== filter) return false;
      if (sectorFilter && i.sector !== sectorFilter) return false;
      if (search) { const q = search.trim(); return i.symbol.includes(q) || i.name.includes(q); }
      return true;
    });
    return filtered;
  }, [instruments, filter, sectorFilter, search]);

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

        {/* ── Sector distribution card (click a slice to filter the table) ── */}
        <Card
          title="📊 توزیع نمادها در بازارها"
          subtitle="تعداد نمادهای ثبت‌شده در هر بخش بازار — برای فیلتر جدول، روی بخش کلیک کنید"
          className="mb-4"
        >
          {sectorSlices.length > 0 ? (
            <DonutChart
              slices={sectorSlices}
              size={120}
              centerLabel="نماد"
              onSliceClick={(label) =>
                setSectorFilter((prev) => (prev === label ? "" : label))
              }
            />
          ) : (
            <div className="text-sm text-surface-500 py-2">
              اطلاعات توزیع بخش‌ها در دسترس نیست
            </div>
          )}
        </Card>

        {/* ── Market sector filter tabs ── */}
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {MARKETS.map((m) => {
            const active = sectorFilter === m.key;
            return (
              <button
                key={m.key}
                onClick={() => setSectorFilter(m.key)}
                className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all ${
                  active
                    ? "bg-primary-600 text-white shadow-sm"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200"
                }`}
              >
                {m.label}
              </button>
            );
          })}
        </div>

        {/* ── Industry filter tabs ── */}
        <div className="flex gap-2 mb-4 flex-wrap">
          <button onClick={() => setFilter("all")}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === "all" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>همه صنایع</button>
          {industries.map((ind) => (
             <button key={String(ind)} onClick={() => setFilter(String(ind))}
               className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === ind ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{String(ind)}</button>
          ))}
        </div>

        {isError && (
          <div role="alert" aria-live="polite" className="mb-4 flex items-center gap-2 rounded-xl border border-accent-rose/30 bg-accent-rose/10 px-4 py-2.5 text-xs text-accent-rose">
            <span className="material-icons text-base">wifi_off</span>
            دریافت فهرست نمادها از سرور ناموفق بود — داده‌ای برای نمایش وجود ندارد.
          </div>
        )}

        <div className="glass-card overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700">
                <th className="pb-2 px-3 font-medium">نماد</th>
                <th className="pb-2 px-3 font-medium">نام</th>
                <th className="pb-2 px-3 font-medium">صنعت</th>
                <th className="pb-2 px-3 font-medium">بازار</th>
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
                    <td colSpan={10} className="py-4"><Skeleton className="h-4 w-full" /></td>
                  </tr>
                ))
              ) : displaySymbols.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-sm text-surface-500">
                    {sectorFilter
                      ? `نمادی در بخش «${sectorFilter}» یافت نشد — روی بخش دیگری از نمودار کلیک کنید یا «همه» را انتخاب کنید`
                      : "نمادی یافت نشد"}
                  </td>
                </tr>
              ) : displaySymbols.slice(0, displayLimit).map((inst: Instrument, idx: number) => {
                const sparkData = sparkMap?.[inst.symbol];
                return (
                <tr key={`${inst.symbol}-${idx}`} className="border-b border-surface-800/50 hover:bg-white/5">
                  <td className="py-2.5 px-3 font-bold text-surface-200">{inst.symbol}</td>
                  <td className="py-2.5 px-3 text-surface-300">{inst.name}</td>
                  <td className="py-2.5 px-3 text-surface-400 text-xs">{inst.industry}</td>
                  <td className="py-2.5 px-3">
                    {inst.sector && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${sectorBadge(inst.sector)}`}>
                        {inst.sector}
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-surface-200">{inst.lastPrice?.toLocaleString("en-US")}</td>
                  <td className={`py-2.5 px-3 font-mono ${inst.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{inst.change >= 0 ? "+" : ""}{inst.change}%</td>
                  <td className="py-2.5 px-3">
                    {sparkData && sparkData.length > 1
                      ? <MiniSparkline data={sparkData} width={72} height={24} />
                      : <span className="text-[10px] text-surface-600">—</span>
                    }
                  </td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.volume?.toLocaleString("en-US")}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.peRatio > 0 ? inst.peRatio.toFixed(1) : "—"}</td>
                  <td className="py-2.5 px-3 font-mono text-surface-400 text-xs">{inst.eps > 0 ? inst.eps.toLocaleString("en-US") : "—"}</td>
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