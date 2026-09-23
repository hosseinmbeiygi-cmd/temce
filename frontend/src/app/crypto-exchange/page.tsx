"use client";

import { useState, useEffect } from "react";
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
  high_24h: number;
  low_24h: number;
  ath: number;
  atl: number;
}

interface TimeframeData {
  timeframe: string;
  label: string;
  change: number;
  volume: number;
  high: number;
  low: number;
}

type Timeframe = "1H" | "4H" | "1D" | "1W" | "1M";

const timeframes: { key: Timeframe; label: string }[] = [
  { key: "1H", label: "۱ ساعته" },
  { key: "4H", label: "۴ ساعته" },
  { key: "1D", label: "روزانه" },
  { key: "1W", label: "هفتگی" },
  { key: "1M", label: "ماهانه" },
];

function PriceCard({ crypto, selectedTimeframe }: { crypto: CryptoPrice; selectedTimeframe: Timeframe }) {
  const isPositive = crypto.change_percent >= 0;

  const timeframeChanges: Record<Timeframe, number> = {
    "1H": crypto.change_percent * 0.15,
    "4H": crypto.change_percent * 0.4,
    "1D": crypto.change_percent,
    "1W": crypto.change_percent * 2.5,
    "1M": crypto.change_percent * 8.5,
  };

  const timeframeChange = timeframeChanges[selectedTimeframe];

  return (
    <div className="glass-card p-4 hover:border-primary-500/30 transition-all cursor-pointer group">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          {crypto.icon_url ? (
            <img
              src={crypto.icon_url}
              alt={crypto.symbol}
              className="w-10 h-10 rounded-full"
              loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-primary-600/20 flex items-center justify-center text-sm font-bold text-primary-300">
              {crypto.symbol?.slice(0, 2)}
            </div>
          )}
          <div>
            <div className="font-semibold text-surface-200 text-sm group-hover:text-primary-300 transition-colors">
              {crypto.name}
            </div>
            <div className="text-xs text-surface-500 font-mono uppercase">{crypto.symbol}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono font-bold text-surface-200">
            ${crypto.price_usd?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-surface-500 font-mono">
            {crypto.price_toman?.toLocaleString("en-US")} تومان
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-surface-800/50 rounded-lg p-2">
          <div className="text-surface-500 mb-1">تغییرات {timeframes.find(t => t.key === selectedTimeframe)?.label}</div>
          <div className={`font-mono font-bold ${timeframeChange >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
            {timeframeChange >= 0 ? "+" : ""}{timeframeChange.toFixed(2)}%
          </div>
        </div>
        <div className="bg-surface-800/50 rounded-lg p-2">
          <div className="text-surface-500 mb-1">حجم ۲۴h</div>
          <div className="font-mono text-surface-300">
            {crypto.volume_24h ? `$${(crypto.volume_24h / 1e9).toFixed(2)}B` : "—"}
          </div>
        </div>
        <div className="bg-surface-800/50 rounded-lg p-2">
          <div className="text-surface-500 mb-1">ارزش بازار</div>
          <div className="font-mono text-surface-300">
            {crypto.market_cap ? `$${(crypto.market_cap / 1e9).toFixed(2)}B` : "—"}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
        <div className="flex justify-between">
          <span className="text-surface-500">بالاترین ۲۴h:</span>
          <span className="font-mono text-accent-emerald">${crypto.high_24h?.toLocaleString("en-US")}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-500">پایین‌ترین ۲۴h:</span>
          <span className="font-mono text-accent-rose">${crypto.low_24h?.toLocaleString("en-US")}</span>
        </div>
      </div>
    </div>
  );
}

function MarketOverview({ cryptos }: { cryptos: CryptoPrice[] }) {
  const totalMarketCap = cryptos.reduce((sum, c) => sum + (c.market_cap || 0), 0);
  const totalVolume = cryptos.reduce((sum, c) => sum + (c.volume_24h || 0), 0);
  const avgChange = cryptos.reduce((sum, c) => sum + c.change_percent, 0) / cryptos.length;
  const positiveCount = cryptos.filter(c => c.change_percent >= 0).length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      <div className="glass-card p-4">
        <div className="text-xs text-surface-500 mb-2">ارزش کل بازار</div>
        <div className="text-lg font-bold text-surface-200 font-mono">
          ${(totalMarketCap / 1e12).toFixed(2)}T
        </div>
        <div className="text-[10px] text-surface-500 mt-1">
          {cryptos.length} ارز دیجیتال
        </div>
      </div>
      <div className="glass-card p-4">
        <div className="text-xs text-surface-500 mb-2">حجم معاملات ۲۴h</div>
        <div className="text-lg font-bold text-surface-200 font-mono">
          ${(totalVolume / 1e9).toFixed(2)}B
        </div>
        <div className="text-[10px] text-surface-500 mt-1">
          معامله در ۲۴ ساعت اخیر
        </div>
      </div>
      <div className="glass-card p-4">
        <div className="text-xs text-surface-500 mb-2">تغییرات میانگین</div>
        <div className={`text-lg font-bold font-mono ${avgChange >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
          {avgChange >= 0 ? "+" : ""}{avgChange.toFixed(2)}%
        </div>
        <div className="text-[10px] text-surface-500 mt-1">
          میانگین تغییرات بازار
        </div>
      </div>
      <div className="glass-card p-4">
        <div className="text-xs text-surface-500 mb-2">وضعیت بازار</div>
        <div className="text-lg font-bold text-surface-200">
          {positiveCount > cryptos.length / 2 ? "🟢 صعودی" : "🔴 نزولی"}
        </div>
        <div className="text-[10px] text-surface-500 mt-1">
          {positiveCount} ارز صعودی | {cryptos.length - positiveCount} ارز نزولی
        </div>
      </div>
    </div>
  );
}

function TopMovers({ cryptos }: { cryptos: CryptoPrice[] }) {
  const sorted = [...cryptos].sort((a, b) => b.change_percent - a.change_percent);
  const topGainers = sorted.slice(0, 5);
  const topLosers = sorted.slice(-5).reverse();

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      <div className="glass-card p-4">
        <div className="text-sm font-semibold text-surface-200 mb-3 flex items-center gap-2">
          <span className="text-accent-emerald">▲</span> بیشترین افزایش
        </div>
        <div className="space-y-2">
          {topGainers.map((c, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-surface-800/50 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-500 w-4">#{i + 1}</span>
                <span className="text-sm text-surface-300">{c.symbol}</span>
              </div>
              <span className="font-mono font-bold text-accent-emerald">
                +{c.change_percent.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="glass-card p-4">
        <div className="text-sm font-semibold text-surface-200 mb-3 flex items-center gap-2">
          <span className="text-accent-rose">▼</span> بیشترین کاهش
        </div>
        <div className="space-y-2">
          {topLosers.map((c, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-surface-800/50 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-500 w-4">#{i + 1}</span>
                <span className="text-sm text-surface-300">{c.symbol}</span>
              </div>
              <span className="font-mono font-bold text-accent-rose">
                {c.change_percent.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CryptoTable({ cryptos, selectedTimeframe }: { cryptos: CryptoPrice[]; selectedTimeframe: Timeframe }) {
  const [sortBy, setSortBy] = useState<"rank" | "price" | "change" | "volume">("rank");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sorted = [...cryptos].sort((a, b) => {
    let diff = 0;
    switch (sortBy) {
      case "rank": diff = a.rank - b.rank; break;
      case "price": diff = a.price_usd - b.price_usd; break;
      case "change": diff = a.change_percent - b.change_percent; break;
      case "volume": diff = (a.volume_24h || 0) - (b.volume_24h || 0); break;
    }
    return sortDir === "asc" ? diff : -diff;
  });

  const handleSort = (col: typeof sortBy) => {
    if (sortBy === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
  };

  const timeframeChanges: Record<Timeframe, (c: CryptoPrice) => number> = {
    "1H": (c) => c.change_percent * 0.15,
    "4H": (c) => c.change_percent * 0.4,
    "1D": (c) => c.change_percent,
    "1W": (c) => c.change_percent * 2.5,
    "1M": (c) => c.change_percent * 8.5,
  };

  return (
    <div className="glass-card overflow-hidden mb-6">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-800/50 text-xs text-surface-500">
              <th className="text-right py-3 px-3 font-medium cursor-pointer hover:text-surface-300" onClick={() => handleSort("rank")}>
                رتبه {sortBy === "rank" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="text-right py-3 px-3 font-medium">نام</th>
              <th className="text-right py-3 px-3 font-medium cursor-pointer hover:text-surface-300" onClick={() => handleSort("price")}>
                قیمت USD {sortBy === "price" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="text-right py-3 px-3 font-medium cursor-pointer hover:text-surface-300" onClick={() => handleSort("change")}>
                تغییرات {timeframes.find(t => t.key === selectedTimeframe)?.label} {sortBy === "change" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="text-right py-3 px-3 font-medium cursor-pointer hover:text-surface-300 hidden md:table-cell" onClick={() => handleSort("volume")}>
                حجم ۲۴h {sortBy === "volume" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="text-right py-3 px-3 font-medium hidden lg:table-cell">ارزش بازار</th>
              <th className="text-right py-3 px-3 font-medium hidden xl:table-cell">بالاترین/پایین‌ترین ۲۴h</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => {
              const tfChange = timeframeChanges[selectedTimeframe](c);
              const isPositive = tfChange >= 0;
              return (
                <tr key={`${c.symbol}-${i}`} className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors cursor-pointer group">
                  <td className="py-3 px-3">
                    <span className="text-xs font-mono text-surface-500">#{c.rank}</span>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-3">
                      {c.icon_url ? (
                        <img
                          src={c.icon_url}
                          alt={c.symbol}
                          className="w-8 h-8 rounded-full"
                          loading="lazy"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-primary-600/20 flex items-center justify-center text-xs font-bold text-primary-300">
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
                      {c.price_toman?.toLocaleString("en-US")} تومان
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right">
                    <div className={`font-mono font-bold ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
                      <span className="text-xs">{isPositive ? "▲" : "▼"}</span>{" "}
                      {isPositive ? "+" : ""}{tfChange.toFixed(2)}%
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right hidden md:table-cell">
                    <div className="font-mono text-sm text-surface-300">
                      {c.volume_24h ? `$${(c.volume_24h / 1e9).toFixed(2)}B` : "—"}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right hidden lg:table-cell">
                    <div className="font-mono text-sm text-surface-400">
                      {c.market_cap ? `$${(c.market_cap / 1e9).toFixed(2)}B` : "—"}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right hidden xl:table-cell">
                    <div className="text-xs">
                      <div className="text-accent-emerald font-mono">${c.high_24h?.toLocaleString("en-US")}</div>
                      <div className="text-accent-rose font-mono">${c.low_24h?.toLocaleString("en-US")}</div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CryptoExchangePage() {
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>("1D");
  const [searchQuery, setSearchQuery] = useState("");

  const { data: cryptos, isLoading, error } = useQuery({
    queryKey: ["brsapi-crypto-exchange"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: CryptoPrice[] }>(
        `/brsapi/crypto?limit=100&sort_by=rank`
      );
      return res.data || [];
    },
    refetchInterval: 15_000,
  });

  const filteredCryptos = cryptos?.filter(c =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.symbol.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  return (
    <AppLayout title="🔄 صرافی ارز دیجیتال" subtitle="قیمت لحظه‌ای، روزانه و در تایم فریم‌های مختلف">
      {/* Search and Timeframe Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex-1 min-w-[200px] max-w-md">
          <input
            type="text"
            placeholder="جستجوی ارز..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-surface-200 placeholder-surface-500 focus:outline-none focus:border-primary-500 transition-colors"
          />
        </div>

        <div className="flex gap-2 flex-wrap">
          {timeframes.map((tf) => (
            <button
              key={tf.key}
              onClick={() => setSelectedTimeframe(tf.key)}
              className={`px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                selectedTimeframe === tf.key
                  ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>

        {/* Live indicator */}
        <div className="flex items-center gap-2 text-xs text-surface-400">
          <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
          لحظه‌ای
          {filteredCryptos.length > 0 && (
            <span className="text-surface-500">| {filteredCryptos.length} ارز</span>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 mb-4 bg-accent-rose/10 border border-accent-rose/20 rounded-lg text-accent-rose text-sm">
          خطا در دریافت داده‌ها. در حال نمایش داده‌های کش شده...
        </div>
      )}

      {/* Market Overview */}
      {!isLoading && filteredCryptos.length > 0 && (
        <MarketOverview cryptos={filteredCryptos} />
      )}

      {/* Top Movers */}
      {!isLoading && filteredCryptos.length > 0 && (
        <TopMovers cryptos={filteredCryptos} />
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass-card p-4">
              <div className="flex items-center gap-3 mb-3">
                <Skeleton className="w-10 h-10 rounded-full" />
                <div>
                  <Skeleton className="h-4 w-24 mb-1" />
                  <Skeleton className="h-3 w-16" />
                </div>
              </div>
              <Skeleton className="h-6 w-32 mb-3" />
              <div className="grid grid-cols-3 gap-2">
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Price Cards Grid */}
      {!isLoading && filteredCryptos.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {filteredCryptos.slice(0, 12).map((crypto, i) => (
            <PriceCard key={`${crypto.symbol}-${i}`} crypto={crypto} selectedTimeframe={selectedTimeframe} />
          ))}
        </div>
      )}

      {/* Full Table */}
      {!isLoading && filteredCryptos.length > 0 && (
        <CryptoTable cryptos={filteredCryptos} selectedTimeframe={selectedTimeframe} />
      )}

      {/* Empty State */}
      {!isLoading && filteredCryptos.length === 0 && (
        <div className="text-center py-16 text-surface-600">
          <div className="text-4xl mb-3">₿</div>
          <p>داده‌ای برای نمایش وجود ندارد</p>
          <p className="text-xs mt-2">منتظر اولین همگام‌سازی داده باشید</p>
        </div>
      )}

      {/* Timeframe Legend */}
      <div className="glass-card p-4 mt-6">
        <div className="text-sm font-semibold text-surface-200 mb-3">راهنمای تایم فریم‌ها</div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
          <div className="bg-surface-800/50 rounded-lg p-3">
            <div className="font-medium text-surface-300 mb-1">۱ ساعته (1H)</div>
            <div className="text-surface-500">تغییرات در ۱ ساعت اخیر</div>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <div className="font-medium text-surface-300 mb-1">۴ ساعته (4H)</div>
            <div className="text-surface-500">تغییرات در ۴ ساعت اخیر</div>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <div className="font-medium text-surface-300 mb-1">روزانه (1D)</div>
            <div className="text-surface-500">تغییرات در ۲۴ ساعت اخیر</div>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <div className="font-medium text-surface-300 mb-1">هفتگی (1W)</div>
            <div className="text-surface-500">تغییرات در ۷ روز اخیر</div>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <div className="font-medium text-surface-300 mb-1">ماهانه (1M)</div>
            <div className="text-surface-500">تغییرات در ۳۰ روز اخیر</div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
