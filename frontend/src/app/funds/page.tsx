"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import FundNavMiniChart, { type FundNavPoint } from "@/components/FundNavMiniChart";
import FundCompareModal from "@/components/FundCompareModal";
import { apiGet } from "@/lib/api";

// ── Types (هماهنگ با API واقعی /funds) ─────────────────────────────────────

export interface Fund {
  symbol: string;
  name: string;
  isin: string;
  fund_type: string;
  market: "tse" | "ime" | string;
  nav: number;
  nav_change: number;
  nav_change_pct: number;
  price_last: number;
  price_close: number;
  price_yesterday: number;
  price_max: number;
  price_min: number;
  trade_volume: number;
  trade_value: number;
  trade_count: number;
  shares_count: number;
  base_volume: number;
  market_value: number;
  buy_real_volume: number;
  buy_legal_volume: number;
  sell_real_volume: number;
  sell_legal_volume: number;
  time: string;
  data_source?: string;
  snapshot_date?: string;
  nav_source?: string;
  nav_date?: string;
}

interface FundsResponse {
  total: number;
  limit: number;
  offset: number;
  items: Fund[];
  type_counts?: Record<string, number>;
  market_counts?: Record<string, number>;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatNum(v: number): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function fundType(name: string, fund_type?: string): string {
  const ft = fund_type || "";
  if (ft) return ft;
  const n = name || "";
  if (n.includes("کالا") || n.includes("طلا") || n.includes("نقره")) return "بخشی";
  if (n.includes("درآمد") || n.includes("ثابت") || n.includes("بانک")) return "درآمد ثابت";
  if (n.includes("اهرم")) return "اهرمی";
  if (n.includes("اختصاصی")) return "اختصاصی";
  if (n.includes("سهام") || n.includes("شاخص")) return "سهامی";
  if (n.includes("مختلط")) return "مختلط";
  return "سهامی";
}

function typeColor(type: string): string {
  const colors: Record<string, string> = {
    "سهامی": "bg-accent-emerald/15 text-accent-emerald",
    "درآمد ثابت": "bg-accent-cyan/15 text-accent-cyan",
    "اهرمی": "bg-accent-purple/15 text-accent-purple",
    "مختلط": "bg-accent-amber/15 text-accent-amber",
    "بخشی": "bg-accent-gold/15 text-accent-gold",
    "اختصاصی": "bg-surface-600/30 text-surface-400",
  };
  return colors[type] || colors["اختصاصی"];
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function FundsPage() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("nav");
  const [typeFilter, setTypeFilter] = useState("همه");
  const [marketFilter, setMarketFilter] = useState("همه");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);

  // ── Deep link from homepage map tiles (?type=…) ──
  const searchParams = useSearchParams();
  useEffect(() => {
    const t = searchParams?.get("type");
    if (t) setTypeFilter(t);
  }, [searchParams]);

  // ── Data: real API ──
  const { data: fundsData, isLoading } = useQuery({
    queryKey: ["funds"],
    queryFn: async (): Promise<FundsResponse> => {
      const params = new URLSearchParams();
      params.set("limit", "500");
      if (marketFilter !== "همه") params.set("market", marketFilter === "بورس تهران" ? "tse" : "ime");
      const res = await apiGet<FundsResponse>(`/funds?${params.toString()}`);
      return res ?? { total: 0, limit: 500, offset: 0, items: [] };
    },
    refetchInterval: 120_000,
    staleTime: 30_000,
  });

  const funds = fundsData?.items ?? [];

  // ── Types for filtering ──
  const types = useMemo(() => {
    const set = new Set<string>(["همه"]);
    funds.forEach((f) => set.add(fundType(f.name, f.fund_type)));
    return Array.from(set);
  }, [funds]);

  // ── Filter + Sort ──
  const filtered = useMemo(() => {
    let list = funds;

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.symbol.toLowerCase().includes(q) ||
          f.name.toLowerCase().includes(q) ||
          f.isin.toLowerCase().includes(q)
      );
    }

