"use client";

import { useEffect, useMemo } from "react";
import { analyzeFund, FundScore, FundIssue, Fund, type FundAnalysis } from "@/lib/fund-analysis";

// ── Helpers ───────────────────────────────────────────────────────

function scoreColor(s: number): string {
  if (s >= 75) return "text-accent-emerald";
  if (s >= 60) return "text-primary-300";
  if (s >= 40) return "text-accent-amber";
  return "text-accent-rose";
}

function scoreBgColor(s: number): string {
  if (s >= 75) return "bg-accent-emerald/15";
  if (s >= 60) return "bg-primary-600/15";
  if (s >= 40) return "bg-accent-amber/15";
  return "bg-accent-rose/15";
}

function priorityBadge(p: string): { label: string; color: string } {
  switch (p) {
    case "A1": return { label: "بحرانی", color: "bg-accent-rose text-white" };
    case "A2": return { label: "مهم", color: "bg-accent-amber text-white" };
    case "B": return { label: "متوسط", color: "bg-primary-600 text-white" };
    default: return { label: "کم", color: "bg-surface-600 text-surface-300" };
  }
}

function recColor(r: string): string {
  switch (r) {
    case "STRONG_BUY": return "bg-accent-emerald";
    case "BUY": return "bg-emerald-600";
    case "WATCHLIST": return "bg-primary-600";
    case "HOLD": return "bg-accent-amber";
    case "REDUCE": return "bg-orange-600";
    case "SELL": return "bg-accent-rose";
    case "AVOID": return "bg-red-900";
    default: return "bg-surface-600";
  }
}

function recLabel(r: string): string {
  switch (r) {
    case "STRONG_BUY": return "خرید قوی ✅";
    case "BUY": return "خرید 👍";
    case "WATCHLIST": return "واچ‌لیست 📌";
    case "HOLD": return "نگهداری 🔄";
    case "REDUCE": return "کاهش ⬇️";
    case "SELL": return "فروش ❌";
    case "AVOID": return "اجتناب 🚫";
    default: return "نامشخص";
  }
}

function riskBadge(r: string): { label: string; color: string } {
  switch (r) {
    case "LOW": return { label: "کم 🟢", color: "bg-accent-emerald/15 text-accent-emerald" };
    case "MEDIUM": return { label: "متوسط 🟡", color: "bg-accent-amber/15 text-accent-amber" };
    case "HIGH": return { label: "زیاد 🔴", color: "bg-accent-rose/15 text-accent-rose" };
    case "CRITICAL": return { label: "بحرانی 🚨", color: "bg-red-900/30 text-red-400" };
    default: return { label: "نامشخص", color: "bg-surface-600/30 text-surface-400" };
  }
}

