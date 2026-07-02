"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
import { useClientData } from "@/hooks/useClientData";
/** Extended with price field that /market/heatmap endpoint returns */
interface TickerCell {
  symbol: string;
  change: number;
  price?: number;
  value?: number;
  volume?: number;
}

function formatPrice(p: number): string {
  if (p >= 1_000_000_000_000) return `${(p / 1_000_000_000_000).toFixed(1)}T`;
  if (p >= 1_000_000_000) return `${(p / 1_000_000_000).toFixed(1)}B`;
  if (p >= 1_000_000) return `${(p / 1_000_000).toFixed(0)}M`;
  return p.toLocaleString("fa-IR");
}

function TickerItem({ symbol, price, change }: { symbol: string; price: number; change: number }) {
  const isUp = change > 0;
  const isDown = change < 0;
  const absPct = Math.min(Math.abs(change), 10);
  const intensity = absPct / 10;

  const bgStyle = isUp
    ? { backgroundColor: `rgba(0, 180, 50, ${0.08 + intensity * 0.22})` }
    : isDown
    ? { backgroundColor: `rgba(220, 30, 60, ${0.08 + intensity * 0.22})` }
    : {};

  return (
    <Link href={`/symbol/${encodeURIComponent(symbol)}`} className="ticker-item-link">
      <div className="ticker-item" style={bgStyle}>
        <span className="ticker-symbol">{symbol}</span>
        <span className="ticker-price">{formatPrice(price)}</span>
        <span className={`ticker-change ${isUp ? "positive" : isDown ? "negative" : "neutral"}`}>
          <span className="material-icons ticker-arrow">
            {isUp ? "arrow_upward" : isDown ? "arrow_downward" : "remove"}
          </span>
          {Math.abs(change).toFixed(2)}%
        </span>
      </div>
    </Link>
  );
}

export default function TickerTape() {
  const [mockCells] = useClientData(() => [] as TickerCell[], [] as TickerCell[]);

  const { data: cells = mockCells } = useQuery({
    queryKey: ["ticker-tape"],
    queryFn: async (): Promise<TickerCell[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: TickerCell[] }>("/market/heatmap");
        const extracted = extractArray<TickerCell>(res);
        return extracted.length > 0 ? extracted : [];
      } catch {
        return [];
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  if (!cells || cells.length === 0) return null;

  // Sort by trade value descending, take top 30
  const top = [...cells]
    .sort((a, b) => (b.value || 0) - (a.value || 0))
    .slice(0, 30);

  return (
    <div className="ticker-wrapper">
      <div className="ticker-label">
        <span className="material-icons ticker-pulse-icon">fiber_manual_record</span>
        <span>زنده</span>
      </div>
      <div className="ticker-track">
        <div className="ticker-content">
          {/* First copy */}
          {top.map((cell, i) => (
            <TickerItem key={`a-${cell.symbol || i}`} symbol={cell.symbol} price={cell.price || cell.value || 0} change={cell.change} />
          ))}
          {/* Duplicate for seamless loop */}
          {top.map((cell, i) => (
            <TickerItem key={`b-${cell.symbol || i}`} symbol={cell.symbol} price={cell.price || cell.value || 0} change={cell.change} />
          ))}
        </div>
      </div>
    </div>
  );
}
