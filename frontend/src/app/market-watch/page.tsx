"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import AddAlertButton from "@/components/AddAlertButton";
import { apiGet } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface MarketSummary {
  index_value: number;
  index_change: number;
  index_change_pct: number;
  index_equal_weight: number;
  index_equal_weight_change: number;
  index_equal_weight_change_pct: number;
  total_trade_value: number;
  total_volume: number;
  net_real_money_flow: number;
  buy_queue_value: number;
  sell_queue_value: number;
  equity_fund_value: number;
  equity_fund_net: number;
  fixed_income_fund_value: number;
  fixed_income_fund_net: number;
}

interface SymbolStats {
  total: number;
  positive: number;
  negative: number;
  unchanged: number;
  above_closing: number;
  below_closing: number;
  buy_queue: number;
  sell_queue: number;
}

interface MoneyFlowItem {
  name: string;
  symbol?: string;
  value: number;
}

interface MarketWatchData {
  date: string;
  market: string;
  sector_filter: string | null;
  summary: MarketSummary;
  symbol_stats: SymbolStats;
  sector_money_flow: { inflow: MoneyFlowItem[]; outflow: MoneyFlowItem[] };
  stock_money_flow: { inflow: MoneyFlowItem[]; outflow: MoneyFlowItem[] };
  sector_trade_values: MoneyFlowItem[];
  sectors: string[];
}

// ── Tab Config ─────────────────────────────────────────────────────────────

const MARKET_TABS = [
  { key: "all", label: "کل بازار" },
  { key: "bourse", label: "بازار بورس" },
  { key: "farabourse", label: "بازار فرابورس" },
  { key: "top30", label: "30 شرکت بزرگ" },
  { key: "top50", label: "50 شرکت برتر" },
];

// ── Helper Components ──────────────────────────────────────────────────────

function StatCard({ label, value, change, unit, color }: {
  label: string;
  value: string | number;
  change?: number;
  unit?: string;
  color?: string;
}) {
  const changeColor = change != null
    ? change >= 0 ? "text-accent-emerald" : "text-accent-rose"
    : "";
  return (
    <div className="bg-surface-800/50 rounded-xl p-4 border border-surface-700/50">
      <div className="text-xs text-surface-500 mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${color || "text-surface-100"}`}>
        {typeof value === "number" ? value.toLocaleString("en-US") : value}
        {unit && <span className="text-xs text-surface-500 mr-1">{unit}</span>}
      </div>
      {change != null && (
        <div className={`text-xs font-mono mt-0.5 ${changeColor}`}>
          {change >= 0 ? "+" : ""}{change.toLocaleString("en-US")} ({change >= 0 ? "+" : ""}{((change / (Math.abs(value as number) || 1)) * 100).toFixed(2)}%)
        </div>
      )}
    </div>
  );
}

