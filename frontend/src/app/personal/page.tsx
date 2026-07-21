"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { apiGet, extractArray } from "@/lib/api";

const PieChartCard = dynamic(() => import("@/components/charts/PieChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl h-[220px]" />,
});

// ── Types ──────────────────────────────────────────────────────────────────────

interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
}

interface PortfolioPosition {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  weight_pct: number;
}

interface PortfolioData {
  id: string;
  name: string;
  current_value: number;
  initial_capital: number;
  total_return_pct: number;
  positions: PortfolioPosition[];
}

interface SignalItem {
  id: string;
  symbol: string;
  name: string;
  direction: string;
  score: number;
  confidence: number;
  source: string;
  created_at: string;
  price: number;
  change_pct: number;
}

interface MarketIndex {
  name: string;
  code: string;
  value: number;
  change: number;
}

interface MarketGainer {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
}

interface MarketDashboardData {
  overview: {
    total_instruments?: number;
    gainers?: number;
    losers?: number;
    unchanged?: number;
    index_value?: number;
    index_change_pct?: number;
  };
  gainers: MarketGainer[];
  losers: MarketGainer[];
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000_000) return (n / 1_000_000_000_000).toFixed(2) + "T";
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + "B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return n.toLocaleString("fa-IR");
}

const DIRECTION_STYLES: Record<string, string> = {
  buy: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30",
  sell: "bg-accent-rose/15 text-accent-rose border-accent-rose/30",
  hold: "bg-surface-700/30 text-surface-400 border-surface-600/30",
};

const DIRECTION_LABELS: Record<string, string> = {
  buy: "خرید",
  sell: "فروش",
  hold: "نگهداری",
};

const PIE_COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#06b6d4", "#f97316", "#ec4899",
  "#14b8a6", "#a855f7",
];

// ── Skeleton ───────────────────────────────────────────────────────────────────

