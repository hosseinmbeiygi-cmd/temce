"use client";

import { useEffect, useRef } from "react";

interface ChartProps {
  data: { time: string; open: number; high: number; low: number; close: number }[];
  height?: number;
  symbol?: string;
}

function generateMockOhlcv(count: number): { time: string; open: number; high: number; low: number; close: number }[] {
  const data: { time: string; open: number; high: number; low: number; close: number }[] = [];
  let price = 35000;
  const now = new Date();
  for (let i = count; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    if (d.getDay() === 5 || d.getDay() === 6) continue;
    const change = price * (Math.random() - 0.48) * 0.02;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.01);
    const low = Math.min(open, close) * (1 - Math.random() * 0.01);
    data.push({ time: d.toISOString().split("T")[0], open, high, low, close });
    price = close;
  }
  return data;
}

export default function Chart({ data, height = 400, symbol = "" }: ChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const chartData = data.length > 0 ? data : generateMockOhlcv(60);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, height);

    const w = rect.width;
    const h = height;
    const pad = { top: 20, bottom: 20, left: 50, right: 10 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    const prices = chartData.flatMap((d) => [d.high, d.low]);
    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    const range = maxP - minP || 1;

    const toX = (i: number) => pad.left + (i / (chartData.length - 1)) * plotW;
    const toY = (v: number) => pad.top + (1 - (v - minP) / range) * plotH;

    // Grid
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 0.5;
    for (let i = 0; i < 5; i++) {
      const y = pad.top + (i / 4) * plotH;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
    }

    // Draw candlesticks
    const candleW = Math.max(1, plotW / chartData.length * 0.6);

    chartData.forEach((d, i) => {
      const x = toX(i);
      const isUp = d.close >= d.open;
      ctx.fillStyle = isUp ? "#10b981" : "#ef4444";
      ctx.strokeStyle = isUp ? "#10b981" : "#ef4444";
      ctx.lineWidth = 1;

      // Wick
      ctx.beginPath();
      ctx.moveTo(x, toY(d.high));
      ctx.lineTo(x, toY(d.low));
      ctx.stroke();

      // Body
      const bodyTop = toY(Math.max(d.open, d.close));
      const bodyBottom = toY(Math.min(d.open, d.close));
      const bodyH = Math.max(1, bodyBottom - bodyTop);
      ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);
    });

    // Price labels (Y axis)
    ctx.fillStyle = "#6b7280";
    ctx.font = "10px Vazirmatn, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i < 5; i++) {
      const v = minP + (1 - i / 4) * range;
      const y = pad.top + (i / 4) * plotH;
      ctx.fillText(v.toLocaleString("fa"), pad.left - 5, y + 3);
    }

    // Date labels (X axis)
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(chartData.length / 6));
    for (let i = 0; i < chartData.length; i += step) {
      const d = chartData[i].time;
      if (d) {
        const dateStr = d.length === 10 ? d.substring(5) : d;
        ctx.fillText(dateStr, toX(i), h - 5);
      }
    }

  }, [chartData, height]);

  return (
    <div className="glass-card p-3">
      {symbol && <p className="text-sm text-gray-400 mb-2 px-1">{symbol}</p>}
      <canvas ref={canvasRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
}
