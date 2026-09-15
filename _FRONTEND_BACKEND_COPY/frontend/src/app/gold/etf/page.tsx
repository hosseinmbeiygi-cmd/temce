"use client";

/** صفحه صندوق‌های ETF طلا — NAV Premium/Discount */

import { useQuery } from "@tanstack/react-query";
import { getETFSnapshot, type ETFNavRow } from "@/lib/goldApi";

const fmt = (n: number | null | undefined, digits = 0): string => {
  if (n === null || n === undefined) return "—";
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

const signalStyle = (sig: string): { bg: string; text: string; ring: string; label: string } => {
  if (sig === "BUY")
    return {
      bg: "bg-emerald-500/10",
      text: "text-emerald-300",
      ring: "ring-emerald-500/30",
      label: "خرید",
    };
  if (sig === "SELL")
    return {
      bg: "bg-rose-500/10",
      text: "text-rose-300",
      ring: "ring-rose-500/30",
      label: "فروش",
    };
  return {
    bg: "bg-zinc-700/30",
    text: "text-zinc-300",
    ring: "ring-zinc-600/30",
    label: "خنثی",
  };
};

export default function GoldETFPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["gold", "etf-snapshot"],
    queryFn: getETFSnapshot,
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-16 rounded-xl bg-zinc-900/40 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">صندوق‌های ETF طلا</h1>
        <p className="text-xs text-zinc-500 mt-1">
          مقایسه NAV Premium/Discount — بهترین فرصت:{" "}
          <span className="text-amber-300 font-semibold">
            {data.best_opportunity ?? "—"}
          </span>
        </p>
      </div>

      {/* Grid view */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {data.items.map((row) => (
          <ETFCard key={row.symbol} row={row} />
        ))}
      </div>

      {/* Table view (مرتب‌سازی‌پذیر) */}
      <div>
        <h2 className="text-base font-semibold text-zinc-200 mb-3">📋 جدول مقایسه‌ای</h2>
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] text-zinc-500 border-b border-zinc-800/60 bg-zinc-900/60">
                <th className="text-right py-2.5 px-3">صندوق</th>
                <th className="text-right py-2.5 px-3">نماد</th>
                <th className="text-right py-2.5 px-3">قیمت بازار</th>
                <th className="text-right py-2.5 px-3">NAV</th>
                <th className="text-right py-2.5 px-3">Premium</th>
                <th className="text-right py-2.5 px-3">سیگنال</th>
                <th className="text-right py-2.5 px-3">نقدشوندگی</th>
                <th className="text-right py-2.5 px-3">کارمزد</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => {
                const ss = signalStyle(row.signal);
                return (
                  <tr
                    key={row.symbol}
                    className="border-b border-zinc-800/40 hover:bg-zinc-800/20 transition"
                  >
                    <td className="py-2.5 px-3 text-sm text-zinc-100 font-semibold">
                      {row.name_fa}
                    </td>
                    <td className="py-2.5 px-3 text-xs text-zinc-400">{row.symbol}</td>
                    <td className="py-2.5 px-3 text-xs tabular-nums text-zinc-200">
                      {fmt(row.market_price)}
                    </td>
                    <td className="py-2.5 px-3 text-xs tabular-nums text-zinc-400">
                      {fmt(row.nav)}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-xs tabular-nums font-semibold ${ss.text}`}
                    >
                      {fmtPct(row.premium_pct)}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ${ss.bg} ${ss.text} ${ss.ring}`}
                      >
                        {ss.label}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-xs text-zinc-400">
                      {row.liquidity === "high" ? "بالا" : "متوسط"}
                    </td>
                    <td className="py-2.5 px-3 text-xs text-zinc-400">
                      {row.management_fee}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reasoning */}
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-4">
        <h2 className="text-sm font-semibold text-zinc-200 mb-3">📖 منطق سیگنال</h2>
        <ul className="text-xs text-zinc-400 space-y-1.5 leading-relaxed">
          <li>
            <span className="text-emerald-300 font-semibold">خرید (BUY):</span> صندوق بیش از ۱٪
            زیر NAV معامله شود (discount).
          </li>
          <li>
            <span className="text-rose-300 font-semibold">فروش (SELL):</span> صندوق بیش از ۲٪ بالای
            NAV معامله شود (premium).
          </li>
          <li>
            <span className="text-zinc-300 font-semibold">خنثی (NEUTRAL):</span> قیمت در بازه -۱٪
            تا +۲٪ NAV.
          </li>
        </ul>
      </div>
    </div>
  );
}

function ETFCard({ row }: { row: ETFNavRow }) {
  const ss = signalStyle(row.signal);
  return (
    <div
      className={`rounded-xl ring-1 ${ss.ring} ${ss.bg} p-4 backdrop-blur transition hover:scale-[1.01]`}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="text-base font-semibold text-zinc-100">{row.name_fa}</div>
          <div className="text-[10px] text-zinc-500">{row.symbol} • {row.isin}</div>
        </div>
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ${ss.ring} ${ss.text}`}
        >
          {ss.label}
        </span>
      </div>
      <div className="text-xl font-bold text-zinc-100 tabular-nums mb-1">
        {fmt(row.market_price)}
      </div>
      <div className="text-[10px] text-zinc-500 mb-2">NAV: {fmt(row.nav)}</div>
      <div className="border-t border-zinc-800/40 pt-2 flex items-baseline justify-between">
        <div className="text-[10px] text-zinc-500">Premium</div>
        <div className={`text-base font-bold tabular-nums ${ss.text}`}>
          {fmtPct(row.premium_pct)}
        </div>
      </div>
      <div className="text-[10px] text-zinc-500 mt-2 leading-relaxed">{row.reason}</div>
    </div>
  );
}
