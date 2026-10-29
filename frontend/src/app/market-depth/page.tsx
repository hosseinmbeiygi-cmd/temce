"use client";

import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import type { OrderBookEntry } from "@/lib/types";
import SSRSafe from "@/components/SSRSafe";

const SYMBOL = "فولاد";

interface OrderBook {
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  lastPrice: number;
}

export default function MarketDepthPage() {
  // Audit FE-11: this page used to fall back to a generated order book (and a
  // hard-coded "top volume" table), so an API outage rendered fictional depth
  // as live. It now shows loading / error / empty explicitly and nothing else.
  const { data: orderBook, isLoading, isError } = useQuery<OrderBook>({
    queryKey: ["orderbook", SYMBOL],
    queryFn: async () => {
      const res = await apiGet<{
        success: boolean;
        data: { bids: OrderBookEntry[]; asks: OrderBookEntry[] };
      }>(`/orderbooks/${encodeURIComponent(SYMBOL)}`);
      return {
        bids: res?.data?.bids ?? [],
        asks: res?.data?.asks ?? [],
        lastPrice: res?.data?.asks?.[0]?.price ?? 0,
      };
    },
    staleTime: 15_000,
  });

  const bids = orderBook?.bids ?? [];
  const asks = orderBook?.asks ?? [];
  const spread = (asks[0]?.price ?? 0) - (bids[0]?.price ?? 0);
  const hasLevels = bids.length > 0 || asks.length > 0;

  return (
    <AppLayout>
      <div className="dashboard-grid">
        <Card title={"دفتر سفارشات - " + SYMBOL}>
          {isLoading ? (
            <Skeleton className="h-[420px] w-full rounded-2xl" />
          ) : isError ? (
            <div role="alert" className="text-center py-16 text-surface-500">
              <p className="text-lg">دریافت دفتر سفارشات ناموفق بود</p>
              <p className="text-sm mt-1">تا رسیدن پاسخ معتبر، عمق بازار نمایش داده نمی‌شود.</p>
            </div>
          ) : !hasLevels ? (
            <div className="text-center py-16 text-surface-500">
              <p className="text-lg">عمقی برای این نماد ثبت نشده است</p>
            </div>
          ) : (
            <SSRSafe className="order-book">
              <div className="order-side">
                <div className="order-header">
                  <div className="order-title">تقاضا</div>
                  <div className="order-title">حجم</div>
                </div>
                <div className="order-rows">
                  {bids.map((bid, i) => (
                    <div
                      key={i}
                      className="order-row bid-row"
                      style={{ "--width": `${(bid.volume / (bids[0]?.volume || 1)) * 100}%` } as React.CSSProperties}
                    >
                      <span className="order-price bid-price">{bid.price.toLocaleString("en-US")}</span>
                      <span className="order-volume">{bid.volume.toLocaleString("en-US")}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="order-spread">
                <span>اسپرد: {spread}</span>
              </div>
              <div className="order-side">
                <div className="order-header">
                  <div className="order-title">عرضه</div>
                  <div className="order-title">حجم</div>
                </div>
                <div className="order-rows">
                  {asks.map((ask, i) => (
                    <div
                      key={i}
                      className="order-row ask-row"
                      style={{ "--width": `${(ask.volume / (asks[0]?.volume || 1)) * 100}%` } as React.CSSProperties}
                    >
                      <span className="order-price ask-price">{ask.price.toLocaleString("en-US")}</span>
                      <span className="order-volume">{ask.volume.toLocaleString("en-US")}</span>
                    </div>
                  ))}
                </div>
              </div>
            </SSRSafe>
          )}
        </Card>
      </div>
    </AppLayout>
  );
}
