"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getETFSnapshot, type ETFNavRow } from "@/lib/goldApi";
import { cn } from "@/lib/cn";

const fmt = (n: number | null | undefined, digits = 0): string => {
  if (n === null || n === undefined || !isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const fmtPct = (n: number | null | undefined, digits = 2): string => {
  if (n === null || n === undefined) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}٪`;
};

const signalStyle = (signal?: string): string => {
  if (signal === "buy") return "text-emerald-400";
  if (signal === "sell") return "text-rose-400";
  return "text-zinc-400";
};

const SORT_OPTIONS = [
  { key: "name", label: "نام" },
  { key: "nav", label: "NAV" },
  { key: "premium", label: "پرمیوم" },
  { key: "bubble", label: "حباب" },
];

export default function GoldETFPage() {
  const [sortKey, setSortKey] = useState<"name" | "nav" | "premium" | "bubble">("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["gold", "etf"],
    queryFn: () => getETFSnapshot(),
    refetchInterval: 30_000,
  });

  const items: ETFNavRow[] = useMemo(
    () =>
      data?.items.filter(
        (row) =>
          !search ||
          row.fund_name?.toLowerCase().includes(search.toLowerCase()) ||
          row.symbol?.toLowerCase().includes(search.toLowerCase()),
      ) ?? [],
    [data, search],
  );

  const sorted = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      let av: number | string | null = null;
      let bv: number | string | null = null;
      if (sortKey === "name") {
        av = a.fund_name ?? "";
        bv = b.fund_name ?? "";
      } else if (sortKey === "nav") {
        av = a.nav_per_unit;
        bv = b.nav_per_unit;
      } else if (sortKey === "premium") {
        av = a.bubble_pct;
        bv = b.bubble_pct;
      } else {
        av = a.bubble_pct;
        bv = b.bubble_pct;
      }
      if (av === null || bv === null) return 0;
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [items, sortKey, sortDir]);

  const best = data?.best_opportunity;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">صندوق‌های طلا (ETF)</h1>
          <p className="text-xs text-zinc-500 mt-1">
            NAV، پرمیوم/تخفیف، حباب و سیگنال خرید
          </p>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="نماد یا نام"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-56 bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
          />
          <button
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
            className="text-xs bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-zinc-200"
          >
            {sortDir === "asc" ? "↑" : "↓"}
          </button>
        </div>
      </div>

      {best && (
        <div className="rounded-xl ring-1 ring-amber-500/40 bg-amber-950/20 border border-amber-700/40 p-4 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-xs text-zinc-400">بهترین فرصت</div>
              <div className="text-lg font-semibold text-zinc-100">{best}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-zinc-400">تاریخ بروزرسانی</div>
              <div className="text-sm text-zinc-200 font-mono">—</div>
            </div>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap gap-2 text-xs">
        {SORT_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setSortKey(opt.key as typeof sortKey)}
            className={cn(
              "rounded-full px-3 py-1 border transition",
              sortKey === opt.key
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                : "bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Table */}
      {/* overflow-x-auto: nine columns cannot fit a 390px phone, so the table
          scrolls horizontally instead of squeezing (same treatment as /gold/options). */}
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="text-xs text-zinc-500 border-b border-zinc-700/60">
              <th className="text-left p-3">نام صندوق</th>
              <th className="text-right p-3">نماد</th>
              <th className="text-right p-3">NAV</th>
              <th className="text-right p-3">بازار</th>
              <th className="text-right p-3">پرمیوم / تخفیف</th>
              <th className="text-right p-3">حباب</th>
              <th className="text-right p-3">سیگنال</th>
              <th className="text-right p-3">نقدشوندگی</th>
              <th className="text-right p-3">کارمزد</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const ss = signalStyle(row.signal);
              return (
                <tr
                  key={row.symbol}
                  className="border-b border-zinc-700/30 hover:bg-zinc-800/20 transition"
                >
                  <td className="p-3 text-sm text-zinc-100 font-semibold">
                    {row.fund_name ?? row.symbol}
                  </td>
                  <td className="p-3 text-right text-zinc-200 font-mono text-xs">
                    {row.symbol}
                  </td>
                  <td className="p-3 text-right font-mono text-zinc-200">
                    {fmt(row.nav_per_unit)}
                  </td>
                  <td className="p-3 text-right font-mono text-zinc-200">
                    {fmt(row.market_price)}
                  </td>
                  <td className="p-3 text-right font-mono font-semibold">
                    {fmtPct(row.bubble_pct)}
                  </td>
                  <td className="p-3 text-right font-mono font-bold">
                    {fmtPct(row.bubble_pct)}
                  </td>
                  <td className={cn("p-3 text-right font-mono", ss)}>
                    {row.signal ?? "—"}
                  </td>
                  <td className="p-3 text-right text-zinc-400 text-xs uppercase tracking-wide">
                    {row.liquidity ?? "متوسط"}
                  </td>
                  <td className="p-3 text-right text-zinc-400 text-xs">
                    {row.management_fee ?? "—"}
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={9} className="p-6 text-center text-zinc-500 text-sm">
                  {isLoading ? "در حال بارگذاری…" : "صندوقی یافت نشد"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Detail cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sorted.slice(0, 6).map((row) => (
          <div
            key={row.symbol}
            className="rounded-xl ring-1 ring-zinc-700/60 bg-zinc-900/40 backdrop-blur p-4"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <div className="text-sm font-semibold text-zinc-100">{row.fund_name}</div>
                <div className="text-[10px] text-zinc-500">
                  {row.symbol} • {row.isin ?? "—"}
                </div>
              </div>
              <span
                className={cn(
                  "text-[10px] px-2 py-0.5 rounded-full font-semibold",
                  (row.bubble_pct ?? 0) > 0 ? "bg-rose-950/40 text-rose-300" : "bg-emerald-950/40 text-emerald-300",
                )}
              >
                {fmtPct(row.bubble_pct)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-zinc-400">
              <div>NAV</div>
              <div className="text-zinc-200 font-mono text-right">{fmt(row.nav_per_unit)}</div>
              <div>بازار</div>
              <div className="text-zinc-200 font-mono text-right">{fmt(row.market_price)}</div>
              <div>پرمیوم / تخفیف</div>
              <div className="text-zinc-200 font-mono text-right">{fmtPct(row.bubble_pct)}</div>
              <div>نقدشوندگی</div>
              <div className="text-zinc-200 text-right">{row.liquidity ?? "متوسط"}</div>
              <div>کارمزد</div>
              <div className="text-zinc-200 text-right">{row.management_fee ?? "—"}</div>
            </div>
            {row.reason && (
              <div className="mt-2 text-[10px] leading-relaxed text-zinc-500 border-t border-zinc-700/40 pt-2">
                {row.reason}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
