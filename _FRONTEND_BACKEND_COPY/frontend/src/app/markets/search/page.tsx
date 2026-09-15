"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

type Market = "option" | "commodity";

interface LiveSymbol {
  symbol: string;
  contracts: number;
  volume: number;
  price: number;
}

interface OptionContract {
  symbol: string;
  name: string;
  type: string;
  strike: number;
  price: number;
  volume: number;
  oi: number;
  days_to_expiry: number;
  underlying_price: number;
  bid: number;
  ask: number;
  open: number;
  high: number;
  low: number;
  trades: number;
  value: number;
}

interface ChainData {
  underlying: string;
  underlying_price: number;
  calls: OptionContract[];
  puts: OptionContract[];
  total_contracts: number;
}

interface Commodity {
  symbol: string;
  name: string;
  price: number;
  change_value: number;
  change_percent: number;
  unit: string;
  category: string;
  date: string;
  time: string;
}

function fmtNum(n: number, digits = 0): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function calcMoneyness(price: number, strike: number, type: string): "ITM" | "ATM" | "OTM" {
  if (!price || !strike) return "OTM";
  const diffPct = Math.abs(price - strike) / strike;
  if (diffPct < 0.01) return "ATM";
  if (type === "call") return price > strike ? "ITM" : "OTM";
  return price < strike ? "ITM" : "OTM";
}

