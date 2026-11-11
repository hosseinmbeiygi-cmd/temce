"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";
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

interface ImeFuturesRow {
  contract_code: string;
  contract_description?: string | null;
  date_end?: string | null;
  date_end_text?: string | null;
  days_remaining?: number | null;
  price_last?: number | null;
  price_last_change?: number | null;
  price_last_change_pct?: number | null;
  price_last_settlement?: number | null;
  trade_volume?: number | null;
  open_interest?: number | null;
  date_update?: string | null;
}

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

  /* Real feeds only — an outage or an empty list renders an explicit state. */
  const { data: commodities, isLoading, isError } = useQuery({
    queryKey: ["commodity-market"],
    queryFn: async () => {
      const res = await apiGet<unknown>("/commodities?latest_only=true");
      const arr = Array.isArray(res) ? res : (res as { data?: unknown })?.data ?? [];
      return (Array.isArray(arr) ? arr : []) as SpotCommodity[];
    },
    refetchInterval: 60_000,
  });

  // Futures come from the public IME endpoint (no derivatives mock table).
  const { data: derivatives, isLoading: derivativesLoading, isError: derivativesError } = useQuery({
    queryKey: ["commodity-derivatives"],
    queryFn: async () => {
      const r = await apiGet<{ success?: boolean; data?: ImeFuturesRow[] }>("/gold/ime/futures");
      const rows = extractArray<ImeFuturesRow>(r?.data ?? r);
      const byCode = new Map<string, ImeFuturesRow>();
      for (const row of rows) {
        if (!row?.contract_code || !(row.price_last ?? 0)) continue;
        const prev = byCode.get(row.contract_code);
        if (!prev || (row.date_update ?? "") > (prev.date_update ?? "")) byCode.set(row.contract_code, row);
      }
      return [...byCode.values()].map<DerivativeContract>((row) => ({
        id: row.contract_code,
        symbol: row.contract_code,
        name: row.contract_description || row.contract_code,
        underlying: row.contract_description || "—",
        contractType: "futures",
        maturityDate: row.date_end_text || row.date_end || "—",
        settlementPrice: row.price_last_settlement ?? 0,
        change: row.price_last_change ?? 0,
        changePercent: row.price_last_change_pct ?? 0,
        volume: row.trade_volume ?? 0,
        openInterest: row.open_interest ?? 0,
        lastPrice: row.price_last ?? 0,
        status: row.days_remaining != null && row.days_remaining < 0 ? "settled" : "active",
      }));
    },
    refetchInterval: 60_000,
  });

  const filteredCommodities = useMemo(() => {
    const rows = commodities ?? [];
    return category === "all" ? rows : rows.filter((c) => c.market === category);
  }, [commodities, category]);

  const gainers = filteredCommodities.filter((c) => c.changePercent >= 0).length;
  const losers = filteredCommodities.filter((c) => c.changePercent < 0).length;
  const sorted = filteredCommodities.toSorted((a, b) => b.changePercent - a.changePercent);
  const topGainer = sorted[0];
  const topLoser = sorted[sorted.length - 1];

  const filteredDerivatives = derivatives ?? [];

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
          {isError && (
            <div role="alert" aria-live="polite" className="mb-5 flex items-center gap-2 rounded-xl border border-accent-rose/30 bg-accent-rose/10 px-4 py-2.5 text-xs text-accent-rose">
              <AlertTriangle className="size-3.5 shrink-0" />
              {"دریافت قیمت‌های بازار کالایی ناموفق بود — داده‌ای برای نمایش وجود ندارد."}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-48 w-full" />)
              : filteredCommodities.map((item) => <SpotCard key={item.symbol} item={item} />)
            }
          </div>

          {!isLoading && !isError && filteredCommodities.length === 0 && (
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
              {"قراردادهای آتی فعال بورس کالای ایران (منبع: BrsApi)"}
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
          {derivativesError && (
            <div role="alert" aria-live="polite" className="mb-4 flex items-center gap-2 rounded-xl border border-accent-rose/30 bg-accent-rose/10 px-4 py-2.5 text-xs text-accent-rose">
              <AlertTriangle className="size-3.5 shrink-0" />
              {"دریافت قراردادهای آتی ناموفق بود — داده‌ای برای نمایش وجود ندارد."}
            </div>
          )}
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
                {derivativesLoading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i} className="border-b border-surface-800/50">
                        <td colSpan={7} className="px-3 py-3">
                          <div className="h-4 w-full animate-pulse rounded bg-surface-800" />
                        </td>
                      </tr>
                    ))
                  : filteredDerivatives.map((contract) => (
                      <DerivativeRow key={contract.id} contract={contract} />
                    ))}
              </tbody>
            </table>
          </div>

          {!derivativesLoading && !derivativesError && filteredDerivatives.length === 0 && (
            <div className="mt-4 flex min-h-[20vh] flex-col items-center justify-center gap-2 text-surface-600">
              <Calendar className="size-10" />
              <p className="text-sm">{"قرارداد آتی فعالی برای نمایش وجود ندارد"}</p>
            </div>
          )}

          <div className="mt-4 flex items-center gap-2 rounded-lg bg-surface-800/50 px-4 py-2.5 text-[10px] text-surface-500">
            <AlertTriangle className="size-3 text-accent-amber" />
            {"قراردادهای اختیار معامله و سلف در این نمای فرانت‌اند منابع داده‌ای مجزا ندارند و نمایش داده نمی‌شوند."}
          </div>
        </>
      )}
    </AppLayout>
  );
}
