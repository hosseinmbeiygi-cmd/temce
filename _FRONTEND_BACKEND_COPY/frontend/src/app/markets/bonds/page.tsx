"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";

interface BondRow {
  symbol: string;
  name: string;
  change: number;
  value: number;
  volume: number;
  price: number;
  state: string;
  sector: string;
  market: string;
  board: string;
}

function formatValue(v: number): string {
  if (v >= 1e12) return (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  return (v || 0).toLocaleString("fa-IR");
}

export default function BondsPage() {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<"value" | "change" | "price">("value");

  const { data: cells, isLoading } = useQuery({
    queryKey: ["bonds-heatmap"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: BondRow[] }>(
        "/market/enriched-heatmap?limit=500"
      );
      return extractArray<BondRow>(res);
    },
    staleTime: 30_000,
    refetchInterval: 120_000,
  });

  // صندوق‌های درآمد ثابت — نزدیک‌ترین طبقه به اوراق بدهی در دیتای فعلی BrsApi.
  const bonds = useMemo(() => {
    const all = (cells ?? []).filter(
      (c) =>
        (c.name || "") + (c.sector || "") + (c.board || "") + (c.symbol || ""),
    );
    const fixed = all.filter((c) => {
      const hay = `${c.name ?? ""} ${c.sector ?? ""} ${c.board ?? ""}`;
      return (
        hay.includes("درآمد") ||
        hay.includes("ثابت") ||
        hay.includes("اوراق") ||
        hay.includes("مشارکت")
      );
    });
    const source = fixed.length > 0 ? fixed : all.slice(0, 50);

    const filtered = source.filter((c) => {
      const q = query.trim();
      if (!q) return true;
      const hay = `${c.symbol ?? ""} ${c.name ?? ""} ${c.board ?? ""}`;
      return hay.includes(q);
    });

    return [...filtered].sort((a, b) => {
      if (sortKey === "change") return (b.change ?? 0) - (a.change ?? 0);
      if (sortKey === "price") return (b.price ?? 0) - (a.price ?? 0);
      return (b.value ?? 0) - (a.value ?? 0);
    });
  }, [cells, query, sortKey]);

  const stats = useMemo(() => {
    const gainers = bonds.filter((b) => (b.change ?? 0) > 0).length;
    const losers = bonds.filter((b) => (b.change ?? 0) < 0).length;
    const totalValue = bonds.reduce((s, b) => s + (b.value ?? 0), 0);
    const avg = bonds.length
      ? bonds.reduce((s, b) => s + (b.change ?? 0), 0) / bonds.length
      : 0;
    return { gainers, losers, totalValue, avg };
  }, [bonds]);

  return (
    <AppLayout title="اوراق بدهی" subtitle="صندوق‌های درآمد ثابت و اوراق با درآمد ثابت">
      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-surface-100">{bonds.length}</div>
          <div className="text-xs text-surface-500">نماد فعال</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-accent-emerald">{stats.gainers}</div>
          <div className="text-xs text-surface-500">مثبت</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-2xl font-bold text-accent-rose">{stats.losers}</div>
          <div className="text-xs text-surface-500">منفی</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className={`text-2xl font-bold ${stats.avg >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
            {stats.avg >= 0 ? "+" : ""}{stats.avg.toFixed(2)}%
          </div>
          <div className="text-xs text-surface-500">میانگین تغییر</div>
        </div>
      </div>

      {/* ── Search & sort ── */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="جستجوی نماد یا نام…"
          className="flex-1 min-w-[220px] px-4 py-2 rounded-lg bg-surface-800 border border-surface-700 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:border-primary-500"
        />
        <div className="flex gap-1.5">
          {([
            { key: "value", label: "ارزش معاملات" },
            { key: "change", label: "بیشترین تغییر" },
            { key: "price", label: "قیمت" },
          ] as const).map((s) => (
            <button
              key={s.key}
              onClick={() => setSortKey(s.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                sortKey === s.key
                  ? "bg-primary-600 text-white"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Table ── */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : bonds.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-5xl mb-4">🏛️</p>
          <p className="text-lg text-surface-300">
            داده‌ای برای نمایش یافت نشد
          </p>
          <p className="text-sm text-surface-500 mt-1">
            اوراق خزانه اسلامی (اخزا) و تسهیلات مسکن در دیتای فعلی BrsApi در دسترس نیستند
          </p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm min-w-[720px]">
              <thead>
                <tr className="bg-surface-800/80 border-b border-surface-700">
                  <th className="px-4 py-3 font-bold text-surface-300">#</th>
                  <th className="px-4 py-3 font-bold text-surface-300">نماد</th>
                  <th className="px-4 py-3 font-bold text-surface-300">نام</th>
                  <th className="px-4 py-3 font-bold text-surface-300">قیمت</th>
                  <th className="px-4 py-3 font-bold text-surface-300">تغییر</th>
                  <th className="px-4 py-3 font-bold text-surface-300">حجم</th>
                  <th className="px-4 py-3 font-bold text-surface-300">ارزش</th>
                  <th className="px-4 py-3 font-bold text-surface-300">وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {bonds.slice(0, 100).map((b, i) => (
                  <tr
                    key={`${b.symbol}-${i}`}
                    className="border-b border-surface-800/50 hover:bg-surface-800/30"
                  >
                    <td className="px-4 py-2.5 text-surface-500 font-mono">{i + 1}</td>
                    <td className="px-4 py-2.5 font-bold text-surface-200 font-mono">
                      {b.symbol}
                    </td>
                    <td className="px-4 py-2.5 text-surface-400 text-xs max-w-[260px] truncate">
                      {b.name}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-surface-200">
                      {(b.price || 0).toLocaleString("fa-IR")}
                    </td>
                    <td
                      className={`px-4 py-2.5 font-mono font-bold ${
                        (b.change ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"
                      }`}
                    >
                      {(b.change ?? 0) >= 0 ? "+" : ""}
                      {(b.change ?? 0).toFixed(2)}%
                    </td>
                    <td className="px-4 py-2.5 font-mono text-surface-400 text-xs">
                      {formatValue(b.volume || 0)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-surface-400 text-xs">
                      {formatValue(b.value || 0)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          (b.state ?? "") === "مجاز"
                            ? "bg-emerald-500/15 text-accent-emerald"
                            : "bg-surface-700 text-surface-400"
                        }`}
                      >
                        {b.state || "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3 text-xs text-surface-500 border-t border-surface-800">
            جمع ارزش معاملات:{" "}
            <span className="font-mono font-bold text-surface-300">
              {formatValue(stats.totalValue)}
            </span>{" "}
            • بروزرسانی خودکار هر ۲ دقیقه
          </div>
        </div>
      )}
    </AppLayout>
  );
}
