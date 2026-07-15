"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";
import { generateMockHeatmap } from "@/lib/types";
import { useClientData } from "@/hooks/useClientData";
import SSRSafe from "@/components/SSRSafe";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------

interface GoldCoinItem {
  symbol: string;
  name?: string;
  price: number;
  change?: number;
  change_percent?: number;
}

interface CurrencyItem {
  symbol: string;
  name?: string;
  price: number;
  change_percent?: number;
  change?: number;
}

interface CryptoItem {
  symbol: string;
  name?: string;
  price_usd?: number;
  price_irr?: number;
  change_percent?: number;
}

/** Extended from HeatmapCell — adds enriched fields from /market/enriched-heatmap */
interface LiveSymbolCell {
  symbol: string;
  name?: string;
  price: number;
  change: number;
  value?: number;
  volume?: number;
  /** آستانه مجاز پایین (tmin) */
  priceLowestAllowed?: number;
  /** آستانه مجاز بالا (tmax) */
  priceHighestAllowed?: number;
  /** درصد سهام شناور */
  freeFloatPct?: number;
  eps?: number;
  peRatio?: number;
  /** وضعیت نماد (مجاز/ممنوع/...) */
  state?: string;
  sector?: string;
  market?: string;
  board?: string;
}

// ------ Formatters ------------------------------------------------------------------------------------------------------------------

function formatPrice(price: number): string {
  if (price >= 1_000_000_000_000) return `${(price / 1_000_000_000_000).toFixed(2)}T`;
  if (price >= 1_000_000_000) return `${(price / 1_000_000_000).toFixed(2)}B`;
  if (price >= 1_000_000) return `${(price / 1_000_000).toFixed(1)}M`;
  if (price >= 1_000) return price.toLocaleString("fa-IR");
  return price.toLocaleString("fa-IR");
}

function formatLargePrice(price: number): string {
  return price.toLocaleString("fa-IR");
}

function formatPercent(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

// ------ Mock Data ---------------------------------------------------------------------------------------------------------------------

function generateMockGoldCoin(): GoldCoinItem[] {
  return [
    { symbol: "طلا ۱۸", price: 4385000, change_percent: 1.2 },
    { symbol: "طلا ۲۴", price: 5295000, change_percent: 1.5 },
    { symbol: "سکه امامی", price: 52350000, change_percent: 0.8 },
    { symbol: "سکه بهار", price: 49800000, change_percent: -0.3 },
    { symbol: "نیم سکه", price: 29500000, change_percent: 0.6 },
    { symbol: "ربع سکه", price: 16800000, change_percent: 0.4 },
  ];
}

function generateMockCurrency(): CurrencyItem[] {
  return [
    { symbol: "USD", name: "دلار آمریکا", price: 60350, change_percent: 0.15 },
    { symbol: "EUR", name: "یورو", price: 65820, change_percent: 0.22 },
    { symbol: "GBP", name: "پوند", price: 76700, change_percent: -0.08 },
    { symbol: "AED", name: "درهم امارات", price: 16430, change_percent: 0.12 },
    { symbol: "TRY", name: "لیر ترکیه", price: 1870, change_percent: 0.35 },
  ];
}

function generateMockCrypto(): CryptoItem[] {
  return [
    { symbol: "BTC", name: "Bitcoin", price_usd: 67500, change_percent: 2.3 },
    { symbol: "ETH", name: "Ethereum", price_usd: 3450, change_percent: 1.8 },
    { symbol: "BNB", name: "BNB", price_usd: 580, change_percent: -0.5 },
    { symbol: "SOL", name: "Solana", price_usd: 145, change_percent: 4.2 },
    { symbol: "XRP", name: "XRP", price_usd: 0.62, change_percent: 1.1 },
  ];
}

// ------ Sub-components ------------------------------------------------------------------------------------------------------

function PriceRange({ low, high, current }: { low?: number; high?: number; current: number }) {
  if (!low && !high) return null;
  const rangePct = high && low && high > low ? ((current - low) / (high - low)) * 100 : 50;
  return (
    <div className="flex items-center gap-1.5" dir="ltr">
      {low != null && low > 0 && (
        <span className="text-[10px] font-mono text-surface-500" title="آستانه مجاز پایین">
          {low.toLocaleString("fa-IR")}
        </span>
      )}
      <div className="relative w-12 h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
        <div
          className="absolute h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(Math.max(rangePct, 2), 98)}%`,
            background: `linear-gradient(90deg, #db2777, #6366f1, #0891b2)`,
          }}
        />
      </div>
      {high != null && high > 0 && (
        <span className="text-[10px] font-mono text-surface-500" title="آستانه مجاز بالا">
          {high.toLocaleString("fa-IR")}
        </span>
      )}
    </div>
  );
}

