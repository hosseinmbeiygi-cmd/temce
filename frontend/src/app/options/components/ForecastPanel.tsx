"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { fmt } from "./helpers";

// ── Backend contract: GET /forecast?symbol=&horizon=&last_close=&xau_usd=&usd_irr= ──

interface ForecastPoint {
  date: string;
  p50: number;
  p_lower: number;
  p_upper: number;
  direction_probability_up: number;
}

interface ForecastResponse {
  symbol: string;
  horizon_days: number;
  data_as_of: string;
  model: { name: string; version: string; trained_at: string; note: string };
  forecast: ForecastPoint[];
  quality: { status: string; is_stale: boolean; last_data_age_minutes: number };
  risk: { level: string; volatility: string; drift_detected: boolean };
  meta: { fair_value_irr: number | null; premium_log: number | null; disclaimer: string; note?: string } | null;
}

const FORECAST_SYMBOLS: { id: string; label: string; anchor: number }[] = [
  { id: "gold_18k", label: "طلای ۱۸ عیار", anchor: 81_200_000 },
  { id: "usd_irr_free", label: "دلار آزاد", anchor: 1_050_000 },
  { id: "xau_usd", label: "انس طلا ($)", anchor: 3_400 },
  { id: "xag_usd", label: "انس نقره ($)", anchor: 42 },
];

const HORIZONS = [1, 3, 7, 14, 30, 90];

const symbolLabel = (id: string) => FORECAST_SYMBOLS.find((s) => s.id === id)?.label ?? id;

// ── Forecast Band Chart ───────────────────────────────────────────────────────

function ForecastChart({ points, anchor }: { points: ForecastPoint[]; anchor: number }) {
  if (!points?.length) return null;
  const width = 640;
  const height = 260;
  const pad = 44;
  const all = [anchor, ...points.map((p) => p.p_lower), ...points.map((p) => p.p_upper)];
  const mn = Math.min(...all);
  const mx = Math.max(...all);
  const r = mx - mn || 1;
  const n = points.length;
  const x = (i: number) => pad + (i / Math.max(n - 1, 1)) * (width - pad * 2);
  const y = (v: number) => pad + ((mx - v) / r) * (height - pad * 2);

  const band = [
    ...points.map((p, i) => `${x(i)},${y(p.p_upper)}`),
    ...points.map((p, i) => `${x(n - 1 - i)},${y(p.p_lower)}`).reverse(),
  ].join(" ");
  const line = points.map((p, i) => `${x(i)},${y(p.p50)}`).join(" ");
  const anchorLevel = y(anchor);
  const step = Math.max(1, Math.floor(n / 6));

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="bg-surface-900 rounded-lg" style={{ direction: "ltr" }}>
      <line x1={pad} y1={anchorLevel} x2={width - pad} y2={anchorLevel} stroke="#f59e0b" strokeWidth={1.2} strokeDasharray="6,3" />
      <text x={pad - 4} y={anchorLevel + 3} textAnchor="end" fill="#f59e0b" fontSize={9} fontFamily="monospace">
        {Math.round(anchor / 1000)}K
      </text>
      <polygon points={band} fill="rgba(59,130,246,0.12)" stroke="rgba(59,130,246,0.35)" strokeWidth={1} />
      <polyline points={line} fill="none" stroke="#3b82f6" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p, i) =>
        i % step === 0 ? (
          <text key={i} x={x(i)} y={height - 8} textAnchor="middle" fill="#64748b" fontSize={9}>
            {i + 1}
          </text>
        ) : null,
      )}
      <text x={pad - 4} y={pad - 8} textAnchor="end" fill="#64748b" fontSize={9} fontFamily="monospace">
        {Math.round(mx / 1000)}K
      </text>
      <text x={pad - 4} y={height - pad + 12} textAnchor="end" fill="#64748b" fontSize={9} fontFamily="monospace">
        {Math.round(mn / 1000)}K
      </text>
    </svg>
  );
}

// ── Strategy Bridge ───────────────────────────────────────────────────────────

