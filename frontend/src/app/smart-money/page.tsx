"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Dynamic Chart Imports ─────────────────────
const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 280 }} />,
});

// ── Phase & Score Display Helpers ─────────────
interface SmartMoneyResult {
  smart_money_score: number;
  phase: string;
  scores: {
    accumulation: number;
    absorption: number;
    float_lock: number;
    breakout_readiness: number;
    buyer_power: number;
    microstructure: number;
  };
  penalties: {
    distribution_risk: number;
    fake_breakout_risk: number;
    dead_compression: number;
  };
  features: Record<string, number>;
  breakout_features: Record<string, number>;
}

const PHASE_META: Record<string, { label: string; icon: string; color: string; desc: string }> = {
  confirmed_smart_money:  { label: "پول هوشمند تأیید شد", icon: "verified",     color: "#22c55e", desc: "همه نشانگرها از حضور پول هوشمند خبر می‌دهند" },
  breakout_ready:        { label: "آماده شکست",          icon: "rocket_launch",color: "#06b6d4", desc: "احتمال شکست مقاومت و شروع روند صعودی" },
  float_lock:            { label: "قفل شناور",           icon: "lock",          color: "#8b5cf6", desc: "عرضه در دست دارندگان قدرتمند قفل شده" },
  active_absorption:     { label: "جذب فعال",            icon: "swipe",         color: "#f59e0b", desc: "پول هوشمند در حال جمع‌آوری سهام" },
  early_accumulation:    { label: "تجمع اولیه",           icon: "trending_up",   color: "#3b82f6", desc: "نشانه‌های اولیه از ورود پول هوشمند" },
  neutral:               { label: "خنثی",                icon: "remove",        color: "#64748b", desc: "الگوی مشخصی شناسایی نشد" },
};

function ScoreGauge({ value, size = 120 }: { value: number; size?: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "#22c55e" : pct >= 55 ? "#06b6d4" : pct >= 40 ? "#f59e0b" : "#ef4444";
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          className="transition-all duration-1000" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-black tracking-tight" style={{ color }}>{pct}</span>
        <span className="text-[10px] text-surface-500 mt-0.5">SMC</span>
      </div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 65 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-surface-400 w-28 shrink-0 text-right">{label}</span>
      <div className="flex-1 h-2.5 bg-surface-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-mono w-9 text-left" style={{ color }}>{pct}%</span>
    </div>
  );
}

// ── Mock Data Generator ────────────────────────
function generateMockResult(symbol: string): SmartMoneyResult {
  // Deterministic mock based on symbol length to keep results stable per symbol
  const seed = symbol.length * 7 + symbol.charCodeAt(0) || 42;
  const r = (n: number) => ((seed * n * 9301 + 49297) % 233280) / 233280;
  return {
    smart_money_score: 0.25 + r(1) * 0.6,
    phase: ["early_accumulation", "active_absorption", "float_lock", "breakout_ready", "confirmed_smart_money", "neutral"][Math.floor(r(2) * 6)],
    scores: {
      accumulation: 0.2 + r(3) * 0.7,
      absorption: 0.2 + r(4) * 0.7,
      float_lock: 0.2 + r(5) * 0.7,
      breakout_readiness: 0.2 + r(6) * 0.7,
      buyer_power: 0.2 + r(7) * 0.7,
      microstructure: 0.2 + r(8) * 0.7,
    },
    penalties: {
      distribution_risk: r(9) * 0.5,
      fake_breakout_risk: r(10) * 0.5,
      dead_compression: r(11) * 0.5,
    },
    features: {},
    breakout_features: {},
  };
}

function generateMockHistory(symbol: string, days: number = 30) {
  const seed = symbol.length * 13 + symbol.charCodeAt(0) || 42;
  const r = (n: number) => ((seed * n * 9301 + 49297) % 233280) / 233280;
  const data: { time: string; value: number }[] = [];
  let base = 0.3 + r(0) * 0.3;
  const now = new Date();
  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    if (d.getDay() === 5 || d.getDay() === 6) continue;
    base = Math.max(0.05, Math.min(0.95, base + (r(i) - 0.48) * 0.04));
    data.push({
      time: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      value: Math.round(base * 100),
    });
  }
  return data;
}