function FlowList({ title, items, color }: {
  title: string;
  items: MoneyFlowItem[];
  color: "emerald" | "rose";
}) {
  const bg = color === "emerald" ? "bg-accent-emerald/10" : "bg-accent-rose/10";
  const text = color === "emerald" ? "text-accent-emerald" : "text-accent-rose";
  return (
    <div className="bg-surface-800/50 rounded-xl p-4 border border-surface-700/50">
      <div className="text-sm font-bold text-surface-200 mb-3">{title}</div>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {items.length === 0 ? (
          <div className="text-xs text-surface-500 text-center py-4">داده‌ای موجود نیست</div>
        ) : (
          items.map((item, i) => (
            <div key={i} className="flex items-center justify-between text-xs gap-2">
              <span className="text-surface-300 truncate max-w-[50%]">
                {item.symbol || item.name}
              </span>
              <span className={`font-mono font-bold ${text}`}>
                {item.value.toLocaleString("en-US")}
              </span>
              {(item.symbol || item.name) && (
                <AddAlertButton compact symbol={item.symbol || item.name || ""} market="stock" />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function MarketWatchPage() {
  const [activeTab, setActiveTab] = useState("all");
  const [selectedSector, setSelectedSector] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["market-watch", activeTab, selectedSector],
    queryFn: async () => {
      const params = new URLSearchParams({ market: activeTab });
      if (selectedSector) params.set("sector", selectedSector);
      const res = await apiGet<{ success: boolean; data: MarketWatchData }>(
        `/market-watch?${params.toString()}`
      );
      return res?.data ?? null;
    },
    refetchInterval: 300_000,
    staleTime: 60_000,
  });

  const summary = data?.summary;
  const stats = data?.symbol_stats;

  return (
    <AppLayout title="📋 دیدبان بازار" subtitle="خلاصه معاملات بازار سرمایه">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* ── Tabs ── */}
        <div className="flex items-center gap-2 flex-wrap">
          {MARKET_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === tab.key
                  ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Sector Filter ── */}
        {data?.sectors && data.sectors.length > 0 && (
          <div className="flex items-center gap-3">
            <select
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value)}
              className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-sm text-surface-200 outline-none focus:border-primary-500"
            >
              <option value="">--- انتخاب گروه ---</option>
              {data.sectors.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            {selectedSector && (
              <button
                onClick={() => setSelectedSector("")}
                className="text-xs text-surface-500 hover:text-surface-300"
              >
                پاک کردن فیلتر
              </button>
            )}
          </div>
        )}

        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        ) : data ? (
          <>
            {/* ── Date ── */}
            <div className="text-xs text-surface-500">
              تاریخ: {data.date}
            </div>

            {/* ── Summary Cards ── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                label="شاخص کل"
                value={summary?.index_value ?? 0}
                change={summary?.index_change ?? 0}
              />
              <StatCard
                label="شاخص هم وزن"
                value={summary?.index_equal_weight ?? 0}
                change={summary?.index_equal_weight_change ?? 0}
              />
              <StatCard
                label="ارزش کل معاملات"
                value={summary?.total_trade_value ?? 0}
                unit="میلیارد ریال"
              />
              <StatCard
                label="خالص پول حقیقی"
                value={summary?.net_real_money_flow ?? 0}
                unit="میلیارد ریال"
                color={(summary?.net_real_money_flow ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}
              />
            </div>

            {/* ── Second Row ── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                label="ارزش صف خرید"
                value={summary?.buy_queue_value ?? 0}
                unit="میلیارد ریال"
                color="text-accent-emerald"
              />
              <StatCard
                label="ارزش صف فروش"
                value={summary?.sell_queue_value ?? 0}
                unit="میلیارد ریال"
                color="text-accent-rose"
              />
              <StatCard
                label="صندوق سهامی"
                value={summary?.equity_fund_value ?? 0}
                unit="میلیارد ریال"
              />
              <StatCard
                label="صندوق درآمد ثابت"
                value={summary?.fixed_income_fund_value ?? 0}
                unit="میلیارد ریال"
              />
            </div>

            {/* ── Symbol Stats ── */}
            <Card title="تعداد نمادها">
              <div className="grid grid-cols-4 md:grid-cols-8 gap-3">
                <div className="text-center">
                  <div className="text-2xl font-bold text-surface-100">{stats?.total ?? 0}</div>
                  <div className="text-xs text-surface-500">کل</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent-emerald">{stats?.positive ?? 0}</div>
                  <div className="text-xs text-surface-500">مثبت</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent-rose">{stats?.negative ?? 0}</div>
                  <div className="text-xs text-surface-500">منفی</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-surface-400">{stats?.unchanged ?? 0}</div>
                  <div className="text-xs text-surface-500">بدون تغییر</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">{stats?.above_closing ?? 0}</div>
                  <div className="text-xs text-surface-500">بالاتر از پایانی</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-400">{stats?.below_closing ?? 0}</div>
                  <div className="text-xs text-surface-500">پایین‌تر از پایانی</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent-emerald">{stats?.buy_queue ?? 0}</div>
                  <div className="text-xs text-surface-500">صف خرید</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent-rose">{stats?.sell_queue ?? 0}</div>
                  <div className="text-xs text-surface-500">صف فروش</div>
                </div>
              </div>
            </Card>

            {/* ── Money Flow ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FlowList
                title="ورود پول حقیقی به گروه"
                items={data.sector_money_flow.inflow}
                color="emerald"
              />
              <FlowList
                title="خروج پول حقیقی از گروه"
                items={data.sector_money_flow.outflow}
                color="rose"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FlowList
                title="ورود پول حقیقی به سهام"
                items={data.stock_money_flow.inflow}
                color="emerald"
              />
              <FlowList
                title="خروج پول حقیقی از سهام"
                items={data.stock_money_flow.outflow}
                color="rose"
              />
            </div>

            {/* ── Sector Trade Values ── */}
            {data.sector_trade_values.length > 0 && (
              <Card title="ارزش معاملات گروه‌ها - میلیارد ریال">
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {data.sector_trade_values.map((item, i) => {
                    const maxVal = data.sector_trade_values[0]?.value || 1;
                    const pct = (item.value / maxVal) * 100;
                    return (
                      <div key={i} className="flex items-center gap-3 text-xs">
                        <span className="text-surface-300 w-40 truncate">{item.name}</span>
                        <div className="flex-1 h-4 bg-surface-700 rounded overflow-hidden">
                          <div
                            className="h-full bg-primary-500/60 rounded"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-surface-200 font-mono w-20 text-left">
                          {item.value.toLocaleString("en-US")}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            )}
          </>
        ) : (
          <div className="text-center py-12 text-surface-500">
            داده‌ای موجود نیست
          </div>
        )}
      </div>
    </AppLayout>
  );
}
