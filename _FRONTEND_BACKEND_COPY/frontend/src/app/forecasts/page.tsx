"use client";
import * as React from "react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Brain,
} from "lucide-react";

interface ForecastPoint {
  date: string;
  predicted: number;
  lower80: number;
  upper80: number;
  lower95: number;
  upper95: number;
}

interface ForecastModel {
  name: string;
  type: string;
  accuracy: number;
  horizon: string;
  points: ForecastPoint[];
}

interface CommodityForecast {
  symbol: string;
  name: string;
  category: string;
  currentPrice: number;
  unit: string;
  direction: string;
  expectedChangePercent: number;
  models: ForecastModel[];
  generatedAt: string;
}

function genPts(base, drift, n80, n95) {
  const pts = [];
  for (let i = 0; i < 30; i++) {
    const t = i / 30;
    const trend = base * (1 + drift * t);
    const predicted = Math.round(trend + Math.sin(i * 0.5) * base * 0.005);
    const lo80 = Math.round(predicted * (1 - n80 * (0.5 + t * 0.5)));
    const hi80 = Math.round(predicted * (1 + n80 * (0.5 + t * 0.5)));
    const lo95 = Math.round(predicted * (1 - n95 * (0.5 + t * 0.5)));
    const hi95 = Math.round(predicted * (1 + n95 * (0.5 + t * 0.5)));
    pts.push({ date: "روز " + (i + 1), predicted, lower80: lo80, upper80: hi80, lower95: lo95, upper95: hi95 });
  }
  return pts;
}

const MOCK = [
  { symbol: "ZRS1", name: "زعفران نگین", category: "کشاورزی", currentPrice: 185000000, unit: "ریال", direction: "up", expectedChangePercent: 2.27, generatedAt: "۱۴۰۵/۰۶/۱۱ ۰۸:۰۰", models: [
      { name: "SARIMA", type: "sarima", accuracy: 0.84, horizon: "۳۰ روز", points: genPts(185000000, 0.02, 0.03, 0.06) },
      { name: "XGBoost", type: "xgboost", accuracy: 0.79, horizon: "۳۰ روز", points: genPts(185000000, 0.025, 0.035, 0.07) },
      { name: "Ensemble", type: "ensemble", accuracy: 0.87, horizon: "۳۰ روز", points: genPts(185000000, 0.022, 0.028, 0.055) },
    ] },
  { symbol: "SB", name: "شمش فولاد", category: "فلزات", currentPrice: 22800000, unit: "ریال", direction: "up", expectedChangePercent: 2.98, generatedAt: "۱۴۰۵/۰۶/۱۱ ۰۸:۰۰", models: [
      { name: "SARIMA", type: "sarima", accuracy: 0.81, horizon: "۳۰ روز", points: genPts(22800000, 0.03, 0.04, 0.08) },
      { name: "LightGBM", type: "lightgbm", accuracy: 0.76, horizon: "۳۰ روز", points: genPts(22800000, 0.028, 0.038, 0.075) },
      { name: "Ensemble", type: "ensemble", accuracy: 0.83, horizon: "۳۰ روز", points: genPts(22800000, 0.026, 0.033, 0.065) },
    ] },
  { symbol: "CU", name: "کاتد مس", category: "فلزات", currentPrice: 95200000, unit: "ریال", direction: "up", expectedChangePercent: 1.94, generatedAt: "۱۴۰۵/۰۶/۱۱ ۰۸:۰۰", models: [
      { name: "SARIMA", type: "sarima", accuracy: 0.83, horizon: "۳۰ روز", points: genPts(95200000, 0.019, 0.03, 0.06) },
      { name: "XGBoost", type: "xgboost", accuracy: 0.78, horizon: "۳۰ روز", points: genPts(95200000, 0.02, 0.032, 0.065) },
      { name: "Ensemble", type: "ensemble", accuracy: 0.86, horizon: "۳۰ روز", points: genPts(95200000, 0.018, 0.025, 0.05) },
    ] },
  { symbol: "PCC", name: "پلی‌اتیلن سنگین", category: "پتروشیمی", currentPrice: 48500000, unit: "ریال", direction: "down", expectedChangePercent: -2.47, generatedAt: "۱۴۰۵/۰۶/۱۱ ۰۸:۰۰", models: [
      { name: "SARIMA", type: "sarima", accuracy: 0.8, horizon: "۳۰ روز", points: genPts(48500000, -0.025, 0.035, 0.07) },
      { name: "LightGBM", type: "lightgbm", accuracy: 0.75, horizon: "۳۰ روز", points: genPts(48500000, -0.022, 0.04, 0.075) },
      { name: "Ensemble", type: "ensemble", accuracy: 0.82, horizon: "۳۰ روز", points: genPts(48500000, -0.02, 0.03, 0.06) },
    ] },
  { symbol: "CEM", name: "سکنه", category: "معدنی", currentPrice: 2850000, unit: "ریال", direction: "up", expectedChangePercent: 3.33, generatedAt: "۱۴۰۵/۰۶/۱۱ ۰۸:۰۰", models: [
      { name: "SARIMA", type: "sarima", accuracy: 0.77, horizon: "۳۰ روز", points: genPts(2850000, 0.033, 0.045, 0.09) },
      { name: "Ensemble", type: "ensemble", accuracy: 0.8, horizon: "۳۰ روز", points: genPts(2850000, 0.03, 0.04, 0.08) },
    ] },
];

function fmtPrice(n) { return n.toLocaleString("fa-IR"); }

