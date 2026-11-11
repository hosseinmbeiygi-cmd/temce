"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

// ------ Types ----------------------------------------------------------------
interface PhaseData {
  symbol: string;
  phase: string;
  smc: number;
  scores: {
    accumulation: number;
    absorption: number;
    float_lock: number;
    breakout_readiness: number;
  };
  timestamp: number;
}

interface PhaseTransition {
  symbol: string;
  from: string;
  to: string;
  timestamp: number;
}

// ------ Phase Metadata -------------------------------------------------------
const PHASE_META: Record<string, { label: string; color: string; icon: string }> = {
  confirmed_smart_money: { label: "پول هوشمند", color: "#22c55e", icon: "verified" },
  breakout_ready: { label: "آماده شکست", color: "#06b6d4", icon: "rocket_launch" },
  float_lock: { label: "قفل شناور", color: "#8b5cf6", icon: "lock" },
  active_absorption: { label: "جذب فعال", color: "#f59e0b", icon: "swipe" },
  early_accumulation: { label: "تجمع اولیه", color: "#3b82f6", icon: "trending_up" },
  neutral: { label: "خنثی", color: "#64748b", icon: "remove" },
};

const PHASE_ORDER = [
  "confirmed_smart_money",
  "breakout_ready",
  "float_lock",
  "active_absorption",
  "early_accumulation",
  "neutral",
];