function SymbolRow({ cell }: { cell: LiveSymbolCell }) {
  const isPositive = cell.change > 0;
  const isNegative = cell.change < 0;
  return (
    <div className="live-symbol-row group">
      <div className="live-symbol-name">
        <span className="live-symbol-text">{cell.symbol}</span>
        {cell.name && <span className="live-symbol-sub text-surface-500">{cell.name}</span>}
        {/* Free float badge */}
        {cell.freeFloatPct != null && cell.freeFloatPct > 0 && (
          <span className="text-[9px] font-mono text-accent-cyan/70 dark:text-accent-cyan/60">
            شناور {cell.freeFloatPct.toFixed(1)}%
          </span>
        )}
      </div>
      <div className="live-symbol-price flex flex-col items-center gap-0.5">
        <span className="live-price-value">{formatLargePrice(cell.price || 0)}</span>
        {/* Price range bar */}
        <PriceRange low={cell.priceLowestAllowed} high={cell.priceHighestAllowed} current={cell.price || 0} />
      </div>
      <div className={`live-symbol-change ${isPositive ? "positive" : isNegative ? "negative" : "neutral"}`}>
        <span className="live-change-icon material-icons text-sm">
          {isPositive ? "arrow_upward" : isNegative ? "arrow_downward" : "remove"}
        </span>
        <span className="live-change-text">{formatPercent(cell.change)}</span>
      </div>
      <div className="live-symbol-volume flex flex-col items-center gap-0.5">
        <span className="live-vol-text">{formatPrice(cell.volume || 0)}</span>
        {cell.peRatio != null && cell.peRatio !== 0 && (
          <span className="text-[9px] font-mono text-surface-500">P/E {cell.peRatio.toFixed(1)}</span>
        )}
      </div>
      {/* Mini spark bar */}
      <div className="live-spark-bar">
        <div
          className={`live-spark-fill ${isPositive ? "bg-accent-cyan" : isNegative ? "bg-accent-rose" : "bg-surface-500"}`}
          style={{ width: `${Math.min(Math.abs(cell.change) * 10, 100)}%` }}
        />
      </div>
    </div>
  );
}