export default function SearchPage() {
  const [market, setMarket] = useState<Market>("option");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<string>("all");
  const [activeUnderlying, setActiveUnderlying] = useState<string | null>(null);

  const { data: liveSymbolsResp, isLoading: symLoading } = useQuery({
    queryKey: ["options", "live-symbols"],
    queryFn: () => apiGet<{ success: boolean; data: LiveSymbol[] }>("/api/v1/options/live/symbols"),
    refetchInterval: 60_000,
  });

  const { data: chainResp, isLoading: chainLoading } = useQuery({
    queryKey: ["options", "live-chain", activeUnderlying],
    queryFn: () => apiGet<{ success: boolean; data: ChainData }>(`/api/v1/options/live/chain/${activeUnderlying}?limit=200`),
    enabled: !!activeUnderlying && market === "option",
    refetchInterval: 30_000,
  });

  const { data: commoditiesResp, isLoading: comLoading } = useQuery({
    queryKey: ["brsapi-commodities", "all"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: Commodity[] }>("/brsapi/commodities");
      return res.data || [];
    },
    refetchInterval: 30_000,
  });

  const commodities = commoditiesResp ?? [];
  const symbols: LiveSymbol[] = liveSymbolsResp?.data ?? [];
  const chainData: ChainData | undefined = chainResp?.data;

  const filteredSymbols = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return symbols;
    return symbols.filter((s) => s.symbol.toLowerCase().includes(q));
  }, [symbols, query]);

  const filteredChain = useMemo(() => {
    if (!chainData) return [] as Array<OptionContract & { moneyness: "ITM" | "ATM" | "OTM" }>;
    const all: OptionContract[] = [...chainData.calls, ...chainData.puts];
    return all
      .filter((c) => {
        if (filter === "call" && c.type !== "call") return false;
        if (filter === "put" && c.type !== "put") return false;
        if (filter === "ITM" || filter === "ATM" || filter === "OTM") {
          const m = calcMoneyness(c.underlying_price, c.strike, c.type);
          if (m !== filter) return false;
        }
        if (query) {
          const q = query.trim().toLowerCase();
          if (!c.symbol.toLowerCase().includes(q) && !c.name?.toLowerCase().includes(q)) return false;
        }
        return true;
      })
      .map((c) => ({ ...c, moneyness: calcMoneyness(c.underlying_price, c.strike, c.type) }));
  }, [chainData, filter, query]);

  const filteredCommodities = useMemo(() => {
    return commodities.filter((c) => {
      if (filter !== "all" && c.category !== filter) return false;
      if (query) {
        const q = query.trim().toLowerCase();
        if (!c.symbol.toLowerCase().includes(q) && !c.name?.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [commodities, filter, query]);

  const optionFilters = [
    { key: "all", label: "همه" },
    { key: "ITM", label: "در سود" },
    { key: "ATM", label: "خنثی" },
    { key: "OTM", label: "در ضرر" },
    { key: "call", label: "اختیار خرید" },
    { key: "put", label: "اختیار فروش" },
  ];

  const commodityFilters = [
    { key: "all", label: "همه" },
    { key: "precious_metal", label: "فلزات گرانبها" },
    { key: "base_metal", label: "فلزات پایه" },
    { key: "energy", label: "انرژی" },
  ];

  const lastUpdate = chainData?.calls?.[0]?.days_to_expiry != null ? "1405/06/11 - 14:59" : "";

  return (
    <AppLayout title="جستجوی بازار آپشن و کالا" subtitle="جستجوی یکپارچه در قراردادهای اختیار معامله و قیمت جهانی کامودیتی‌ها">
      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={() => { setMarket("option"); setFilter("all"); setActiveUnderlying(null); }}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            market === "option" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"
          }`}
        >
          اختیار معامله
        </button>
        <button
          onClick={() => { setMarket("commodity"); setFilter("all"); setActiveUnderlying(null); }}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            market === "commodity" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"
          }`}
        >
          کامودیتی
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-3 mb-4">
        <div className="flex-1 flex items-center gap-2 bg-surface-800 rounded-lg px-3 py-2 border border-surface-700">
          <span className="material-icons text-sm text-surface-500">search</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={market === "option" ? "جستجوی نماد یا دارایی پایه..." : "جستجوی نماد یا نام کالا..."}
            className="bg-transparent text-sm text-white placeholder-surface-500 outline-none flex-1 min-w-0"
          />
          {query && (
            <button onClick={() => setQuery("")} className="text-xs text-surface-400 hover:text-white">✕</button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(market === "option" ? optionFilters : commodityFilters).map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-2 rounded-lg text-xs transition-all ${
                filter === f.key
                  ? "bg-primary-600/20 text-primary-300 border border-primary-600/40"
                  : "bg-surface-800 text-surface-400 border border-surface-700 hover:text-surface-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="glass-card overflow-hidden">
        <div className="px-4 py-2 border-b border-surface-800 text-[10px] text-surface-500 flex justify-between">
          <span>
            {market === "option"
              ? activeUnderlying
                ? `${filteredChain.length} قرارداد از ${chainData?.underlying}`
                : `${filteredSymbols.length} دارایی پایه`
              : `${filteredCommodities.length} کالا`}
          </span>
          {market === "option" && activeUnderlying && lastUpdate && (
            <span>به‌روزرسانی: {lastUpdate}</span>
          )}
        </div>

        {market === "option" && !activeUnderlying && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-surface-900/50 text-surface-500">
                <tr>
                  <th className="px-3 py-2 text-right">نماد پایه</th>
                  <th className="px-3 py-2 text-right">قیمت پایه</th>
                  <th className="px-3 py-2 text-right">تعداد قرارداد فعال</th>
                  <th className="px-3 py-2 text-right">حجم کل</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800">
                {symLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i}><td colSpan={5} className="px-3 py-2"><Skeleton className="h-6 w-full" /></td></tr>
                    ))
                  : filteredSymbols.map((s) => (
                      <tr key={s.symbol} className="hover:bg-surface-800/40">
                        <td className="px-3 py-2 font-mono font-bold text-surface-200">{s.symbol}</td>
                        <td className="px-3 py-2 font-mono">{fmtNum(s.price)}</td>
                        <td className="px-3 py-2 font-mono">{fmtNum(s.contracts)}</td>
                        <td className="px-3 py-2 font-mono">{fmtNum(s.volume)}</td>
                        <td className="px-3 py-2 text-left">
                          <button
                            onClick={() => setActiveUnderlying(s.symbol)}
                            className="px-2 py-1 text-[10px] rounded bg-primary-600/20 text-primary-300 border border-primary-600/40 hover:bg-primary-600/30"
                          >
                            مشاهده زنجیره ←
                          </button>
                        </td>
                      </tr>
                    ))
                }
              </tbody>
            </table>
          </div>
        )}

        {market === "option" && activeUnderlying && (
          <div>
            <div className="px-4 py-2 border-b border-surface-800 flex items-center justify-between">
              <button
                onClick={() => setActiveUnderlying(null)}
                className="text-[10px] text-primary-400 hover:text-primary-300"
              >
                → بازگشت به لیست نمادها
              </button>
              <div className="text-xs text-surface-300">
                {chainData?.underlying} | قیمت پایه: {fmtNum(chainData?.underlying_price ?? 0)} | {chainData?.total_contracts ?? 0} قرارداد
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-surface-900/50 text-surface-500">
                  <tr>
                    <th className="px-3 py-2 text-right">نماد</th>
                    <th className="px-3 py-2 text-right">نوع</th>
                    <th className="px-3 py-2 text-right">قیمت اعمال</th>
                    <th className="px-3 py-2 text-right">آخرین</th>
                    <th className="px-3 py-2 text-right">روز تا سررسید</th>
                    <th className="px-3 py-2 text-right">حجم</th>
                    <th className="px-3 py-2 text-right">OI</th>
                    <th className="px-3 py-2 text-right">وضعیت</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-800">
                  {chainLoading
                    ? Array.from({ length: 6 }).map((_, i) => (
                        <tr key={i}><td colSpan={8} className="px-3 py-2"><Skeleton className="h-6 w-full" /></td></tr>
                      ))
                    : filteredChain.map((r) => (
                        <tr key={r.symbol} className="hover:bg-surface-800/40">
                          <td className="px-3 py-2 font-mono font-bold text-surface-200">{r.symbol}</td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] ${r.type === "call" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"}`}>
                              {r.type === "call" ? "خرید" : "فروش"}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono">{fmtNum(r.strike)}</td>
                          <td className="px-3 py-2 font-mono text-surface-200">{fmtNum(r.price)}</td>
                          <td className="px-3 py-2 font-mono">{r.days_to_expiry ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{fmtNum(r.volume)}</td>
                          <td className="px-3 py-2 font-mono">{fmtNum(r.oi)}</td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] ${
                              r.moneyness === "ITM" ? "bg-accent-emerald/15 text-accent-emerald"
                              : r.moneyness === "OTM" ? "bg-accent-rose/15 text-accent-rose"
                              : "bg-surface-700 text-surface-300"
                            }`}>
                              {r.moneyness === "ITM" ? "در سود" : r.moneyness === "OTM" ? "در ضرر" : "خنثی"}
                            </span>
                          </td>
                        </tr>
                      ))
                  }
                </tbody>
              </table>
            </div>
          </div>
        )}

        {market === "commodity" && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-surface-900/50 text-surface-500">
                <tr>
                  <th className="px-3 py-2 text-right">نماد</th>
                  <th className="px-3 py-2 text-right">نام</th>
                  <th className="px-3 py-2 text-right">دسته</th>
                  <th className="px-3 py-2 text-right">قیمت</th>
                  <th className="px-3 py-2 text-right">تغییر</th>
                  <th className="px-3 py-2 text-right">درصد</th>
                  <th className="px-3 py-2 text-right">واحد</th>
                  <th className="px-3 py-2 text-right">زمان</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800">
                {comLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i}><td colSpan={8} className="px-3 py-2"><Skeleton className="h-6 w-full" /></td></tr>
                    ))
                  : filteredCommodities.map((r) => (
                      <tr key={r.symbol} className="hover:bg-surface-800/40">
                        <td className="px-3 py-2 font-mono font-bold text-surface-200">{r.symbol}</td>
                        <td className="px-3 py-2 text-surface-300">{r.name}</td>
                        <td className="px-3 py-2">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-surface-700 text-surface-300">
                            {r.category === "precious_metal" ? "فلزات گرانبها" : r.category === "base_metal" ? "فلزات پایه" : "انرژی"}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-mono text-surface-200">{fmtNum(r.price, 2)}</td>
                        <td className={`px-3 py-2 font-mono ${(r.change_value ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                          {(r.change_value ?? 0) >= 0 ? "+" : ""}{fmtNum(r.change_value, 2)}
                        </td>
                        <td className={`px-3 py-2 font-mono ${(r.change_percent ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                          {(r.change_percent ?? 0) >= 0 ? "+" : ""}{fmtNum(r.change_percent, 2)}%
                        </td>
                        <td className="px-3 py-2 font-mono text-surface-400">{r.unit || "USD"}</td>
                        <td className="px-3 py-2 font-mono text-surface-400">{r.date} {r.time}</td>
                      </tr>
                    ))
                }
              </tbody>
            </table>
          </div>
        )}

        {((market === "option" && activeUnderlying && !chainLoading && filteredChain.length === 0) ||
          (market === "option" && !activeUnderlying && !symLoading && filteredSymbols.length === 0) ||
          (market === "commodity" && !comLoading && filteredCommodities.length === 0)) && (
          <div className="text-center py-10 text-surface-500 text-sm">
            نتیجه‌ای یافت نشد
          </div>
        )}
      </div>
    </AppLayout>
  );
}