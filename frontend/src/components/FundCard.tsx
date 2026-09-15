"use client";

import Link from "next/link";
import { useMemo } from "react";
import FundNavMiniChart, { type FundNavPoint } from "./FundNavMiniChart";
import {
  detectFundGroup,
  detectFundSubgroup,
  getGroupDef,
  calcBubble,
  bubbleColor,
  type FundGroup,
} from "@/lib/fund-categories";
import { scoringEngine, type Fund } from "@/lib/fund-analysis";

// ── Helpers ──────────────────────────────────────────────────

function formatNum(v: number): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function scoreColor(score: number): string {
  if (score >= 75) return "#10b981";
  if (score >= 60) return "#6366f1";
  if (score >= 45) return "#f59e0b";
  return "#ef4444";
}

function scoreLabel(score: number): string {
  if (score >= 75) return "عالی";
  if (score >= 60) return "خوب";
  if (score >= 45) return "متوسط";
  return "ضعیف";
}

// ── Score Gauge (Circular) ───────────────────────────────────

function ScoreGauge({ score, size = 36 }: { score: number; size?: number }) {
  const radius = (size - 4) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="block -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          className="text-surface-700/50"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span
          className="font-mono text-[9px] font-black"
          style={{ color }}
        >
          {score}
        </span>
      </div>
    </div>
  );
}

// ── P/NAV Bubble Badge ──────────────────────────────────────

function BubbleBadge({ price, nav }: { price: number; nav: number }) {
  const bubble = calcBubble(price, nav);
  if (bubble === null) return null;

  const color = bubbleColor(bubble);
  const isPositive = bubble > 0;

  return (
    <div
      className={`flex items-center gap-0.5 text-[9px] font-mono font-bold ${color}`}
      title={`حباب: ${bubble.toFixed(2)}% — قیمت: ${price.toLocaleString("fa-IR")} / NAV: ${nav.toLocaleString("fa-IR")}`}
    >
      <span>{isPositive ? "▲" : "▼"}</span>
      <span>{Math.abs(bubble).toFixed(1)}%</span>
    </div>
  );
}

// ── Fund Card Props ─────────────────────────────────────────

interface FundCardProps {
  fund: Fund;
  navPoints?: FundNavPoint[];
  isSelected?: boolean;
  onSelect?: (symbol: string) => void;
  view?: "grid" | "list";
}

// ── Main Component ──────────────────────────────────────────

