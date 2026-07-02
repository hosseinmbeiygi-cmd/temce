"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";
import { generateMockWatchlist } from "@/lib/types";
import type { WatchlistItem } from "@/lib/types";

// ------ Inline Price Range Bar for enriched watchlist ------------------------
function WatchlistPriceRange({ low, high, current }: { low?: number; high?: number; current?: number }) {
  if (low == null || high == null || high <= low || current == null) return null;
  const pct = Math.max(2, Math.min(98, ((current - low) / (high - low)) * 100));
  const distToFloor = ((current - low) / (high - low)) * 100;
  const distToCeiling = 100 - distToFloor;
  const [hovered, setHovered] = useState(false);
  return (
    <div dir="ltr" style={{ display: "flex", alignItems: "center", gap: 6, width: "100%", position: "relative" }}>
      <span style={{ fontSize: 10, color: "var(--text-secondary)", minWidth: 50, textAlign: "left" }}>{low.toLocaleString()}</span>
      <div style={{ flex: 1, height: 4, borderRadius: 2, background: "linear-gradient(to right, rgba(239,68,68,0.3), rgba(168,85,247,0.3), rgba(59,130,246,0.3))", position: "relative" }}>
        <div
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{ position: "absolute", top: "50%", transform: `translate(-50%, -50%) scale(${hovered ? 1.8 : 1})`, left: `${pct}%`, width: 7, height: 7, borderRadius: "50%", background: "var(--text-primary)", border: "2px solid var(--primary)", cursor: "crosshair", transition: "transform 0.2s, box-shadow 0.2s", boxShadow: hovered ? "0 0 12px rgba(99,102,241,0.6)" : "none" }}
        />
        {/* Tooltip */}
        {hovered && (
          <div style={{ position: "absolute", bottom: "calc(100% + 6px)", left: `${pct}%`, transform: "translateX(-50%)", zIndex: 100, pointerEvents: "none" }}>
            <div style={{ background: "var(--surface-900, #1e1b4b)", border: "1px solid var(--surface-700, #334155)", borderRadius: 10, padding: "8px 12px", boxShadow: "0 8px 24px rgba(0,0,0,0.4)", fontSize: 11, direction: "rtl", textAlign: "right", whiteSpace: "nowrap" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "var(--text-secondary, #94a3b8)" }}>فاصله از کف:</span>
                <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--positive, #22c55e)" }}>{distToFloor.toFixed(1)}%</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
                <span style={{ color: "var(--text-secondary, #94a3b8)" }}>فاصله از سقف:</span>
                <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--negative, #ef4444)" }}>{distToCeiling.toFixed(1)}%</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4, paddingTop: 6, borderTop: "1px solid var(--surface-700, #334155)" }}>
                <span style={{ color: "var(--text-secondary, #94a3b8)" }}>موقعیت:</span>
                <span style={{ fontFamily: "monospace", color: "var(--primary, #818cf8)" }}>{distToFloor.toFixed(1)}%</span>
              </div>
            </div>
            <div style={{ position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)", width: 0, height: 0, borderLeft: "6px solid transparent", borderRight: "6px solid transparent", borderTop: "6px solid var(--surface-700, #334155)" }} />
          </div>
        )}
      </div>
      <span style={{ fontSize: 10, color: "var(--text-secondary)", minWidth: 50, textAlign: "right" }}>{high.toLocaleString()}</span>
    </div>
  );
}

export default function WatchlistPage() {
  const [localItems, setLocalItems] = useState<WatchlistItem[]>(() => generateMockWatchlist());

  const { data: apiItems, isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: WatchlistItem[] }>("/watchlist");
        return extractArray<WatchlistItem>(res);
      } catch {
        return [];
      }
    },
    staleTime: 30000,
  });

  const items = apiItems && apiItems.length > 0 ? apiItems : localItems;

  const removeItem = (symbol: string) => {
    setLocalItems((prev) => prev.filter((item) => item.symbol !== symbol));
  };

  return (
    <AppLayout title="علاقه‌مندی‌ها" subtitle="نمادهای تحت نظر شما">
      <div className="dashboard-grid" style={{ gridTemplateColumns: "1fr", gridTemplateRows: "1fr" }}>
        <Card title="لیست پیگیری">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {[1,2,3,4].map(i => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
            </div>
          ) : items.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
              <span className="material-icons" style={{ fontSize: 48, marginBottom: 10 }}>star_border</span>
              <p>نمادی برای نمایش وجود ندارد</p>
              <p style={{ fontSize: 12 }}>از صفحه نمادها، نمادهای مورد نظر خود را به لیست پیگیری اضافه کنید.</p>
            </div>
          ) : (
            items.map((item, i) => (
              <div key={`${item.symbol}-${i}`} className="watchlist-item" style={{ padding: "10px 12px" }}>
                {/* Row 1: Symbol + Name + Price + Remove */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: item.priceLowestAllowed != null ? 6 : 0 }}>
                  <div style={{ minWidth: 60 }}>
                    <div className="watchlist-symbol" style={{ fontSize: 15 }}>{item.symbol}</div>
                    <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>{item.name || item.symbol}</div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div className="watchlist-price" style={{ textAlign: "left" }}>
                    <div className="watchlist-value" style={{ fontSize: 15 }}>{item.price?.toLocaleString() ?? '—'}</div>
                    <div className={`watchlist-change ${(item.change ?? 0) >= 0 ? "positive" : "negative"}`} style={{ fontSize: 11 }}>
                      {(item.change ?? 0) >= 0 ? "+" : ""}{(item.change ?? 0).toFixed(2)}%
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {item.state && (
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: item.state === "مجاز" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: item.state === "مجاز" ? "var(--positive)" : "var(--negative)" }}>{item.state}</span>
                    )}
                    {item.freeFloatPct != null && item.freeFloatPct > 0 && (
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "rgba(59,130,246,0.1)", color: "var(--text-secondary)" }}>شناور {item.freeFloatPct.toFixed(0)}%</span>
                    )}
                    {item.eps != null && item.eps !== 0 && (
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "rgba(245,158,11,0.1)", color: "var(--text-secondary)" }}>EPS {item.eps.toLocaleString()}</span>
                    )}
                    {item.peRatio != null && item.peRatio !== 0 && (
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "rgba(168,85,247,0.1)", color: "var(--text-secondary)" }}>P/E {item.peRatio.toFixed(1)}</span>
                    )}
                    {item.psRatio != null && item.psRatio !== 0 && (
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "rgba(236,72,153,0.1)", color: "var(--text-secondary)" }}>P/S {item.psRatio.toFixed(2)}</span>
                    )}
                    {item.groupPeRatio != null && item.groupPeRatio !== 0 && (
                      <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "rgba(99,102,241,0.1)", color: "var(--text-secondary)" }}>P/E گروه {item.groupPeRatio.toFixed(1)}</span>
                    )}
                  </div>
                  <button
                    onClick={() => removeItem(item.symbol)}
                    className="watchlist-btn"
                    title="حذف از لیست"
                    style={{ background: "rgba(219,39,119,0.1)", color: "var(--negative)", minWidth: 28, height: 28, borderRadius: "50%", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                  >
                    <span className="material-icons" style={{ fontSize: 14 }}>close</span>
                  </button>
                </div>
                {/* Row 2: Price Range Bar */}
                <WatchlistPriceRange
                  low={item.priceLowestAllowed}
                  high={item.priceHighestAllowed}
                  current={item.price}
                />
              </div>
            ))
          )}
        </Card>
      </div>
    </AppLayout>
  );
}
