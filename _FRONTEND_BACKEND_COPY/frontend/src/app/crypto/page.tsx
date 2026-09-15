"use client";

import { useState, useMemo } from "react";
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
  high_24h?: number;
  low_24h?: number;
}

type SortKey = "rank" | "price_usd" | "change_percent" | "market_cap" | "volume_24h";

function MiniSparkline({ seed }: { seed: number }) {
  const points = Array.from({ length: 24 }, (_, i) => {
    const base = Math.sin(seed * 100 + i * 0.5) * 30 + 50;
    return Math.max(10, Math.min(90, base + (Math.sin(i * 1.3 + seed) * 15)));
  });
  const pathD = points.map((y, i) => `${i === 0 ? "M" : "L"} ${(i / 23) * 100} ${y}`).join(" ");
  const isPositive = points[23] >= points[0];

  return (
    <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`sg-${seed}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={isPositive ? "#10b981" : "#f43f5e"} stopOpacity="0.3" />
          <stop offset="100%" stopColor={isPositive ? "#10b981" : "#f43f5e"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={pathD + " L100 100 L0 100 Z"} fill={`url(#sg-${seed})`} />
      <path d={pathD} fill="none" stroke={isPositive ? "#10b981" : "#f43f5e"} strokeWidth="1.5" />
    </svg>
  );
}

function formatUsd(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function HeroCard({ cryptos }: { cryptos: CryptoPrice[] }) {
  const totalMarketCap = cryptos.reduce((s, c) => s + (c.market_cap || 0), 0);
  const totalVolume = cryptos.reduce((s, c) => s + (c.volume_24h || 0), 0);
  const avgChange = cryptos.reduce((s, c) => s + c.change_percent, 0) / cryptos.length;
  const positive = cryptos.filter((c) => c.change_percent >= 0).length;
  const isMarketPositive = avgChange >= 0;

  const stats = [
    {
      label: "ارزش کل بازار",
      value: formatUsd(totalMarketCap),
      sub: `${cryptos.length} ارز فعال`,
      color: "from-primary-500/20 to-accent-violet/20",
    },
    {
      label: "حجم معاملات ۲۴ ساعت",
      value: formatUsd(totalVolume),
      sub: "معامله انجام شده",
      color: "from-accent-cyan/20 to-primary-500/20",
    },
    {
      label: "میانگین تغییرات",
      value: `${avgChange >= 0 ? "+" : ""}${avgChange.toFixed(2)}%`,
      sub: isMarketPositive ? "بازار صعودی" : "بازار نزولی",
      color: isMarketPositive ? "from-accent-emerald/20 to-accent-cyan/20" : "from-accent-rose/20 to-accent-amber/20",
      valueColor: isMarketPositive ? "text-accent-emerald" : "text-accent-rose",
    },
    {
      label: "وضعیت بازار",
      value: `${positive}/${cryptos.length}`,
      sub: positive > cryptos.length / 2 ? "اکثر صعودی" : "اکثر نزولی",
      color: positive > cryptos.length / 2 ? "from-accent-emerald/20 to-accent-amber/20" : "from-accent-rose/20 to-primary-500/20",
      valueColor: positive > cryptos.length / 2 ? "text-accent-emerald" : "text-accent-rose",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      {stats.map((s, i) => (
        <div
          key={i}
          className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${s.color} border border-white/5 p-4 lg:p-5`}
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.05),transparent_60%)]" />
          <div className="relative">
            <div className="text-xs text-surface-400 mb-2 font-medium">{s.label}</div>
            <div className={`text-lg lg:text-xl font-bold font-mono ${s.valueColor || "text-surface-100"}`}>
              {s.value}
            </div>
            <div className="text-[10px] text-surface-500 mt-1">{s.sub}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function FeaturedCoins({ cryptos }: { cryptos: CryptoPrice[] }) {
  const top5 = [...cryptos].sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0)).slice(0, 5);

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-primary-400" />
        برترین ارزها بر اساس ارزش بازار
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {top5.map((c, i) => {
          const isPositive = c.change_percent >= 0;
          return (
            <div
              key={c.symbol}
              className="group relative overflow-hidden rounded-xl bg-surface-900/60 border border-white/5 p-4 hover:border-primary-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-primary-500/5"
            >
              <div className="absolute top-0 right-0 w-20 h-20 opacity-20">
                <MiniSparkline seed={c.rank + i * 7} />
              </div>
              <div className="relative">
                <div className="flex items-center gap-2 mb-3">
                  {c.icon_url ? (
                    <img src={c.icon_url} alt={c.symbol} className="w-8 h-8 rounded-full" loading="lazy"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500/30 to-accent-violet/30 flex items-center justify-center text-xs font-bold text-primary-300">
                      {c.symbol?.slice(0, 2)}
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-surface-200 truncate">{c.name}</div>
                    <div className="text-[10px] text-surface-500 font-mono uppercase">{c.symbol}</div>
                  </div>
                </div>
                <div className="font-mono font-bold text-surface-100 text-sm mb-1">
                  ${c.price_usd?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div className={`font-mono text-xs font-bold ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {isPositive ? "+" : ""}{c.change_percent?.toFixed(2)}%
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MoversSection({ cryptos }: { cryptos: CryptoPrice[] }) {
  const sorted = [...cryptos].sort((a, b) => b.change_percent - a.change_percent);
  const gainers = sorted.slice(0, 5);
  const losers = sorted.slice(-5).reverse();

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      {/* Gainers */}
      <div className="rounded-2xl border border-accent-emerald/10 bg-gradient-to-br from-accent-emerald/5 to-transparent p-4">
        <div className="text-sm font-semibold text-accent-emerald mb-3 flex items-center gap-2">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M7 17l5-5 5 5M7 7l5 5 5-5" />
          </svg>
          بیشترین افزایش قیمت
        </div>
        <div className="space-y-1">
          {gainers.map((c, i) => (
            <div
              key={c.symbol}
              className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-accent-emerald/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-surface-600 w-5">#{i + 1}</span>
                {c.icon_url ? (
                  <img src={c.icon_url} alt="" className="w-6 h-6 rounded-full" loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                ) : (
                  <div className="w-6 h-6 rounded-full bg-accent-emerald/10 flex items-center justify-center text-[9px] font-bold text-accent-emerald">
                    {c.symbol?.slice(0, 1)}
                  </div>
                )}
                <div>
                  <div className="text-xs font-medium text-surface-300">{c.symbol}</div>
                  <div className="text-[10px] text-surface-600">{c.name}</div>
                </div>
              </div>
              <div className="text-left">
                <div className="font-mono font-bold text-accent-emerald text-sm">
                  +{c.change_percent.toFixed(2)}%
                </div>
                <div className="font-mono text-[10px] text-surface-500">
                  ${c.price_usd?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Losers */}
      <div className="rounded-2xl border border-accent-rose/10 bg-gradient-to-br from-accent-rose/5 to-transparent p-4">
        <div className="text-sm font-semibold text-accent-rose mb-3 flex items-center gap-2">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M7 7l5 5 5-5M7 17l5-5 5 5" />
          </svg>
          بیشترین کاهش قیمت
        </div>
        <div className="space-y-1">
          {losers.map((c, i) => (
            <div
              key={c.symbol}
              className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-accent-rose/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-surface-600 w-5">#{i + 1}</span>
                {c.icon_url ? (
                  <img src={c.icon_url} alt="" className="w-6 h-6 rounded-full" loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                ) : (
                  <div className="w-6 h-6 rounded-full bg-accent-rose/10 flex items-center justify-center text-[9px] font-bold text-accent-rose">
                    {c.symbol?.slice(0, 1)}
                  </div>
                )}
                <div>
                  <div className="text-xs font-medium text-surface-300">{c.symbol}</div>
                  <div className="text-[10px] text-surface-600">{c.name}</div>
                </div>
              </div>
              <div className="text-left">
                <div className="font-mono font-bold text-accent-rose text-sm">
                  {c.change_percent.toFixed(2)}%
                </div>
                <div className="font-mono text-[10px] text-surface-500">
                  ${c.price_usd?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CryptoTable({ cryptos }: { cryptos: CryptoPrice[] }) {
  const [sortBy, setSortBy] = useState<SortKey>("rank");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sorted = useMemo(() => {
    return [...cryptos].sort((a, b) => {
      const av = sortBy === "volume_24h" ? (a.volume_24h || 0) : (a[sortBy] || 0);
      const bv = sortBy === "volume_24h" ? (b.volume_24h || 0) : (b[sortBy] || 0);
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [cryptos, sortBy, sortDir]);

  const toggleSort = (col: SortKey) => {
    if (sortBy === col) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(col); setSortDir(col === "rank" ? "asc" : "desc"); }
  };

  const SortIcon = ({ col }: { col: SortKey }) => (
    <span className="text-[10px] ml-1 opacity-50">
      {sortBy === col ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
    </span>
  );

  const columns: { key: SortKey; label: string; className?: string }[] = [
    { key: "rank", label: "رتبه" },
    { key: "price_usd", label: "قیمت", className: "text-left" },
    { key: "change_percent", label: "تغییرات ۲۴h", className: "text-left" },
    { key: "market_cap", label: "ارزش بازار", className: "text-left hidden md:table-cell" },
    { key: "volume_24h", label: "حجم ۲۴h", className: "text-left hidden lg:table-cell" },
  ];

  return (
    <div className="rounded-2xl border border-white/5 overflow-hidden bg-surface-900/40">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5">
              <th className="text-right py-3 px-4 font-medium text-xs text-surface-500 w-12">#</th>
              <th className="text-right py-3 px-4 font-medium text-xs text-surface-500">ارز</th>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`py-3 px-4 font-medium text-xs text-surface-500 cursor-pointer hover:text-surface-300 transition-colors select-none ${col.className || "text-right"}`}
                  onClick={() => toggleSort(col.key)}
                >
                  {col.label}
                  <SortIcon col={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => {
              const isPositive = c.change_percent >= 0;
              return (
                <tr
                  key={`${c.symbol}-${i}`}
                  className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors group"
                >
                  <td className="py-3 px-4">
                    <span className="text-[10px] font-mono text-surface-600">{c.rank}</span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      {c.icon_url ? (
                        <img src={c.icon_url} alt="" className="w-7 h-7 rounded-full" loading="lazy"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                        />
                      ) : (
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary-500/20 to-accent-violet/20 flex items-center justify-center text-[10px] font-bold text-primary-300">
                          {c.symbol?.slice(0, 2)}
                        </div>
                      )}
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-surface-200 group-hover:text-primary-300 transition-colors truncate">
                          {c.name}
                        </div>
                        <div className="text-[10px] text-surface-600 font-mono uppercase">{c.symbol}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-left">
                    <div className="font-mono font-bold text-surface-200">
                      ${c.price_usd?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    <div className="text-[10px] text-surface-600 font-mono">
                      {c.price_toman ? `${c.price_toman.toLocaleString()} تومان` : ""}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-left">
                    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono font-bold ${
                      isPositive ? "bg-accent-emerald/10 text-accent-emerald" : "bg-accent-rose/10 text-accent-rose"
                    }`}>
                      <span className="text-[10px]">{isPositive ? "▲" : "▼"}</span>
                      {isPositive ? "+" : ""}{c.change_percent.toFixed(2)}%
                    </div>
                  </td>
                  <td className="py-3 px-4 text-left hidden md:table-cell">
                    <span className="font-mono text-surface-400">{formatUsd(c.market_cap || 0)}</span>
                  </td>
                  <td className="py-3 px-4 text-left hidden lg:table-cell">
                    <span className="font-mono text-surface-500">{formatUsd(c.volume_24h || 0)}</span>
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

export default function CryptoPage() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("rank");

  const { data: cryptos, isLoading, error } = useQuery({
    queryKey: ["brsapi-crypto-market", sortBy],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: CryptoPrice[] }>(
        `/brsapi/crypto?limit=100&sort_by=${sortBy}`
      );
      return res.data || [];
    },
    refetchInterval: 30_000,
  });

  const filtered = useMemo(() => {
    if (!cryptos) return [];
    if (!search.trim()) return cryptos;
    const q = search.toLowerCase();
    return cryptos.filter(
      (c) => c.name.toLowerCase().includes(q) || c.symbol.toLowerCase().includes(q)
    );
  }, [cryptos, search]);

  return (
    <AppLayout title="بازار ارز دیجیتال" subtitle="قیمت لحظه‌ای بیش از ۱۰۰ ارز دیجیتال به دلار و تومان">
      {/* Hero Stats */}
      {!isLoading && filtered.length > 0 && <HeroCard cryptos={filtered} />}

      {/* Search + Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            placeholder="جستجو بر اساس نام یا نماد..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pr-10 pl-4 py-2.5 bg-surface-900/60 border border-white/5 rounded-xl text-sm text-surface-200 placeholder-surface-600 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20 transition-all"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex gap-1 bg-surface-900/60 rounded-xl p-1 border border-white/5">
            {[
              { key: "rank", label: "رتبه" },
              { key: "market_cap", label: "ارزش بازار" },
              { key: "change_percent", label: "تغییرات" },
              { key: "price_usd", label: "قیمت" },
            ].map((s) => (
              <button
                key={s.key}
                onClick={() => setSortBy(s.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  sortBy === s.key
                    ? "bg-primary-600 text-white shadow-md shadow-primary-600/20"
                    : "text-surface-500 hover:text-surface-300"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 text-xs text-surface-500">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse" />
            <span>لحظه‌ای</span>
            {filtered.length > 0 && (
              <span className="text-surface-600">({filtered.length})</span>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 mb-4 bg-accent-rose/10 border border-accent-rose/20 rounded-xl text-accent-rose text-sm flex items-center gap-2">
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          خطا در دریافت داده‌ها
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-2xl bg-surface-900/40 border border-white/5 p-5">
                <Skeleton className="h-3 w-20 mb-3" />
                <Skeleton className="h-6 w-28 mb-2" />
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="rounded-xl bg-surface-900/40 border border-white/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Skeleton className="w-8 h-8 rounded-full" />
                  <div>
                    <Skeleton className="h-3 w-16 mb-1" />
                    <Skeleton className="h-2.5 w-10" />
                  </div>
                </div>
                <Skeleton className="h-4 w-24 mb-1" />
                <Skeleton className="h-3 w-12" />
              </div>
            ))}
          </div>
        </>
      )}

      {/* Featured Coins */}
      {!isLoading && filtered.length > 0 && <FeaturedCoins cryptos={filtered} />}

      {/* Top Movers */}
      {!isLoading && filtered.length > 0 && <MoversSection cryptos={filtered} />}

      {/* Full Table */}
      {!isLoading && filtered.length > 0 && <CryptoTable cryptos={filtered} />}

      {/* Empty */}
      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-30">₿</div>
          <p className="text-surface-500 text-sm">داده‌ای یافت نشد</p>
          <p className="text-surface-600 text-xs mt-2">
            {search ? "عبارت جستجو را تغییر دهید" : "منتظر همگام‌سازی داده‌ها باشید"}
          </p>
        </div>
      )}
    </AppLayout>
  );
}