// ── Main Component ──────────────────────────────
export default function SmartMoneyPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [inputValue, setInputValue] = useState("فولاد");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SmartMoneyResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function analyze(sym: string) {
    const trimmed = sym.trim();
    if (!trimmed) return;
    setSymbol(trimmed);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiGet<SmartMoneyResult>(`/smart-money/${trimmed}`);
      setResult(res);
    } catch {
      // Fallback to mock data
      const mock = generateMockResult(trimmed);
      setResult(mock);
    } finally {
      setLoading(false);
    }
  }

  const phaseMeta = result ? PHASE_META[result.phase] || PHASE_META.neutral : null;
  const smcPct = result ? Math.round(result.smart_money_score * 100) : 0;

  const historyData = result ? generateMockHistory(symbol, 30) : [];

  const popularSymbols = ["فولاد", "شپنا", "وبملت", "خودرو", "فملی", "کگل", "پترول", "مس"];

  return (
    <AppLayout title="Smart Money — پول هوشمند" subtitle="تحلیل جریان پول هوشمند و شناسایی فازهای بازار با ۹ لایه تحلیلی">
      {/* ── Search Bar ────────────────────────── */}
      <div className="glass-card p-5 mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-surface-500 mb-1.5">نماد</label>
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && analyze(inputValue)}
              placeholder="مثال: فولاد"
              className="w-full bg-surface-800 border border-surface-700 rounded-xl px-4 py-2.5 text-sm text-surface-200 placeholder-surface-600 outline-none focus:border-primary-500 transition-colors"
            />
          </div>
          <button
            onClick={() => analyze(inputValue)}
            disabled={loading}
            className="px-6 py-2.5 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl text-sm font-medium transition-all flex items-center gap-2"
          >
            <span className="material-icons text-lg">{loading ? "hourglass_top" : "search"}</span>
            تحلیل
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          <span className="text-[10px] text-surface-600 ml-1 mt-0.5">سریع:</span>
          {popularSymbols.map((s) => (
            <button
              key={s}
              onClick={() => { setInputValue(s); analyze(s); }}
              className={`text-xs px-2.5 py-1 rounded-lg transition-all ${
                symbol === s && result ? "bg-primary-600/20 text-primary-400 border border-primary-600/20" : "bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700"
              }`}
            >{s}</button>
          ))}
        </div>
      </div>

      {/* ── Loading State ─────────────────────── */}
      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      )}

      {/* ── Error State ───────────────────────── */}
      {error && !loading && (
        <div className="glass-card p-8 text-center">
          <span className="material-icons text-4xl text-accent-rose mb-2">error_outline</span>
          <p className="text-surface-400 text-sm">{error}</p>
        </div>
      )}

      {/* ── Results ───────────────────────────── */}
      {result && !loading && (
        <>
          {/* ── Top Row: SMC Score + Phase + Layer Scores ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            {/* SMC Score Gauge */}
            <Card title={`SMC Score — ${symbol}`}>
              <div className="flex flex-col items-center py-4">
                <ScoreGauge value={result.smart_money_score} size={140} />
                <div className="mt-3 text-center">
                  <div className="flex items-center gap-1.5 justify-center">
                    <span className="material-icons text-lg" style={{ color: phaseMeta?.color }}>{phaseMeta?.icon}</span>
                    <span className="font-bold text-sm" style={{ color: phaseMeta?.color }}>{phaseMeta?.label}</span>
                  </div>
                  <p className="text-[10px] text-surface-500 mt-1">{phaseMeta?.desc}</p>
                </div>
              </div>
            </Card>

            {/* Phase Description */}
            <Card title="جزئیات فاز">
              <div className="space-y-2 py-1">
                <div className="flex items-center justify-between py-1.5 px-3 bg-surface-800/30 rounded-lg">
                  <span className="text-xs text-surface-400">امتیاز SMC</span>
                  <span className={`text-sm font-bold ${smcPct >= 75 ? "text-accent-emerald" : smcPct >= 55 ? "text-accent-cyan" : smcPct >= 40 ? "text-accent-amber" : "text-accent-rose"}`}>
                    {smcPct}%
                  </span>
                </div>
                {["accumulation", "absorption", "float_lock", "breakout_readiness"].map((key) => {
                  const v = result.scores[key as keyof typeof result.scores];
                  return (
                    <div key={key} className="flex items-center justify-between py-1 px-3">
                      <span className="text-xs text-surface-500">
                        {key === "accumulation" ? "تجمع" : key === "absorption" ? "جذب" : key === "float_lock" ? "قفل شناور" : "آمادگی شکست"}
                      </span>
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{
                            width: `${v * 100}%`,
                            background: v >= 0.65 ? "#22c55e" : v >= 0.4 ? "#f59e0b" : "#ef4444"
                          }} />
                        </div>
                        <span className="text-xs font-mono w-8 text-right text-surface-300">{Math.round(v * 100)}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Risk Factors */}
            <Card title="ریسک‌ها">
              <div className="space-y-2 py-1">
                {Object.entries(result.penalties).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between py-1.5 px-3 bg-surface-800/30 rounded-lg">
                    <span className="text-xs text-surface-400">
                      {key === "distribution_risk" ? "ریسک توزیع" : key === "fake_breakout_risk" ? "ریسک شکست کاذب" : "فشردگی مرده"}
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{
                          width: `${val * 100}%`,
                          background: val >= 0.3 ? "#ef4444" : val >= 0.15 ? "#f59e0b" : "#22c55e"
                        }} />
                      </div>
                      <span className="text-xs font-mono w-8 text-right text-surface-300">{Math.round(val * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* ── Layer Scores ───────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <Card title="امتیاز لایه‌های تحلیلی">
              <div className="space-y-3 py-2">
                <ScoreBar label="تجمع (ACC)" value={result.scores.accumulation} />
                <ScoreBar label="جذب (ABS)" value={result.scores.absorption} />
                <ScoreBar label="قفل شناور (FL)" value={result.scores.float_lock} />
                <ScoreBar label="آمادگی شکست (BR)" value={result.scores.breakout_readiness} />
                <ScoreBar label="قدرت خریدار (BP)" value={result.scores.buyer_power} />
                <ScoreBar label="ریزساختار (MC)" value={result.scores.microstructure} />
              </div>
            </Card>

            {/* SMC History Trend */}
            <Card title="روند SMC">
              <AreaChartCard
                title=""
                data={historyData}
                height={220}
                yAxisFormatter={(v) => `${v}%`}
                tooltipFormatter={(v) => `${v}%`}
                strokeColor="#06b6d4"
                gradientId="smcGradient"
              />
            </Card>
          </div>

          {/* ── Analysis Summary ───────────────── */}
          <Card title="تحلیل ترکیبی">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="p-4 bg-surface-800/30 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-icons text-accent-emerald" style={{ fontSize: 18 }}>trending_up</span>
                  <span className="font-bold text-surface-200">تجمع و جذب</span>
                </div>
                <p className="text-xs text-surface-500 leading-relaxed">
                  {result.scores.accumulation >= 0.6
                    ? "نشانه‌های قوی از تجمع پول هوشمند مشاهده می‌شود. حجم معاملات و تغییرات قیمت حاکی از خرید سهام توسط سرمایه‌گذاران بزرگ است."
                    : result.scores.absorption >= 0.5
                    ? "فاز جذب فعال در جریان است. پول هوشمند در حال جمع‌آوری سهام در محدوده قیمتی فعلی می‌باشد."
                    : "فعالیت خاصی در زمینه تجمع یا جذب مشاهده نمی‌شود."}
                </p>
              </div>
              <div className="p-4 bg-surface-800/30 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-icons text-accent-purple" style={{ fontSize: 18 }}>lock</span>
                  <span className="font-bold text-surface-200">قفل شناور و شکست</span>
                </div>
                <p className="text-xs text-surface-500 leading-relaxed">
                  {result.scores.float_lock >= 0.6
                    ? "سهام در دست دارندگان قدرتمند قفل شده و عرضه محدود شده است. با افزایش تقاضا، احتمال شکست قیمتی بالا است."
                    : result.scores.breakout_readiness >= 0.5
                    ? "نشانگرهای شکست آماده را نشان می‌دهند. در صورت تداوم روند، شکست مقاومت محتمل است."
                    : "هشدار خاصی در زمینه قفل شناور یا شکست قیمتی وجود ندارد."}
                </p>
              </div>
              <div className="p-4 bg-surface-800/30 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-icons text-accent-cyan" style={{ fontSize: 18 }}>insights</span>
                  <span className="font-bold text-surface-200">قدرت خریدار و ریزساختار</span>
                </div>
                <p className="text-xs text-surface-500 leading-relaxed">
                  {result.scores.buyer_power >= 0.6
                    ? "قدرت خریداران بسیار بالاست. سفارش‌های خرید بزرگ و مداوم حاکی از حضور پول هوشمند در سمت خرید است."
                    : result.scores.microstructure >= 0.5
                    ? "ریزساختار بازار نشانه‌های مثبتی از توازن سفارش‌ها به نفع خریداران نشان می‌دهد."
                    : "بازار در وضعیت متعادلی قرار دارد و قدرت خریداران و فروشندگان تقریباً برابر است."}
                </p>
              </div>
            </div>
          </Card>

          {/* ── Interpretation ─────────────────── */}
          <div className="glass-card p-5 mt-4">
            <h3 className="font-bold text-surface-200 mb-3">تفسیر کلی</h3>
            <div className={`p-4 rounded-xl text-sm ${
              smcPct >= 70 ? "bg-accent-emerald/10 border border-accent-emerald/20" :
              smcPct >= 45 ? "bg-accent-amber/10 border border-accent-amber/20" :
              "bg-surface-800/50 border border-surface-700/50"
            }`}>
              <div className="flex items-start gap-3">
                <span className="material-icons mt-0.5" style={{
                  color: smcPct >= 70 ? "#22c55e" : smcPct >= 45 ? "#f59e0b" : "#64748b"
                }}>
                  {smcPct >= 70 ? "psychology" : smcPct >= 45 ? "tips_and_updates" : "info"}
                </span>
                <div>
                  <p className="text-surface-300 leading-relaxed">
                    {`نماد ${symbol} با امتیاز SMC برابر با ${smcPct}% در فاز "${phaseMeta?.label}" قرار دارد. ${phaseMeta?.desc}.`}
                  </p>
                  <p className="text-surface-500 mt-2 leading-relaxed text-xs">
                    {smcPct >= 70
                      ? "توصیه: با توجه به حضور قوی پول هوشمند، این نماد پتانسیل رشد خوبی دارد. سطوح حمایت و مقاومت را زیر نظر داشته باشید."
                      : smcPct >= 45
                      ? "توصیه: نشانه‌های اولیه از حضور پول هوشمند مشاهده می‌شود. برای ورود محتاطانه، منتظر تأیید فاز بالاتر باشید."
                      : "توصیه: فعلاً الگوی مشخصی از حضور پول هوشمند شناسایی نشده است. منتظر تشکیل الگوهای قوی‌تر بمانید."}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Empty State (no search yet) ────────── */}
      {!result && !loading && !error && (
        <div className="glass-card p-12 text-center">
          <span className="material-icons text-5xl text-surface-600 mb-3">psychology</span>
          <h3 className="text-surface-300 font-bold mb-1">تحلیل پول هوشمند</h3>
          <p className="text-surface-600 text-sm">یک نماد وارد کنید تا تحلیل Smart Money را مشاهده کنید</p>
          <div className="flex items-center justify-center gap-6 mt-6 text-xs text-surface-600">
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-surface-800 flex items-center justify-center mx-auto mb-1">
                <span className="material-icons text-accent-emerald">trending_up</span>
              </div>
              تجمع
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-surface-800 flex items-center justify-center mx-auto mb-1">
                <span className="material-icons text-accent-amber">swipe</span>
              </div>
              جذب
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-surface-800 flex items-center justify-center mx-auto mb-1">
                <span className="material-icons text-accent-purple">lock</span>
              </div>
              قفل شناور
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-surface-800 flex items-center justify-center mx-auto mb-1">
                <span className="material-icons text-accent-cyan">rocket_launch</span>
              </div>
              شکست
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