function strategyBridge(direction: string, probUp: number, premiumLog: number | null) {
  const bubbleNote = premiumLog !== null && premiumLog > 0.03 ? " — حباب مثبت: احتیاط در خرید پرمیوم" : "";
  if (direction === "up" && probUp >= 0.55)
    return { text: "خرید Call / Bull Call Spread / فروش Put (Cash-Secured)", color: "text-accent-emerald", detail: "احتمال رشد بالا" + bubbleNote };
  if (direction === "down" && probUp <= 0.45)
    return { text: "خرید Put / Bear Put Spread / فروش Call پوشش‌دار", color: "text-accent-rose", detail: "احتمال افت بالا" + bubbleNote };
  if (direction === "neutral")
    return { text: "Iron Condor / Short Straddle / Butterfly — فروش نوسان", color: "text-accent-amber", detail: "بازار خنثی" + bubbleNote };
  return { text: "Covered Call یا Protective Put — پوشش ریسک دوطرفه", color: "text-surface-300", detail: "جهت‌گیری ضعیف" };
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function ForecastPanel() {
  const [symbol, setSymbol] = useState("gold_18k");
  const [horizon, setHorizon] = useState(30);
  const [lastCloseInput, setLastCloseInput] = useState(String(FORECAST_SYMBOLS[0].anchor));
  const [lastClose, setLastClose] = useState(FORECAST_SYMBOLS[0].anchor);
  const [xauUsd, setXauUsd] = useState("");
  const [usdIrr, setUsdIrr] = useState("");

  const commitAnchor = (v: string) => {
    setLastCloseInput(v);
    const n = Number(v.replace(/[^\d.]/g, ""));
    if (n > 0) setLastClose(n);
  };

  const pickSymbol = (id: string) => {
    setSymbol(id);
    const preset = FORECAST_SYMBOLS.find((s) => s.id === id);
    if (preset) {
      setLastCloseInput(String(preset.anchor));
      setLastClose(preset.anchor);
      setXauUsd(preset.id === "gold_18k" ? String(FORECAST_SYMBOLS[2].anchor) : "");
      setUsdIrr(preset.id === "gold_18k" ? String(FORECAST_SYMBOLS[1].anchor) : "");
    }
  };

  const xauNum = Number(xauUsd) || 0;
  const usdNum = Number(usdIrr) || 0;

  const qs = new URLSearchParams({ symbol, horizon: String(horizon), last_close: String(lastClose) });
  if (xauNum > 0) qs.set("xau_usd", String(xauNum));
  if (usdNum > 0) qs.set("usd_irr", String(usdNum));

  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["options-forecast", symbol, horizon, lastClose, xauNum, usdNum],
    queryFn: () => apiGet<{ success: boolean; data?: ForecastResponse; error?: { message?: string } }>(`/forecast?${qs.toString()}`),
    staleTime: 60_000,
    retry: 1,
  });

  const fc = data?.success ? data.data : undefined;
  const apiError = data && !data.success ? data.error?.message ?? "پیش‌بینی در دسترس نیست" : null;
  const last = fc?.forecast?.[fc.forecast.length - 1];
  const expectedChange = last ? ((last.p50 - lastClose) / lastClose) * 100 : 0;
  const direction = expectedChange > 0.5 ? "up" : expectedChange < -0.5 ? "down" : "neutral";
  const probUp = last?.direction_probability_up ?? 0.5;
  const bridge = strategyBridge(direction, probUp, fc?.meta?.premium_log ?? null);
  const qualityOk = fc?.quality?.status === "good";

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card title="پیش‌بینی قیمت دارایی پایه" subtitle="پیش‌بینی آماری از تاریخچه واقعی دیتابیس (دریفت + نوسان) — بازه اطمینان ۸۰٪ و احتمال رشد">
        <div className="space-y-4">
          <div>
            <p className="text-[10px] text-surface-500 mb-1.5">دارایی‌های پشتیبانی‌شده</p>
            <div className="flex flex-wrap gap-2">
              {FORECAST_SYMBOLS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => pickSymbol(s.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${symbol === s.id ? "bg-primary-600 text-white border-primary-500" : "bg-surface-800 text-surface-300 border-surface-700/30 hover:bg-surface-700"}`}
                >
                  {s.label}
                  <span className="block text-[9px] font-mono opacity-60" dir="ltr">{s.id}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="text-[10px] text-surface-500">قیمت پایه (anchor)</label>
              <input
                type="number"
                value={lastCloseInput}
                onChange={(e) => setLastCloseInput(e.target.value)}
                onBlur={(e) => commitAnchor(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && commitAnchor(lastCloseInput)}
                className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1 font-mono"
                dir="ltr"
              />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">انس طلا ($) — اختیاری</label>
              <input type="number" value={xauUsd} onChange={(e) => setXauUsd(e.target.value)} placeholder="برای Fair Value" className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1 font-mono" dir="ltr" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">دلار آزاد — اختیاری</label>
              <input type="number" value={usdIrr} onChange={(e) => setUsdIrr(e.target.value)} placeholder="برای Fair Value" className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1 font-mono" dir="ltr" />
            </div>
            <div className="col-span-2">
              <label className="text-[10px] text-surface-500">افق پیش‌بینی (روز)</label>
              <div className="flex gap-1 mt-1">
                {HORIZONS.map((h) => (
                  <button key={h} onClick={() => setHorizon(h)} className={`flex-1 py-2 rounded-lg text-[10px] font-bold border transition-all ${horizon === h ? "bg-primary-600 text-white border-primary-500" : "bg-surface-800 text-surface-400 border-surface-700/30 hover:bg-surface-700"}`}>
                    {h}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button onClick={() => refetch()} disabled={isFetching} className="w-full bg-primary-600 hover:bg-primary-500 text-white font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            {isFetching ? "در حال دریافت پیش‌بینی..." : "دریافت پیش‌بینی"}
          </button>
        </div>
      </Card>

      {(error || apiError) && (
        <Card className="border-accent-rose/20">
          <p className="text-xs text-accent-rose">{apiError ?? `خطا در دریافت پیش‌بینی: ${(error as Error).message}`}</p>
        </Card>
      )}

      {isFetching && !fc && <Skeleton className="h-72 w-full rounded-2xl" />}

      {fc && last && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <Card className="text-center">
              <p className="text-[10px] text-surface-500 mb-1">قیمت پایه</p>
              <p className="text-sm font-bold text-surface-200 font-mono" dir="ltr">{fmt(lastClose)}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500 mb-1">پیش‌بینی ({fc.horizon_days} روز)</p>
              <p className="text-sm font-bold text-accent-cyan font-mono" dir="ltr">{fmt(last.p50)}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500 mb-1">تغییر انتظاری</p>
              <p className={`text-sm font-bold font-mono ${expectedChange > 0 ? "text-accent-emerald" : expectedChange < 0 ? "text-accent-rose" : "text-surface-300"}`} dir="ltr">
                {expectedChange > 0 ? "+" : ""}{expectedChange.toFixed(2)}%
              </p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500 mb-1">احتمال رشد</p>
              <p className="text-sm font-bold text-surface-200" dir="ltr">{(probUp * 100).toFixed(0)}%</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500 mb-1">کیفیت داده</p>
              <p className={`text-sm font-bold ${qualityOk ? "text-accent-emerald" : "text-accent-amber"}`}>
                {qualityOk ? "مطلوب" : fc.quality.status === "stale_anchor" ? "تاریخچه کهنه" : fc.quality.status}
              </p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500 mb-1">ریسک</p>
              <p className="text-sm font-bold text-surface-200">{fc.risk.level} / {fc.risk.volatility}</p>
            </Card>
          </div>

          {/* Chart */}
          <Card title={`نمودار پیش‌بینی — ${symbolLabel(fc.symbol)}`} subtitle={`بازه ۸۰٪ اطمینان (p_lower ↔ p_upper) حول p50 • خط‌چین نارنجی: قیمت پایه`}>
            <ForecastChart points={fc.forecast} anchor={lastClose} />
            <div className="flex flex-wrap gap-3 mt-3 text-[10px] text-surface-500">
              <span>آخرین به‌روزرسانی داده: <span className="text-surface-300">{new Date(fc.data_as_of).toLocaleString("fa-IR")}</span></span>
              <span>مدل: <span className="text-surface-300 font-mono" dir="ltr">{fc.model.name} @ {fc.model.version}</span></span>
              {fc.meta?.fair_value_irr != null && (
                <span>ارزش منصفانه: <span className="text-accent-amber font-mono" dir="ltr">{fmt(fc.meta.fair_value_irr)}</span></span>
              )}
              {fc.meta?.premium_log != null && (
                <span>پریمیوم/حباب لگاریتمی: <span className={`font-mono ${fc.meta.premium_log > 0 ? "text-accent-rose" : "text-accent-emerald"}`} dir="ltr">{fc.meta.premium_log.toFixed(4)}</span></span>
              )}
            </div>
          </Card>

          {/* Strategy bridge */}
          <Card title="اتصال پیش‌بینی به استراتژی اختیار" subtitle="پل بین خروجی مدل و انتخاب استراتژی" className="border-primary-600/20">
            <div className={`rounded-xl p-3 border ${direction === "up" ? "bg-accent-emerald/10 border-accent-emerald/20" : direction === "down" ? "bg-accent-rose/10 border-accent-rose/20" : "bg-surface-800/50 border-surface-700/50"}`}>
              <p className={`text-xs font-bold ${bridge.color}`}>{bridge.text}</p>
              <p className="text-[10px] text-surface-500 mt-1">{bridge.detail}</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-[10px]">
              <div className="bg-surface-800/40 rounded-lg p-2.5 text-center">
                <p className="text-surface-500">بازه پایین (۸۰٪)</p>
                <p className="text-surface-200 font-mono" dir="ltr">{fmt(last.p_lower)}</p>
              </div>
              <div className="bg-surface-800/40 rounded-lg p-2.5 text-center">
                <p className="text-surface-500">بازه بالا (۸۰٪)</p>
                <p className="text-surface-200 font-mono" dir="ltr">{fmt(last.p_upper)}</p>
              </div>
              <div className="bg-surface-800/40 rounded-lg p-2.5 text-center">
                <p className="text-surface-500">قیمت اعمال پیشنهادی (Call)</p>
                <p className="text-accent-emerald font-mono" dir="ltr">{fmt(Math.round((last.p50 + last.p_upper) / 2))}</p>
              </div>
              <div className="bg-surface-800/40 rounded-lg p-2.5 text-center">
                <p className="text-surface-500">قیمت اعمال پیشنهادی (Put)</p>
                <p className="text-accent-rose font-mono" dir="ltr">{fmt(Math.round((last.p50 + last.p_lower) / 2))}</p>
              </div>
            </div>
            {fc.meta?.note && <p className="text-[10px] text-surface-500 mt-3 leading-relaxed">{fc.meta.note}</p>}
            <p className="text-[10px] text-surface-600 mt-3 leading-relaxed">
              {fc.meta?.disclaimer ?? "برای تصمیم مالی از این خروجی به‌تنهایی استفاده نکنید."} برای ورود، تب‌های «تحلیل پیشرفته» (یونان‌ها) و «ابزار حرفه‌ای» (IV Rank و سایزینگ) را بررسی کنید.
            </p>
          </Card>
        </>
      )}

      {!isFetching && !fc && !error && (
        <div className="flex min-h-[20vh] flex-col items-center justify-center gap-2 text-surface-600">
          <p className="text-sm">داده پیش‌بینی در دسترس نیست</p>
          <p className="text-xs">یک دارایی پایه انتخاب کنید و دکمه دریافت پیش‌بینی را بزنید</p>
        </div>
      )}
    </div>
  );
}
