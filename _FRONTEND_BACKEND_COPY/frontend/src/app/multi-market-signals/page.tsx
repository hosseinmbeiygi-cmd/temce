"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import { apiGet, apiPost } from "@/lib/api";
import SSRSafe from "@/components/SSRSafe";
import { useNotificationSound } from "@/hooks/useNotificationSound";

const MarketBiasRadar = dynamic(
  () => import("./MarketBiasRadar"),
  { ssr: false, loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl h-[280px]" /> }
);

// ── Types ───────────────────────────────────────────────────────────────────

interface CronStatus {
  last_run: string | null;
  last_signal_count: number;
  last_accuracy: Record<string, number>;
  last_retrain_count: number;
  last_error: string | null;
  run_count: number;
  enabled: boolean;
  history: Array<{
    run: number;
    timestamp: string;
    signals: number;
    accuracy: number;
    retrain_count: number;
    success: boolean;
    error?: string;
    source?: string;
  }>;
  alerts?: {
    consecutive_failures: number;
    accuracy_drop: number;
    was_in_failure_streak: number;
    was_accuracy_below_50: number;
  };
  health?: {
    status: "healthy" | "in_crisis";
    failure_streak_active: boolean;
    accuracy_below_50_active: boolean;
    last_critical_alert_sent: number;
  };
}

interface EnrichedSignalDict {
  symbol: string;
  name: string;
  market: string;
  direction: string;
  timeframe: string;
  entry_zone: string;
  stop_loss: string;
  targets: string;
  risk_reward: string;
  position_sizing: string;
  confirmation_condition: string;
  reason: string;
  invalidation: string;
  trailing_stop: string;
  price: number;
  change_pct: number;
  rule_score: number;
  ml_score: number;
  boosted_score: number;
  ml_influence_pct: number;
  confidence: number;
  calibration_level: string;
  confidence_factors: Record<string, number>;
  confidence_notes: string[];
  vote_strategy: string;
  vote_direction_scores: Record<string, number>;
  source: string;
  created_at: string;
  decision_verdict?: string;
  decision_grade?: string;
  gate_results?: GateResult[];
}

interface GateResult {
  gate: string;
  verdict: "pass" | "warn" | "block";
  reason: string;
}

interface MarketBias {
  bias: string;
  buy_pct: number;
  sell_pct: number;
  total: number;
}

interface CrossMarketSignal {
  name: string;
  signal: string;
  description: string;
  strength: number;
  gold_pct?: number;
  stock_sell_pct?: number;
  stock_buy_pct?: number;
  biases?: Record<string, MarketBias>;
}

interface MultiMarketResponse {
  success: boolean;
  data?: {
    signals: EnrichedSignalDict[];
    summary: {
      total_signals: number;
      buy_count: number;
      sell_count: number;
      hold_count: number;
      avg_confidence: number;
      calibration_counts: Record<string, number>;
      markets: Record<string, { buy: number; sell: number; hold: number }>;
      filters: Record<string, unknown>;
    };
    reports: Array<{ market: string; success: boolean; signal_count: number; error?: string }>;
    accuracy: Record<string, number>;
    cross_market: CrossMarketSignal[];
    retrain: Array<{
      pipeline_run_id: string;
      market: string;
      trigger: string;
      models_retrained: string[];
      models_skipped: string[];
      new_accuracy_pct: number;
      old_accuracy_pct: number;
      samples_used: number;
      duration_seconds: number;
      errors: string[];
      timestamp: string;
    }>;
    generated_at: string;
  };
  error?: { message: string };
}

// ── Constants ───────────────────────────────────────────────────────────────

const MARKET_COLORS: Record<string, string> = {
  stock: "#64FFDA",
  gold: "#FFD700",
  currency: "#FF6B6B",
  crypto: "#A78BFA",
  option: "#38BDF8",
  commodity: "#FB923C",
  ime: "#94A3B8",
};

const MARKET_LABELS: Record<string, string> = {
  stock: "سهام",
  gold: "طلا",
  currency: "ارز",
  crypto: "رمزارز",
  option: "آپشن",
  commodity: "کالا",
  ime: "بورس کالا",
};

const MARKET_ICONS: Record<string, string> = {
  stock: "📈",
  gold: "🪙",
  currency: "💵",
  crypto: "₿",
  option: "🎯",
  commodity: "🛢️",
  ime: "🏭",
};

const CALIBRATION_COLORS: Record<string, string> = {
  very_high: "bg-accent-emerald/20 text-accent-emerald border-accent-emerald/30",
  high: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/20",
  medium: "bg-accent-amber/15 text-accent-amber border-accent-amber/20",
  low: "bg-accent-rose/15 text-accent-rose border-accent-rose/20",
};

const CALIBRATION_LABELS: Record<string, string> = {
  very_high: "بسیار بالا",
  high: "بالا",
  medium: "متوسط",
  low: "پایین",
};

const GRADE_COLORS: Record<string, string> = {
  "A+": "bg-accent-emerald/20 text-accent-emerald border-accent-emerald/30",
  "A": "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/20",
  "B": "bg-accent-amber/15 text-accent-amber border-accent-amber/20",
  WATCHLIST: "bg-surface-600/30 text-surface-400 border-surface-600/30",
  REJECT: "bg-accent-rose/10 text-surface-500 border-surface-600/20",
};

const GRADE_LABELS: Record<string, string> = {
  "A+": "A+",
  "A": "A",
  "B": "B",
  WATCHLIST: "—",
  REJECT: "✕",
};

const SIGNAL_COLORS: Record<string, string> = {
  DEFENSIVE: "border-accent-amber/30 bg-accent-amber/5",
  AGGRESSIVE: "border-accent-emerald/30 bg-accent-emerald/5",
  HEDGE: "border-primary-500/30 bg-primary-500/5",
  CAUTION: "border-accent-rose/30 bg-accent-rose/5",
  CASH: "border-red-500/30 bg-red-500/5",
  INFO: "border-surface-600/30 bg-surface-800/20",
};

const SIGNAL_ICONS: Record<string, string> = {
  DEFENSIVE: "🛡️",
  AGGRESSIVE: "🚀",
  HEDGE: "🏛️",
  CAUTION: "⚠️",
  CASH: "💵",
  INFO: "ℹ️",
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function fmtConf(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return n.toLocaleString("fa-IR");
  return n.toFixed(2);
}

function getDirectionBadge(direction: string): string {
  const map: Record<string, string> = {
    buy: "bg-accent-emerald/15 text-accent-emerald",
    sell: "bg-accent-rose/15 text-accent-rose",
    hold: "bg-surface-600/30 text-surface-400",
    wait: "bg-accent-amber/15 text-accent-amber",
  };
  return map[direction] || map.hold;
}

function getDirectionLabel(direction: string): string {
  const map: Record<string, string> = { buy: "خرید", sell: "فروش", hold: "خنثی", wait: "انتظار" };
  return map[direction] || direction;
}

// ── Sub-components ──────────────────────────────────────────────────────────

function ConfidenceGauge({ value, size = 80, strokeWidth = 8 }: { value: number; size?: number; strokeWidth?: number }) {
  const r = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - value);
  const color = value >= 0.6 ? "#10b981" : value >= 0.4 ? "#f59e0b" : "#f43f5e";

  return (
    <svg width={size} height={size} className="shrink-0" viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e293b" strokeWidth={strokeWidth} />
      <circle
        cx={cx} cy={cy} r={r} fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: "stroke-dashoffset 0.8s ease" }}
      />
      <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle"
        className="text-xs font-black" fill="#e2e8f0">
        {fmtConf(value)}
      </text>
    </svg>
  );
}

