"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  Package,
  Calendar,
  BarChart3,
  DollarSign,
  AlertTriangle,
} from "lucide-react";

/* -- Shared Types -- */

interface SpotCommodity {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  high: number;
  low: number;
  open: number;
  close: number;
  volume: number;
  unit: string;
  market: string;
  updatedAt: string;
}

interface DerivativeContract {
  id: string;
  symbol: string;
  name: string;
  underlying: string;
  contractType: "futures" | "option" | "salaf";
  maturityDate: string;
  settlementPrice: number;
  change: number;
  changePercent: number;
  volume: number;
  openInterest: number;
  lastPrice: number;
  status: "active" | "settled" | "pending";
}

/* -- Categories -- */

const CATEGORIES = [
  { key: "all", label: "همه", emoji: "📊" },
  { key: "agriculture", label: "کشاورزی", emoji: "🌾" },
  { key: "petrochemical", label: "پتروشیمی", emoji: "🧪" },
  { key: "metal", label: "فلزات", emoji: "⛏️" },
  { key: "mineral", label: "معدنی", emoji: "🟨" },
];

const CATEGORY_MAP: Record<string, string> = {
  agriculture: "کشاورزی",
  petrochemical: "پتروشیمی",
  metal: "فلزات",
  mineral: "معدنی",
};

/* -- Mock Spot Data -- */

