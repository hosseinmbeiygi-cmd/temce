"use client";

import { useMemo, useEffect } from "react";
import Link from "next/link";
import { analyzeFund, type Fund } from "@/lib/fund-analysis";
import {
  detectFundGroup,
  getGroupDef,
  calcBubble,
  bubbleColor,
  bubbleLabel,
} from "@/lib/fund-categories";

// ── Helpers ──────────────────────────────────────────────────

function formatNum(v: number | null | undefined): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + " هزار میلیارد";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + " میلیارد";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + " میلیون";
  return v.toLocaleString("fa-IR");
}

function recLabel(r: string): string {
  const map: Record<string, string> = {
    STRONG_BUY: "خرید قوی 🟢",
    BUY: "خرید ✅",
    WATCHLIST: "تحت نظر 👀",
    HOLD: "نگهداری ⏸️",
    REDUCE: "کاهش ⚠️",
    SELL: "فروش 🔻",
    AVOID: "اجتناب 🔴",
  };
  return map[r] || r;
}

function recColor(r: string): string {
  if (r === "STRONG_BUY" || r === "BUY") return "text-emerald-400 bg-emerald-500/15";
  if (r === "WATCHLIST") return "text-primary-300 bg-primary-600/15";
  if (r === "HOLD") return "text-ink-2 bg-surface-600/20";
  return "text-rose-400 bg-rose-500/15";
}

function riskLabel(r: string): string {
  const map: Record<string, string> = { LOW: "کم", MEDIUM: "متوسط", HIGH: "زیاد", CRITICAL: "بحرانی" };
  return map[r] || r;
}

function riskColor(r: string): string {
  if (r === "LOW") return "text-emerald-400 bg-emerald-500/15";
  if (r === "MEDIUM") return "text-amber-400 bg-amber-500/15";
  return "text-rose-400 bg-rose-500/15";
}

function scoreColor(s: number): string {
  if (s >= 75) return "#10b981";
  if (s >= 60) return "#6366f1";
  if (s >= 45) return "#f59e0b";
  return "#ef4444";
}

// ── Score Bar ───────────────────────────────────────────────

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = scoreColor(value);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-ink-3">{label}</span>
        <span className="font-mono text-[11px] font-bold" style={{ color }}>{value}%</span>
      </div>
      <div className="h-1.5 bg-surface-700/50 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.max(3, value)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────

interface FundDetailDrawerProps {
  fund: Fund;
  onClose: () => void;
}

