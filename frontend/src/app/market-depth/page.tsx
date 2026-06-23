"use client";

import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import { generateMockOrderBook } from "@/lib/types";

const ORDER_BOOK = generateMockOrderBook();

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

  return (
    <AppLayout>
      <div className="dashboard-grid">
        {/* ── Order Book ───────────────────────── */}
        <Card title="دفتر سفارشات - فولاد">
          <div className="order-book">
            {/* Bids */}
            <div className="order-side">
              <div className="order-header">
                <div className="order-title">تقاضا</div>
                <div className="order-title">حجم</div>
              </div>
              <div className="order-rows">
                {ORDER_BOOK.bids.map((bid, i) => (
                  <div key={i} className="order-row bid-row" style={{ "--width": `${(bid.volume / ORDER_BOOK.bids[0].volume) * 100}%` } as React.CSSProperties}>
                    <span className="order-price bid-price">{bid.price.toLocaleString()}</span>
                    <span className="order-volume">{bid.volume.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Asks */}
            <div className="order-side">
              <div className="order-header">
                <div className="order-title">عرضه</div>
                <div className="order-title">حجم</div>
              </div>
              <div className="order-rows">
                {ORDER_BOOK.asks.map((ask, i) => (
                  <div key={i} className="order-row ask-row" style={{ "--width": `${(ask.volume / ORDER_BOOK.asks[ORDER_BOOK.asks.length - 1].volume) * 100}%` } as React.CSSProperties}>
                    <span className="order-price ask-price">{ask.price.toLocaleString()}</span>
                    <span className="order-volume">{ask.volume.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* ── Depth Chart ──────────────────────── */}
        <Card
          title="عمق بازار - فولاد"
          actions={
            <>
              <CardAction active={depthView === "count"} onClick={() => setDepthView("count")}>تعداد</CardAction>
              <CardAction active={depthView === "volume"} onClick={() => setDepthView("volume")}>حجم</CardAction>
              <CardAction active={depthView === "value"} onClick={() => setDepthView("value")}>ارزش</CardAction>
            </>
          }
        >
          <div className="depth-chart">
            <svg width="100%" height="100%" viewBox="0 0 400 300" preserveAspectRatio="none">
              {/* Grid */}
              {[50,100,150,200,250].map((y) => (
                <line key={y} x1="0" y1={y} x2="400" y2={y} stroke="rgba(128,128,128,0.08)" strokeWidth="1" />
              ))}
              {/* Center price line */}
              <line x1="200" y1="0" x2="200" y2="300" stroke="rgba(128,128,128,0.2)" strokeWidth="1" strokeDasharray="5,5" />
              {/* Bid area */}
              <path d="M200,250 L180,240 L160,220 L140,190 L120,150 L100,100 L80,60 L60,40 L40,30 L20,25 L0,20 L0,300 L200,300 Z"
                fill="rgba(8,145,178,0.15)" stroke="var(--positive)" strokeWidth="2" />
              {/* Ask area */}
              <path d="M200,250 L220,245 L240,235 L260,220 L280,200 L300,175 L320,150 L340,120 L360,90 L380,60 L400,40 L400,300 L200,300 Z"
                fill="rgba(219,39,119,0.15)" stroke="var(--negative)" strokeWidth="2" />
              {/* Labels */}
              <text x="200" y="290" fill="var(--text-primary)" fontSize="12" fontFamily="Inter" textAnchor="middle">۱۲,۴۵۰</text>
              <text x="100" y="290" fill="var(--text-secondary)" fontSize="10" fontFamily="Inter" textAnchor="middle">۱۲,۴۰۰</text>
              <text x="300" y="290" fill="var(--text-secondary)" fontSize="10" fontFamily="Inter" textAnchor="middle">۱۲,۵۰۰</text>
              <text x="10" y="30" fill="var(--text-secondary)" fontSize="10" fontFamily="Inter">۱۰۰K</text>
              <text x="10" y="150" fill="var(--text-secondary)" fontSize="10" fontFamily="Inter">۵۰K</text>
              <text x="10" y="250" fill="var(--text-secondary)" fontSize="10" fontFamily="Inter">۰</text>
              {/* Legend */}
              <rect x="250" y="10" width="12" height="12" fill="var(--positive)" />
              <text x="270" y="20" fill="var(--text-primary)" fontSize="11" fontFamily="Vazirmatn">تقاضا</text>
              <rect x="320" y="10" width="12" height="12" fill="var(--negative)" />
              <text x="340" y="20" fill="var(--text-primary)" fontSize="11" fontFamily="Vazirmatn">عرضه</text>
            </svg>
          </div>
        </Card>

        {/* ── High Volume Symbols ─────────────── */}
        <Card
          title="نمادهای پرحجم"
          actions={
            <>
              <CardAction active>تقاضا</CardAction>
              <CardAction>عرضه</CardAction>
            </>
          }
        >
          <div style={{ overflow: "hidden", height: "100%" }}>
            <table className="symbols-table">
              <thead>
                <tr>
                  <th>نماد</th>
                  <th>قیمت</th>
                  <th>حجم تقاضا</th>
                  <th>حجم عرضه</th>
                  <th>نسبت</th>
                </tr>
              </thead>
              <tbody>
                {HIGH_VOLUME_SYMBOLS.map((row) => (
                  <tr key={row.symbol}>
                    <td className="symbol">{row.symbol}</td>
                    <td className="value">{row.price}</td>
                    <td className="value">{row.bidVol}</td>
                    <td className="value">{row.askVol}</td>
                    <td className={`value ${row.positive ? "positive" : "negative"}`}>{row.ratio.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}