const MOCK_COMMODITIES: SpotCommodity[] = [
  { symbol: "ZRS1", name: "زعفران نگین", price: 185000000, change: 2500000, changePercent: 1.37, high: 187000000, low: 182000000, open: 183000000, close: 185000000, volume: 12500, unit: "ریال", market: "agriculture", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۲۵" },
  { symbol: "ZRS2", name: "زعفران پوشال", price: 142000000, change: -1200000, changePercent: -0.84, high: 144500000, low: 141000000, open: 143200000, close: 142000000, volume: 8900, unit: "ریال", market: "agriculture", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۲۵" },
  { symbol: "PCC", name: "پلی‌اتیلن سنگین", price: 48500000, change: 850000, changePercent: 1.78, high: 49000000, low: 47800000, open: 47800000, close: 48500000, volume: 45200, unit: "ریال", market: "petrochemical", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۲۰" },
  { symbol: "PP", name: "پلی‌پروپیلن", price: 52300000, change: -350000, changePercent: -0.66, high: 52800000, low: 51900000, open: 52650000, close: 52300000, volume: 28700, unit: "ریال", market: "petrochemical", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۲۰" },
  { symbol: "SB", name: "شمش فولاد", price: 22800000, change: 420000, changePercent: 1.88, high: 23100000, low: 22400000, open: 22400000, close: 22800000, volume: 120000, unit: "ریال", market: "metal", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۱۵" },
  { symbol: "CU", name: "کاتد مس", price: 95200000, change: 1600000, changePercent: 1.71, high: 96000000, low: 93500000, open: 93600000, close: 95200000, volume: 32000, unit: "ریال", market: "metal", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۱۵" },
  { symbol: "AL", name: "شمش آلومینیوم", price: 38600000, change: -500000, changePercent: -1.28, high: 39200000, low: 38300000, open: 39100000, close: 38600000, volume: 18500, unit: "ریال", market: "metal", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۱۵" },
  { symbol: "CEM", name: "سکنه", price: 2850000, change: 45000, changePercent: 1.60, high: 2890000, low: 2810000, open: 2810000, close: 2850000, volume: 210000, unit: "ریال", market: "mineral", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۱۰" },
  { symbol: "ZC1", name: "ذرت دانه‌ای", price: 9200000, change: -120000, changePercent: -1.29, high: 9350000, low: 9150000, open: 9320000, close: 9200000, volume: 67000, unit: "ریال", market: "agriculture", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۲۵" },
  { symbol: "BR", name: "برنج طارم", price: 156000000, change: 3800000, changePercent: 2.50, high: 158000000, low: 152000000, open: 152200000, close: 156000000, volume: 5200, unit: "ریال", market: "agriculture", updatedAt: "۱۴۰۵/۰۶/۱۱ ۱۰:۲۵" },
];

/* -- Mock Derivatives Data -- */

const MOCK_DERIVATIVES: DerivativeContract[] = [
  { id: "d1", symbol: "ZRSF-1405-09", name: "آتی زعفران نگین - آذر ۱۴۰۵", underlying: "زعفران نگین", contractType: "futures", maturityDate: "۱۴۰۵/۰۹/۱۵", settlementPrice: 192000000, change: 3200000, changePercent: 1.69, volume: 4200, openInterest: 15800, lastPrice: 192000000, status: "active" },
  { id: "d2", symbol: "ZRSF-1405-12", name: "آتی زعفران نگین - اسفند ۱۴۰۵", underlying: "زعفران نگین", contractType: "futures", maturityDate: "۱۴۰۵/۱۲/۲۰", settlementPrice: 198000000, change: -1100000, changePercent: -0.55, volume: 2800, openInterest: 11200, lastPrice: 198000000, status: "active" },
  { id: "d3", symbol: "SBF-1405-08", name: "آتی شمش فولاد - آبان ۱۴۰۵", underlying: "شمش فولاد", contractType: "futures", maturityDate: "۱۴۰۵/۰۸/۳۰", settlementPrice: 24100000, change: 520000, changePercent: 2.20, volume: 18500, openInterest: 62000, lastPrice: 24100000, status: "active" },
  { id: "d4", symbol: "SBF-1405-10", name: "آتی شمش فولاد - دی ۱۴۰۵", underlying: "شمش فولاد", contractType: "futures", maturityDate: "۱۴۰۵/۱۰/۱۵", settlementPrice: 24800000, change: 380000, changePercent: 1.56, volume: 12100, openInterest: 41500, lastPrice: 24800000, status: "active" },
  { id: "d5", symbol: "CUF-1405-09", name: "آتی کاتد مس - آذر ۱۴۰۵", underlying: "کاتد مس", contractType: "futures", maturityDate: "۱۴۰۵/۰۹/۲۲", settlementPrice: 98500000, change: 2100000, changePercent: 2.18, volume: 8300, openInterest: 28700, lastPrice: 98500000, status: "active" },
  { id: "d6", symbol: "PCCF-1405-08", name: "آتی پلی‌اتیلن - آبان ۱۴۰۵", underlying: "پلی‌اتیلن سنگین", contractType: "futures", maturityDate: "۱۴۰۵/۰۸/۲۵", settlementPrice: 50200000, change: 950000, changePercent: 1.93, volume: 6700, openInterest: 19200, lastPrice: 50200000, status: "active" },
  { id: "d7", symbol: "ZRSO-1405-09", name: "اختیار خرید زعفران - آذر", underlying: "زعفران نگین", contractType: "option", maturityDate: "۱۴۰۵/۰۹/۱۵", settlementPrice: 6500000, change: 450000, changePercent: 7.44, volume: 1200, openInterest: 4800, lastPrice: 6500000, status: "active" },
  { id: "d8", symbol: "ZRSO-1405-09-P", name: "اختیار فروش زعفران - آذر", underlying: "زعفران نگین", contractType: "option", maturityDate: "۱۴۰۵/۰۹/۱۵", settlementPrice: 4200000, change: -280000, changePercent: -6.25, volume: 950, openInterest: 3600, lastPrice: 4200000, status: "active" },
  { id: "d9", symbol: "SBSL-1405-08", name: "سلف شمش فولاد - آبان", underlying: "شمش فولاد", contractType: "salaf", maturityDate: "۱۴۰۵/۰۸/۳۰", settlementPrice: 22100000, change: 310000, changePercent: 1.42, volume: 25000, openInterest: 85000, lastPrice: 22100000, status: "active" },
  { id: "d10", symbol: "ZRSF-1405-06", name: "آتی زعفران نگین - شهریور ۱۴۰۵", underlying: "زعفران نگین", contractType: "futures", maturityDate: "۱۴۰۵/۰۶/۳۱", settlementPrice: 186000000, change: 0, changePercent: 0, volume: 0, openInterest: 0, lastPrice: 186000000, status: "settled" },
];

/* -- Format helpers -- */

function formatPrice(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatVolume(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toFixed(0);
}

/* -- Sub-components -- */

function SpotCard({ item }: { item: SpotCommodity }) {
  const isUp = item.changePercent >= 0;
  return (
    <div className="glass-card group cursor-pointer p-4 transition-all hover:ring-1 hover:ring-accent-cyan/40" dir="rtl">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <span className="font-mono text-[11px] font-bold text-surface-500">{item.symbol}</span>
          <h3 className="text-sm font-bold text-surface-200">{item.name}</h3>
        </div>
        <span className="rounded-full bg-surface-800 px-2 py-0.5 text-[10px] text-surface-400">
          {CATEGORY_MAP[item.market] ?? item.market}
        </span>
      </div>
      <div className="mb-2">
        <span className="text-xl font-bold text-surface-100" dir="ltr">
          {formatPrice(item.price)}
        </span>
        <span className="mr-1 text-[10px] text-surface-500">{item.unit}</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className={"flex items-center gap-1 font-bold " + (isUp ? "text-accent-emerald" : "text-accent-rose")}>
          {isUp ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
          {isUp ? "+" : ""}{item.changePercent.toFixed(2)}%
        </span>
        <span className="text-surface-500">
          {isUp ? "+" : ""}{formatPrice(Math.abs(item.change))}
        </span>
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-surface-500">
        <span>{"حجم"}: {formatVolume(item.volume)}</span>
        <span>H: {formatPrice(item.high)}</span>
        <span>L: {formatPrice(item.low)}</span>
      </div>
      <div className="mt-2 border-t border-surface-800 pt-2 text-[9px] text-surface-600">
        {item.updatedAt}
      </div>
    </div>
  );
}

function DerivativeRow({ contract }: { contract: DerivativeContract }) {
  const isUp = contract.changePercent >= 0;
  const typeLabel = contract.contractType === "futures" ? "آتی" : contract.contractType === "option" ? "اختیار" : "سلف";
  const typeBadgeClass = contract.contractType === "futures"
    ? "bg-accent-cyan/10 text-accent-cyan"
    : contract.contractType === "option"
      ? "bg-accent-purple/10 text-accent-purple"
      : "bg-accent-amber/10 text-accent-amber";
  const isSettled = contract.status === "settled";

  return (
    <tr className={"border-b border-surface-800/50 transition-colors hover:bg-surface-800/30 " + (isSettled ? "opacity-50" : "")}>
      <td className="px-3 py-3">
        <div className="flex items-center gap-2">
          <span className={"rounded-full px-2 py-0.5 text-[10px] font-bold " + typeBadgeClass}>
            {typeLabel}
          </span>
          <div>
            <div className="text-sm font-bold text-surface-200">{contract.symbol}</div>
            <div className="text-[10px] text-surface-500">{contract.underlying}</div>
          </div>
        </div>
      </td>
      <td className="px-3 py-3 text-xs text-surface-400">{contract.maturityDate}</td>
      <td className="px-3 py-3 text-right font-mono text-sm font-bold text-surface-100" dir="ltr">
        {formatPrice(contract.lastPrice)}
      </td>
      <td className={"px-3 py-3 text-right font-mono text-xs font-bold " + (isUp ? "text-accent-emerald" : "text-accent-rose")} dir="ltr">
        {isUp ? "+" : ""}{contract.changePercent.toFixed(2)}%
      </td>
      <td className="px-3 py-3 text-right font-mono text-xs text-surface-400" dir="ltr">
        {formatVolume(contract.volume)}
      </td>
      <td className="px-3 py-3 text-right font-mono text-xs text-surface-400" dir="ltr">
        {formatVolume(contract.openInterest)}
      </td>
      <td className="px-3 py-3 text-center">
        {isSettled ? (
          <span className="rounded bg-surface-700 px-2 py-0.5 text-[10px] text-surface-400">{"تسویه"}</span>
        ) : (
          <span className="rounded bg-accent-emerald/10 px-2 py-0.5 text-[10px] text-accent-emerald">{"فعال"}</span>
        )}
      </td>
    </tr>
  );
}

/* -- Main Page -- */

export default function CommodityMarketPage() {
  const [category, setCategory] = useState("all");
  const [view, setView] = useState<"spot" | "derivatives">("spot");

  /* API fetch with fallback to mock */
  const { data: commodities, isLoading } = useQuery({
    queryKey: ["commodity-market", category],
    queryFn: async () => {
      try {
        const res = await apiGet<unknown>("/commodities");
        const arr = Array.isArray(res) ? res : (res as { data?: unknown })?.data ?? [];
        if (Array.isArray(arr)) return arr as SpotCommodity[];
      } catch {
        /* fall through to mock */
      }
      if (category === "all") return MOCK_COMMODITIES;
      return MOCK_COMMODITIES.filter((c) => c.market === category);
    },
    refetchInterval: 60_000,
  });

  const gainers = commodities?.filter((c) => c.changePercent >= 0).length ?? 0;
  const losers = commodities?.filter((c) => c.changePercent < 0).length ?? 0;
  const sorted = (commodities ?? []).toSorted((a, b) => b.changePercent - a.changePercent);
  const topGainer = sorted[0];
  const topLoser = sorted[sorted.length - 1];

  const filteredDerivatives = useMemo(() => {
    return MOCK_DERIVATIVES.filter((d) => d.status === "active");
  }, []);

  return (
    <AppLayout
      title="بازار کالایی"
      subtitle="قیمت‌های لحظه‌ای محصولات بورس کالای ایران (IME)"
    >
      {/* -- View Toggle: Spot / Derivatives -- */}
      <div className="mb-5 flex gap-2">
        <button
          onClick={() => setView("spot")}
          className={"flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-all " + (
            view === "spot"
              ? "bg-accent-cyan text-white shadow-lg shadow-accent-cyan/20"
              : "bg-surface-800 text-surface-400 hover:bg-surface-700"
          )}
        >
          <BarChart3 className="size-3.5" />
          بازار نقدی
        </button>
        <button
          onClick={() => setView("derivatives")}
          className={"flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-all " + (
            view === "derivatives"
              ? "bg-accent-purple text-white shadow-lg shadow-accent-purple/20"
              : "bg-surface-800 text-surface-400 hover:bg-surface-700"
          )}
        >
          <Calendar className="size-3.5" />
          مشتقه کالایی
        </button>
      </div>

      {view === "spot" ? (
        <>
          {/* -- Summary Cards -- */}
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-surface-100">{commodities?.length ?? 0}</div>
              <div className="text-[10px] text-surface-500">{"کل محصولات"}</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-accent-emerald">{gainers}</div>
              <div className="text-[10px] text-surface-500">{"صعودی"}</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-accent-rose">{losers}</div>
              <div className="text-[10px] text-surface-500">{"نزولی"}</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-accent-emerald">
                {topGainer ? topGainer.changePercent.toFixed(1) + "%" : "—"}
              </div>
              <div className="text-[10px] text-surface-500">{"بیشترین رشد"}</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-accent-rose">
                {topLoser ? topLoser.changePercent.toFixed(1) + "%" : "—"}
              </div>
              <div className="text-[10px] text-surface-500">{"بیشترین کاهش"}</div>
            </div>
          </div>

          {/* -- Category Filter -- */}
          <div className="mb-5 flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.key}
                onClick={() => setCategory(cat.key)}
                className={"flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-medium transition-all " + (
                  category === cat.key
                    ? "bg-accent-cyan/15 text-accent-cyan ring-1 ring-accent-cyan/30"
                    : "bg-surface-800/60 text-surface-400 hover:bg-surface-700 hover:text-surface-300"
                )}
              >
                <span>{cat.emoji}</span>
                {cat.label}
              </button>
            ))}
          </div>

          {/* -- Disclaimer -- */}
          <div className="mb-5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-[11px] text-amber-300">
            <strong>{"⚠️"} {"هشدار:"}</strong> {"قیمت‌های نمایش‌داده‌شده صرفاً جهت آموزش و تحقیقاتی است و به‌عنوان توصیه سرمایه‌گذاری محسوب نمی‌شوند."}
          </div>

          {/* -- Commodity Grid -- */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-48 w-full" />)
              : commodities?.map((item) => <SpotCard key={item.symbol} item={item} />)
            }
          </div>

          {!isLoading && commodities?.length === 0 && (
            <div className="flex min-h-[30vh] flex-col items-center justify-center gap-2 text-surface-600">
              <Package className="size-12" />
              <p className="text-sm">{"محصولی برای نمایش وجود ندارد"}</p>
            </div>
          )}
        </>
      ) : (
        <>
          {/* -- Derivatives Header -- */}
          <div className="mb-5 rounded-lg border border-accent-purple/20 bg-accent-purple/5 px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-bold text-accent-purple">
              <Calendar className="size-4" />
              {"قراردادهای مشتقه کالایی"}
            </div>
            <p className="mt-1 text-[11px] text-surface-400">
              {"فهرست قراردادهای آتی، اختیار معامله و سلف فعال در بورس کالای ایران"}
            </p>
          </div>

          {/* -- Disclaimer -- */}
          <div className="mb-5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-[11px] text-amber-300">
            <strong>{"⚠️"} {"هشدار:"}</strong> {"قیمت‌ها و اطلاعات قراردادهای مشتقه صرفاً جهت آموزش و تحقیقاتی است و به‌عنوان توصیه سرمایه‌گذاری محسوب نمی‌شوند."}
          </div>

          {/* -- Summary Stats -- */}
          <div className="mb-4 grid grid-cols-3 gap-3">
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-surface-100">{filteredDerivatives.length}</div>
              <div className="text-[10px] text-surface-500">{"قرارداد فعال"}</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-accent-emerald">
                {filteredDerivatives.filter((d) => d.changePercent >= 0).length}
              </div>
              <div className="text-[10px] text-surface-500">{"صعودی"}</div>
            </div>
            <div className="glass-card p-3 text-center">
              <div className="text-lg font-bold text-accent-rose">
                {filteredDerivatives.filter((d) => d.changePercent < 0).length}
              </div>
              <div className="text-[10px] text-surface-500">{"نزولی"}</div>
            </div>
          </div>

          {/* -- Derivatives Table -- */}
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="border-b border-surface-700 bg-surface-800/80">
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"قرارداد"}</th>
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"سررسید"}</th>
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"قیمت"}</th>
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"تغییر"}</th>
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"حجم"}</th>
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"موقعیت باز"}</th>
                  <th className="px-3 py-3 text-[11px] font-bold text-surface-400">{"وضعیت"}</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_DERIVATIVES.map((contract) => (
                  <DerivativeRow key={contract.id} contract={contract} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center gap-2 rounded-lg bg-surface-800/50 px-4 py-2.5 text-[10px] text-surface-500">
            <AlertTriangle className="size-3 text-accent-amber" />
            {"موقعیت‌های باز و حجم معاملات به‌صورت شبیه‌سازی نمایش داده شده‌اند. در نسخه نهایی از داده‌های واقعی بورس کالا استفاده خواهد شد."}
          </div>
        </>
      )}
    </AppLayout>
  );
}
