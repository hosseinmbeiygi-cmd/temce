"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import MiniSparkline from "@/components/MiniSparkline";
import { apiGet, extractArray } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface Fund {
  symbol: string;
  name: string;
  isin: string;
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
}

// ── Helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatNum(v: number): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function extractFunds(resp: unknown): Fund[] {
  const raw = extractArray<Record<string, unknown>>(resp);
  return raw.map((f) => ({
    symbol: String(f.symbol ?? f.ins_id ?? ""),
    name: String(f.name ?? ""),
    isin: String(f.isin ?? ""),
    nav: Number(f.price_close ?? f.price_last ?? 0),
    nav_change: Number(f.price_close_change ?? f.price_last_change ?? 0),
    nav_change_pct: Number(f.price_close_change_pct ?? f.price_last_change_pct ?? 0),
    price_last: Number(f.price_last ?? 0),
    price_close: Number(f.price_close ?? 0),
    price_yesterday: Number(f.price_yesterday ?? 0),
    price_max: Number(f.price_max ?? 0),
    price_min: Number(f.price_min ?? 0),
    trade_volume: Number(f.trade_volume ?? 0),
    trade_value: Number(f.trade_value ?? 0),
    trade_count: Number(f.trade_count ?? 0),
    shares_count: Number(f.shares_count ?? 0),
    base_volume: Number(f.base_volume ?? 0),
    market_value: Number(f.market_value ?? 0),
    buy_real_volume: Number(f.buy_real_volume ?? 0),
    buy_legal_volume: Number(f.buy_legal_volume ?? 0),
    sell_real_volume: Number(f.sell_real_volume ?? 0),
    sell_legal_volume: Number(f.sell_legal_volume ?? 0),
    time: String(f.time ?? ""),
  }));
}

function fundType(name: string): "کالایی" | "سهامی" | "درآمد ثابت" | "مختلط" | "سایر" {
  const n = name || "";
  if (n.includes("کالا") || n.includes("کالایی") || n.includes("طلا")) return "کالایی";
  if (n.includes("سهام") || n.includes("سهامی") || n.includes("شاخصی")) return "سهامی";
  if (n.includes("درآمد") || n.includes("ثابت") || n.includes("بازده") || n.includes("بانک")) return "درآمد ثابت";
  if (n.includes("مختلط") || n.includes("متنوع")) return "مختلط";
  return "سایر";
}