function MarketConfidenceCard({ market, accuracy, signalCount }: { market: string; accuracy: number; signalCount: number }) {
  const color = MARKET_COLORS[market] || "#94A3B8";
  const label = MARKET_LABELS[market] || market;
  const icon = MARKET_ICONS[market] || "📊";

  return (
    <div className="glass-card p-3 flex flex-col items-center gap-2 hover:bg-white/[0.02] transition-colors">
      <span className="text-2xl">{icon}</span>
      <span className="text-xs font-bold" style={{ color }}>{label}</span>
      <ConfidenceGauge value={accuracy / 100} size={64} strokeWidth={7} />
      <div className="text-[10px] text-surface-500">
        {signalCount} سیگنال
      </div>
    </div>
  );
}

import { MiniSparklineSignal as MiniSparkline } from "@/components/MiniSparklineSignal";

function HistoryChartModal({
  history,
  onClose,
}: {
  history: Array<{ run: number; timestamp: string; accuracy: number; signals: number; success: boolean }>;
  onClose: () => void;
}) {
  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const W = 700;
  const H = 280;
  const pad = { top: 20, right: 20, bottom: 40, left: 40 };
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;

  const accVals = history.map((e) => e.accuracy).filter((v) => typeof v === "number" && !isNaN(v));
  const sigVals = history.map((e) => e.signals).filter((v) => typeof v === "number");
  const accMin = Math.min(0, ...accVals);
  const accMax = Math.max(100, ...accVals);
  const accRange = accMax - accMin || 1;
  const sigMin = 0;
  const sigMax = Math.max(1, ...sigVals);
  const sigRange = sigMax - sigMin || 1;

  const x = (i: number) => pad.left + (i / Math.max(1, history.length - 1)) * pw;
  const yAcc = (v: number) => pad.top + ph - ((v - accMin) / accRange) * ph;
  const ySig = (v: number) => pad.top + ph - ((v - sigMin) / sigRange) * ph;

  // Annotate alert events
  let consFails = 0;
  let inStreak = false;
  let wasBelow50 = false;
  const annotations: Array<{ idx: number; type: string; label: string }> = [];
  history.forEach((e, i) => {
    if (!e.success) {
      consFails++;
      if (consFails === 3) { annotations.push({ idx: i, type: "fail", label: "⚠️ ۳ شکست متوالی" }); inStreak = true; }
    } else {
      if (inStreak) { annotations.push({ idx: i, type: "recover", label: "✅ بازیابی" }); inStreak = false; }
      consFails = 0;
    }
    const a = e.accuracy;
    if (typeof a === "number" && !isNaN(a)) {
      if (a < 50 && !wasBelow50) { annotations.push({ idx: i, type: "drop", label: "🔻 دقت زیر ۵۰٪" }); wasBelow50 = true; }
      else if (a >= 50 && wasBelow50) { annotations.push({ idx: i, type: "recover", label: "✅ بازگشت دقت" }); wasBelow50 = false; }
    }
  });

  const accLine = history
    .filter((e) => typeof e.accuracy === "number" && !isNaN(e.accuracy))
    .map((e, i) => `${x(history.indexOf(e))},${yAcc(e.accuracy)}`)
    .join(" ");

  const sigLine = history
    .filter((e) => typeof e.signals === "number")
    .map((e, i) => `${x(history.indexOf(e))},${ySig(e.signals)}`)
    .join(" ");

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <div
          className="glass-card p-5 border border-surface-700 rounded-2xl shadow-2xl max-w-[780px] w-full"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label="تاریخچه دقت و سیگنال‌ها"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-surface-200">📈 تاریخچه دقت و سیگنال‌ها</h3>
            <button onClick={onClose} className="text-surface-500 hover:text-surface-300 text-sm px-2 py-0.5 rounded hover:bg-surface-700/50 transition-colors">✕</button>
          </div>

          <div className="flex items-center gap-4 mb-3 text-[10px]">
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-accent-emerald rounded" /> دقت</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-cyan-400 rounded" /> سیگنال‌ها</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-accent-rose/40 rounded" /> آستانه ۵۰٪</span>
          </div>

          <SSRSafe style={{ overflowX: "auto" }}>
            <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="w-full max-w-full">
              {/* Grid lines */}
              {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                const gy = pad.top + ph * (1 - pct);
                const label = (accMin + pct * accRange).toFixed(0);
                return (
                  <g key={pct}>
                    <line x1={pad.left} y1={gy} x2={W - pad.right} y2={gy} stroke="#1e293b" strokeWidth="0.5" />
                    <text x={pad.left - 6} y={gy + 3} textAnchor="end" className="text-[9px]" fill="#64748b">{label}</text>
                  </g>
                );
              })}

              {/* 50% reference line */}
              {accMin <= 50 && accMax >= 50 && (
                <line x1={pad.left} y1={yAcc(50)} x2={W - pad.right} y2={yAcc(50)} stroke="#f43f5e" strokeWidth="1" strokeDasharray="4 3" strokeOpacity="0.4" />
              )}

              {/* Signal count area */}
              <polygon
                points={`${sigLine} ${W - pad.right},${pad.top + ph} ${pad.left},${pad.top + ph}`}
                fill="#38BDF8" fillOpacity="0.06"
              />
              <polyline points={sigLine} fill="none" stroke="#38BDF8" strokeWidth="1" strokeOpacity="0.6" />

              {/* Accuracy area + line */}
              <polygon
                points={`${accLine} ${W - pad.right},${pad.top + ph} ${pad.left},${pad.top + ph}`}
                fill="#10b981" fillOpacity="0.10"
              />
              <polyline points={accLine} fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

              {/* Data points */}
              {history
                .filter((e) => typeof e.accuracy === "number" && !isNaN(e.accuracy))
                .map((e, i) => {
                  const idx = history.indexOf(e);
                  return <circle key={i} cx={x(idx)} cy={yAcc(e.accuracy)} r="2.5" fill="#10b981" stroke="#0f172a" strokeWidth="1" />;
                })}

              {/* Annotation markers */}
              {annotations.map((ann, i) => {
                const ax = x(ann.idx);
                const isFail = ann.type === "fail" || ann.type === "drop";
                const color = isFail ? "#f43f5e" : "#10b981";
                return (
                  <g key={i}>
                    <line x1={ax} y1={pad.top} x2={ax} y2={pad.top + ph} stroke={color} strokeWidth="1" strokeOpacity="0.2" strokeDasharray="2 4" />
                    <circle cx={ax} cy={pad.top - 2} r="4" fill={color} fillOpacity="0.3" stroke={color} strokeWidth="1" />
                    <text x={ax} y={pad.top - 8} textAnchor="middle" className="text-[8px]" fill={color}>{ann.label}</text>
                  </g>
                );
              })}

              {/* X-axis timestamps */}
              {history.length <= 12
                ? history.map((e, i) => (
                    <text key={i} x={x(i)} y={H - 10} textAnchor="middle" className="text-[8px]" fill="#475569">
                      {new Date(e.timestamp).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
                    </text>
                  ))
                : history
                    .filter((_, i) => i % Math.ceil(history.length / 8) === 0 || i === history.length - 1)
                    .map((e, i) => (
                      <text key={i} x={x(history.indexOf(e))} y={H - 10} textAnchor="middle" className="text-[8px]" fill="#475569">
                        {new Date(e.timestamp).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
                      </text>
                    ))}
            </svg>
          </SSRSafe>
        </div>
      </div>
    </>
  );
}

