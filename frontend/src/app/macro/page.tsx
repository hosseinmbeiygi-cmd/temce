"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";
import Link from "next/link";

// ------ Types -------------------------------------------------------------------------------------------------------

interface MacroIndicator {
  name: string;
  value: number;
  unit: string;
  date: string;
  change: number;
}

interface BrsapiItem {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
  time: string;
}

// ------ Indicator Configuration (matches MOCK_INDICATORS in backend) ------------------------------------------------

const INDICATOR_META: Record<string, { label: string; icon: string; category: string; decimals?: number; }> = {
  inflation: { label: "نرخ تورم", icon: "🔥", category: "اقتصاد کلان", decimals: 1 },
  gdp: { label: "تولید ناخالص داخلی", icon: "🏭", category: "اقتصاد کلان", decimals: 0 },
  unemployment: { label: "نرخ بیکاری", icon: "👥", category: "اقتصاد کلان", decimals: 1 },
  oil_price: { label: "قیمت نفت برنت", icon: "🛢️", category: "کامودیتی", decimals: 1 },
  gold_ounce: { label: "قیمت طلا (اونس)", icon: "🥇", category: "کامودیتی", decimals: 0 },
  dollar: { label: "نرخ دلار", icon: "💵", category: "ارز", decimals: 0 },
  eur: { label: "نرخ یورو", icon: "💶", category: "ارز", decimals: 0 },
  interest_rate: { label: "نرخ بهره بانکی", icon: "🏦", category: "اقتصاد کلان", decimals: 1 },
};

const CATEGORY_ORDER = ["اقتصاد کلان", "کامودیتی", "ارز"];

// BrsApi gold/coin/currency symbols for live data
const GOLD_SYMBOLS = ["18ayar", "24ayar", "emi", "bahar", "nim", "rob", "sekee"];
const CURRENCY_SYMBOLS = ["usd", "eur", "gbp", "aed", "try", "cny", "jpy"];

// ------ Helpers -----------------------------------------------------------------------------------------------------

