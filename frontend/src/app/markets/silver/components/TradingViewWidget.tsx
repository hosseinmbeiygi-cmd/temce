"use client";

import { useEffect, useRef } from "react";
import { Coins } from "lucide-react";
interface Props {
  symbol: { symbol?: string; price?: number; price_close?: number; price_last?: number; price_change?: number; price_change_pct?: number; change_percent?: number; unit?: string; date?: string; time_unix?: number } | null;
  className?: string;
}

const FALLBACK_SYMBOL = "FX_IDC:XAGUSD";

export default function TradingViewWidget({ symbol, className = "" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const ticker = (symbol?.symbol ?? "").toUpperCase().includes("XAG") ? "TVC:SILVER" : FALLBACK_SYMBOL;

  useEffect(() => {
    if (!containerRef.current) return;
    if ((window as unknown as Record<string, unknown>). TradingView) {
      return; // already injected
    }
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => {
      const tv = (window as unknown as Record<string, unknown>).TradingView;
      if (typeof tv !== "function") return;
      try {
        tv({
          autosize: true,
          symbol: ticker,
          interval: "D",
          timezone: "Tehran",
          theme: "dark",
          style: "1",
          locale: "fa",
          toolbar_bg: "#0b1220",
          enable_publishing: false,
          allow_symbol_change: false,
          volume: false,
          warning_color: "#f43f5e",
         up_color: "#10b981",
          down_color: "#f43f5e",
          border_up: "#10b981",
          border_down: "#f43f5e",
          grid_color: "#334155",
          volume_up_color: "#10b981",
          volume_down_color: "#f43f5e",
        });
      } catch {
        // fallback silent
      }
    };
    document.head.appendChild(script);
    return () => {
      // script injected once, not removed to keep widget stable
    };
  }, [ticker]);

  return (
    <div className={`relative rounded-2xl border border-line bg-soft p-3 ${className}`}>
      <div className="flex items-center justify-between text-xs text-ink-3">
        <div className="flex items-center gap-2">
          <Coins className="size-4 text-primary-500" />
          <span className="font-semibold text-ink">ویجت 실시간 تداول</span>
        </div>
        <span className="font-mono text-ink-2">{ticker}</span>
      </div>
      <div ref={containerRef} className="mt-2 aspect-[3/2] min-h-[280px] rounded-xl bg-primary-950/40" />
      <p className="mt-2 text-[10px] text-ink-3">
        اندیکاتورها و ابزارهای تکنیکال داخلی را می‌توانید روی ویجت aktif کنید.
      </p>
    </div>
  );
}