function CrossMarketCard({ signal }: { signal: CrossMarketSignal }) {
  const borderClass = SIGNAL_COLORS[signal.signal] || SIGNAL_COLORS.INFO;
  const icon = SIGNAL_ICONS[signal.signal] || "ℹ️";

  return (
    <div className={`glass-card p-4 border ${borderClass} transition-all hover:bg-white/[0.02]`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{icon}</span>
        <span className="text-sm font-bold text-surface-200">{signal.name}</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-700/50 text-surface-400 ml-auto">
          {signal.signal}
        </span>
      </div>
      <p className="text-xs text-surface-400 leading-relaxed mb-3">{signal.description}</p>
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-surface-500">قدرت سیگنال:</span>
        <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
          <div className="h-full bg-primary-500 rounded-full transition-all duration-500"
            style={{ width: `${signal.strength * 100}%` }} />
        </div>
        <span className="text-[10px] font-mono text-surface-400">{fmtConf(signal.strength)}</span>
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function MultiMarketSignalsPage() {
  const [marketFilter, setMarketFilter] = useState("all");
  const [signalFilter, setSignalFilter] = useState("all");
  const [timeframeFilter, setTimeframeFilter] = useState("all");
  const [minConfidence, setMinConfidence] = useState(0.3);
  const [sortBy, setSortBy] = useState<"boosted_score" | "confidence" | "rule_score">("boosted_score");

  // ── Cron status ──
  const queryClient = useQueryClient();

  const { data: cronData } = useQuery({
    queryKey: ["orchestrator-cron-status"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: CronStatus }>("/api/v1/orchestrator-cron-status");
      return res?.data ?? null;
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const [runNowError, setRunNowError] = useState<string | null>(null);

  // ── Notification sounds (AudioContext + mute toggle + playChime) ──
  const { muted: audioMuted, toggleMute, playChime } = useNotificationSound({ storageKey: "cron-audio-muted" });

  // ── Recovery detection ──
  const prevAlertsRef = useRef<{ failureStreak: number; accuracyBelow50: number }>({
    failureStreak: 0,
    accuracyBelow50: 0,
  });
  const [recoveryMessage, setRecoveryMessage] = useState<string | null>(null);

  // ── Scan history for alert transition counts ──
  const alertCounts = useMemo(() => {
    if (!cronData?.history || cronData.history.length === 0) {
      return { critical: 0, recovery: 0 };
    }

    const sorted = [...cronData.history].sort((a, b) => a.run - b.run);
    let critical = 0;
    let recovery = 0;
    let consecutiveFailures = 0;
    let inFailureStreak = false;
    let wasBelow50 = false;

    for (let i = 0; i < sorted.length; i++) {
      const entry = sorted[i];

      if (!entry.success) {
        consecutiveFailures++;
        if (consecutiveFailures === 3) {
          critical++;
          inFailureStreak = true;
        }
      } else {
        if (inFailureStreak) {
          recovery++;
          inFailureStreak = false;
        }
        consecutiveFailures = 0;
      }

      const acc = entry.accuracy;
      if (typeof acc === "number") {
        if (acc < 50 && !wasBelow50) {
          critical++;
          wasBelow50 = true;
        } else if (acc >= 50 && wasBelow50) {
          recovery++;
          wasBelow50 = false;
        }
      }
    }

    return { critical, recovery };
  }, [cronData]);

  useEffect(() => {
    const alerts = cronData?.alerts;
    if (!alerts) return;

    const prev = prevAlertsRef.current;
    const msgs: string[] = [];
    let chimeType: "recovery" | "crisis" | null = null;

    // Detected crisis: failure streak or accuracy drop began
    if (prev.failureStreak === 0 && alerts.was_in_failure_streak > 0) {
      chimeType = "crisis";
    } else if (prev.accuracyBelow50 === 0 && alerts.was_accuracy_below_50 > 0) {
      chimeType = "crisis";
    }

    // Detected recovery from failure streak
    if (prev.failureStreak > 0 && alerts.was_in_failure_streak === 0) {
      msgs.push("سیستم از شکست‌های متوالی کرون بازیابی شد ✅");
      chimeType = "recovery";
    }

    // Detected recovery from accuracy drop
    if (prev.accuracyBelow50 > 0 && alerts.was_accuracy_below_50 === 0) {
      msgs.push("دقت سیگنال‌ها به بالای ۵۰٪ بازگشت ✅");
      chimeType = "recovery";
    }

    if (msgs.length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter change
      setRecoveryMessage(msgs.join(" | "));
    }

    // Play notification chime (crisis or recovery) only when user is in another tab
    if (chimeType) {
      const tones = chimeType === "crisis" ? [392, 311.13] : [523.25, 659.25]; // G4→E♭4 descending vs C5→E5 ascending
      playChime(tones, { skipWhenVisible: true });
    }

    prevAlertsRef.current = {
      failureStreak: alerts.was_in_failure_streak,
      accuracyBelow50: alerts.was_accuracy_below_50,
    };
  }, [cronData?.alerts]);



  const runNowMutation = useMutation({
    mutationFn: async () => {
      setRunNowError(null);
      await apiPost("/api/v1/orchestrator-cron/run-now");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orchestrator-cron-status"] });
    },
    onError: (err: Error) => {
      setRunNowError(err.message || "خطا در اجرای فوری");
    },
  });

  // ── History chart modal ──
  const [historyChartOpen, setHistoryChartOpen] = useState(false);

  // ── Export cron history ──
  const [exportOpen, setExportOpen] = useState(false);

  const exportHistory = useCallback((format: "json" | "csv") => {
    if (!cronData?.history || cronData.history.length === 0) return;

    const sorted = [...cronData.history].sort((a, b) => a.run - b.run);
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);

    if (format === "json") {
      const blob = new Blob([JSON.stringify(sorted, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cron-history-${ts}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      const headers = ["run", "timestamp", "success", "signals", "accuracy", "retrain_count", "error", "source"];
      const rows = sorted.map((e) =>
        headers.map((h) => {
          const v = e[h as keyof typeof e];
          if (v == null) return "";
          const s = String(v);
          return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
        }).join(",")
      );
      const csv = [headers.join(","), ...rows].join("\n");
      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cron-history-${ts}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }

    setExportOpen(false);
  }, [cronData]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["multi-market-signals", marketFilter, signalFilter, timeframeFilter, minConfidence, sortBy],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (marketFilter !== "all") params.set("market", marketFilter);
      if (signalFilter !== "all") params.set("signal", signalFilter);
      if (timeframeFilter !== "all") params.set("timeframe", timeframeFilter);
      params.set("min_confidence", String(minConfidence));
      params.set("sort_by", sortBy);
      params.set("use_ml", "true");
      params.set("use_confidence", "true");
      params.set("limit", "100");

      const res = await apiGet<MultiMarketResponse>(`/multi-market-signals?${params.toString()}`);
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const signals = data?.signals ?? [];
  const summary = data?.summary;
  const accuracy = data?.accuracy ?? {};
  const crossMarket = data?.cross_market ?? [];
  const reports = data?.reports ?? [];
  const retrainReports = data?.retrain ?? [];

  // ── Accuracy trend points for sparkline ──
  const accuracyPoints = useMemo(() => {
    if (!cronData?.history || cronData.history.length < 2) return [];
    const sorted = [...cronData.history].sort((a, b) => a.run - b.run);
    return sorted
      .filter((e) => typeof e.accuracy === "number" && !isNaN(e.accuracy))
      .map((e) => e.accuracy);
  }, [cronData]);

  // ── Signal count trend points for sparkline ──
  const signalCountPoints = useMemo(() => {
    if (!cronData?.history || cronData.history.length < 2) return [];
    const sorted = [...cronData.history].sort((a, b) => a.run - b.run);
    return sorted
      .filter((e) => typeof e.signals === "number")
      .map((e) => e.signals);
  }, [cronData]);

  // Separate cross-market signals from bias info
  const crossSignals = useMemo(() => crossMarket.filter((s) => s.name !== "Market-Biases"), [crossMarket]);
  const marketBiases = useMemo(() => crossMarket.find((s) => s.name === "Market-Biases")?.biases, [crossMarket]);

  return (
    <AppLayout title="سیگنال‌های چندبازاره" subtitle="سیگنال‌های خرید و فروش در تمام بازارها با اطمینان کالیبره‌شده">
      {/* ═══ Cron Status Bar ═══ */}
      {cronData && (
        <div className={`glass-card px-4 py-2 mb-4 flex items-center gap-4 flex-wrap text-xs border-l-2 ${
          cronData.health?.status === "in_crisis" ? "border-accent-amber/60" :
          cronData.enabled ? "border-accent-emerald/40" : "border-accent-rose/40"
        }`}>
          {/* Status dot + label + health badge */}
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full animate-pulse ${
              cronData.health?.status === "in_crisis" ? "bg-accent-amber" :
              cronData.enabled ? "bg-accent-emerald" : "bg-accent-rose"
            }`} />
            <span className={`font-bold ${
              cronData.health?.status === "in_crisis" ? "text-accent-amber" :
              cronData.enabled ? "text-accent-emerald" : "text-accent-rose"
            }`}>
              {cronData.enabled ? "Cron فعال" : "Cron غیرفعال"}
            </span>

            {/* Health badge: سالم / بحرانی */}
            {cronData.health && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold border ${
                cronData.health.status === "healthy"
                  ? "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30"
                  : "bg-accent-rose/15 text-accent-rose border-accent-rose/30"
              }`}>
                {cronData.health.status === "healthy" ? "سالم 🟢" : "بحرانی 🔴"}
              </span>
            )}
          </div>

          {/* ═══ Crisis indicator badges ═══ */}
          {cronData.alerts && (
            <>
              {cronData.alerts.was_in_failure_streak > 0 && (
                <>
                  <span className="text-surface-700">|</span>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full bg-accent-rose/15 text-accent-rose border border-accent-rose/30 font-bold animate-pulse"
                    title={`در بحران از: ${new Date(cronData.alerts.was_in_failure_streak * 1000).toLocaleTimeString("fa-IR")}`}
                  >
                    ⚠️ شکست متوالی کرون
                  </span>
                </>
              )}
              {cronData.alerts.was_accuracy_below_50 > 0 && (
                <>
                  <span className="text-surface-700">|</span>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber border border-accent-amber/30 font-bold"
                    title={`در بحران از: ${new Date(cronData.alerts.was_accuracy_below_50 * 1000).toLocaleTimeString("fa-IR")}`}
                  >
                    ⚠️ دقت زیر ۵۰٪
                  </span>
                </>
              )}
            </>
          )}

          {/* Alert counts */}
          {alertCounts.critical > 0 && (
            <>
              <span className="text-surface-700">|</span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-rose/15 text-accent-rose border border-accent-rose/30 font-bold"
                title="تعداد هشدارهای بحرانی ارسال شده (شکست متوالی یا کاهش دقت)"
              >
                🔴 {alertCounts.critical} هشدار
              </span>
            </>
          )}
          {alertCounts.recovery > 0 && (
            <>
              <span className="text-surface-700">|</span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30 font-bold"
                title="تعداد هشدارهای بازیابی ارسال شده (بازگشت به حالت سالم)"
              >
                🟢 {alertCounts.recovery} بازیابی
              </span>
            </>
          )}

          {/* Accuracy sparkline (clickable → opens history chart) */}
          {accuracyPoints.length >= 2 && (
            <>
              <span className="text-surface-700">|</span>
              <button
                onClick={() => setHistoryChartOpen(true)}
                className="cursor-pointer"
                title="کلیک کنید تا نمودار کامل تاریخچه را ببینید"
              >
                <MiniSparkline points={accuracyPoints} className="opacity-80 hover:opacity-100 transition-opacity" />
              </button>
            </>
          )}

          {/* Signal count sparkline */}
          {signalCountPoints.length >= 2 && (
            <>
              <span className="text-surface-700">|</span>
              <MiniSparkline
                points={signalCountPoints}
                color="#38BDF8"
                label="سیگنال‌ها"
                className="opacity-80 hover:opacity-100 transition-opacity"
              />
            </>
          )}

          <span className="text-surface-700">|</span>

          {/* Run count */}
          <div className="flex items-center gap-1">
            <span className="text-surface-500">اجراها:</span>
            <span className="text-surface-200 font-mono">{cronData.run_count}</span>
          </div>

          <span className="text-surface-700">|</span>

          {/* Last run */}
          {cronData.last_run ? (
            <div className="flex items-center gap-1">
              <span className="text-surface-500">آخرین اجرا:</span>
              <span className="text-surface-300 font-mono">
                {new Date(cronData.last_run).toLocaleTimeString("fa-IR")}
              </span>
            </div>
          ) : (
            <span className="text-surface-600">هنوز اجرا نشده</span>
          )}

          <span className="text-surface-700">|</span>

          {/* Last signal count */}
          <div className="flex items-center gap-1">
            <span className="text-surface-500">سیگنال‌ها:</span>
            <span className="text-surface-200 font-mono">{cronData.last_signal_count}</span>
          </div>

          {cronData.last_accuracy && Object.keys(cronData.last_accuracy).length > 0 && (
            <>
              <span className="text-surface-700">|</span>
              <div className="flex items-center gap-1">
                <span className="text-surface-500">دقت:</span>
                <span className="text-accent-cyan font-mono font-bold">
                  {cronData.last_accuracy.overall != null ? `${cronData.last_accuracy.overall.toFixed(0)}%` : "—"}
                </span>
              </div>
            </>
          )}

          {cronData.last_error && (
            <>
              <span className="text-surface-700">|</span>
              <span className="text-accent-rose truncate max-w-[200px]" title={cronData.last_error}>
                خطا: {cronData.last_error.slice(0, 60)}...
              </span>
            </>
          )}

          {/* Run Now error */}
          {runNowError && (
            <span className="text-[10px] text-accent-rose">{runNowError}</span>
          )}

          {/* Audio mute toggle */}
          <button
            onClick={toggleMute}
            className={`text-sm px-1.5 py-0.5 rounded transition-colors ${audioMuted ? "text-surface-600 hover:text-surface-400" : "text-accent-amber hover:text-accent-yellow"}`}
            title={audioMuted ? "صدای اعلان غیرفعال است — کلیک کنید تا فعال شود" : "صدای اعلان فعال است — کلیک کنید تا قطع شود"}
          >
            {audioMuted ? "🔕" : "🔔"}
          </button>

          {/* Export + Run Now (right-aligned group) */}
          <div className="mr-auto flex items-center gap-1.5">
            {cronData.history && cronData.history.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setExportOpen((v) => !v)}
                  className="text-[10px] px-2.5 py-1 rounded-lg bg-surface-700/50 text-surface-400 border border-surface-600/50 hover:bg-surface-700 hover:text-surface-300 transition-colors"
                  title="خروجی گرفتن از تاریخچه کرون"
                >
                  📥 خروجی
                </button>
                {exportOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setExportOpen(false)} />
                    <div className="absolute bottom-full mb-1 right-0 z-20 bg-surface-800 border border-surface-700 rounded-lg shadow-xl overflow-hidden">
                      <button
                        onClick={() => exportHistory("json")}
                        className="block w-full text-right px-3 py-1.5 text-[10px] text-surface-300 hover:bg-surface-700 hover:text-surface-100 transition-colors"
                      >
                        📄 JSON
                      </button>
                      <button
                        onClick={() => exportHistory("csv")}
                        className="block w-full text-right px-3 py-1.5 text-[10px] text-surface-300 hover:bg-surface-700 hover:text-surface-100 transition-colors border-t border-surface-700"
                      >
                        📊 CSV
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Run Now button */}
            <button
              onClick={() => runNowMutation.mutate()}
              disabled={runNowMutation.isPending}
              className="text-[10px] px-3 py-1 rounded-lg bg-primary-600/20 text-primary-300 border border-primary-600/30 hover:bg-primary-600/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {runNowMutation.isPending ? (
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 border border-primary-300 border-t-transparent rounded-full animate-spin" />
                  در حال اجرا...
                </span>
              ) : (
                "اجرای فوری"
              )}
            </button>
          </div>
        </div>
      )}

      {/* ═══ History Chart Modal ═══ */}
      {historyChartOpen && cronData?.history && (
        <HistoryChartModal
          history={cronData.history
            .filter((e) => typeof e.accuracy === "number" && !isNaN(e.accuracy) || typeof e.signals === "number")
            .sort((a, b) => a.run - b.run)}
          onClose={() => setHistoryChartOpen(false)}
        />
      )}

      {/* ═══ Recovery Banner ═══ */}
      {recoveryMessage && (
        <div className="glass-card p-3 mb-4 flex items-center gap-3 border border-accent-emerald/40 bg-accent-emerald/5">
          <span className="text-lg">🟢</span>
          <p className="text-sm text-accent-emerald font-medium flex-1">{recoveryMessage}</p>
          <button
            onClick={() => setRecoveryMessage(null)}
            className="text-surface-500 hover:text-surface-300 text-xs px-2 py-1 rounded hover:bg-surface-700/50 transition-colors"
          >
            ✕
          </button>
        </div>
      )}

      {/* ═══ Row 1: Filter Controls ═══ */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {/* Market Filter */}
        <select
          value={marketFilter}
          onChange={(e) => setMarketFilter(e.target.value)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="all">همه بازارها</option>
          {Object.entries(MARKET_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>

        {/* Signal Filter */}
        <select
          value={signalFilter}
          onChange={(e) => setSignalFilter(e.target.value)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="all">همه سیگنال‌ها</option>
          <option value="buy">خرید</option>
          <option value="sell">فروش</option>
          <option value="hold">خنثی</option>
        </select>

        {/* Timeframe Filter */}
        <select
          value={timeframeFilter}
          onChange={(e) => setTimeframeFilter(e.target.value)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="all">همه بازه‌ها</option>
          <option value="daily">روزانه</option>
          <option value="2day">۲ روزه</option>
          <option value="3day">۳ روزه</option>
          <option value="weekly">هفتگی</option>
          <option value="monthly">ماهانه</option>
        </select>

        {/* Confidence Slider */}
        <div className="flex items-center gap-2 bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5">
          <span className="text-[10px] text-surface-500">حداقل اطمینان:</span>
          <input
            type="range"
            min="0"
            max="0.8"
            step="0.05"
            value={minConfidence}
            onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
            className="w-20 accent-primary-500"
          />
          <span className="text-xs font-mono text-surface-300">{fmtConf(minConfidence)}</span>
        </div>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="boosted_score">امتیاز ترکیبی</option>
          <option value="confidence">اطمینان</option>
          <option value="rule_score">امتیاز تکنیکال</option>
        </select>

        {isLoading && (
          <span className="text-xs text-surface-500 animate-pulse">در حال بارگذاری...</span>
        )}
        {error && (
          <span className="text-xs text-accent-rose">خطا در دریافت داده</span>
        )}
        {data && (
          <span className="text-xs text-surface-500">
            {data.generated_at ? `آخرین به‌روزرسانی: ${new Date(data.generated_at).toLocaleTimeString("fa-IR")}` : ""}
          </span>
        )}
      </div>

      {/* Error Banner */}
      {error && !isLoading && (
        <div className="glass-card p-6 mb-4 text-center border border-accent-rose/30">
          <span className="material-icons text-3xl text-accent-rose mb-2 block">error_outline</span>
          <p className="text-sm text-accent-rose mb-1">خطا در دریافت سیگنال‌ها</p>
          <p className="text-xs text-surface-500">لطفاً اتصال به سرور را بررسی کنید و دوباره تلاش کنید.</p>
        </div>
      )}

      {/* ═══ Row 2: Summary Stats (with loading skeleton) ═══ */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-4 animate-pulse">
          {[1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div key={i} className="glass-card p-3 text-center">
              <div className="h-3 bg-surface-700/50 rounded w-16 mx-auto mb-2" />
              <div className="h-6 bg-surface-700/30 rounded w-12 mx-auto" />
            </div>
          ))}
        </div>
      )}
      {!isLoading && summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-4">
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">کل سیگنال‌ها</div>
            <div className="text-xl font-black text-surface-100">{summary.total_signals}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">خرید</div>
            <div className="text-xl font-black text-accent-emerald">{summary.buy_count}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">فروش</div>
            <div className="text-xl font-black text-accent-rose">{summary.sell_count}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">خنثی</div>
            <div className="text-xl font-black text-surface-400">{summary.hold_count}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">میانگین اطمینان</div>
            <div className="text-xl font-black text-primary-300">{fmtConf(summary.avg_confidence)}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">بازارها</div>
            <div className="text-xl font-black text-surface-200">{Object.keys(summary.markets ?? {}).length}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">دقت کل</div>
            <div className="text-xl font-black text-accent-cyan">{accuracy?.overall != null ? `${accuracy.overall.toFixed(0)}%` : "—"}</div>
          </div>
        </div>
      )}

      {/* ═══ Row 3: Accuracy Gauges per Market (with loading skeleton) ═══ */}
      {isLoading && (
        <div className="mb-4 animate-pulse">
          <div className="h-4 bg-surface-700/50 rounded w-48 mb-2" />
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <div key={i} className="glass-card p-3 flex flex-col items-center gap-2">
                <div className="w-16 h-16 bg-surface-700/30 rounded-full" />
                <div className="h-3 bg-surface-700/50 rounded w-20" />
              </div>
            ))}
          </div>
        </div>
      )}
      {!isLoading && Object.keys(accuracy).length > 1 && (
        <div className="mb-4">
          <div className="text-xs font-bold text-surface-400 mb-2">دقت سیگنال‌ها در هر بازار (۹۰ روز اخیر)</div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
            {Object.entries(MARKET_LABELS).map(([market, label]) => {
              const acc = accuracy[market];
              if (acc == null) return null;
              const count = summary?.markets?.[market]
                ? (summary.markets[market].buy + summary.markets[market].sell + summary.markets[market].hold)
                : 0;
              return (
                <MarketConfidenceCard
                  key={market}
                  market={market}
                  accuracy={acc}
                  signalCount={count}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* ═══ Row 4: Top Signals Table (with loading skeleton) ═══ */}
      {isLoading && (
        <div className="animate-pulse mb-4">
          <div className="glass-card p-4">
            <div className="h-4 bg-surface-700/50 rounded w-48 mb-3" />
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 bg-surface-700/20 rounded mb-2" />
            ))}
          </div>
        </div>
      )}
      {!isLoading && (
      <Card title={`سیگنال‌های برتر (${signals.length})`}
        actions={
          <div className="flex gap-1">
            {(["all", "buy", "sell", "hold"] as const).map((f) => (
              <CardAction key={f} active={signalFilter === f} onClick={() => setSignalFilter(f)}>
                {f === "all" ? "همه" : getDirectionLabel(f)}
              </CardAction>
            ))}
          </div>
        }
      >
        <SSRSafe style={{ overflowX: "auto" }}>
          {signals.length === 0 ? (
            <div className="text-center py-12 text-surface-500">
              <span className="material-icons text-4xl mb-2 block">signal_cellular_alt</span>
              <p className="text-sm">
                {error ? "خطا در دریافت داده" : "هیچ سیگنالی با فیلترهای فعلی یافت نشد"}
              </p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-800 sticky top-0 bg-surface-900">
                  <th className="py-2 text-right font-normal px-2">بازار</th>
                  <th className="py-2 text-right font-normal px-2">نماد</th>
                  <th className="py-2 text-right font-normal px-2">جهت</th>
                  <th className="py-2 text-right font-normal px-2">بازه</th>
                  <th className="py-2 text-right font-normal px-2">امتیاز</th>
                  <th className="py-2 text-right font-normal px-2">اطمینان</th>
                  <th className="py-2 text-right font-normal px-2">سطح</th>
                  <th className="py-2 text-right font-normal px-2">قیمت</th>
                  <th className="py-2 text-right font-normal px-2">تغییر</th>
                  <th className="py-2 text-right font-normal px-2">استراتژی رأی</th>
                  <th className="py-2 text-right font-normal px-2 max-w-[200px]">دلیل</th>
                  <th className="py-2 text-right font-normal px-2">جزئیات</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s, i) => (
                  <tr key={`${s.symbol}-${s.market}-${s.timeframe}-${i}`}
                    className="border-b border-surface-800/50 hover:bg-white/[0.02] transition-colors">
                    <td className="py-2 px-2">
                      <span className="text-xs" style={{ color: MARKET_COLORS[s.market] || "#94A3B8" }}>
                        {MARKET_ICONS[s.market] || "📊"} {MARKET_LABELS[s.market] || s.market}
                      </span>
                    </td>
                    <td className="py-2 px-2">
                      <Link href={`/symbol/${encodeURIComponent(s.symbol)}`}
                        className="text-surface-200 hover:text-primary-300 font-bold">
                        {s.symbol}
                      </Link>
                      <div className="text-[10px] text-surface-600">{s.name}</div>
                    </td>
                    <td className="py-2 px-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${getDirectionBadge(s.direction)}`}>
                        {getDirectionLabel(s.direction)}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-surface-400">{s.timeframe}</td>
                    <td className="py-2 px-2">
                      <span className="font-mono text-surface-200">{s.boosted_score.toFixed(1)}</span>
                      {s.ml_influence_pct > 0 && (
                        <span className="text-[9px] text-primary-400 block">
                          ML: {s.ml_influence_pct.toFixed(0)}%
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-2">
                      <ConfidenceGauge value={s.confidence} size={36} strokeWidth={4} />
                    </td>
                    <td className="py-2 px-2">
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${CALIBRATION_COLORS[s.calibration_level] || CALIBRATION_COLORS.medium}`}>
                        {CALIBRATION_LABELS[s.calibration_level] || s.calibration_level}
                      </span>
                    </td>
                    <td className="py-2 px-2 font-mono text-surface-300">{fmtPrice(s.price)}</td>
                    <td className={`py-2 px-2 font-mono ${s.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {fmtPct(s.change_pct)}
                    </td>
                    <td className="py-2 px-2 text-[10px] text-surface-500">{s.vote_strategy}</td>
                    <td className="py-2 px-2 text-[10px] text-surface-500 max-w-[200px] truncate" title={s.reason}>
                      {s.reason}
                    </td>
                    <td className="py-2 px-2">
                      <Link href={`/symbol/${encodeURIComponent(s.symbol)}`}
                        className="text-[10px] text-primary-400 hover:text-primary-300">
                        تحلیل ←
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SSRSafe>
      </Card>
      )}

      {/* ═══ Row 5: Cross-Market Signals + Radar ═══ */}
      {crossSignals.length > 0 && (
        <div className="mb-4 mt-4">
          <div className="text-xs font-bold text-surface-400 mb-2">سیگنال‌های میان‌بازاری</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {crossSignals.map((cs) => (
              <CrossMarketCard key={cs.name} signal={cs} />
            ))}
          </div>
        </div>
      )}

      {/* Market Bias Radar */}
      {marketBiases && Object.keys(marketBiases).length > 0 && (
        <div className="mb-4">
          <Card title="رادار بازارها">
            <MarketBiasRadar biases={marketBiases} />
          </Card>
        </div>
      )}

      {/* ═══ Row 6: Market Bias Summary + Generation Reports ═══ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">          {/* Market Biases */}
          {marketBiases && (
          <Card title="وضعیت بازارها">
            <div className="grid grid-cols-1 gap-2">
              {Object.entries(MARKET_LABELS).map(([market, label]) => {
                const bias = marketBiases[market] as MarketBias | undefined;
                if (!bias) return null;
                const biasColor = bias.bias === "bullish" ? "text-accent-emerald"
                  : bias.bias === "bearish" ? "text-accent-rose"
                  : "text-surface-400";
                const biasLabel = bias.bias === "bullish" ? "صعودی"
                  : bias.bias === "bearish" ? "نزولی"
                  : "خنثی";
                return (
                  <div key={market} className="flex items-center gap-3 py-2 border-b border-surface-800/50 last:border-0">
                    <span className="text-sm w-16 shrink-0" style={{ color: MARKET_COLORS[market] || "#94A3B8" }}>
                      {MARKET_ICONS[market] || "📊"} {label}
                    </span>
                    <span className={`text-xs font-bold ${biasColor} w-12 shrink-0`}>{biasLabel}</span>
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden flex">
                        <div className="h-full bg-accent-emerald rounded-r-full transition-all"
                          style={{ width: `${bias.buy_pct}%` }} />
                      </div>
                      <span className="text-[10px] font-mono text-surface-500 w-14 shrink-0 text-left">
                        {bias.buy_pct}% / {bias.sell_pct}%
                      </span>
                      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden flex flex-row-reverse">
                        <div className="h-full bg-accent-rose rounded-l-full transition-all"
                          style={{ width: `${bias.sell_pct}%` }} />
                      </div>
                    </div>
                    <span className="text-[10px] text-surface-600 w-10 shrink-0 text-left">{bias.total} عدد</span>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Retrain Status */}
        {retrainReports.length > 0 && (
          <Card title="وضعیت بازآموزی مدل‌ها">
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {retrainReports.map((rr) => (
                <div key={rr.pipeline_run_id} className="glass-card p-3 border border-surface-700/50">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm" style={{ color: MARKET_COLORS[rr.market] || "#94A3B8" }}>
                        {MARKET_ICONS[rr.market] || "📊"} {MARKET_LABELS[rr.market] || rr.market}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        rr.trigger === "accuracy_drop" ? "bg-accent-rose/15 text-accent-rose" :
                        rr.trigger === "manual" ? "bg-primary-600/20 text-primary-300" :
                        "bg-surface-600/30 text-surface-400"
                      }`}>
                        {rr.trigger === "accuracy_drop" ? "کاهش دقت" : rr.trigger === "manual" ? "دستی" : "زمان‌بندی"}
                      </span>
                    </div>
                    {rr.timestamp && (
                      <span className="text-[10px] text-surface-600">
                        {new Date(rr.timestamp).toLocaleTimeString("fa-IR")}
                      </span>
                    )}
                  </div>

                  {/* Accuracy change */}
                  <div className="flex items-center gap-4 mb-2 text-xs">
                    <div className="flex items-center gap-1">
                      <span className="text-surface-500">دقت قبلی:</span>
                      <span className="font-mono text-surface-400">{rr.old_accuracy_pct.toFixed(1)}%</span>
                    </div>
                    <span className="text-surface-600">→</span>
                    <div className="flex items-center gap-1">
                      <span className="text-surface-500">دقت جدید:</span>
                      <span className={`font-mono font-bold ${rr.new_accuracy_pct > rr.old_accuracy_pct ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {rr.new_accuracy_pct.toFixed(1)}%
                      </span>
                      {rr.new_accuracy_pct > rr.old_accuracy_pct && (
                        <span className="text-accent-emerald text-[9px]">↑</span>
                      )}
                    </div>
                  </div>

                  {/* Models */}
                  <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    {rr.models_retrained.map((m) => (
                      <span key={m} className="text-[9px] px-1.5 py-0.5 rounded bg-accent-emerald/15 text-accent-emerald">
                        {m} ✓
                      </span>
                    ))}
                    {rr.models_skipped.map((m) => (
                      <span key={m} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-700/50 text-surface-500">
                        {m} ⊘
                      </span>
                    ))}
                  </div>

                  {/* Meta */}
                  <div className="flex items-center gap-4 text-[10px] text-surface-500">
                    <span>{rr.samples_used} نمونه</span>
                    <span>{rr.duration_seconds.toFixed(1)}s</span>
                    {rr.errors.length > 0 && (
                      <span className="text-accent-rose">{rr.errors.length} خطا</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Generation Reports */}
        {reports.length > 0 && (
          <Card title="گزارش تولید">
            <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
              {reports.map((r) => (
                <div key={r.market} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${r.success ? "bg-accent-emerald" : "bg-accent-rose"}`} />
                    <span className="text-xs text-surface-300">{MARKET_LABELS[r.market] || r.market}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-surface-400">{r.signal_count} سیگنال</span>
                    {!r.success && r.error && (
                      <span className="text-[10px] text-accent-rose truncate max-w-[120px]" title={r.error}>
                        {r.error}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