    if (typeFilter !== "همه") {
      list = list.filter((f) => fundType(f.name, f.fund_type) === typeFilter);
    }

    list = [...list].sort((a, b) => {
      switch (sortBy) {
        case "change":
          return b.nav_change_pct - a.nav_change_pct;
        case "volume":
          return b.trade_volume - a.trade_volume;
        case "value":
          return b.trade_value - a.trade_value;
        case "market_value":
          return b.market_value - a.market_value;
        case "shares":
          return b.shares_count - a.shares_count;
        case "name":
          return a.name.localeCompare(b.name, "fa");
        default:
          return b.nav - a.nav;
      }
    });

    return list;
  }, [funds, search, typeFilter, sortBy]);

  // ── NAV sparkline data (تاریخچه NAV واقعی از API صندوق‌ها) ──
  const displaySymbols = useMemo(() => filtered.slice(0, 100), [filtered]);
  const navSymbols = useMemo(() => displaySymbols.map((f) => f.symbol), [displaySymbols]);
  const { data: navHistory } = useQuery({
    queryKey: ["funds-nav-history", navSymbols.join(",")],
    queryFn: async () => {
      if (!navSymbols.length) return {} as Record<string, { date: string; nav: number; source?: string }[]>;
      try {
        const res = await apiGet<{
          symbols?: Record<string, { date: string; nav: number; source?: string }[]>;
        }>(`/funds/nav-history?symbols=${encodeURIComponent(navSymbols.join(","))}&limit=60`);
        return res?.symbols ?? {};
      } catch {
        return {};
      }
    },
    staleTime: 120_000,
  });

  const navSparkMap = useMemo(() => {
    const result: Record<string, FundNavPoint[]> = {};
    for (const [sym, points] of Object.entries(navHistory ?? {})) {
      const cleaned = (points ?? [])
        .map((p) => ({ date: p.date, nav: Number(p.nav) }))
        .filter((p) => Number.isFinite(p.nav) && p.nav > 0 && p.date);
      if (cleaned.length > 1) result[sym] = cleaned.slice(-30);
    }
    return result;
  }, [navHistory]);

  // ── Stats ──
  const stats = useMemo(() => {
    if (!filtered.length) return null;
    const positive = filtered.filter((f) => f.nav_change_pct > 0).length;
    const totalAum = filtered.reduce((s, f) => s + f.market_value, 0);
    const totalVolume = filtered.reduce((s, f) => s + f.trade_volume, 0);
    return {
      count: filtered.length,
      positive,
      negative: filtered.length - positive,
      totalAum,
      totalVolume,
    };
  }, [filtered]);

  // ── Compare selection ──
  const selectedFunds = useMemo(
    () => funds.filter((f) => selected.has(f.symbol)),
    [funds, selected]
  );

  const toggleSelect = (symbol: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

  const removeFromCompare = (symbol: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(symbol);
      // کمتر از ۲ صندوق باقی مانده → مودال را ببند تا با انتخاب مجدد ناگهان باز نشود
      if (next.size < 2) setCompareOpen(false);
      return next;
    });
  };

  const closeCompare = () => {
    setCompareOpen(false);
    setSelected(new Set());
  };

  return (
    <AppLayout title="🏦 صندوق‌های سرمایه‌گذاری" subtitle="صندوق‌های بورس تهران و بورس کالا — داده واقعی">
      {/* ── Stats cards ── */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-surface-100">{stats.count}</p>
            <p className="text-xs text-surface-500">صندوق</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-accent-emerald">{stats.positive}</p>
            <p className="text-xs text-surface-500">مثبت امروز</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-accent-rose">{stats.negative}</p>
            <p className="text-xs text-surface-500">منفی امروز</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-black font-mono text-primary-300">{formatNum(stats.totalAum)}</p>
            <p className="text-xs text-surface-500">ارزش کل بازار</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-black font-mono text-surface-100">{formatNum(stats.totalVolume)}</p>
            <p className="text-xs text-surface-500">حجم کل</p>
          </div>
        </div>
      )}

      {/* ── Filters ── */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جستجوی نام، نماد، ISIN..."
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-56"
        />

        {/* بازار */}
        <select
          value={marketFilter}
          onChange={(e) => setMarketFilter(e.target.value)}
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value="همه">همه بازارها</option>
          <option value="بورس تهران">بورس تهران</option>
          <option value="بورس کالا">بورس کالا</option>
        </select>

        <div className="flex gap-1 flex-wrap">
          {types.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${
                typeFilter === t
                  ? "bg-primary-600 text-white"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value="nav">NAV</option>
          <option value="change">تغییرات</option>
          <option value="volume">حجم</option>
          <option value="value">ارزش معاملات</option>
          <option value="market_value">ارزش بازار</option>
          <option value="shares">تعداد واحد</option>
          <option value="name">نام</option>
        </select>

        {/* Compare button */}
        <button
          onClick={() => setCompareOpen(true)}
          disabled={selected.size < 2}
          className={`px-3 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
            selected.size >= 2
              ? "bg-primary-600 text-white hover:bg-primary-500 shadow-lg shadow-primary-600/20"
              : "bg-surface-800 text-surface-500 cursor-not-allowed"
          }`}
        >
          <span className="material-icons text-sm">compare_arrows</span>
          مقایسه
          {selected.size > 0 && (
            <span className="text-[9px] bg-black/20 px-1.5 py-0.5 rounded-full">
              {selected.size}
            </span>
          )}
        </button>

        {selected.size > 0 && (
          <button
            onClick={() => setSelected(new Set())}
            className="text-[10px] text-surface-500 hover:text-accent-rose transition-colors"
          >
            پاک کردن انتخاب
          </button>
        )}

        <span className="text-xs text-surface-500">{filtered.length} صندوق</span>
      </div>

      {/* ── Loading ── */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* ── Empty ── */}
      {!isLoading && filtered.length === 0 && (
        <div className="glass-card p-12 text-center text-surface-500">
          <p className="text-5xl mb-3">🏦</p>
          <p className="font-bold">صندوقی یافت نشد</p>
          <p className="text-sm mt-1">
            {search ? "صندوقی با این مشخصات وجود ندارد" : "داده‌ای از صندوق‌ها موجود نیست"}
          </p>
        </div>
      )}

      {/* ── Fund cards (کلیک → صفحه جزئیات) ── */}
      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map((fund) => {
            const type = fundType(fund.name, fund.fund_type);
            const isUp = fund.nav_change_pct >= 0;
            const isSelected = selected.has(fund.symbol);
            return (
              <div
                key={fund.symbol}
                className={`glass-card p-4 flex items-center gap-3 transition-all group relative ${
                  isSelected
                    ? "border-primary-500/60 bg-primary-600/[0.06]"
                    : "hover:bg-white/[0.04] hover:border-primary-500/40"
                }`}
              >
                {/* Compare checkbox */}
                <button
                  onClick={() => toggleSelect(fund.symbol)}
                  title={isSelected ? "حذف از مقایسه" : "افزودن به مقایسه"}
                  className={`shrink-0 w-6 h-6 rounded-lg border flex items-center justify-center transition-all ${
                    isSelected
                      ? "bg-primary-600 border-primary-500 text-white"
                      : "border-surface-600 text-transparent hover:border-primary-500 hover:text-surface-600"
                  }`}
                >
                  <span className="material-icons text-[14px]">check</span>
                </button>

                <Link
                  href={`/funds/${encodeURIComponent(fund.symbol)}`}
                  className="flex-1 flex items-center gap-3 min-w-0"
                >
                {/* NAV mini-chart (نمودار NAV واقعی برای صندوق‌های دارای چند نقطه) */}
                <div className="shrink-0 w-[88px]">
                  {navSparkMap[fund.symbol]?.length > 1 ? (
                    <FundNavMiniChart points={navSparkMap[fund.symbol]} width={88} height={30} />
                  ) : (
                    <div className="h-[30px] flex items-center justify-center text-[9px] text-surface-600">—</div>
                  )}
                </div>

                {/* Symbol + Name */}
                <div className="min-w-[130px] shrink-0">
                  <p className="font-bold text-surface-100 group-hover:text-primary-300 transition-colors">{fund.symbol}</p>
                  <p className="text-[10px] text-surface-500 truncate max-w-[150px]">{fund.name || "—"}</p>
                </div>

                {/* Type badge */}
                <div className="shrink-0">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${typeColor(type)}`}>
                    {type}
                  </span>
                </div>

                {/* Market badge */}
                <div className="shrink-0 hidden sm:block">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                    fund.market === "tse" ? "bg-primary-600/20 text-primary-300" : "bg-accent-gold/15 text-accent-gold"
                  }`}>
                    {fund.market === "tse" ? "بورس تهران" : "بورس کالا"}
                  </span>
                </div>

                {/* NAV — ارزش خالص دارایی واقعی از API (nav_records) */}
                <div
                  className="min-w-[90px] shrink-0 text-right"
                  title={
                    fund.nav_date
                      ? `NAV واقعی — تاریخ ${fund.nav_date}${fund.nav_source === "nav_record" ? " (صدور/ابطال)" : ""}`
                      : "NAV بر اساس آخرین قیمت"
                  }
                >
                  <p className="text-xs text-surface-500">NAV</p>
                  <p className="font-mono text-sm font-bold text-surface-200">
                    {fund.nav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
                  </p>
                  {fund.nav_date && (
                    <p className="text-[8px] text-surface-600" dir="ltr">
                      {fund.nav_date}
                    </p>
                  )}
                </div>

                {/* Change */}
                <div className="min-w-[80px] shrink-0 text-right">
                  <p className={`font-mono text-sm font-bold ${isUp ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {isUp ? "+" : ""}{fund.nav_change_pct?.toFixed(2)}%
                  </p>
                  <p className={`font-mono text-xs ${isUp ? "text-accent-emerald/60" : "text-accent-rose/60"}`}>
                    {isUp ? "+" : ""}{fund.nav_change?.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
                  </p>
                </div>

                {/* Price range */}
                <div className="hidden md:block min-w-[100px] shrink-0">
                  <p className="text-[9px] text-surface-600">بازه روز</p>
                  <div className="flex items-center gap-1 text-[10px] font-mono text-surface-400">
                    <span>{fund.price_min?.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}</span>
                    <span className="text-surface-600">–</span>
                    <span>{fund.price_max?.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}</span>
                  </div>
                </div>

                {/* Volume / Value */}
                <div className="hidden lg:block min-w-[80px] shrink-0 text-right">
                  <p className="text-[9px] text-surface-600">حجم</p>
                  <p className="font-mono text-xs text-surface-400">{formatNum(fund.trade_volume)}</p>
                </div>

                {/* Real/Legal */}
                <div className="hidden xl:block min-w-[80px] shrink-0">
                  <p className="text-[9px] text-surface-600">حقیقی خالص</p>
                  <p className={`font-mono text-xs ${fund.buy_real_volume >= fund.sell_real_volume ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {formatNum(Math.abs(fund.buy_real_volume - fund.sell_real_volume))}
                  </p>
                </div>

                {/* Market value */}
                <div className="hidden xl:block min-w-[90px] shrink-0 text-right">
                  <p className="text-[9px] text-surface-600">ارزش بازار</p>
                  <p className="font-mono text-xs text-primary-300">{formatNum(fund.market_value)}</p>
                </div>

                {/* Arrow */}
                <div className="mr-auto text-surface-600 group-hover:text-primary-400 transition-colors text-lg">
                  ←
                </div>
                </Link>
              </div>
            );
          })}
        </div>
      )}
      {/* ── Compare Modal ── */}
      {compareOpen && selectedFunds.length >= 2 && (
        <FundCompareModal
          funds={selectedFunds}
          onClose={closeCompare}
          onRemove={removeFromCompare}
        />
      )}
    </AppLayout>
  );
}