export default function FundDetailDrawer({ fund, onClose }: FundDetailDrawerProps) {
  const analysis = useMemo(() => analyzeFund(fund), [fund]);
  const group = useMemo(() => detectFundGroup(fund.name, fund.fund_type), [fund.name, fund.fund_type]);
  const groupDef = useMemo(() => getGroupDef(group), [group]);
  const bubble = calcBubble(fund.price_last, fund.nav);
  const isUp = fund.nav_change_pct >= 0;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-stretch justify-end bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      dir="rtl"
    >
      <div className="w-full max-w-md h-full overflow-y-auto bg-canvas border-l border-line shadow-2xl animate-slide-left">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 bg-canvas/95 backdrop-blur border-b border-line">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${groupDef.color} ${groupDef.textColor}`}>
              {groupDef.icon} {groupDef.label}
            </span>
            <span className="font-bold text-ink">{fund.symbol}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-ink-3 hover:text-ink hover:bg-soft transition-all"
          >
            <span className="material-icons text-sm">close</span>
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Fund name + ISIN */}
          <div>
            <h3 className="text-lg font-black text-ink">{fund.name}</h3>
            <p className="text-[10px] text-ink-3 font-mono mt-0.5" dir="ltr">ISIN: {fund.isin || "—"}</p>
          </div>

          {/* Score + Recommendation + Risk */}
          <div className="glass-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative" style={{ width: 56, height: 56 }}>
                  <svg width={56} height={56} className="block -rotate-90">
                    <circle cx={28} cy={28} r={24} fill="none" stroke="currentColor" strokeWidth="3" className="text-surface-700/50" />
                    <circle
                      cx={28} cy={28} r={24} fill="none"
                      stroke={scoreColor(analysis.scores.total)}
                      strokeWidth="3" strokeLinecap="round"
                      strokeDasharray={2 * Math.PI * 24}
                      strokeDashoffset={2 * Math.PI * 24 - (analysis.scores.total / 100) * 2 * Math.PI * 24}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="font-mono text-lg font-black" style={{ color: scoreColor(analysis.scores.total) }}>
                      {analysis.scores.total}
                    </span>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-ink-3">امتیاز کل</p>
                  <p className="text-sm font-bold text-ink">{analysis.summary}</p>
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${recColor(analysis.recommendation)}`}>
                {recLabel(analysis.recommendation)}
              </span>
              <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${riskColor(analysis.riskLevel)}`}>
                ریسک: {riskLabel(analysis.riskLevel)}
              </span>
            </div>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 gap-2">
            <div className="glass-card p-3">
              <p className="text-[9px] text-ink-3">NAV</p>
              <p className="font-mono text-sm font-bold text-primary-300">
                {fund.nav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div className="glass-card p-3">
              <p className="text-[9px] text-ink-3">تغییرات</p>
              <p className={`font-mono text-sm font-bold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
                {isUp ? "+" : ""}{fund.nav_change_pct?.toFixed(2)}%
              </p>
            </div>
            <div className="glass-card p-3">
              <p className="text-[9px] text-ink-3">حجم معاملات</p>
              <p className="font-mono text-xs text-ink-2">{formatNum(fund.trade_volume)}</p>
            </div>
            <div className="glass-card p-3">
              <p className="text-[9px] text-ink-3">ارزش بازار</p>
              <p className="font-mono text-xs text-primary-300">{formatNum(fund.market_value)}</p>
            </div>
            <div className="glass-card p-3">
              <p className="text-[9px] text-ink-3">تعداد واحد</p>
              <p className="font-mono text-xs text-ink-2">{formatNum(fund.shares_count)}</p>
            </div>
            <div className="glass-card p-3">
              <p className="text-[9px] text-ink-3">حقیقی خالص</p>
              <p className={`font-mono text-xs ${fund.buy_real_volume >= fund.sell_real_volume ? "text-emerald-400" : "text-rose-400"}`}>
                {formatNum(Math.abs(fund.buy_real_volume - fund.sell_real_volume))}
              </p>
            </div>
          </div>

          {/* P/NAV Bubble */}
          {bubble !== null && (
            <div className="glass-card p-3">
              <div className="flex items-center justify-between">
                <p className="text-[10px] text-ink-3">صرف/کسر NAV (حباب)</p>
                <span className={`text-xs font-mono font-bold ${bubbleColor(bubble)}`}>
                  {bubble > 0 ? "+" : ""}{bubble.toFixed(2)}%
                </span>
              </div>
              <p className="text-[9px] text-ink-3 mt-1">{bubbleLabel(bubble)}</p>
              <div className="mt-2 h-2 bg-surface-700/50 rounded-full overflow-hidden relative">
                <div className="absolute left-1/2 top-0 bottom-0 w-px bg-ink-3/30" />
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, Math.abs(bubble) * 5)}%`,
                    backgroundColor: bubble > 0 ? "#ef4444" : "#10b981",
                    marginLeft: bubble < 0 ? "auto" : undefined,
                    marginRight: bubble > 0 ? "auto" : undefined,
                  }}
                />
              </div>
            </div>
          )}

          {/* 6-dimension scores */}
          <div className="glass-card p-4 space-y-2.5">
            <p className="text-xs font-bold text-ink mb-2">تحلیل ۶‌بعدی</p>
            <ScoreBar label="مالی (بازدهی و عملکرد)" value={analysis.scores.financial} />
            <ScoreBar label="نقدشوندگی (حجم و عمق بازار)" value={analysis.scores.liquidity} />
            <ScoreBar label="مدیریت (تجربه و ثبات)" value={analysis.scores.management} />
            <ScoreBar label="ریسک (نوسان و افت)" value={analysis.scores.risk} />
            <ScoreBar label="هزینه (کارمزد و صرف)" value={analysis.scores.cost} />
            <ScoreBar label="شفافیت (گزارش‌دهی)" value={analysis.scores.transparency} />
          </div>

          {/* Strengths */}
          {analysis.strengths.length > 0 && (
            <div className="glass-card p-3">
              <p className="text-[10px] font-bold text-emerald-400 mb-2">نقاط قوت</p>
              {analysis.strengths.map((s, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px] text-ink-2 mb-1">
                  <span className="text-emerald-400">✓</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}

          {/* Weaknesses */}
          {analysis.weaknesses.length > 0 && (
            <div className="glass-card p-3">
              <p className="text-[10px] font-bold text-rose-400 mb-2">نقاط ضعف</p>
              {analysis.weaknesses.map((w, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px] text-ink-2 mb-1">
                  <span className="text-rose-400">⚠</span>
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {/* Issues */}
          {analysis.issues.length > 0 && (
            <div className="glass-card p-3">
              <p className="text-[10px] font-bold text-amber-400 mb-2">مشکلات شناسایی‌شده ({analysis.issues.length})</p>
              {analysis.issues.slice(0, 5).map((issue) => (
                <div key={issue.id} className="flex items-start gap-2 text-[10px] text-ink-2 mb-2 pb-2 border-b border-line last:border-0 last:mb-0 last:pb-0">
                  <span className={`shrink-0 text-[8px] px-1 py-0.5 rounded font-bold ${
                    issue.priority === "A1" ? "bg-rose-500/20 text-rose-400" :
                    issue.priority === "A2" ? "bg-amber-500/20 text-amber-400" :
                    "bg-surface-600/30 text-ink-3"
                  }`}>
                    {issue.priority}
                  </span>
                  <div>
                    <p className="font-bold">{issue.title}</p>
                    <p className="text-ink-3 text-[9px]">{issue.description}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Next Steps */}
          {analysis.nextSteps.length > 0 && (
            <div className="glass-card p-3">
              <p className="text-[10px] font-bold text-primary-300 mb-2">گام‌های بعدی</p>
              {analysis.nextSteps.map((step, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px] text-ink-2 mb-1">
                  <span className="text-primary-300 font-mono text-[8px]">{i + 1}.</span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <Link
              href={`/funds/${encodeURIComponent(fund.symbol)}`}
              className="flex-1 text-center text-xs font-bold text-primary-300 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg py-2.5 transition-all"
            >
              مشاهده کامل صندوق →
            </Link>
            <button
              onClick={onClose}
              className="text-xs font-bold text-ink-3 bg-surface-800 hover:bg-surface-700 border border-surface-700 rounded-lg px-4 py-2.5 transition-all"
            >
              بستن
            </button>
          </div>

          {/* Disclaimer */}
          <p className="text-[8px] text-ink-3/50 text-center leading-relaxed">
            این تحلیل خودکار و صرفاً اطلاعاتی است، توصیه مالی رسمی محسوب نمی‌شود و مسئولیت تصمیم سرمایه‌گذاری بر عهده کاربر است.
          </p>
        </div>
      </div>

      <style jsx>{`
        @keyframes slideLeft {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .animate-slide-left {
          animation: slideLeft 0.25s ease-out;
        }
      `}</style>
    </div>
  );
}