function SkeletonBlock({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-surface-800/50 rounded-xl ${className}`} />;
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function PersonalDashboardPage() {
  const [signalFilter, setSignalFilter] = useState<string>("all");

  // ── Fetch watchlist ──
  const { data: watchlistData, isLoading: loadingWatchlist } = useQuery({
    queryKey: ["watchlist"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { items: WatchlistItem[] } }>("/watchlist");
        return extractArray<WatchlistItem>(res);
      } catch {
        return [] as WatchlistItem[];
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  // ── Fetch portfolio ──
  const { data: portfolioData, isLoading: loadingPortfolio } = useQuery({
    queryKey: ["personal-portfolio"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { items: PortfolioData[] } }>("/portfolios");
        const items = extractArray<PortfolioData>(res);
        return items.length > 0 ? items[0] : null;
      } catch {
        return null;
      }
    },
    refetchInterval: 60_000,
  });

  // ── Fetch signals ──
  const { data: signalsData, isLoading: loadingSignals } = useQuery({
    queryKey: ["personal-signals"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { items: SignalItem[] } }>("/signals?page=1&page_size=10");
        return extractArray<SignalItem>(res);
      } catch {
        return [] as SignalItem[];
      }
    },
    refetchInterval: 30_000,
  });

  // ── Fetch market data ──
  const { data: marketData, isLoading: loadingMarket } = useQuery<MarketDashboardData>({
    queryKey: ["personal-market"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: MarketDashboardData }>("/market-dashboard");
        return res?.data ?? ({} as MarketDashboardData);
      } catch {
        return { overview: {}, gainers: [], losers: [] } as MarketDashboardData;
      }
    },
    refetchInterval: 60_000,
  });

  // ── Fetch indices ──
  const { data: indices } = useQuery({
    queryKey: ["personal-indices"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { items: MarketIndex[] } }>("/market/indices");
        return extractArray<MarketIndex>(res);
      } catch {
        return [
          { name: "شاخص کل", code: "TEDPIX", value: 0, change: 0 },
          { name: "شاخص هم وزن", code: "IFX", value: 0, change: 0 },
        ] as MarketIndex[];
      }
    },
    refetchInterval: 60_000,
  });

  // ── Portfolio pie chart data ──
  const pieData = useMemo(() => {
    if (!portfolioData?.positions?.length) return [];
    return portfolioData.positions
      .sort((a, b) => b.weight_pct - a.weight_pct)
      .slice(0, 10)
      .map((p, i) => ({
        name: p.symbol,
        value: Math.abs(p.weight_pct),
        color: PIE_COLORS[i % PIE_COLORS.length],
      }));
  }, [portfolioData]);

  // ── Filtered signals ──
  const filteredSignals = useMemo(() => {
    if (!signalsData) return [];
    if (signalFilter === "all") return signalsData;
    return signalsData.filter((s) => s.direction === signalFilter);
  }, [signalsData, signalFilter]);

  // ── Quick actions ──
  const quickActions = [
    { label: "سیگنال‌ها", icon: "trending_up", href: "/signals", color: "from-primary-600 to-primary-800" },
    { label: "پرتفوی", icon: "account_balance_wallet", href: "/portfolio", color: "from-accent-emerald/80 to-accent-emerald" },
    { label: "پول هوشمند", icon: "psychology", href: "/smart-money", color: "from-accent-amber/80 to-accent-amber" },
    { label: "بک‌تست", icon: "science", href: "/backtest", color: "from-accent-violet/80 to-accent-violet" },
    { label: "تحلیل", icon: "analytics", href: "/analysis", color: "from-accent-cyan/80 to-accent-cyan" },
    { label: "علاقه‌مندی‌ها", icon: "star", href: "/watchlist", color: "from-accent-rose/80 to-accent-rose" },
  ];

  return (
    <AppLayout>
      <div className="space-y-6 p-4 md:p-6" dir="rtl">
        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-surface-50">داشبورد شخصی</h1>
            <p className="text-sm text-surface-400 mt-1">نمای کلی بازار و پرتفوی شما</p>
          </div>
        </div>

        {/* ── Market Indices Strip ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {(indices || []).slice(0, 3).map((idx) => (
            <div key={idx.code} className="flex items-center justify-between bg-surface-800/60 rounded-xl px-4 py-3 border border-surface-700/50">
              <span className="text-sm text-surface-300">{idx.name}</span>
              <div className="flex items-center gap-3" dir="ltr">
                <span className="text-lg font-bold text-surface-100 font-mono">{idx.value.toLocaleString("en-US")}</span>
                <span className={`text-xs font-mono font-semibold ${idx.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {idx.change >= 0 ? "+" : ""}{idx.change.toFixed(2)}%
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── Left Column (2/3) ── */}
          <div className="lg:col-span-2 space-y-6">
            {/* ── Quick Actions ── */}
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
              {quickActions.map((action) => (
                <Link
                  key={action.label}
                  href={action.href}
                  className={`flex flex-col items-center gap-2 p-3 rounded-xl bg-gradient-to-br ${action.color} text-white/90 hover:scale-105 transition-transform`}
                >
                  <span className="material-icons text-2xl">{action.icon}</span>
                  <span className="text-xs font-medium">{action.label}</span>
                </Link>
              ))}
            </div>

            {/* ── Watchlist ── */}
            <Card title="لیست علاقه‌مندی‌ها" subtitle="قیمت‌های لحظه‌ای">
              {loadingWatchlist ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => <SkeletonBlock key={i} className="h-14" />)}
                </div>
              ) : !watchlistData?.length ? (
                <div className="text-center py-8 text-surface-500 text-sm">
                  نمادی در لیست علاقه‌مندی‌ها وجود ندارد
                  <Link href="/watchlist" className="text-primary-400 hover:underline mr-2">افزودن نماد</Link>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-surface-500 text-xs border-b border-surface-700/50">
                        <th className="text-right py-2 px-3">نماد</th>
                        <th className="text-right py-2 px-3">نام</th>
                        <th className="text-left py-2 px-3" dir="ltr">قیمت</th>
                        <th className="text-left py-2 px-3" dir="ltr">تغییر</th>
                      </tr>
                    </thead>
                    <tbody>
                      {watchlistData.slice(0, 10).map((item) => (
                        <tr key={item.symbol} className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors">
                          <td className="py-2.5 px-3 font-medium text-primary-300">{item.symbol}</td>
                          <td className="py-2.5 px-3 text-surface-300">{item.name}</td>
                          <td className="py-2.5 px-3 text-left font-mono text-surface-100" dir="ltr">{fmtPrice(item.price)}</td>
                          <td className="py-2.5 px-3 text-left" dir="ltr">
                            <span className={`font-mono font-semibold text-xs px-2 py-0.5 rounded ${item.change_pct >= 0 ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"}`}>
                              {item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {/* ── Recent Signals ── */}
            <Card
              title="سیگنال‌های اخیر"
              actions={
                <div className="flex gap-1">
                  {["all", "buy", "sell"].map((f) => (
                    <button
                      key={f}
                      onClick={() => setSignalFilter(f)}
                      className={`text-xs px-3 py-1 rounded-lg transition-colors ${
                        signalFilter === f
                          ? "bg-primary-600/20 text-primary-300"
                          : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
                      }`}
                    >
                      {f === "all" ? "همه" : f === "buy" ? "خرید" : "فروش"}
                    </button>
                  ))}
                </div>
              }
            >
              {loadingSignals ? (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => <SkeletonBlock key={i} className="h-16" />)}
                </div>
              ) : !filteredSignals.length ? (
                <div className="text-center py-8 text-surface-500 text-sm">سیگنالی یافت نشد</div>
              ) : (
                <div className="space-y-2">
                  {filteredSignals.slice(0, 8).map((sig) => (
                    <div key={sig.id} className="flex items-center justify-between p-3 rounded-xl bg-surface-800/40 hover:bg-surface-800/60 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className={`px-2 py-1 rounded-lg text-xs font-semibold border ${DIRECTION_STYLES[sig.direction] || DIRECTION_STYLES.hold}`}>
                          {DIRECTION_LABELS[sig.direction] || sig.direction}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-surface-100">{sig.symbol}</div>
                          <div className="text-xs text-surface-500">{sig.source}</div>
                        </div>
                      </div>
                      <div className="text-left" dir="ltr">
                        <div className="font-mono text-sm text-surface-200">{fmtPrice(sig.price)}</div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={`text-xs font-mono ${sig.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                            {sig.change_pct >= 0 ? "+" : ""}{sig.change_pct.toFixed(2)}%
                          </span>
                          <span className="text-[10px] text-surface-500">{(sig.confidence * 100).toFixed(0)}% اعتماد</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* ── Right Column (1/3) ── */}
          <div className="space-y-6">
            {/* ── Portfolio Summary ── */}
            <Card title="خلاصه پرتفوی">
              {loadingPortfolio ? (
                <div className="space-y-3">
                  <SkeletonBlock className="h-8 w-32" />
                  <SkeletonBlock className="h-4 w-24" />
                  <SkeletonBlock className="h-[220px]" />
                </div>
              ) : !portfolioData ? (
                <div className="text-center py-8 text-surface-500 text-sm">
                  پرتفویی یافت نشد
                  <Link href="/portfolio" className="text-primary-400 hover:underline mr-2">ایجاد پرتفوی</Link>
                </div>
              ) : (
                <>
                  <div className="mb-4">
                    <div className="text-2xl font-bold text-surface-50 font-mono" dir="ltr">{fmtPrice(portfolioData.current_value)}</div>
                    <div className="text-xs text-surface-400 mt-1">ارزش کل پرتفوی</div>
                    <div className={`text-sm font-semibold mt-1 ${portfolioData.total_return_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {portfolioData.total_return_pct >= 0 ? "+" : ""}{portfolioData.total_return_pct.toFixed(2)}% بازده
                    </div>
                  </div>

                  {pieData.length > 0 && (
                    <PieChartCard
                      title="ترکیب پرتفوی"
                      data={pieData}
                      height={220}
                      innerRadius={55}
                      outerRadius={85}
                      valueFormatter={(v) => `${v.toFixed(1)}%`}
                    />
                  )}

                  {portfolioData.positions?.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {portfolioData.positions
                        .sort((a, b) => b.weight_pct - a.weight_pct)
                        .slice(0, 5)
                        .map((pos, i) => (
                          <div key={pos.symbol} className="flex items-center justify-between text-sm py-1.5 border-b border-surface-800/30">
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                              <span className="text-surface-200">{pos.symbol}</span>
                            </div>
                            <div className="text-left" dir="ltr">
                              <span className="text-surface-300 font-mono">{pos.weight_pct.toFixed(1)}%</span>
                              <span className={`text-xs mr-2 font-mono ${pos.unrealized_pnl >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                                {pos.unrealized_pnl >= 0 ? "+" : ""}{((pos.current_price / pos.avg_cost - 1) * 100).toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </>
              )}
            </Card>

            {/* ── Top Gainers ── */}
            <Card title="بیشترین رشد">
              {loadingMarket ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => <SkeletonBlock key={i} className="h-10" />)}
                </div>
              ) : (
                <div className="space-y-1">
                  {(marketData?.gainers || []).slice(0, 5).map((g) => (
                    <Link
                      key={g.symbol}
                      href={`/symbol/${g.symbol}`}
                      className="flex items-center justify-between py-2 px-2 rounded-lg hover:bg-surface-800/50 transition-colors"
                    >
                      <div>
                        <span className="text-sm text-surface-100 font-medium">{g.symbol}</span>
                        <span className="text-xs text-surface-500 mr-2">{g.name}</span>
                      </div>
                      <span className="text-xs font-mono font-semibold text-accent-emerald">
                        +{g.change_pct.toFixed(2)}%
                      </span>
                    </Link>
                  ))}
                  {(!marketData?.gainers || marketData.gainers.length === 0) && (
                    <div className="text-center py-4 text-surface-500 text-xs">داده‌ای موجود نیست</div>
                  )}
                </div>
              )}
            </Card>

            {/* ── Top Losers ── */}
            <Card title="بیشترین افت">
              {loadingMarket ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => <SkeletonBlock key={i} className="h-10" />)}
                </div>
              ) : (
                <div className="space-y-1">
                  {(marketData?.losers || []).slice(0, 5).map((l) => (
                    <Link
                      key={l.symbol}
                      href={`/symbol/${l.symbol}`}
                      className="flex items-center justify-between py-2 px-2 rounded-lg hover:bg-surface-800/50 transition-colors"
                    >
                      <div>
                        <span className="text-sm text-surface-100 font-medium">{l.symbol}</span>
                        <span className="text-xs text-surface-500 mr-2">{l.name}</span>
                      </div>
                      <span className="text-xs font-mono font-semibold text-accent-rose">
                        {l.change_pct.toFixed(2)}%
                      </span>
                    </Link>
                  ))}
                  {(!marketData?.losers || marketData.losers.length === 0) && (
                    <div className="text-center py-4 text-surface-500 text-xs">داده‌ای موجود نیست</div>
                  )}
                </div>
              )}
            </Card>

            {/* ── Market Summary ── */}
            <Card title="خلاصه بازار">
              {loadingMarket ? (
                <SkeletonBlock className="h-24" />
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                    <div className="text-lg font-bold text-accent-emerald font-mono">{marketData?.overview?.gainers || 0}</div>
                    <div className="text-xs text-surface-400">سبزها</div>
                  </div>
                  <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                    <div className="text-lg font-bold text-accent-rose font-mono">{marketData?.overview?.losers || 0}</div>
                    <div className="text-xs text-surface-400">قرمزها</div>
                  </div>
                  <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                    <div className="text-lg font-bold text-surface-300 font-mono">{marketData?.overview?.unchanged || 0}</div>
                    <div className="text-xs text-surface-400">بدون تغییر</div>
                  </div>
                  <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                    <div className="text-lg font-bold text-primary-300 font-mono">{marketData?.overview?.total_instruments || 0}</div>
                    <div className="text-xs text-surface-400">کل نمادها</div>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