export default function FundCard({
  fund,
  navPoints,
  isSelected = false,
  onSelect,
  view = "list",
}: FundCardProps) {
  const group = useMemo(() => detectFundGroup(fund.name, fund.fund_type), [fund.name, fund.fund_type]);
  const subgroup = useMemo(() => detectFundSubgroup(fund.name, group), [fund.name, group]);
  const groupDef = useMemo(() => getGroupDef(group), [group]);
  const scores = useMemo(() => scoringEngine(fund), [fund]);
  const isUp = fund.nav_change_pct >= 0;

  const bubble = calcBubble(fund.price_last, fund.nav);

  if (view === "grid") {
    return (
      <div
        className={`glass-card p-4 flex flex-col gap-3 transition-all group relative ${
          isSelected
            ? "border-primary-500/60 bg-primary-600/[0.06] ring-1 ring-primary-500/30"
            : "hover:bg-white/[0.04] hover:border-primary-500/40 hover:shadow-lg"
        }`}
      >
        {/* Header: Score + Group + Compare */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <ScoreGauge score={scores.total} size={40} />
            <div>
              <Link
                href={`/funds/${encodeURIComponent(fund.symbol)}`}
                className="font-bold text-sm text-ink group-hover:text-primary-300 transition-colors"
              >
                {fund.symbol}
              </Link>
              <p className="text-[9px] text-ink-3 truncate max-w-[100px]">{fund.name}</p>
            </div>
          </div>
          {onSelect && (
            <button
              onClick={() => onSelect(fund.symbol)}
              className={`shrink-0 w-5 h-5 rounded-md border flex items-center justify-center transition-all ${
                isSelected
                  ? "bg-primary-600 border-primary-500 text-white"
                  : "border-surface-600 text-transparent hover:border-primary-500"
              }`}
            >
              <span className="material-icons text-[10px]">check</span>
            </button>
          )}
        </div>

        {/* Type + Market badges */}
        <div className="flex flex-wrap gap-1">
          <span className={`text-[8px] px-1.5 py-0.5 rounded-full font-bold ${groupDef.color} ${groupDef.textColor}`}>
            {groupDef.icon} {groupDef.label}
          </span>
          {subgroup && group === "sector" && (
            <span className="text-[8px] px-1.5 py-0.5 rounded-full font-bold bg-orange-500/10 text-orange-300">
              {subgroup}
            </span>
          )}
        </div>

        {/* NAV + Change */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[8px] text-ink-3">NAV</p>
            <p className="font-mono text-xs font-bold text-ink">
              {fund.nav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
            </p>
          </div>
          <div className="text-left">
            <p className={`font-mono text-sm font-bold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
              {isUp ? "+" : ""}{fund.nav_change_pct?.toFixed(2)}%
            </p>
          </div>
        </div>

        {/* Sparkline */}
        {navPoints && navPoints.length > 1 && (
          <div className="w-full">
            <FundNavMiniChart points={navPoints} width={200} height={32} />
          </div>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-[8px] text-ink-3">حجم</p>
            <p className="font-mono text-[10px] text-ink-2">{formatNum(fund.trade_volume)}</p>
          </div>
          <div>
            <p className="text-[8px] text-ink-3">ارزش بازار</p>
            <p className="font-mono text-[10px] text-primary-300">{formatNum(fund.market_value)}</p>
          </div>
          <div>
            <p className="text-[8px] text-ink-3">واحد</p>
            <p className="font-mono text-[10px] text-ink-2">{formatNum(fund.shares_count)}</p>
          </div>
        </div>

        {/* Bubble + Score footer */}
        <div className="flex items-center justify-between pt-2 border-t border-line">
          <BubbleBadge price={fund.price_last} nav={fund.nav} />
          <span className="text-[8px] text-ink-3">{scoreLabel(scores.total)}</span>
        </div>

        {/* Disclaimer */}
        <p className="text-[7px] text-ink-3/50 text-center leading-tight">
          تحلیل خودکار — توصیه مالی نیست
        </p>
      </div>
    );
  }

  // ── List view (default) ──
  return (
    <div
      className={`glass-card p-3 flex items-center gap-3 transition-all group relative ${
        isSelected
          ? "border-primary-500/60 bg-primary-600/[0.06]"
          : "hover:bg-white/[0.04] hover:border-primary-500/40"
      }`}
    >
      {/* Compare checkbox */}
      {onSelect && (
        <button
          onClick={() => onSelect(fund.symbol)}
          title={isSelected ? "حذف از مقایسه" : "افزودن به مقایسه"}
          className={`shrink-0 w-6 h-6 rounded-lg border flex items-center justify-center transition-all ${
            isSelected
              ? "bg-primary-600 border-primary-500 text-white"
              : "border-surface-600 text-transparent hover:border-primary-500 hover:text-surface-600"
          }`}
        >
          <span className="material-icons text-[14px]">check</span>
        </button>
      )}

      <Link
        href={`/funds/${encodeURIComponent(fund.symbol)}`}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        {/* Score gauge */}
        <div className="shrink-0">
          <ScoreGauge score={scores.total} size={38} />
        </div>

        {/* NAV mini-chart */}
        <div className="shrink-0 w-[88px]">
          {navPoints && navPoints.length > 1 ? (
            <FundNavMiniChart points={navPoints} width={88} height={30} />
          ) : (
            <div className="h-[30px] flex items-center justify-center text-[9px] text-ink-3">—</div>
          )}
        </div>

        {/* Symbol + Name */}
        <div className="min-w-[120px] shrink-0">
          <p className="font-bold text-sm text-ink group-hover:text-primary-300 transition-colors">{fund.symbol}</p>
          <p className="text-[10px] text-ink-3 truncate max-w-[140px]">{fund.name || "—"}</p>
        </div>

        {/* Group badge */}
        <div className="shrink-0">
          <span className={`text-[8px] px-1.5 py-0.5 rounded-full font-bold ${groupDef.color} ${groupDef.textColor}`}>
            {groupDef.icon} {groupDef.label}
          </span>
        </div>

        {/* NAV */}
        <div className="min-w-[80px] shrink-0 text-right" title={fund.nav_date ? `NAV واقعی — ${fund.nav_date}` : ""}>
          <p className="text-[8px] text-ink-3">NAV</p>
          <p className="font-mono text-xs font-bold text-ink">
            {fund.nav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
          </p>
          {fund.nav_date && <p className="text-[7px] text-ink-3/50" dir="ltr">{fund.nav_date}</p>}
        </div>

        {/* Change */}
        <div className="min-w-[70px] shrink-0 text-right">
          <p className={`font-mono text-sm font-bold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
            {isUp ? "+" : ""}{fund.nav_change_pct?.toFixed(2)}%
          </p>
          <p className={`font-mono text-[10px] ${isUp ? "text-emerald-400/60" : "text-rose-400/60"}`}>
            {isUp ? "+" : ""}{fund.nav_change?.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
          </p>
        </div>

        {/* P/NAV Bubble */}
        <div className="hidden sm:block min-w-[60px] shrink-0">
          <BubbleBadge price={fund.price_last} nav={fund.nav} />
        </div>

        {/* Volume */}
        <div className="hidden md:block min-w-[70px] shrink-0 text-right">
          <p className="text-[8px] text-ink-3">حجم</p>
          <p className="font-mono text-[10px] text-ink-2">{formatNum(fund.trade_volume)}</p>
        </div>

        {/* Real/Legal net */}
        <div className="hidden lg:block min-w-[70px] shrink-0">
          <p className="text-[8px] text-ink-3">حقیقی خالص</p>
          <p className={`font-mono text-[10px] ${fund.buy_real_volume >= fund.sell_real_volume ? "text-emerald-400" : "text-rose-400"}`}>
            {formatNum(Math.abs(fund.buy_real_volume - fund.sell_real_volume))}
          </p>
        </div>

        {/* Market value */}
        <div className="hidden xl:block min-w-[80px] shrink-0 text-right">
          <p className="text-[8px] text-ink-3">ارزش بازار</p>
          <p className="font-mono text-[10px] text-primary-300">{formatNum(fund.market_value)}</p>
        </div>

        {/* Arrow */}
        <div className="mr-auto text-ink-3 group-hover:text-primary-400 transition-colors text-lg">
          ←
        </div>
      </Link>
    </div>
  );
}
