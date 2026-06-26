"use client";

import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { generateMockWatchlist } from "@/lib/types";
import type { WatchlistItem } from "@/lib/types";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>(generateMockWatchlist);

  const removeItem = (symbol: string) => {
    setItems((prev) => prev.filter((item) => item.symbol !== symbol));
  };

  return (
    <AppLayout title="علاقه‌مندی‌ها" subtitle="نمادهای تحت نظر شما">
      <div className="dashboard-grid" style={{ gridTemplateColumns: "1fr", gridTemplateRows: "1fr" }}>
        <Card title="لیست پیگیری">
          <div className="watchlist">
            {items.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                <span className="material-icons" style={{ fontSize: 48, marginBottom: 10 }}>star_border</span>
                <p>نمادی برای نمایش وجود ندارد</p>
                <p style={{ fontSize: 12 }}>از صفحه نمادها، نمادهای مورد نظر خود را به لیست پیگیری اضافه کنید.</p>
              </div>
            ) : (
              items.map((item) => (
                <div key={item.symbol} className="watchlist-item">
                  <div className="watchlist-symbol">{item.symbol}</div>
                  <div className="watchlist-info">
                    <div className="watchlist-name">{item.name || item.symbol}</div>
                    <div className="watchlist-meta">{item.symbol}</div>
                  </div>
                  <div className="watchlist-price">
                    <div className="watchlist-value">{item.price?.toLocaleString() ?? '—'}</div>
                    <div className={`watchlist-change ${(item.change ?? 0) >= 0 ? "positive" : "negative"}`}>
                      {(item.change ?? 0) >= 0 ? "+" : ""}{(item.change ?? 0).toFixed(2)}%
                    </div>
                  </div>
                  <div className="watchlist-actions">
                    <button
                      onClick={() => removeItem(item.symbol)}
                      className="watchlist-btn"
                      title="حذف از لیست"
                      style={{ background: "rgba(219,39,119,0.1)", color: "var(--negative)" }}
                    >
                      <span className="material-icons" style={{ fontSize: 16 }}>close</span>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}