function typeColor(type: string): string {
  const colors: Record<string, string> = {
    "کالایی": "bg-accent-amber/15 text-accent-amber",
    "سهامی": "bg-accent-emerald/15 text-accent-emerald",
    "درآمد ثابت": "bg-accent-cyan/15 text-accent-cyan",
    "مختلط": "bg-accent-purple/15 text-accent-purple",
    "سایر": "bg-surface-600/30 text-surface-400",
  };
  return colors[type] || colors["سایر"];
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function FundsPage() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("nav");
  const [typeFilter, setTypeFilter] = useState("همه");

  // ── Data ──
  const { data: funds, isLoading } = useQuery({
    queryKey: ["funds"],
    queryFn: async () => {
      try {
        const res = await apiGet<Record<string, unknown>>("/tables/brsapi_ime_funds?page=1&page_size=500");
        const extracted = extractFunds(res);
        if (extracted.length > 0) return extracted;
      } catch {
        // ignore, will try fallback
      }
      // Fallback: try market-info/funds or BrsApi direct
      try {
        const fallback = await apiGet<{ success: boolean; data: { items: { symbol: string; name: string; nav: number; date: string }[] } }>("/market-info/funds");
        const items = fallback?.data?.items ?? [];
        if (items.length > 0) {
          return items.map((f) => ({
            symbol: f.symbol,
            name: f.name,
            isin: "",
            nav: f.nav,
            nav_change: 0,
            nav_change_pct: 0,
            price_last: f.nav,
            price_close: f.nav,
            price_yesterday: 0,
            price_max: 0,
            price_min: 0,
            trade_volume: 0,
            trade_value: 0,
            trade_count: 0,
            shares_count: 0,
            base_volume: 0,
            market_value: 0,
            buy_real_volume: 0,
            buy_legal_volume: 0,
            sell_real_volume: 0,
            sell_legal_volume: 0,
            time: "",
          }));
        }
      } catch {
        // ignore
      }
      // Final fallback: BrsApi IME funds endpoint directly
      try {
        const brsRes = await apiGet<{ success: boolean; data: { items: Record<string, unknown>[] } }>("/brsapi/manage/sections");
        // If sections exist, the user needs to sync IME Funds first
        return [];
      } catch {
        return [];
      }
    },
    refetchInterval: 120_000,
  });

  // ── Types for filtering ──
  const types = useMemo(() => {
    const set = new Set<string>();
    set.add("همه");
    (funds ?? []).forEach((f) => set.add(fundType(f.name)));
    return Array.from(set);
  }, [funds]);

  // ── Filter + Sort ──
  const filtered = useMemo(() => {
    let list = funds ?? [];

    // Search
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.symbol.toLowerCase().includes(q) ||
          f.name.toLowerCase().includes(q) ||
          f.isin.toLowerCase().includes(q)
      );
    }

    // Type filter
    if (typeFilter !== "همه") {
      list = list.filter((f) => fundType(f.name) === typeFilter);
    }

    // Sort
    list = [...list].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case "nav":
          cmp = b.nav - a.nav;
          break;
        case "change":
          cmp = b.nav_change_pct - a.nav_change_pct;
          break;
        case "volume":
          cmp = b.trade_volume - a.trade_volume;
          break;
        case "value":
          cmp = b.trade_value - a.trade_value;
          break;
        case "market_value":
          cmp = b.market_value - a.market_value;
          break;
        case "shares":
          cmp = b.shares_count - a.shares_count;
          break;
        default:
          cmp = b.nav - a.nav;
      }
      return cmp;
    });

    return list;
  }, [funds, search, typeFilter, sortBy]);

  // ── NAV sparkline data ──
  const displaySymbols = useMemo(() => filtered.slice(0, 100), [filtered]);
  const { data: navRecords } = useQuery({
    queryKey: ["funds-nav-history"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { rows: Record<string, unknown>[] } }>(
          "/tables/brsapi_nav_records?page=1&page_size=500"
        );
        return res?.data?.rows ?? [];
      } catch {
        return [];
      }
    },
    staleTime: 120_000,
  });

  // Build symbol → [nav_issue] map (last 30 per symbol, chronological)
  const navSparkMap = useMemo(() => {
    const map = new Map<string, { date: string; nav: number }[]>();
    const symSet = new Set(displaySymbols.map((f) => f.symbol));

    for (const row of navRecords ?? []) {
      const sym = String(row.symbol ?? "");
      if (!sym || !symSet.has(sym)) continue;
      const nav = Number(row.nav_issue ?? row.nav_redemption ?? 0);
      const date = String(row.date ?? "");
      if (!nav || !date) continue;
      if (!map.has(sym)) map.set(sym, []);
      map.get(sym)!.push({ date, nav });
    }

    // Sort by date, take last 30
    const result: Record<string, number[]> = {};
    for (const [sym, records] of map.entries()) {
      records.sort((a, b) => a.date.localeCompare(b.date));
      result[sym] = records.slice(-30).map((r) => r.nav);
    }
    return result;
  }, [navRecords, displaySymbols]);

  // ── Stats ──
  const stats = useMemo(() => {
    if (!filtered.length) return null;
    const totalNav = filtered.reduce((s, f) => s + f.nav, 0);
    const avgNav = totalNav / filtered.length;
    const positive = filtered.filter((f) => f.nav_change_pct > 0).length;
    const totalAum = filtered.reduce((s, f) => s + f.market_value, 0);
    const totalVolume = filtered.reduce((s, f) => s + f.trade_volume, 0);
    return { count: filtered.length, avgNav, positive, negative: filtered.length - positive, totalAum, totalVolume };
  }, [filtered]);

  return (
    <AppLayout title="🏦 صندوق‌های سرمایه‌گذاری" subtitle="صندوق‌های کالایی، سهامی، درآمد ثابت و مختلط">
      {/* ── Stats cards ── */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-surface-100">{stats.count}</p>
            <p className="text-xs text-surface-500">صندوق</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-accent-emerald">{stats.positive}</p>
            <p className="text-xs text-surface-500">مثبت</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-accent-rose">{stats.negative}</p>
            <p className="text-xs text-surface-500">منفی</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-black font-mono text-primary-300">{formatNum(stats.totalAum)}</p>
            <p className="text-xs text-surface-500">ارزش کل بازار</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-black font-mono text-surface-100">{stats.avgNav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}</p>
            <p className="text-xs text-surface-500">میانگین NAV</p>
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
          <option value="value">ارزش</option>
          <option value="market_value">ارزش بازار</option>
          <option value="shares">تعداد واحد</option>
        </select>

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
            {search
              ? "صندوقی با این مشخصات وجود ندارد"
              : "داده‌ای از صندوق‌ها موجود نیست — ابتدا بخش IME Funds را همگام‌سازی کنید"}
          </p>
        </div>
      )}

      {/* ── Fund cards ── */}
      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map((fund) => {
            const type = fundType(fund.name);
            const isUp = fund.nav_change_pct >= 0;
            return (
              <div
                key={fund.symbol}
                className="glass-card p-4 flex items-center gap-3 hover:bg-white/[0.03] transition-colors"
              >
                {/* NAV Sparkline */}
                <div className="shrink-0 w-[72px]">
                  {navSparkMap[fund.symbol]?.length > 1 ? (
                    <MiniSparkline data={navSparkMap[fund.symbol]} width={72} height={24} />
                  ) : (
                    <div className="h-6 flex items-center justify-center text-[9px] text-surface-600">—</div>
                  )}
                </div>

                {/* Symbol + Name */}
                <div className="min-w-[130px] shrink-0">
                  <p className="font-bold text-surface-100">{fund.symbol}</p>
                  <p className="text-[10px] text-surface-500 truncate max-w-[150px]">{fund.name || "—"}</p>
                </div>

                {/* Type badge */}
                <div className="shrink-0">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${typeColor(type)}`}>
                    {type}
                  </span>
                </div>

                {/* NAV */}
                <div className="min-w-[90px] shrink-0 text-right">
                  <p className="text-xs text-surface-500">NAV</p>
                  <p className="font-mono text-sm font-bold text-surface-200">
                    {fund.nav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
                  </p>
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

                {/* Units */}
                <div className="hidden xl:block min-w-[70px] shrink-0 text-right">
                  <p className="text-[9px] text-surface-600">واحد</p>
                  <p className="font-mono text-xs text-surface-400">{formatNum(fund.shares_count)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
