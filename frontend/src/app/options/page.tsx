"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";

interface OptionContract {
  symbol: string;
  name: string;
  underlying_symbol: string;
  option_type: string;
  strike_price: number;
  open_interest: number;
  date_begin: string;
  date_end: string;
  days_remaining: number;
}

function extract(resp: unknown) {
  if (resp && typeof resp === "object" && "data" in resp) {
    const d = (resp as { data?: unknown }).data;
    if (d && typeof d === "object" && "rows" in d) return (d as { rows?: unknown[] }).rows ?? [];
    return extractArray(d);
  }
  return extractArray(resp);
}

export default function OptionsPage() {
  const [filter, setFilter] = useState<"all" | "call" | "put">("all");
  const [search, setSearch] = useState("");

  const { data: resp, isLoading } = useQuery({
    queryKey: ["options"],
    queryFn: async () => apiGet<unknown>("/tables/brsapi_option_snapshots?page=1&page_size=500"),
  });

  const raw: OptionContract[] = extract(resp) as OptionContract[];
  const options = raw.map((o: OptionContract) => ({
    symbol: String(o.symbol || ""),
    name: String(o.name || ""),
    underlying_symbol: String(o.underlying_symbol || ""),
    option_type: String(o.option_type || ""),
    strike_price: Number(o.strike_price || 0),
    open_interest: Number(o.open_interest || 0),
    date_begin: String(o.date_begin || ""),
    date_end: String(o.date_end || ""),
    days_remaining: Number(o.days_remaining || 0),
  }));

  const filtered = options
    .filter(o => filter === "all" || (filter === "call" ? o.option_type.includes("call") || o.option_type === "خرید" : o.option_type.includes("put") || o.option_type === "فروش"))
    .filter(o => !search || o.symbol.includes(search) || o.underlying_symbol.includes(search) || o.name.includes(search));

  // Group by underlying
  const underlyingMap = new Map<string, OptionContract[]>();
  for (const o of filtered) {
    const key = o.underlying_symbol || "نامشخص";
    if (!underlyingMap.has(key)) underlyingMap.set(key, []);
    underlyingMap.get(key)!.push(o);
  }
  const underlyingList = Array.from(underlyingMap.entries()).sort((a, b) => b[1].length - a[1].length);

  return (
    <AppLayout title="بازار آپشن" subtitle="قراردادهای اختیار معامله بورس">
      {/* ------ Filters ------ */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <div className="flex gap-2">
          {([["all", "همه"], ["call", "اختیار خرید"], ["put", "اختیار فروش"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => setFilter(k)}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${filter === k ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
              {l}
            </button>
          ))}
        </div>
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="جستجوی نماد پایه..."
          className="px-3 py-1.5 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-48" />
        <span className="text-xs text-surface-500">{filtered.length} قرارداد</span>
      </div>

      {/* ------ Content ------ */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : underlyingList.length === 0 ? (
        <div className="text-center py-16 text-surface-500">
          <span className="material-icons text-5xl mb-4 block">options</span>
          <div className="text-lg font-bold">داده‌ای یافت نشد</div>
          <div className="text-sm mt-2">ابتدا بخش آپشن را از BrsApi همگام‌سازی کنید</div>
        </div>
      ) : (
        <div className="space-y-4">
          {underlyingList.map(([symbol, contracts]) => (
            <div key={symbol} className="glass-card overflow-hidden">
              <div className="flex items-center justify-between p-4 bg-surface-800/50">
                <div className="flex items-center gap-3">
                  <span className="material-icons text-primary-400">show_chart</span>
                  <span className="font-bold text-surface-100 text-base">{symbol}</span>
                  <span className="text-xs bg-primary-600/20 text-primary-300 px-2 py-0.5 rounded-full font-bold">
                    {contracts.length} قرارداد
                  </span>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-right text-sm">
                  <thead>
                    <tr className="border-b border-surface-700">
                      <th className="px-3 py-2.5 font-bold text-surface-400">نماد</th>
                      <th className="px-3 py-2.5 font-bold text-surface-400">نوع</th>
                      <th className="px-3 py-2.5 font-bold text-surface-400">قیمت اعمال</th>
                      <th className="px-3 py-2.5 font-bold text-surface-400">موقعیت باز</th>
                      <th className="px-3 py-2.5 font-bold text-surface-400">تاریخ شروع</th>
                      <th className="px-3 py-2.5 font-bold text-surface-400">تاریخ سررسید</th>
                      <th className="px-3 py-2.5 font-bold text-surface-400">روزهای باقیمانده</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contracts.map((c, i) => (
                      <tr key={`${c.symbol}-${i}`} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                        <td className="px-3 py-2 font-mono font-bold text-surface-200">{c.symbol}</td>
                        <td className="px-3 py-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                            c.option_type.includes("call") || c.option_type === "خرید"
                              ? "bg-accent-emerald/15 text-accent-emerald"
                              : "bg-accent-rose/15 text-accent-rose"
                          }`}>
                            {c.option_type.includes("call") || c.option_type === "خرید" ? "خرید (Call)" : "فروش (Put)"}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-mono text-surface-200">{c.strike_price.toLocaleString("fa-IR")}</td>
                        <td className="px-3 py-2 font-mono text-surface-300">{c.open_interest.toLocaleString("fa-IR")}</td>
                        <td className="px-3 py-2 text-surface-400 text-xs font-mono">{c.date_begin}</td>
                        <td className="px-3 py-2 text-surface-400 text-xs font-mono">{c.date_end}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs font-bold font-mono ${
                            c.days_remaining <= 7 ? "text-accent-rose" : c.days_remaining <= 30 ? "text-accent-amber" : "text-surface-300"
                          }`}>
                            {c.days_remaining}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