function formatIndicatorValue(indicator: MacroIndicator): string {
  const meta = INDICATOR_META[indicator.name.replace(/ /g, "_") as string] || 
               Object.entries(INDICATOR_META).find(([_, v]) => v.label === indicator.name)?.[1];
  const decimals = meta?.decimals ?? 0;
  
  // Use locale formatting for better readability with Persian numbers
  return indicator.value.toLocaleString("fa-IR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatChange(change: number): { text: string; color: string; icon: string } {
  if (change > 0) return { text: `+${change.toLocaleString()}`, color: "text-accent-emerald", icon: "trending_up" };
  if (change < 0) return { text: `${change.toLocaleString()}`, color: "text-accent-rose", icon: "trending_down" };
  return { text: "0", color: "text-surface-400", icon: "remove_red_eye" };
}

function formatPrice(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

// ------ Components --------------------------------------------------------------------------------------------------

function IndicatorCard({ 
  indicatorKey, 
  data, 
  loading 
}: { 
  indicatorKey: string; 
  data: MacroIndicator | undefined; 
  loading: boolean;
}) {
  const meta = INDICATOR_META[indicatorKey];
  if (!meta) return null;

  if (loading) {
    return (
      <div className="glass-card p-4">
        <Skeleton className="h-4 w-20 mb-2 rounded" />
        <Skeleton className="h-8 w-32 mb-2 rounded" />
        <Skeleton className="h-3 w-24 rounded" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-card p-4 opacity-60">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">{meta.icon}</span>
          <span className="text-xs text-surface-500">{meta.label}</span>
        </div>
        <p className="text-lg font-bold text-surface-500">—</p>
        <p className="text-[10px] text-surface-600 mt-1">No data available</p>
      </div>
    );
  }

  const change = formatChange(data.change);
  const formattedDate = formatDateShamsi(data.date);

  return (
    <div className="glass-card p-4 hover:bg-surface-800/50 transition-colors group">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{meta.icon}</span>
          <span className="text-xs font-medium text-surface-400">{meta.label}</span>
        </div>
        <span className="material-icons text-surface-600 opacity-0 group-hover:opacity-100 transition-opacity text-sm">
          info
        </span>
      </div>
      
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-black font-mono text-surface-100">
          {formatIndicatorValue(data)}
        </span>
        <span className="text-xs text-surface-500">{data.unit}</span>
      </div>

      <div className="flex items-center gap-2 mt-2">
        <span className={`material-icons text-sm ${change.color}`}>{change.icon}</span>
        <span className={`text-sm font-mono font-bold ${change.color}`}>{change.text}</span>
        <span className="text-[10px] text-surface-600 mr-auto">{formattedDate}</span>
      </div>
    </div>
  );
}

function LivePriceRow({ item }: { item: BrsapiItem }) {
  const change = item.change ?? 0;
  const changePct = item.change_pct ?? 0;
  const changeColor = change >= 0 ? "text-accent-emerald" : "text-accent-rose";
  const changeIcon = change >= 0 ? "trending_up" : "trending_down";

  return (
    <tr className="border-b border-surface-800/30 hover:bg-white/[0.03] transition-colors">
      <td className="py-2.5 px-3">
        <span className="font-medium text-surface-200">{item.symbol}</span>
      </td>
      <td className="py-2.5 px-3 font-mono font-bold text-surface-100 text-right" dir="ltr">
        {formatPrice(item.price)}
      </td>
      <td className="py-2.5 px-3 text-right">
        <span className={`inline-flex items-center gap-1 text-xs font-mono font-bold ${changeColor}`}>
          <span className="material-icons text-sm">{changeIcon}</span>
          {change >= 0 ? "+" : ""}{change.toLocaleString()}
        </span>
      </td>
      <td className={`py-2.5 px-3 text-right font-mono ${changeColor}`}>
        {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
      </td>
      <td className="py-2.5 px-3 text-xs text-surface-500 text-right">{item.time || "—"}</td>
    </tr>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------

export default function MacroPage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<string | null>(null);

  // Fetch all indicators from backend
  const { data: indicators, isLoading, isError, refetch } = useQuery({
    queryKey: ["macro-indicators"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: string[] }>("/macro/");
      const keys = res?.data ?? [];
      
      // Fetch each indicator detail
      const detailPromises = keys.map(async (key) => {
        try {
          const detailRes = await apiGet<{ success: boolean; data: MacroIndicator }>(`/macro/${key}`);
          return { key, data: detailRes?.data };
        } catch {
          return { key, data: undefined };
        }
      });
      
      const results = await Promise.all(detailPromises);
      const map: Record<string, MacroIndicator> = {};
      results.forEach((r) => {
        if (r.data) map[r.key] = r.data;
      });
      return { keys, data: map };
    },
    refetchInterval: 600_000,
    staleTime: 300_000,
  });

  // Fetch live gold/coin prices from BrsApi
  const { data: goldData } = useQuery({
    queryKey: ["macro-gold"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: BrsapiItem[] }>("/brsapi/gold-coin");
        return res?.data ?? [];
      } catch {
        return [];
      }
    },
    refetchInterval: 600_000,
  });

  // Fetch live currency prices from BrsApi
  const { data: currencyData } = useQuery({
    queryKey: ["macro-currency"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: BrsapiItem[] }>("/brsapi/currency");
        return res?.data ?? [];
      } catch {
        return [];
      }
    },
    refetchInterval: 600_000,
  });

  const indicatorData = indicators?.data ?? {};
  const indicatorKeys = indicators?.keys ?? [];
  
  // Group by category
  const groupedIndicators = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    items: indicatorKeys
      .filter((key) => INDICATOR_META[key]?.category === cat)
      .map((key) => ({ key, data: indicatorData[key] })),
  })).filter((g) => g.items.length > 0);

  const filteredIndicators = selectedCategory
    ? groupedIndicators.filter((g) => g.category === selectedCategory)
    : groupedIndicators;

  // Filter gold data to show relevant items
  const filteredGold = goldData?.filter((g) => 
    GOLD_SYMBOLS.some((s) => g.symbol.toLowerCase().includes(s))
  ) ?? [];

  // Filter currency data
  const filteredCurrency = currencyData?.filter((c) =>
    CURRENCY_SYMBOLS.some((s) => c.symbol.toLowerCase().includes(s))
  ) ?? [];

  // Selected indicator detail
  const selectedDetail = selectedIndicator ? indicatorData[selectedIndicator] : null;
  const selectedMeta = selectedIndicator ? INDICATOR_META[selectedIndicator] : null;

  return (
    <AppLayout
      title="داده‌های کلان اقتصادی"
      subtitle={indicatorKeys.length + " شاخص • پشتیبانی از داده‌های زنده BrsApi"}
    >
      <div className="max-w-7xl mx-auto space-y-5">
        {/* Stats Summary */}
        {!isLoading && indicatorKeys.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3 text-center">
              <div className="text-2xl font-bold text-surface-100">{indicatorKeys.length}</div>
              <div className="text-xs text-surface-500">شاخص اقتصادی</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-2xl font-bold text-accent-emerald">{filteredGold.length}</div>
              <div className="text-xs text-surface-500">قیمت طلا و سکه</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-2xl font-bold text-accent-amber">{filteredCurrency.length}</div>
              <div className="text-xs text-surface-500">نرخ ارز</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-2xl font-bold text-primary-300">BrsApi</div>
              <div className="text-xs text-surface-500">داده‌های زنده</div>
            </div>
          </div>
        )}

        {/* Category Filter */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              !selectedCategory
                ? "bg-primary-600 text-white shadow-lg"
                : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            همه ({indicatorKeys.length})
          </button>
          {CATEGORY_ORDER.map((cat) => {
            const count = indicatorKeys.filter((k) => INDICATOR_META[k]?.category === cat).length;
            if (count === 0) return null;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedCategory === cat
                    ? "bg-primary-600 text-white shadow-lg"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200"
                }`}
              >
                {cat} ({count})
              </button>
            );
          })}

          <div className="flex-1" />

          <button
            onClick={() => refetch()}
            className="p-1.5 rounded-lg bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
            title="Refresh"
          >
            <span className="material-icons text-sm">refresh</span>
          </button>
        </div>

        {/* Indicator Cards Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-accent-rose">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-lg font-medium">خطا در دریافت داده‌های اقتصادی</p>
            <p className="text-sm mt-1 text-surface-500">اتصال به سرور را بررسی کنید</p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm transition-colors"
            >
              تلاش مجدد
            </button>
          </div>
        ) : indicatorKeys.length === 0 ? (
          <div className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">📊</p>
            <p className="text-lg">داده‌ای برای نمایش وجود ندارد</p>
            <p className="text-sm mt-1">شاخص‌های اقتصادی از سرور بارگذاری می‌شوند</p>
          </div>
        ) : (
          <>
            {/* Indicator cards by category */}
            {filteredIndicators.map((group) => (
              <div key={group.category}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold text-surface-400 bg-surface-800 px-2.5 py-1 rounded-full">
                    {group.category}
                  </span>
                  <span className="text-xs text-surface-600">{group.items.length} شاخص</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {group.items.map(({ key, data }) => (
                    <div key={key} onClick={() => setSelectedIndicator(selectedIndicator === key ? null : key)}>
                      <IndicatorCard indicatorKey={key} data={data} loading={false} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </>
        )}

        {/* Selected Indicator Detail */}
        {selectedIndicator && selectedDetail && selectedMeta && (
          <Card title={`📋 ${selectedMeta.label}`} subtitle={`${selectedDetail.name}`}>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
              <div className="bg-surface-800/50 rounded-xl p-4">
                <p className="text-xs text-surface-500 mb-1">مقدار فعلی</p>
                <p className="text-2xl font-black font-mono text-surface-100">
                  {formatIndicatorValue(selectedDetail)}
                </p>
                <p className="text-xs text-surface-500 mt-1">{selectedDetail.unit}</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-4">
                <p className="text-xs text-surface-500 mb-1">تغییرات</p>
                <p className={`text-2xl font-black font-mono ${
                  selectedDetail.change > 0 ? "text-accent-emerald" : selectedDetail.change < 0 ? "text-accent-rose" : "text-surface-400"
                }`}>
                  {selectedDetail.change > 0 ? "+" : ""}{selectedDetail.change.toLocaleString()}
                </p>
                <p className="text-xs text-surface-500 mt-1">نسبت به دوره قبل</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-4">
                <p className="text-xs text-surface-500 mb-1">تاریخ</p>
                <p className="text-xl font-bold font-mono text-primary-300">
                  {formatDateShamsi(selectedDetail.date)}
                </p>
                <p className="text-xs text-surface-500 mt-1">آخرین به‌روزرسانی</p>
              </div>
            </div>
          </Card>
        )}

        {/* Live Gold & Coin Prices from BrsApi */}
        {filteredGold.length > 0 && (
          <Card
            title="🥇 قیمت طلا و سکه (BrsApi)"
            subtitle="داده‌های زنده از BrsApi.ir"
            actions={
              <Link href="/commodities" className="text-xs text-primary-400 hover:text-primary-300 transition-colors">
                مشاهده همه
              </Link>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700 text-xs">
                    <th className="pb-2 px-3">نماد</th>
                    <th className="pb-2 px-3 text-right">قیمت</th>
                    <th className="pb-2 px-3 text-right">تغییر</th>
                    <th className="pb-2 px-3 text-right">تغییر %</th>
                    <th className="pb-2 px-3 text-right">زمان</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredGold.map((item, i) => (
                    <LivePriceRow key={item.symbol || i} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Live Currency Prices from BrsApi */}
        {filteredCurrency.length > 0 && (
          <Card
            title="💵 نرخ ارز (BrsApi)"
            subtitle="داده‌های زنده از BrsApi.ir"
            actions={
              <Link href="/commodities" className="text-xs text-primary-400 hover:text-primary-300 transition-colors">
                مشاهده همه
              </Link>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700 text-xs">
                    <th className="pb-2 px-3">نماد</th>
                    <th className="pb-2 px-3 text-right">قیمت</th>
                    <th className="pb-2 px-3 text-right">تغییر</th>
                    <th className="pb-2 px-3 text-right">تغییر %</th>
                    <th className="pb-2 px-3 text-right">زمان</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCurrency.map((item, i) => (
                    <LivePriceRow key={item.symbol || i} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Quick Links */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/commodities" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← کامودیتی‌ها
          </Link>
          <Link href="/crypto" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ارز دیجیتال
          </Link>
          <Link href="/brsapi" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            BrsApi Management
          </Link>
          <Link href="/markets" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            بازارها
          </Link>
        </div>

        {/* Info Note */}
        <div className="glass-card p-3 text-xs text-surface-500">
          <p className="font-medium text-surface-400 mb-1">ℹ️ درباره داده‌ها</p>
          <p>
            شاخص‌های کلان اقتصادی (تورم، GDP، بیکاری، نرخ بهره) از منابع رسمی جمع‌آوری می‌شوند و به‌روزرسانی دوره‌ای دارند.
            قیمت طلا، سکه و ارز به صورت زنده از سرویس BrsApi.ir دریافت می‌شود.
          </p>
        </div>
      </div>
    </AppLayout>
  );
}