// ── ScoreBar Component ──

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-surface-400">{label}</span>
        <span className={`font-mono font-bold ${scoreColor(score)}`}>{score}%</span>
      </div>
      <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${scoreBgColor(score)}`}
          style={{
            width: `${Math.max(2, score)}%`,
            backgroundColor: score >= 75 ? "#10b981" : score >= 60 ? "#6366f1" : score >= 40 ? "#f59e0b" : "#ef4444",
          }}
        />
      </div>
    </div>
  );
}

// ── Radar Chart (simple CSS-based) ──

function ScoreRadar({ scores }: { scores: FundScore }) {
  const entries: [string, number][] = [
    ["مالی", scores.financial],
    ["نقدشوندگی", scores.liquidity],
    ["مدیریت", scores.management],
    ["ریسک", scores.risk],
    ["هزینه", scores.cost],
    ["شفافیت", scores.transparency],
  ];

  const cx = 60, cy = 60, r = 52;
  const angleStep = (2 * Math.PI) / entries.length;

  const points = entries.map(([, v], i) => {
    const a = -Math.PI / 2 + i * angleStep;
    const val = v / 100;
    return {
      x: cx + r * val * Math.cos(a),
      y: cy + r * val * Math.sin(a),
    };
  });
  const polygon = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="flex justify-center">
      <svg viewBox="0 0 120 120" className="w-28 h-28">
        {/* Grid */}
        {[0.25, 0.5, 0.75, 1].map((scale, i) => {
          const pts = entries.map((_, j) => {
            const a = -Math.PI / 2 + j * angleStep;
            return {
              x: cx + r * scale * Math.cos(a),
              y: cy + r * scale * Math.sin(a),
            };
          });
          const gridPoly = pts.map((p) => `${p.x},${p.y}`).join(" ");
          return <polygon key={i} points={gridPoly} fill="none" stroke="#ffffff10" strokeWidth="0.5" />;
        })}
        {/* Axes */}
        {entries.map((_, i) => {
          const a = -Math.PI / 2 + i * angleStep;
          return <line key={i} x1={cx} y1={cy} x2={cx + r * Math.cos(a)} y2={cy + r * Math.sin(a)} stroke="#ffffff10" strokeWidth="0.5" />;
        })}
        {/* Data */}
        <polygon points={polygon} fill="#6366f130" stroke="#6366f1" strokeWidth="1.2" />
        {/* Labels */}
        {entries.map(([label], i) => {
          const a = -Math.PI / 2 + i * angleStep;
          const lx = cx + (r + 14) * Math.cos(a);
          const ly = cy + (r + 14) * Math.sin(a);
          return (
            <text key={i} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fill="#94a3b8" fontSize="3.5" fontWeight="bold">
              {label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

// ── Main Component ──

interface FundAnalysisModalProps {
  fund: Fund;
  onClose: () => void;
}

export default function FundAnalysisModal({ fund, onClose }: FundAnalysisModalProps) {
  const analysis = useMemo(() => analyzeFund(fund), [fund]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const risk = riskBadge(analysis.riskLevel);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={handleBackdrop}
      dir="rtl"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-surface-700/50 bg-surface-900 shadow-2xl">
        {/* ── Header ── */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 bg-surface-900/95 backdrop-blur border-b border-surface-800 rounded-t-2xl">
          <div className="flex items-center gap-2">
            <span className="material-icons text-primary-400 text-lg">account_balance</span>
            <span className="text-sm font-bold text-surface-200">تحلیل صندوق</span>
            <span className="text-xs font-mono font-bold text-primary-300 bg-primary-600/10 px-2 py-0.5 rounded-lg">{fund.symbol}</span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-surface-500 hover:text-surface-200 hover:bg-surface-800 transition-all">
            <span className="material-icons text-sm">close</span>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="px-4 py-4 space-y-4">
          {/* Fund info */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-bold text-surface-100">{fund.name || fund.symbol}</p>
              <p className="text-[10px] text-surface-500 mt-0.5">NAV: {fund.nav.toLocaleString("fa-IR")} ریال</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-[9px] px-2 py-0.5 rounded-full ${risk.color}`}>{risk.label}</span>
              <span className={`text-[10px] font-bold px-2.5 py-1 rounded-lg text-white ${recColor(analysis.recommendation)}`}>
                {recLabel(analysis.recommendation)}
              </span>
            </div>
          </div>

          {/* ── Score Radar + Total ── */}
          <div className="glass-card p-3 flex items-center gap-4">
            <ScoreRadar scores={analysis.scores} />
            <div className="flex-1 space-y-2">
              <ScoreBar label="امتیاز کل" score={analysis.scores.total} />
              <ScoreBar label="مالی" score={analysis.scores.financial} />
              <ScoreBar label="نقدشوندگی" score={analysis.scores.liquidity} />
              <ScoreBar label="مدیریت" score={analysis.scores.management} />
              <ScoreBar label="ریسک" score={analysis.scores.risk} />
              <ScoreBar label="هزینه" score={analysis.scores.cost} />
              <ScoreBar label="شفافیت" score={analysis.scores.transparency} />
            </div>
          </div>

          {/* ── Summary ── */}
          <div className="text-[10px] text-surface-400 bg-surface-800/30 rounded-xl p-2.5 border border-surface-700/30">
            {analysis.summary}
          </div>

          {/* ── Strengths & Weaknesses ── */}
          <div className="grid grid-cols-2 gap-2">
            {analysis.strengths.length > 0 && (
              <div className="rounded-xl p-2.5 border border-accent-emerald/20 bg-accent-emerald/05">
                <p className="text-[9px] font-bold text-accent-emerald mb-1">✅ نقاط قوت</p>
                {analysis.strengths.map((s, i) => (
                  <p key={i} className="text-[9px] text-surface-400">{s}</p>
                ))}
              </div>
            )}
            {analysis.weaknesses.length > 0 && (
              <div className="rounded-xl p-2.5 border border-accent-rose/20 bg-accent-rose/05">
                <p className="text-[9px] font-bold text-accent-rose mb-1">⚠️ نقاط ضعف</p>
                {analysis.weaknesses.map((w, i) => (
                  <p key={i} className="text-[9px] text-surface-400">{w}</p>
                ))}
              </div>
            )}
          </div>

          {/* ── Issues ── */}
          {analysis.issues.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-surface-300 mb-2">مشکلات شناسایی شده ({analysis.issues.length})</p>
              <div className="space-y-1.5">
                {analysis.issues.map((issue) => {
                  const pb = priorityBadge(issue.priority);
                  return (
                    <div key={issue.id} className="rounded-xl p-2.5 border border-surface-700/30 bg-surface-800/20">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className={`text-[8px] px-1.5 py-0.5 rounded-full font-bold ${pb.color}`}>{pb.label}</span>
                        <span className="text-[10px] font-bold text-surface-200">{issue.title}</span>
                      </div>
                      <p className="text-[9px] text-surface-500">{issue.description}</p>
                      <p className="text-[8px] text-primary-400 mt-0.5">💡 {issue.solution}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Next Steps ── */}
          {analysis.nextSteps.length > 0 && (
            <div className="rounded-xl p-2.5 border border-primary-600/20 bg-primary-600/05">
              <p className="text-[9px] font-bold text-primary-300 mb-1">🎯 اقدامات پیشنهادی</p>
              {analysis.nextSteps.map((step, i) => (
                <p key={i} className="text-[9px] text-surface-400 flex items-start gap-1">
                  <span className="text-primary-400">{i + 1}.</span>
                  <span>{step}</span>
                </p>
              ))}
            </div>
          )}

          {/* Fund details */}
          <div className="rounded-xl p-2.5 border border-surface-700/30 bg-surface-800/20">
            <p className="text-[9px] font-bold text-surface-400 mb-1.5">📋 مشخصات صندوق</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[9px]">
              <div className="flex justify-between">
                <span className="text-surface-500">NAV</span>
                <span className="font-mono text-surface-300">{fund.nav.toLocaleString("fa-IR")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-500">تغییرات</span>
                <span className={`font-mono ${fund.nav_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {fund.nav_change_pct >= 0 ? "+" : ""}{fund.nav_change_pct?.toFixed(2)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-500">حجم</span>
                <span className="font-mono text-surface-300">{fund.trade_volume?.toLocaleString("fa-IR")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-500">ارزش</span>
                <span className="font-mono text-surface-300">{fund.trade_value?.toLocaleString("fa-IR")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-500">واحد</span>
                <span className="font-mono text-surface-300">{fund.shares_count?.toLocaleString("fa-IR")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-500">بازه</span>
                <span className="font-mono text-surface-300">{fund.price_min?.toLocaleString("fa-IR")} – {fund.price_max?.toLocaleString("fa-IR")}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="sticky bottom-0 px-4 py-2.5 bg-surface-900/95 backdrop-blur border-t border-surface-800 rounded-b-2xl flex items-center justify-between">
          <span className="text-[8px] text-surface-600">
            تحلیل هوشمند بر اساس ۶ بعد مالی، نقدشوندگی، مدیریت، ریسک، هزینه، شفافیت
          </span>
          <button onClick={onClose} className="text-[10px] px-3 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg transition-all">
            بستن
          </button>
        </div>
      </div>
    </div>
  );
}
