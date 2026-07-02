"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface CryptoPrice {
  name: string;
  symbol: string;
  price_usd: number;
  price_toman: number;
  change_percent: number;
  market_cap: number;
  volume_24h: number;
  icon_url: string;
  rank: number;
}

function CryptoRow({ c }: { c: CryptoPrice }) {
  const isPositive = c.change_percent >= 0;

  return (
    <tr className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors cursor-pointer group">
      <td className="py-3 px-3">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-surface-500 w-6">#{c.rank}</span>
          {c.icon_url ? (
            <img
              src={c.icon_url}
              alt={c.symbol}
              className="w-7 h-7 rounded-full"
              loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <div className="w-7 h-7 rounded-full bg-primary-600/20 flex items-center justify-center text-xs font-bold text-primary-300">
              {c.symbol?.slice(0, 2)}
            </div>
          )}
          <div>
            <div className="font-semibold text-surface-200 text-sm group-hover:text-primary-300 transition-colors">
              {c.name}
            </div>
            <div className="text-[10px] text-surface-500 font-mono uppercase">{c.symbol}</div>
          </div>
        </div>
      </td>
      <td className="py-3 px-3 text-right">
        <div className="font-mono font-bold text-surface-200">
          ${c.price_usd?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="text-[10px] text-surface-500 font-mono">
          {c.price_toman?.toLocaleString()} تومان
        </div>
      </td>
      <td className="py-3 px-3 text-right">
        <div className={`font-mono font-bold ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
          <span className="text-xs">{isPositive ? "▲" : "▼"}</span>{" "}
          {isPositive ? "+" : ""}{c.change_percent?.toFixed(2)}%
        </div>
      </td>
      <td className="py-3 px-3 text-right hidden md:table-cell">
        <div className="font-mono text-sm text-surface-300">
          {c.market_cap ? `$${(c.market_cap / 1e9).toFixed(2)}B` : "—"}
        </div>
      </td>
      <td className="py-3 px-3 text-right hidden lg:table-cell">
        <div className="font-mono text-sm text-surface-400">
          {c.volume_24h ? `$${(c.volume_24h / 1e9).toFixed(2)}B` : "—"}
        </div>
      </td>
    </tr>
  );
}

export default function CryptoPage() {
  const [sortBy, setSortBy] = useState("rank");

  const { data: cryptos, isLoading, error } = useQuery({
    queryKey: ["brsapi-crypto", sortBy],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: CryptoPrice[] }>(
        `/brsapi/crypto?limit=100&sort_by=${sortBy}`
      );
      return res.data || [];
    },
    refetchInterval: 30_000,
  });

  return (
    <AppLayout title="₿ قیمت‌های ارز دیجیتال" subtitle="بیش از ۳۰۰۰ ارز دیجیتال - قیمت لحظه‌ای به دلار و تومان">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex gap-2 flex-wrap">
          {[
            { key: "rank", label: "رتبه" },
            { key: "market_cap", label: "ارزش بازار" },
            { key: "change_percent", label: "تغییرات" },
            { key: "price_usd", label: "قیمت" },
          ].map((s) => (
            <button
              key={s.key}
              onClick={() => setSortBy(s.key)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                sortBy === s.key
                  ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Live indicator */}
        <div className="flex items-center gap-2 text-xs text-surface-400">
          <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
          لحظه‌ای
          {cryptos && cryptos.length > 0 && (
            <span className="text-surface-500">| {cryptos.length} ارز</span>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 mb-4 bg-accent-rose/10 border border-accent-rose/20 rounded-lg text-accent-rose text-sm">
          خطا در دریافت داده‌ها. در حال نمایش داده‌های کش شده...
        </div>
      )}

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-800/50 text-xs text-surface-500">
                <th className="text-right py-3 px-3 font-medium">نام</th>
                <th className="text-right py-3 px-3 font-medium">قیمت</th>
                <th className="text-right py-3 px-3 font-medium">تغییرات</th>
                <th className="text-right py-3 px-3 font-medium hidden md:table-cell">ارزش بازار</th>
                <th className="text-right py-3 px-3 font-medium hidden lg:table-cell">حجم ۲۴h</th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 10 }).map((_, i) => (
                    <tr key={i} className="border-b border-surface-800/50">
                      {[1, 2, 3, 4, 5].map((j) => (
                        <td key={j} className="py-3 px-3">
                          <Skeleton className="h-5 w-24" />
                        </td>
                      ))}
                    </tr>
                  ))
                : cryptos?.map((c, i) => <CryptoRow key={`${c.symbol}-${i}`} c={c} />)
              }
            </tbody>
          </table>
        </div>

        {!isLoading && cryptos?.length === 0 && (
          <div className="text-center py-16 text-surface-600">
            <div className="text-4xl mb-3">₿</div>
            <p>داده‌ای برای نمایش وجود ندارد</p>
            <p className="text-xs mt-2">منتظر اولین همگام‌سازی داده باشید</p>
          </div>
        )}
      </div>

      {/* Summary Cards */}
      {cryptos && cryptos.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">بیشترین افزایش</div>
            <div className="text-sm font-bold text-accent-emerald font-mono">
              {([...cryptos].sort((a, b) => b.change_percent - a.change_percent)[0]?.change_percent || 0).toFixed(2)}%
            </div>
            <div className="text-[10px] text-surface-500">
              {[...cryptos].sort((a, b) => b.change_percent - a.change_percent)[0]?.symbol}
            </div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">بیشترین کاهش</div>
            <div className="text-sm font-bold text-accent-rose font-mono">
              {([...cryptos].sort((a, b) => a.change_percent - b.change_percent)[0]?.change_percent || 0).toFixed(2)}%
            </div>
            <div className="text-[10px] text-surface-500">
              {[...cryptos].sort((a, b) => a.change_percent - b.change_percent)[0]?.symbol}
            </div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">بزرگترین ارزش بازار</div>
            <div className="text-sm font-bold text-surface-200 font-mono">
              {cryptos[0]?.symbol || "—"}
            </div>
            <div className="text-[10px] text-surface-500">
              ${((cryptos[0]?.market_cap || 0) / 1e9).toFixed(2)}B
            </div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">تعداد کل</div>
            <div className="text-sm font-bold text-primary-300 font-mono">{cryptos.length}</div>
            <div className="text-[10px] text-surface-500">ارز دیجیتال</div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
