"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 280 }} />,
});

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

// ------ Mock Data ------------------------------------------------------------
const MOCK_SYMBOLS = ["فولاد", "شپنا", "وبملت", "خودرو", "فملی", "کگل", "پترول", "مس", "شبندر", "خساپا"];

function generateMockPhaseData(): PhaseData[] {
  return MOCK_SYMBOLS.map((symbol, i) => ({
    symbol,
    phase: PHASE_ORDER[Math.floor((i * 7 + 3) % 6)],
    smc: 0.3 + (i * 0.07) % 0.6,
    scores: {
      accumulation: 0.2 + (i * 0.08) % 0.7,
      absorption: 0.2 + (i * 0.06) % 0.7,
      float_lock: 0.2 + (i * 0.05) % 0.7,
      breakout_readiness: 0.2 + (i * 0.09) % 0.7,
    },
    timestamp: Date.now(),
  }));
}

function generateMockHistory(days: number = 30) {
  const data: { date: string; time: string; value: number }[] = [];
  let base = 45;
  const now = new Date();
  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    if (d.getDay() === 5 || d.getDay() === 6) continue;
    base = Math.max(10, Math.min(90, base + (Math.random() - 0.48) * 8));
    data.push({
      date: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      time: d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" }),
      value: Math.round(base),
    });
  }
  return data;
}

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
  const prevDataRef = useRef<Map<string, string>>(new Map());

  const fetchData = useCallback(async () => {
    try {
      const res = await apiGet<{ success: boolean; data: PhaseData[] }>("/smart-money/monitor");
      if (res?.data) {
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
      }
    } catch {
      // Fallback to mock data
      const mock = generateMockPhaseData();
      setPhaseData(mock);
      setConnected(false);
      setLastUpdate(new Date());
    }
  }, []);

  useEffect(() => {
    // Defer the first fetch so setState doesn't run synchronously during commit
    const timer = setTimeout(fetchData, 0);
    const interval = setInterval(fetchData, 30000); // Poll every 30s
    return () => { clearTimeout(timer); clearInterval(interval); };
  }, [fetchData]);

  const historyData = generateMockHistory(30);
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
            آخرین بروزرسانی: {lastUpdate.toLocaleTimeString("fa-IR")}
          </span>
        )}
        <button
          onClick={fetchData}
          className="text-xs px-3 py-1 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-400 transition-colors"
        >
          <span className="material-icons text-sm align-middle">refresh</span>
        </button>
      </div>

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
          <AreaChartCard
            title=""
            data={historyData}
            height={260}
            yAxisFormatter={(v) => `${v}%`}
            tooltipFormatter={(v) => `${v}%`}
            strokeColor="#06b6d4"
            gradientId="monitorGradient"
            crosshair
            animate
            showAverage
            primaryLabel="میانگین SMC"
          />
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