// ------ Phase Distribution Chart ---------------------------------------------
function PhaseDistribution({ data }: { data: PhaseData[] }) {
  const counts = PHASE_ORDER.map((phase) => ({
    phase,
    count: data.filter((d) => d.phase === phase).length,
    meta: PHASE_META[phase],
  }));

  const total = data.length || 1;

  return (
    <Card title="توزیع فازها">
      <div className="space-y-3 py-2">
        {counts.map(({ phase, count, meta }) => (
          <div key={phase} className="flex items-center gap-3">
            <div className="flex items-center gap-2 w-32 shrink-0">
              <span className="material-icons text-sm" style={{ color: meta.color }}>{meta.icon}</span>
              <span className="text-xs text-surface-400">{meta.label}</span>
            </div>
            <div className="flex-1 h-3 bg-surface-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(count / total) * 100}%`,
                  background: meta.color,
                }}
              />
            </div>
            <span className="text-xs font-mono w-12 text-right" style={{ color: meta.color }}>
              {count}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ------ Phase Transition Timeline --------------------------------------------
function PhaseTimeline({ transitions }: { transitions: PhaseTransition[] }) {
  return (
    <Card title="تاریخچه تغییر فاز">
      <div className="space-y-2 py-2 max-h-[400px] overflow-y-auto">
        {transitions.length === 0 && (
          <p className="text-xs text-surface-600 text-center py-4">هنوز تغییر فازی ثبت نشده</p>
        )}
        {transitions.map((t, i) => {
          const fromMeta = PHASE_META[t.from] || PHASE_META.neutral;
          const toMeta = PHASE_META[t.to] || PHASE_META.neutral;
          const time = new Date(t.timestamp).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
          return (
            <div key={i} className="flex items-center gap-3 py-2 px-3 bg-surface-800/30 rounded-lg">
              <span className="text-xs font-mono text-surface-600 w-14">{time}</span>
              <span className="text-xs text-surface-500 w-16">{t.symbol}</span>
              <span className="material-icons text-sm" style={{ color: fromMeta.color }}>{fromMeta.icon}</span>
              <span className="text-xs" style={{ color: fromMeta.color }}>{fromMeta.label}</span>
              <span className="material-icons text-xs text-surface-600">arrow_left</span>
              <span className="material-icons text-sm" style={{ color: toMeta.color }}>{toMeta.icon}</span>
              <span className="text-xs font-bold" style={{ color: toMeta.color }}>{toMeta.label}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ------ Symbol Grid ----------------------------------------------------------
function SymbolGrid({ data, onSelect }: { data: PhaseData[]; onSelect: (s: string) => void }) {
  return (
    <Card title="وضعیت نمادها">
      {data.length === 0 && (
        <p className="py-6 text-center text-xs text-surface-500">وضعیت فازی برای هیچ نمادی از سرور دریافت نشد.</p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2 py-2">
        {data.map((d) => {
          const meta = PHASE_META[d.phase] || PHASE_META.neutral;
          const smcPct = Math.round(d.smc * 100);
          return (
            <button
              key={d.symbol}
              onClick={() => onSelect(d.symbol)}
              className="p-3 bg-surface-800/50 rounded-xl hover:bg-surface-700/50 transition-all text-right group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-surface-300">{d.symbol}</span>
                <span className="material-icons text-sm" style={{ color: meta.color }}>{meta.icon}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: meta.color }}>{meta.label}</span>
                <span className="text-xs font-mono" style={{ color: meta.color }}>{smcPct}%</span>
              </div>
              <div className="mt-2 h-1 bg-surface-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${smcPct}%`, background: meta.color }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

// ------ Main Component -------------------------------------------------------
export default function PhaseMonitorPage() {
  const [phaseData, setPhaseData] = useState<PhaseData[]>([]);
  const [transitions, setTransitions] = useState<PhaseTransition[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const prevDataRef = useRef<Map<string, string>>(new Map());

  const fetchData = useCallback(async () => {
    try {
      const res = await apiGet<{ success: boolean; data: PhaseData[] }>("/smart-money/monitor");
      if (!res?.data) throw new Error("empty payload");
      // Detect transitions
      const newTransitions: PhaseTransition[] = [];
      for (const item of res.data) {
        const prevPhase = prevDataRef.current.get(item.symbol);
        if (prevPhase && prevPhase !== item.phase) {
          newTransitions.push({
            symbol: item.symbol,
            from: prevPhase,
            to: item.phase,
            timestamp: Date.now(),
          });
        }
        prevDataRef.current.set(item.symbol, item.phase);
      }
      if (newTransitions.length > 0) {
        setTransitions((prev) => [...newTransitions, ...prev].slice(0, 50));
      }
      setPhaseData(res.data);
      setLastUpdate(new Date());
      setConnected(true);
      setError(null);
    } catch {
      // No sample rows: show the outage and keep the last real snapshot.
      setConnected(false);
      setError("دریافت وضعیت فاز نمادها ناموفق بود — ارتباط با سرور برقرار نشد.");
    }
  }, []);

  useEffect(() => {
    // Defer the first fetch so setState doesn't run synchronously during commit
    const timer = setTimeout(fetchData, 0);
    const interval = setInterval(fetchData, 30000); // Poll every 30s
    return () => { clearTimeout(timer); clearInterval(interval); };
  }, [fetchData]);

  const activeCount = phaseData.filter((d) => d.phase !== "neutral").length;
  const avgSmc = phaseData.length
    ? Math.round((phaseData.reduce((s, d) => s + d.smc, 0) / phaseData.length) * 100)
    : 0;

  return (
    <AppLayout
      title="مانیتورینگ فاز"
      subtitle="نمایش لحظه‌ای تغییرات فاز پول هوشمند نمادها"
    >
      {/* Status Bar */}
      <div className="flex items-center gap-4 mb-4 px-1">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-accent-emerald animate-pulse" : "bg-accent-rose"}`} />
          <span className="text-xs text-surface-500">{connected ? "متصل" : "آفلاین"}</span>
        </div>
        {lastUpdate && (
          <span className="text-[10px] text-surface-600">
            آخرین بروزرسانی موفق: {lastUpdate.toLocaleTimeString("fa-IR")}
          </span>
        )}
        <button
          onClick={fetchData}
          className="text-xs px-3 py-1 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-400 transition-colors"
        >
          <span className="material-icons text-sm align-middle">refresh</span>
        </button>
      </div>

      {error && (
        <div role="alert" aria-live="polite" className="mb-4 flex items-center gap-2 rounded-xl border border-accent-rose/30 bg-accent-rose/10 px-4 py-2.5 text-xs text-accent-rose">
          <span className="material-icons text-base">wifi_off</span>
          {error}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="glass-card p-4">
          <div className="text-[10px] text-surface-500 mb-1">تعداد نمادها</div>
          <div className="text-2xl font-black text-surface-200">{phaseData.length}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-[10px] text-surface-500 mb-1">نمادهای فعال</div>
          <div className="text-2xl font-black text-accent-emerald">{activeCount}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-[10px] text-surface-500 mb-1">میانگین SMC</div>
          <div className="text-2xl font-black text-accent-cyan">{avgSmc}%</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-[10px] text-surface-500 mb-1">تغییرات فاز</div>
          <div className="text-2xl font-black text-accent-amber">{transitions.length}</div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <SymbolGrid data={phaseData} onSelect={setSelectedSymbol} />
        </div>
        <PhaseDistribution data={phaseData} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Card title="روند میانگین SMC بازار">
          <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 px-6 text-center">
            <span className="material-icons text-3xl text-surface-600">show_chart</span>
            <p className="text-xs text-surface-500">
              سری تاریخی میانگین SMC از سرور در دسترس نیست؛ به‌جای نمایش نمودار ساختگی، این بخش خالی می‌ماند.
            </p>
          </div>
        </Card>
        <PhaseTimeline transitions={transitions} />
      </div>

      {/* Selected Symbol Detail */}
      {selectedSymbol && (
        <Card title={`جزئیات ${selectedSymbol}`}>
          {(() => {
            const d = phaseData.find((p) => p.symbol === selectedSymbol);
            if (!d) return <p className="text-xs text-surface-500">داده‌ای یافت نشد</p>;
            const meta = PHASE_META[d.phase] || PHASE_META.neutral;
            return (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 py-2">
                <div className="text-center">
                  <span className="material-icons text-3xl" style={{ color: meta.color }}>{meta.icon}</span>
                  <div className="text-sm font-bold mt-1" style={{ color: meta.color }}>{meta.label}</div>
                </div>
                {Object.entries(d.scores).map(([key, val]) => (
                  <div key={key} className="text-center">
                    <div className="text-lg font-black text-surface-200">{Math.round(val * 100)}%</div>
                    <div className="text-[10px] text-surface-500">
                      {key === "accumulation" ? "تجمع" : key === "absorption" ? "جذب" : key === "float_lock" ? "قفل شناور" : "شکست"}
                    </div>
                  </div>
                ))}
              </div>
            );
          })()}
        </Card>
      )}
    </AppLayout>
  );
}
