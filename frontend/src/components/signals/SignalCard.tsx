"use client";

import type { EnrichedSignal } from "@/lib/types";

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

const DIRECTION_COLORS: Record<string, string> = {
  buy: "bg-accent-emerald/15 text-accent-emerald",
  sell: "bg-accent-rose/15 text-accent-rose",
  hold: "bg-surface-600/30 text-surface-400",
  wait: "bg-accent-amber/15 text-accent-amber",
};

const DIRECTION_LABELS: Record<string, string> = {
  buy: "خرید",
  sell: "فروش",
  hold: "خنثی",
  wait: "انتظار",
};

const GRADE_COLORS: Record<string, string> = {
  "A+": "bg-accent-emerald/20 text-accent-emerald border-accent-emerald/30",
  A: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/20",
  B: "bg-accent-amber/15 text-accent-amber border-accent-amber/20",
  WATCHLIST: "bg-surface-600/30 text-surface-400 border-surface-600/30",
  REJECT: "bg-accent-rose/10 text-surface-500 border-surface-600/20",
};

const CALIBRATION_COLORS: Record<string, string> = {
  very_high: "text-accent-emerald",
  high: "text-accent-emerald",
  medium: "text-accent-amber",
  low: "text-accent-rose",
};

const CALIBRATION_LABELS: Record<string, string> = {
  very_high: "بسیار بالا",
  high: "بالا",
  medium: "متوسط",
  low: "پایین",
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return n.toLocaleString("fa-IR");
  return n.toFixed(2);
}

function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

// ── ConfidenceGauge ─────────────────────────────────────────────────────────