function GainersLosersTab({ gainers, losers }: { gainers: LiveSymbolCell[]; losers: LiveSymbolCell[] }) {
  const [view, setView] = useState<"gainers" | "losers">("gainers");
  const items = view === "gainers" ? gainers : losers;

  return (
    <div className="live-tab-content">
      <div className="live-gl-toggle">
        <button
          className={`live-gl-btn ${view === "gainers" ? "active-gainers" : ""}`}
          onClick={() => setView("gainers")}
        >
          <span className="material-icons text-sm">trending_up</span>
          بیشترین رشد
        </button>
        <button
          className={`live-gl-btn ${view === "losers" ? "active-losers" : ""}`}
          onClick={() => setView("losers")}
        >
          <span className="material-icons text-sm">trending_down</span>
          بیشترین کاهش
        </button>
      </div>
      <div className="live-symbol-list">
        {items.length === 0 ? (
          <div className="text-center py-6 text-surface-500 text-sm">داده‌ای موجود نیست</div>
        ) : (
          items.slice(0, 7).map((cell, i) => (
            <div key={`${cell.symbol}-${i}`} className="live-gl-row">
              <div className="live-gl-rank">#{i + 1}</div>
              <div className="live-gl-symbol">{cell.symbol}</div>
              <div className="live-gl-price">{formatLargePrice(cell.price || 0)}</div>
              <div className={`live-gl-change ${cell.change > 0 ? "positive" : cell.change < 0 ? "negative" : "neutral"}`}>
                {formatPercent(cell.change)}
              </div>
              <div className="live-gl-bar-wrapper">
                <div
                  className={`live-gl-bar ${cell.change > 0 ? "bar-positive" : "bar-negative"}`}
                  style={{ width: `${Math.min(Math.abs(cell.change) * 8, 100)}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function GoldCurrencyTab({ goldItems, currencyItems, cryptoItems }: {
  goldItems: GoldCoinItem[];
  currencyItems: CurrencyItem[];
  cryptoItems: CryptoItem[];
}) {
  type TabItem = GoldCoinItem | CurrencyItem | CryptoItem;

  const [activeMarket, setActiveMarket] = useState<"gold" | "currency" | "crypto">("gold");

  function formatTabPrice(item: TabItem): string {
    if ("price_usd" in item) {
      return item.price_usd ? `$${item.price_usd.toLocaleString()}` : "—";
    }
    return formatLargePrice((item as GoldCoinItem | CurrencyItem).price);
  }

  function formatTabChange(item: TabItem): string {
    const pct = "change_percent" in item ? (item as GoldCoinItem | CurrencyItem | CryptoItem).change_percent : 0;
    return formatPercent(pct ?? 0);
  }

  const marketData = useMemo(() => {
    switch (activeMarket) {
      case "gold":
        return { items: goldItems, label: "طلا و سکه" };
      case "currency":
        return { items: currencyItems, label: "نرخ ارز" };
      case "crypto":
        return { items: cryptoItems, label: "ارز دیجیتال" };
    }
  }, [activeMarket, goldItems, currencyItems, cryptoItems]);

  return (
    <div className="live-tab-content">
      <div className="live-market-tabs">
        {[
          { key: "gold", label: "🥇 طلا و سکه", icon: "monetization_on" },
          { key: "currency", label: "💵 ارز", icon: "currency_exchange" },
          { key: "crypto", label: "₿ کریپتو", icon: "token" },
        ].map((tab) => (
          <button
            key={tab.key}
            className={`live-market-tab ${activeMarket === tab.key ? "active-market" : ""}`}
            onClick={() => setActiveMarket(tab.key as "gold" | "currency" | "crypto")}
          >
            <span className="material-icons text-sm">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="live-gl-market-label">{marketData?.label}</div>

      <div className="live-symbol-list">
        {marketData?.items.map((item: TabItem, i: number) => (
          <div key={`${item.symbol || item.name}-${i}`} className="live-gl-row">
            <div className="live-gl-rank">#{i + 1}</div>
            <div className="live-gl-symbol">
              <span className="live-gl-symbol-text">{item.symbol}</span>
              {item.name && <span className="live-gl-name text-surface-500 text-xs">{item.name}</span>}
            </div>
            <div className="live-gl-price font-mono">{formatTabPrice(item)}</div>
            <div className={`live-gl-change ${(item.change_percent || 0) > 0 ? "positive" : (item.change_percent || 0) < 0 ? "negative" : "neutral"}`}>
              {formatTabChange(item)}
            </div>
            <div className="live-gl-bar-wrapper">
              <div
                className={`live-gl-bar ${(item.change_percent || 0) > 0 ? "bar-positive" : "bar-negative"}`}
                style={{ width: `${Math.min(Math.abs(item.change_percent || 0) * 10, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ------ Main Component ------------------------------------------------------------------------------------------------------

interface LiveMarketWidgetProps {
  className?: string;
}

export default function LiveMarketWidget({ className = "" }: LiveMarketWidgetProps) {
  const [activeTab, setActiveTab] = useState<"symbols" | "gainers-losers" | "gold-currency">("symbols");

  // Client-safe mock data (use LiveSymbolCell for extended fields)
  const [mockCells] = useClientData(() => generateMockHeatmap() as LiveSymbolCell[], [] as LiveSymbolCell[]);
  const [mockGold] = useClientData(() => generateMockGoldCoin(), [] as GoldCoinItem[]);
  const [mockCurrency] = useClientData(() => generateMockCurrency(), [] as CurrencyItem[]);
  const [mockCrypto] = useClientData(() => generateMockCrypto(), [] as CryptoItem[]);

  // ------ Fetch enriched real-time symbol data ---------------------------
  const { data: symbolCells = mockCells as LiveSymbolCell[], isFetching: symbolsLoading, dataUpdatedAt: symbolsUpdatedAt } = useQuery<LiveSymbolCell[]>({
    queryKey: ["live-market-symbols-enriched"],
    queryFn: async (): Promise<LiveSymbolCell[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: LiveSymbolCell[] }>("/market/enriched-heatmap");
        const extracted = extractArray<LiveSymbolCell>(res);
        return extracted.length > 0 ? extracted : mockCells;
      } catch {
        return mockCells;
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  // ------ Fetch gold/coin prices ---------------------------------------------------------------------
  const { data: goldData = mockGold, dataUpdatedAt: goldUpdatedAt } = useQuery({
    queryKey: ["live-gold-coin"],
    queryFn: async (): Promise<GoldCoinItem[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: GoldCoinItem[] }>("/brsapi/gold-coin");
        const extracted = extractArray<GoldCoinItem>(res);
        return extracted.length > 0 ? extracted : mockGold;
      } catch {
        return mockGold;
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ------ Fetch currency prices ------------------------------------------------------------------------
  const { data: currencyData = mockCurrency, dataUpdatedAt: currencyUpdatedAt } = useQuery({
    queryKey: ["live-currency"],
    queryFn: async (): Promise<CurrencyItem[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: CurrencyItem[] }>("/brsapi/currency");
        const extracted = extractArray<CurrencyItem>(res);
        return extracted.length > 0 ? extracted : mockCurrency;
      } catch {
        return mockCurrency;
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ------ Fetch crypto prices ------------------------------------------------------------------------------
  const { data: cryptoData = mockCrypto, dataUpdatedAt: cryptoUpdatedAt } = useQuery({
    queryKey: ["live-crypto"],
    queryFn: async (): Promise<CryptoItem[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: CryptoItem[] }>("/brsapi/crypto");
        const extracted = extractArray<CryptoItem>(res);
        return extracted.length > 0 ? extracted : mockCrypto;
      } catch {
        return mockCrypto;
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ------ Compute gainers & losers ---------------------------------------------------------------
  const sortedCells = useMemo(() => {
    return [...symbolCells].sort((a, b) => b.change - a.change);
  }, [symbolCells]);

  const gainers = useMemo(() => sortedCells.filter((c) => c.change > 0), [sortedCells]);
  const losers = useMemo(() => sortedCells.filter((c) => c.change < 0), [sortedCells]);

  // ------ Latest fetch timestamp (from React Query's built-in tracking) ---
  const lastUpdateTime = useMemo(() => {
    const timestamps = [symbolsUpdatedAt, goldUpdatedAt, currencyUpdatedAt, cryptoUpdatedAt]
      .filter((t): t is number => typeof t === "number" && t > 0);
    return timestamps.length > 0
      ? new Date(Math.max(...timestamps)).toLocaleTimeString("fa-IR")
      : new Date().toLocaleTimeString("fa-IR");
  }, [symbolsUpdatedAt, goldUpdatedAt, currencyUpdatedAt, cryptoUpdatedAt]);

  return (
    <Card
      title="📊 بازار زنده"
      subtitle={"آخرین به‌روزرسانی: " + lastUpdateTime}
      className={className}
      headerClassName="live-market-header"
      actions={
        <div className="live-tab-actions">
          <CardAction active={activeTab === "symbols"} onClick={() => setActiveTab("symbols")}>
            <span className="material-icons text-sm">monitoring</span>
            نمادها
          </CardAction>
          <CardAction active={activeTab === "gainers-losers"} onClick={() => setActiveTab("gainers-losers")}>
            <span className="material-icons text-sm">leaderboard</span>
            پربازده
          </CardAction>
          <CardAction active={activeTab === "gold-currency"} onClick={() => setActiveTab("gold-currency")}>
            <span className="material-icons text-sm">payments</span>
            طلا و ارز
          </CardAction>
        </div>
      }
    >
      <SSRSafe className="live-market-body">
        {/* Loading shimmer */}
        {symbolsLoading && (
          <div className="live-loading-bar">
            <div className="live-loading-shimmer" />
          </div>
        )}

        {/* ------ Tab: Symbols ------------------------------------------------------------------ */}
        {activeTab === "symbols" && (
          <div className="live-tab-content">
            <div className="live-symbols-header">
              <span className="live-header-label">نماد</span>
              <span className="live-header-label">قیمت</span>
              <span className="live-header-label">تغییر</span>
              <span className="live-header-label">حجم</span>
            </div>
            <div className="live-symbol-list">
              {symbolCells.length === 0 ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full mb-1" />
                ))
              ) : (
                symbolCells.slice(0, 8).map((cell, i) => (
                  <SymbolRow key={`${cell.symbol}-${i}`} cell={cell} />
                ))
              )}
            </div>
          </div>
        )}

        {/* ------ Tab: Gainers / Losers ------------------------------------ */}
        {activeTab === "gainers-losers" && (
          <GainersLosersTab gainers={gainers} losers={losers} />
        )}

        {/* ------ Tab: Gold / Currency / Crypto ------------ */}
        {activeTab === "gold-currency" && (
          <GoldCurrencyTab
            goldItems={goldData}
            currencyItems={currencyData}
            cryptoItems={cryptoData}
          />
        )}
      </SSRSafe>
    </Card>
  );
}
