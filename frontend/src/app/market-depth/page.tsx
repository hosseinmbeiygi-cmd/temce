"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { generateMockOrderBook } from "@/lib/types";
import type { OrderBookEntry } from "@/lib/types";
import { useClientData } from "@/hooks/useClientData";
import SSRSafe from "@/components/SSRSafe";

const HIGH_VOLUME_SYMBOLS = [
  { symbol: "فولاد", price: "۱۲,۴۵۰", bidVol: "۸۵,۰۰۰", askVol: "۲۵,۰۰۰", ratio: 3.40, positive: true },
  { symbol: "پترول", price: "۲۳,۸۹۰", bidVol: "۷۲,۰۰۰", askVol: "۳۸,۰۰۰", ratio: 1.89, positive: true },
  { symbol: "خودرو", price: "۸,۷۶۰", bidVol: "۴۵,۰۰۰", askVol: "۸۲,۰۰۰", ratio: 0.55, positive: false },
  { symbol: "مس", price: "۲۵,۶۸۰", bidVol: "۶۳,۰۰۰", askVol: "۲۸,۰۰۰", ratio: 2.25, positive: true },
  { symbol: "کالا", price: "۱۸,۲۳۰", bidVol: "۵۸,۰۰۰", askVol: "۳۵,۰۰۰", ratio: 1.66, positive: true },
  { symbol: "وغدیر", price: "۱۵,۳۴۰", bidVol: "۴۹,۰۰۰", askVol: "۳۲,۰۰۰", ratio: 1.53, positive: true },
];

export default function MarketDepthPage() {
  const [depthView, setDepthView] = useState<"count" | "volume" | "value">("count");
  const symbol = "فولاد";
  const [mockOrderBook] = useClientData(() => generateMockOrderBook(), {
    bids: [] as OrderBookEntry[],
    asks: [] as OrderBookEntry[],
    lastPrice: 0,
  });

  const { data: orderBook } = useQuery({
    queryKey: ["orderbook", symbol],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { bids: OrderBookEntry[]; asks: OrderBookEntry[] } }>(`/orderbooks/${encodeURIComponent(symbol)}`);
        if (res?.data) {
          return { bids: res.data.bids || [], asks: res.data.asks || [], lastPrice: res.data.asks?.[0]?.price || 0 };
        }
      } catch {}
      return mockOrderBook;
    },
    staleTime: 15000,
  });

  const ob = orderBook || mockOrderBook;

  return (
    <AppLayout>
      <div className="dashboard-grid">
        <Card title={`دفتر سفارشات - ${symbol}`}>
          <SSRSafe className="order-book">
            <div className="order-side">
              <div className="order-header">
                <div className="order-title">تقاضا</div>
                <div className="order-title">حجم</div>
              </div>
              <div className="order-rows">
                {ob.bids.map((bid, i) => (
                  <div key={i} className="order-row bid-row" style={{ "--width": `${(bid.volume / ob.bids[0]?.volume || 1) * 100}%` } as React.CSSProperties}>
                    <span className="order-price bid-price">{bid.price.toLocaleString()}</span>
                    <span className="order-volume">{bid.volume.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="order-spread">
              <span>اسپرد: {ob.asks[0]?.price - ob.bids[0]?.price || 0}</span>
            </div>
            <div className="order-side">
              <div className="order-header">
                <div className="order-title">عرضه</div>
                <div className="order-title">حجم</div>
              </div>
              <div className="order-rows">
                {ob.asks.map((ask, i) => (
                  <div key={i} className="order-row ask-row" style={{ "--width": `${(ask.volume / ob.asks[0]?.volume || 1) * 100}%` } as React.CSSProperties}>
                    <span className="order-price ask-price">{ask.price.toLocaleString()}</span>
                    <span className="order-volume">{ask.volume.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </SSRSafe>
        </Card>

        <Card title="نمادهای پرحجم">
          <SSRSafe>
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="pb-2 px-1">نماد</th>
                  <th className="pb-2 px-1">قیمت</th>
                  <th className="pb-2 px-1">حجم تقاضا</th>
                  <th className="pb-2 px-1">حجم عرضه</th>
                  <th className="pb-2 px-1">نسبت</th>
                </tr>
              </thead>
              <tbody>
                {HIGH_VOLUME_SYMBOLS.map((s, i) => (
                  <tr key={`${s.symbol}-${i}`} className="border-b border-surface-800/50 text-xs">
                    <td className="py-2 px-1 font-medium text-surface-200">{s.symbol}</td>
                    <td className="py-2 px-1 font-mono text-surface-200">{s.price}</td>
                    <td className="py-2 px-1 font-mono text-accent-emerald">{s.bidVol}</td>
                    <td className="py-2 px-1 font-mono text-accent-rose">{s.askVol}</td>
                    <td className="py-2 px-1 font-mono" style={{ color: s.positive ? "var(--positive)" : "var(--negative)" }}>{s.ratio.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SSRSafe>
        </Card>
      </div>
    </AppLayout>
  );
}