function MiniChart({ pts, dir }) {
  const mx = Math.max(...pts.map(p => p.upper95));
  const mn = Math.min(...pts.map(p => p.lower95));
  const r = mx - mn || 1;
  const c = dir === "up" ? "var(--accent-emerald)" : "var(--accent-rose)";
  const filtered = pts.filter((_, i) => i % 3 === 0);
  return React.createElement("div", { className: "flex h-16 items-end gap-[2px]", dir: "ltr" },
    ...filtered.map((p, i) => {
      const h = ((p.predicted - mn) / r) * 100;
      const lo = ((p.lower95 - mn) / r) * 100;
      const hi = ((p.upper95 - mn) / r) * 100;
      return React.createElement("div", { key: i, className: "relative flex-1", style: { height: "100%" } },
        React.createElement("div", { className: "absolute bottom-0 w-full rounded-sm opacity-20", style: { height: hi + "%", backgroundColor: c, bottom: lo + "%" } }),
        React.createElement("div", { className: "absolute bottom-0 w-full rounded-t-sm", style: { height: h + "%", backgroundColor: c, opacity: 0.8 } })
      );
    })
  );
}

export default function ForecastsPage() {
  const [sel, setSel] = useState(null);
  const [selM, setSelM] = useState(null);
  const { data: fc, isLoading } = useQuery({
    queryKey: ["forecasts"],
    queryFn: async () => {
      try { const r = await apiGet("/commodities/all/forecasts?horizon=30"); if (r?.data?.length) return r.data; } catch {}
      return MOCK;
    },
    staleTime: 60000,
  });
  const act = sel ? fc?.find(f => f.symbol === sel) : null;
  const actM = act && selM ? act.models.find(m => m.name === selM) : null;

  return React.createElement(AppLayout, { title: "پیش‌بینی‌ها", subtitle: "مدل‌های پیش‌بینی قیمت کالاها" },
    React.createElement("div", { className: "mb-5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-[11px] text-amber-300" },
      React.createElement("strong", null, "⚠️ هشدار:"),
      " پیش‌بینی‌ها صرفاً جهت آموزش و تحقیقات است."
    ),
    React.createElement("div", { className: "grid gap-4 sm:grid-cols-2 lg:grid-cols-3" },
      isLoading ? Array.from({ length: 5 }).map((_, i) => React.createElement(Skeleton, { key: i, className: "h-64 w-full" }))
      : fc?.map(f => React.createElement("div", {
        key: f.symbol, dir: "rtl",
        className: "glass-card cursor-pointer p-4 transition-all hover:ring-1 " + (sel === f.symbol ? "ring-2 ring-accent-cyan/50" : "hover:ring-accent-cyan/30"),
        onClick: () => { setSel(f.symbol === sel ? null : f.symbol); setSelM(null); }
      },
        React.createElement("div", { className: "mb-2 flex items-center justify-between" },
          React.createElement("div", null,
            React.createElement("span", { className: "font-mono text-[11px] font-bold text-surface-500" }, f.symbol),
            React.createElement("h3", { className: "text-sm font-bold text-surface-200" }, f.name)
          ),
          React.createElement("span", { className: "rounded-full bg-surface-800 px-2 py-0.5 text-[10px] text-surface-400" }, f.category)
        ),
        React.createElement("div", { className: "mb-2 flex items-center justify-between" },
          React.createElement("span", { className: "text-lg font-bold text-surface-100", dir: "ltr" }, fmtPrice(f.currentPrice)),
          React.createElement("span", { className: "flex items-center gap-1 text-xs font-bold " + (f.direction === "up" ? "text-accent-emerald" : "text-accent-rose") },
            f.direction === "up" ? React.createElement(TrendingUp, { className: "size-3" }) : React.createElement(TrendingDown, { className: "size-3" }),
            (f.direction === "up" ? "+" : "") + f.expectedChangePercent.toFixed(2) + "%"
          )
        ),
        MiniChart({ pts: f.models[f.models.length - 1].points, dir: f.direction }),
        React.createElement("div", { className: "mt-2 flex flex-wrap gap-1" },
          ...f.models.map(m => React.createElement("span", {
            key: m.name,
            className: "rounded-full px-2 py-0.5 text-[10px] font-bold " + ({
              sarima: "bg-blue-500/10 text-blue-400",
              garch: "bg-purple-500/10 text-purple-400",
              xgboost: "bg-emerald-500/10 text-emerald-400",
              lightgbm: "bg-amber-500/10 text-amber-400",
              ensemble: "bg-accent-cyan/10 text-accent-cyan",
            }[m.type] || "bg-surface-700 text-surface-400")
          }, m.name === "sarima" ? "SARIMA" : m.name === "garch" ? "GARCH" : m.name === "xgboost" ? "XGBoost" : m.name === "lightgbm" ? "LightGBM" : "Ensemble"))
        ),
        React.createElement("div", { className: "mt-2 border-t border-surface-800 pt-2 text-[9px] text-surface-600" },
          "بروزرسانی: " + f.generatedAt
        )
      ))
    ),
    act && !actM && React.createElement("div", { className: "mt-6 flex items-center justify-center rounded-lg bg-surface-800/50 px-4 py-6 text-xs text-surface-500" },
      React.createElement(Brain, { className: "ml-2 size-4" }), " روی یک مدل کلیک کنید."
    ),
    !isLoading && (!fc || fc.length === 0) && React.createElement("div", { className: "flex min-h-[30vh] flex-col items-center justify-center gap-2 text-surface-600" },
      React.createElement(BarChart3, { className: "size-12" }),
      React.createElement("p", { className: "text-sm" }, "پیش‌بینی‌هایی وجود ندارد")
    )
  );
}