function ConfidenceGauge({
  value,
  size = 64,
  strokeWidth = 7,
}: {
  value: number;
  size?: number;
  strokeWidth?: number;
}) {
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
        {(value * 100).toFixed(0)}%
      </text>
    </svg>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

interface SignalCardProps {
  signal: EnrichedSignal;
  variant?: "compact" | "full" | "hero";
  onClick?: () => void;
}

export default function SignalCard({ signal, variant = "compact", onClick }: SignalCardProps) {
  const marketColor = MARKET_COLORS[signal.market] || "#94A3B8";
  const marketLabel = MARKET_LABELS[signal.market] || signal.market;
  const marketIcon = MARKET_ICONS[signal.market] || "📊";
  const dirColor = DIRECTION_COLORS[signal.direction] || DIRECTION_COLORS.hold;
  const dirLabel = DIRECTION_LABELS[signal.direction] || signal.direction;

  if (variant === "hero") {
    return (
      <div
        className="glass-card p-6 border border-surface-700/50 hover:border-primary-500/30 transition-all cursor-pointer"
        onClick={onClick}
      >
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-3xl">{marketIcon}</span>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-lg font-black text-surface-100">{signal.symbol}</span>
              <span className="text-sm text-surface-400">{signal.name}</span>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ color: marketColor, backgroundColor: `${marketColor}15` }}>
                {marketLabel}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${dirColor}`}>
                {dirLabel}
              </span>
              <span className="text-xs text-surface-500">{signal.timeframe}</span>
              {signal.decision_grade && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${GRADE_COLORS[signal.decision_grade] || GRADE_COLORS.B}`}>
                  {signal.decision_grade}
                </span>
              )}
              <span className={`text-[10px] ${CALIBRATION_COLORS[signal.calibration_level] || "text-surface-500"}`}>
                اطمینان: {CALIBRATION_LABELS[signal.calibration_level] || signal.calibration_level}
              </span>
            </div>
          </div>
          <ConfidenceGauge value={signal.confidence} size={80} strokeWidth={8} />
        </div>

        {/* 11 Columns Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">نقطه ورود</div>
            <div className="text-surface-200 font-medium">{signal.entry_zone}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">حد ضرر</div>
            <div className="text-accent-rose font-medium">{signal.stop_loss}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">اهداف سود</div>
            <div className="text-accent-emerald font-medium">{signal.targets}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">ریسک به ریوارد</div>
            <div className="text-primary-300 font-medium">{signal.risk_reward}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">حجم پیشنهادی</div>
            <div className="text-surface-300">{signal.position_sizing}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">شرط تأیید</div>
            <div className="text-surface-300">{signal.confirmation_condition}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">شرایط فسخ</div>
            <div className="text-accent-amber">{signal.invalidation}</div>
          </div>
          <div className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-1">مدیریت پس از ورود</div>
            <div className="text-surface-300">{signal.trailing_stop}</div>
          </div>
        </div>

        {/* Reason */}
        <div className="mt-3 p-3 glass-card">
          <div className="text-[10px] text-surface-500 mb-1">علت و منطق</div>
          <div className="text-sm text-surface-200">{signal.reason}</div>
        </div>

        {/* Scores Bar */}
        <div className="mt-3 flex items-center gap-4 text-[10px] text-surface-500">
          <span>امتیاز تکنیکال: <span className="text-surface-300 font-mono">{signal.rule_score.toFixed(0)}</span></span>
          <span>امتیاز ML: <span className="text-surface-300 font-mono">{(signal.ml_score * 100).toFixed(0)}%</span></span>
          <span>امتیاز ترکیبی: <span className="text-primary-300 font-mono font-bold">{signal.boosted_score.toFixed(0)}</span></span>
          <span className="mr-auto">تغییر: <span className={`font-mono ${signal.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{fmtPct(signal.change_pct)}</span></span>
          <span>قیمت: <span className="text-surface-300 font-mono">{fmtPrice(signal.price)}</span></span>
        </div>
      </div>
    );
  }

  if (variant === "full") {
    return (
      <div
        className="glass-card p-4 border border-surface-700/50 hover:border-primary-500/20 transition-all cursor-pointer"
        onClick={onClick}
      >
        <div className="flex items-center gap-3 mb-3">
          <span className="text-2xl">{marketIcon}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-surface-100 truncate">{signal.symbol}</span>
              <span className="text-xs text-surface-500 truncate">{signal.name}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${dirColor}`}>{dirLabel}</span>
              {signal.decision_grade && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${GRADE_COLORS[signal.decision_grade] || GRADE_COLORS.B}`}>{signal.decision_grade}</span>
              )}
            </div>
          </div>
          <ConfidenceGauge value={signal.confidence} size={56} strokeWidth={6} />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-3">
          <div className="p-2 rounded-lg bg-surface-800/50">
            <div className="text-[10px] text-surface-500">ورود</div>
            <div className="text-surface-200 truncate">{signal.entry_zone}</div>
          </div>
          <div className="p-2 rounded-lg bg-surface-800/50">
            <div className="text-[10px] text-surface-500">حد ضرر</div>
            <div className="text-accent-rose truncate">{signal.stop_loss}</div>
          </div>
          <div className="p-2 rounded-lg bg-surface-800/50">
            <div className="text-[10px] text-surface-500">اهداف</div>
            <div className="text-accent-emerald truncate">{signal.targets}</div>
          </div>
          <div className="p-2 rounded-lg bg-surface-800/50">
            <div className="text-[10px] text-surface-500">ریسک/ریوارد</div>
            <div className="text-primary-300">{signal.risk_reward}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 text-[10px] text-surface-500">
          <span className="text-xs" style={{ color: marketColor }}>{marketLabel}</span>
          <span>{signal.timeframe}</span>
          <span className="font-mono">{fmtPrice(signal.price)}</span>
          <span className={`font-mono ${signal.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{fmtPct(signal.change_pct)}</span>
          <span className="mr-auto text-surface-400 truncate max-w-[200px]">{signal.reason}</span>
          <span className="text-primary-300 font-mono font-bold">{signal.boosted_score.toFixed(0)}</span>
        </div>
      </div>
    );
  }

  // compact
  return (
    <div
      className="glass-card p-3 border border-surface-700/50 hover:border-primary-500/20 transition-all cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">{marketIcon}</span>
        <span className="text-sm font-bold text-surface-100">{signal.symbol}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${dirColor}`}>{dirLabel}</span>
        <span className="text-[10px] text-surface-500">{signal.timeframe}</span>
        <ConfidenceGauge value={signal.confidence} size={40} strokeWidth={5} />
        <span className="text-xs text-surface-400 mr-auto truncate max-w-[150px]">{signal.reason}</span>
        <span className="text-xs font-mono text-primary-300 font-bold">{signal.boosted_score.toFixed(0)}</span>
      </div>
    </div>
  );
}
