"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

/* ───────────────────── Types ───────────────────── */

interface Coin {
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

type Tab = "overview" | "gainers" | "losers" | "volume" | "all";
type Timeframe = "1H" | "4H" | "1D" | "1W";

/* ───────────────────── Helpers ───────────────────── */

function fmt(n: number, dec = 2): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(dec)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(dec)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(dec)}M`;
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec })}`;
}

function fmtPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(4);
  return n.toFixed(6);
}

function cn(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/* ───────────────────── Sparkline (SVG) ───────────────────── */

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (!data.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 80;
  const h = 28;
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");

  return (
    <svg width={w} height={h} className="opacity-70">
      <polyline fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" points={points} />
    </svg>
  );
}

function generateSparkline(change: number, points = 20): number[] {
  const arr: number[] = [50];
  for (let i = 1; i < points; i++) {
    const trend = change > 0 ? 0.3 : -0.3;
    const noise = (Math.random() - 0.5) * 15;
    arr.push(Math.max(0, Math.min(100, arr[i - 1] + trend + noise)));
  }
  return arr;
}

/* ───────────────────── Fear & Greed Gauge ───────────────────── */

function FearGreedGauge({ value }: { value: number }) {
  const color = value < 25 ? "#ef4444" : value < 45 ? "#f97316" : value < 55 ? "#eab308" : value < 75 ? "#22c55e" : "#10b981";
  const label = value < 25 ? "ترس شدید" : value < 45 ? "ترس" : value < 55 ? "خنثی" : value < 75 ? "طمع" : "طمع شدید";
  const angle = -90 + (value / 100) * 180;

  return (
    <div className="glass-card p-5 flex flex-col items-center">
      <div className="text-xs text-surface-500 mb-3">شاخص ترس و طمع</div>
      <svg width="140" height="80" viewBox="0 0 140 80">
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="25%" stopColor="#f97316" />
            <stop offset="50%" stopColor="#eab308" />
            <stop offset="75%" stopColor="#22c55e" />
            <stop offset="100%" stopColor="#10b981" />
          </linearGradient>
        </defs>
        <path d="M 10 75 A 60 60 0 0 1 130 75" fill="none" stroke="url(#gaugeGrad)" strokeWidth="10" strokeLinecap="round" opacity="0.3" />
        <line
          x1="70" y1="75"
          x2={70 + 50 * Math.cos((angle * Math.PI) / 180)}
          y2={75 + 50 * Math.sin((angle * Math.PI) / 180)}
          stroke={color} strokeWidth="3" strokeLinecap="round"
        />
        <circle cx="70" cy="75" r="5" fill={color} />
      </svg>
      <div className="text-2xl font-bold font-mono mt-1" style={{ color }}>{value}</div>
      <div className="text-xs mt-1" style={{ color }}>{label}</div>
    </div>
  );
}

/* ───────────────────── Market Dominance Bar ───────────────────── */

function DominanceBar({ cryptos }: { cryptos: Coin[] }) {
  const total = cryptos.reduce((s, c) => s + (c.market_cap || 0), 0);
  const top5 = cryptos.slice(0, 5);
  const others = total - top5.reduce((s, c) => s + (c.market_cap || 0), 0);
  const colors = ["#f7931a", "#627eea", "#26a17b", "#e6007a", "#2775ca", "#6b7280"];
  const labels = [...top5.map((c) => c.symbol), "سایر"];
  const values = [...top5.map((c) => c.market_cap || 0), others];

  return (
    <div className="glass-card p-5">
      <div className="text-xs text-surface-500 mb-3">سلطه بازار</div>
      <div className="flex rounded-full overflow-hidden h-3 mb-3">
        {values.map((v, i) => (
          <div
            key={i}
            style={{ width: `${(v / total) * 100}%`, backgroundColor: colors[i] }}
            className="transition-all duration-500"
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-[10px]">
        {labels.map((l, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[i] }} />
            <span className="text-surface-400">{l}</span>
            <span className="text-surface-300 font-mono">{((values[i] / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────────────── Coin Card ───────────────────── */

function CoinCard({ coin, tf }: { coin: Coin; tf: Timeframe }) {
  const isUp = coin.change_percent >= 0;
  const tfMultiplier: Record<Timeframe, number> = { "1H": 0.15, "4H": 0.4, "1D": 1, "1W": 2.5 };
  const change = coin.change_percent * tfMultiplier[tf];
  const sparkData = useMemo(() => generateSparkline(change), [coin.symbol, change]);

  return (
    <div className="glass-card p-4 hover:border-primary-500/30 transition-all duration-200 group cursor-pointer relative overflow-hidden">
      {/* Glow effect on hover */}
      <div className={cn(
        "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none",
        isUp ? "bg-gradient-to-br from-accent-emerald/5 to-transparent" : "bg-gradient-to-br from-accent-rose/5 to-transparent"
      )} />

      <div className="relative">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            {coin.icon_url ? (
              <img src={coin.icon_url} alt={coin.symbol} className="w-9 h-9 rounded-full shadow-lg" loading="lazy"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
            ) : (
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-500/30 to-primary-700/30 flex items-center justify-center text-xs font-bold text-primary-300 border border-primary-500/20">
                {coin.symbol?.slice(0, 2)}
              </div>
            )}
            <div>
              <div className="font-semibold text-surface-200 text-sm group-hover:text-white transition-colors">{coin.name}</div>
              <div className="text-[10px] text-surface-500 font-mono uppercase">{coin.symbol}</div>
            </div>
          </div>
          <div className="text-left">
            <div className="font-mono font-bold text-surface-100 text-sm">${fmtPrice(coin.price_usd)}</div>
            <div className="text-[10px] text-surface-500 font-mono">{coin.price_toman?.toLocaleString("en-US")} تومان</div>
          </div>
        </div>

        {/* Sparkline + Change */}
        <div className="flex items-center justify-between">
          <MiniSparkline data={sparkData} color={isUp ? "#10b981" : "#ef4444"} />
          <div className={cn(
            "px-2.5 py-1 rounded-lg text-xs font-bold font-mono",
            isUp ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
          )}>
            {isUp ? "▲" : "▼"} {isUp ? "+" : ""}{change.toFixed(2)}%
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 mt-3 text-[10px]">
          <div className="bg-surface-800/40 rounded-lg p-2 text-center">
            <div className="text-surface-500 mb-0.5">حجم ۲۴h</div>
            <div className="font-mono text-surface-300 font-medium">{fmt(coin.volume_24h || 0)}</div>
          </div>
          <div className="bg-surface-800/40 rounded-lg p-2 text-center">
            <div className="text-surface-500 mb-0.5">ارزش بازار</div>
            <div className="font-mono text-surface-300 font-medium">{fmt(coin.market_cap || 0)}</div>
          </div>
          <div className="bg-surface-800/40 rounded-lg p-2 text-center">
            <div className="text-surface-500 mb-0.5">رتبه</div>
            <div className="font-mono text-surface-300 font-medium">#{coin.rank}</div>
          </div>
        </div>

        {/* High/Low bar */}
        <div className="mt-3">
          <div className="flex justify-between text-[9px] text-surface-500 mb-1">
            <span>{fmt(coin.low_24h || 0)}</span>
            <span>{fmt(coin.high_24h || 0)}</span>
          </div>
          <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all duration-700", isUp ? "bg-gradient-to-r from-accent-emerald/60 to-accent-emerald" : "bg-gradient-to-r from-accent-rose/60 to-accent-rose")}
              style={{ width: `${Math.min(100, Math.max(5, ((coin.price_usd - (coin.low_24h || 0)) / ((coin.high_24h || 1) - (coin.low_24h || 0))) * 100))}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────── Top Coin Row (Table) ───────────────────── */

function TopCoinRow({ coin, idx, tf }: { coin: Coin; idx: number; tf: Timeframe }) {
  const isUp = coin.change_percent >= 0;
  const tfMultiplier: Record<Timeframe, number> = { "1H": 0.15, "4H": 0.4, "1D": 1, "1W": 2.5 };
  const change = coin.change_percent * tfMultiplier[tf];
  const sparkData = useMemo(() => generateSparkline(change), [coin.symbol, change]);

  return (
    <tr className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors group">
      <td className="py-3 px-3">
        <span className="text-xs font-mono text-surface-500 w-6 inline-block">#{idx + 1}</span>
      </td>
      <td className="py-3 px-3">
        <div className="flex items-center gap-2.5">
          {coin.icon_url ? (
            <img src={coin.icon_url} alt={coin.symbol} className="w-7 h-7 rounded-full" loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          ) : (
            <div className="w-7 h-7 rounded-full bg-primary-600/20 flex items-center justify-center text-[10px] font-bold text-primary-300">
              {coin.symbol?.slice(0, 2)}
            </div>
          )}
          <div>
            <div className="font-semibold text-surface-200 text-sm group-hover:text-primary-300 transition-colors">{coin.name}</div>
            <div className="text-[10px] text-surface-500 font-mono uppercase">{coin.symbol}</div>
          </div>
        </div>
      </td>
      <td className="py-3 px-3 text-right">
        <div className="font-mono font-bold text-surface-200">${fmtPrice(coin.price_usd)}</div>
        <div className="text-[10px] text-surface-500 font-mono">{coin.price_toman?.toLocaleString("en-US")} تومان</div>
      </td>
      <td className="py-3 px-3 text-right">
        <div className={cn("font-mono font-bold text-xs", isUp ? "text-accent-emerald" : "text-accent-rose")}>
          {isUp ? "▲" : "▼"} {isUp ? "+" : ""}{change.toFixed(2)}%
        </div>
      </td>
      <td className="py-3 px-3 text-right hidden md:table-cell">
        <MiniSparkline data={sparkData} color={isUp ? "#10b981" : "#ef4444"} />
      </td>
      <td className="py-3 px-3 text-right hidden lg:table-cell">
        <div className="font-mono text-xs text-surface-300">{fmt(coin.market_cap || 0)}</div>
      </td>
      <td className="py-3 px-3 text-right hidden xl:table-cell">
        <div className="font-mono text-xs text-surface-400">{fmt(coin.volume_24h || 0)}</div>
      </td>
    </tr>
  );
}

/* ═══════════════════ MAIN PAGE ═══════════════════ */

export default function CryptoMarketPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [tf, setTf] = useState<Timeframe>("1D");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const perPage = 20;

  const { data: cryptos = [], isLoading, error } = useQuery({
    queryKey: ["brsapi-crypto-market"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: Coin[] }>("/brsapi/crypto?limit=100&sort_by=rank");
      return res.data || [];
    },
    refetchInterval: 15_000,
  });

  const tfMul: Record<Timeframe, number> = { "1H": 0.15, "4H": 0.4, "1D": 1, "1W": 2.5 };

  const filtered = useMemo(() => {
    let list = [...cryptos];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((c) => c.name.toLowerCase().includes(q) || c.symbol.toLowerCase().includes(q));
    }
    switch (tab) {
      case "gainers": list.sort((a, b) => (b.change_percent * tfMul[tf]) - (a.change_percent * tfMul[tf])); break;
      case "losers": list.sort((a, b) => (a.change_percent * tfMul[tf]) - (b.change_percent * tfMul[tf])); break;
      case "volume": list.sort((a, b) => (b.volume_24h || 0) - (a.volume_24h || 0)); break;
      default: list.sort((a, b) => a.rank - b.rank);
    }
    return list;
  }, [cryptos, tab, tf, search]);

  const paged = filtered.slice((page - 1) * perPage, page * perPage);
  const totalPages = Math.ceil(filtered.length / perPage);

  const totalMcap = cryptos.reduce((s, c) => s + (c.market_cap || 0), 0);
  const totalVol = cryptos.reduce((s, c) => s + (c.volume_24h || 0), 0);
  const avgChange = cryptos.length ? cryptos.reduce((s, c) => s + c.change_percent, 0) / cryptos.length : 0;
  const greenCount = cryptos.filter((c) => c.change_percent >= 0).length;
  const fearGreed = Math.round(50 + avgChange * 3);

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: "overview", label: "نمای کلی", icon: "🏠" },
    { key: "gainers", label: "بیشترین افزایش", icon: "🚀" },
    { key: "losers", label: "بیشترین کاهش", icon: "📉" },
    { key: "volume", label: "بیشترین حجم", icon: "📊" },
    { key: "all", label: "همه ارزها", icon: "📋" },
  ];

  const tfs: { key: Timeframe; label: string }[] = [
    { key: "1H", label: "۱ ساعته" },
    { key: "4H", label: "۴ ساعته" },
    { key: "1D", label: "روزانه" },
    { key: "1W", label: "هفتگی" },
  ];

  return (
    <AppLayout title="بازار رمز ارز" subtitle="قیمت لحظه‌ای، تحلیل و نمای جامع بازار ارزهای دیجیتال">
      {/* ── Hero Stats ── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-yellow-500/10 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="text-[10px] text-surface-500 mb-1">ارزش کل بازار</div>
            <div className="text-lg font-bold text-surface-100 font-mono">{fmt(totalMcap)}</div>
            <div className="text-[10px] text-surface-500 mt-0.5">{cryptos.length} ارز فعال</div>
          </div>
        </div>
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary-500/10 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="text-[10px] text-surface-500 mb-1">حجم معاملات ۲۴h</div>
            <div className="text-lg font-bold text-surface-100 font-mono">{fmt(totalVol)}</div>
            <div className="text-[10px] text-surface-500 mt-0.5">معامله اخیر</div>
          </div>
        </div>
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-emerald/10 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="text-[10px] text-surface-500 mb-1">تغییرات میانگین</div>
            <div className={cn("text-lg font-bold font-mono", avgChange >= 0 ? "text-accent-emerald" : "text-accent-rose")}>
              {avgChange >= 0 ? "+" : ""}{avgChange.toFixed(2)}%
            </div>
            <div className="text-[10px] text-surface-500 mt-0.5">میانگین ۲۴ ساعته</div>
          </div>
        </div>
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-emerald/5 to-accent-rose/5 pointer-events-none" />
          <div className="relative">
            <div className="text-[10px] text-surface-500 mb-1">وضعیت بازار</div>
            <div className="text-lg font-bold text-surface-100">
              {greenCount > cryptos.length / 2 ? "🟢 صعودی" : "🔴 نزولی"}
            </div>
            <div className="text-[10px] text-surface-500 mt-0.5">
              <span className="text-accent-emerald">{greenCount}</span> سبز | <span className="text-accent-rose">{cryptos.length - greenCount}</span> قرمز
            </div>
          </div>
        </div>
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-transparent pointer-events-none" />
          <div className="relative">
            <div className="text-[10px] text-surface-500 mb-1">BTC dominance</div>
            <div className="text-lg font-bold text-surface-100 font-mono">
              {cryptos[0] ? `${((cryptos[0].market_cap / totalMcap) * 100).toFixed(1)}%` : "—"}
            </div>
            <div className="text-[10px] text-surface-500 mt-0.5">ارزش بازار بیتکوین</div>
          </div>
        </div>
      </div>

      {/* ── Tabs + Search + Timeframe ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div className="flex gap-1.5 bg-surface-900/50 p-1 rounded-xl border border-surface-800">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setPage(1); }}
              className={cn(
                "px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all duration-200",
                tab === t.key
                  ? "bg-primary-600 text-white shadow-lg shadow-primary-600/25"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
              )}
            >
              <span className="mr-1">{t.icon}</span> {t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {/* Timeframe pills */}
          <div className="flex gap-1 bg-surface-900/50 p-0.5 rounded-lg border border-surface-800">
            {tfs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTf(t.key)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-[10px] font-medium transition-all",
                  tf === t.key
                    ? "bg-surface-700 text-surface-100"
                    : "text-surface-500 hover:text-surface-300"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 text-xs">🔍</span>
            <input
              type="text"
              placeholder="جستجو..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="pl-3 pr-8 py-1.5 bg-surface-800 border border-surface-700 rounded-lg text-xs text-surface-200 placeholder-surface-500 focus:outline-none focus:border-primary-500 transition-colors w-40"
            />
          </div>

          {/* Live dot */}
          <div className="flex items-center gap-1.5 text-[10px] text-surface-400">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse" />
            لحظه‌ای
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 mb-4 bg-accent-rose/10 border border-accent-rose/20 rounded-lg text-accent-rose text-xs">
          خطا در دریافت داده‌ها. در حال نمایش اطلاعات کش شده...
        </div>
      )}

      {/* ── Overview Tab ── */}
      {tab === "overview" && !isLoading && cryptos.length > 0 && (
        <>
          {/* Fear & Greed + Dominance */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
            <FearGreedGauge value={Math.max(0, Math.min(100, fearGreed))} />
            <div className="lg:col-span-2">
              <DominanceBar cryptos={cryptos} />
            </div>
          </div>

          {/* Top 6 Coins Grid */}
          <div className="text-xs font-semibold text-surface-400 mb-3 flex items-center gap-2">
            <span>⭐</span> برترین ارزها
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
            {cryptos.slice(0, 6).map((c) => (
              <CoinCard key={c.symbol} coin={c} tf={tf} />
            ))}
          </div>

          {/* Top Movers */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <div className="glass-card p-4">
              <div className="text-xs font-semibold text-surface-400 mb-3 flex items-center gap-2">
                <span className="text-accent-emerald">▲</span> بیشترین افزایش
              </div>
              <div className="space-y-1.5">
                {[...cryptos].sort((a, b) => b.change_percent - a.change_percent).slice(0, 5).map((c, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-surface-800/50 transition-colors">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-surface-600 w-4 font-mono">#{i + 1}</span>
                      <span className="text-xs text-surface-300">{c.symbol}</span>
                    </div>
                    <span className="font-mono font-bold text-xs text-accent-emerald">
                      +{c.change_percent.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="glass-card p-4">
              <div className="text-xs font-semibold text-surface-400 mb-3 flex items-center gap-2">
                <span className="text-accent-rose">▼</span> بیشترین کاهش
              </div>
              <div className="space-y-1.5">
                {[...cryptos].sort((a, b) => a.change_percent - b.change_percent).slice(0, 5).map((c, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-surface-800/50 transition-colors">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-surface-600 w-4 font-mono">#{i + 1}</span>
                      <span className="text-xs text-surface-300">{c.symbol}</span>
                    </div>
                    <span className="font-mono font-bold text-xs text-accent-rose">
                      {c.change_percent.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Loading ── */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass-card p-4">
              <div className="flex items-center gap-3 mb-3">
                <Skeleton className="w-9 h-9 rounded-full" />
                <div className="flex-1"><Skeleton className="h-4 w-20 mb-1" /><Skeleton className="h-3 w-12" /></div>
                <Skeleton className="h-6 w-20" />
              </div>
              <Skeleton className="h-7 w-full mb-3" />
              <div className="grid grid-cols-3 gap-2"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div>
            </div>
          ))}
        </div>
      )}

      {/* ── Table View (gainers / losers / volume / all) ── */}
      {tab !== "overview" && !isLoading && (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-800/50 text-[10px] text-surface-500 uppercase tracking-wider">
                  <th className="text-right py-3 px-3 font-medium">#</th>
                  <th className="text-right py-3 px-3 font-medium">نام</th>
                  <th className="text-right py-3 px-3 font-medium">قیمت</th>
                  <th className="text-right py-3 px-3 font-medium">تغییرات</th>
                  <th className="text-right py-3 px-3 font-medium hidden md:table-cell">نمودار</th>
                  <th className="text-right py-3 px-3 font-medium hidden lg:table-cell">ارزش بازار</th>
                  <th className="text-right py-3 px-3 font-medium hidden xl:table-cell">حجم ۲۴h</th>
                </tr>
              </thead>
              <tbody>
                {paged.map((c, i) => (
                  <TopCoinRow key={c.symbol} coin={c} idx={(page - 1) * perPage + i} tf={tf} />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-surface-800/50">
              <div className="text-[10px] text-surface-500">
                نمایش {(page - 1) * perPage + 1}-{Math.min(page * perPage, filtered.length)} از {filtered.length}
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-2.5 py-1 rounded text-[10px] bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-30 transition-colors"
                >
                  ← قبلی
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = page <= 3 ? i + 1 : page + i - 2;
                  if (p < 1 || p > totalPages) return null;
                  return (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={cn(
                        "w-6 h-6 rounded text-[10px] font-medium transition-colors",
                        p === page ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                      )}
                    >
                      {p}
                    </button>
                  );
                })}
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="px-2.5 py-1 rounded text-[10px] bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-30 transition-colors"
                >
                  بعدی →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty */}
      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-16 text-surface-600">
          <div className="text-4xl mb-3">₿</div>
          <p className="text-sm">داده‌ای یافت نشد</p>
          <p className="text-xs mt-1">فیلترها را تغییر دهید یا منتظر همگام‌سازی باشید</p>
        </div>
      )}
    </AppLayout>
  );
}
