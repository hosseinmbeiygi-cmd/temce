"use client";

import { useEffect } from "react";
import type { EnrichedSignal } from "@/lib/types";
import AddAlertButton from "@/components/AddAlertButton";

const MARKET_COLORS: Record<string, string> = {
  stock: "#64FFDA", gold: "#FFD700", currency: "#FF6B6B",
  crypto: "#A78BFA", option: "#38BDF8", commodity: "#FB923C", ime: "#94A3B8",
};

const MARKET_LABELS: Record<string, string> = {
  stock: "سهام", gold: "طلا", currency: "ارز",
  crypto: "رمزارز", option: "آپشن", commodity: "کالا", ime: "بورس کالا",
};

const DIRECTION_COLORS: Record<string, string> = {
  buy: "bg-accent-emerald/15 text-accent-emerald",
  sell: "bg-accent-rose/15 text-accent-rose",
  hold: "bg-surface-600/30 text-surface-400",
  wait: "bg-accent-amber/15 text-accent-amber",
};

const DIRECTION_LABELS: Record<string, string> = {
  buy: "خرید", sell: "فروش", hold: "خنثی", wait: "انتظار",
};

const GRADE_COLORS: Record<string, string> = {
  "A+": "bg-accent-emerald/20 text-accent-emerald border-accent-emerald/30",
  A: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/20",
  B: "bg-accent-amber/15 text-accent-amber border-accent-amber/20",
  WATCHLIST: "bg-surface-600/30 text-surface-400 border-surface-600/30",
  REJECT: "bg-accent-rose/10 text-surface-500 border-surface-600/20",
};

const VERDICT_COLORS: Record<string, string> = {
  release: "text-accent-emerald", watchlist: "text-accent-amber", reject: "text-accent-rose",
};

const CALIBRATION_LABELS: Record<string, string> = {
  very_high: "بسیار بالا", high: "بالا", medium: "متوسط", low: "پایین",
};

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return n.toLocaleString("fa-IR");
  return n.toFixed(2);
}

function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

interface SignalDetailModalProps {
  signal: EnrichedSignal;
  onClose: () => void;
}

export default function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const marketColor = MARKET_COLORS[signal.market] || "#94A3B8";
  const marketLabel = MARKET_LABELS[signal.market] || signal.market;
  const dirColor = DIRECTION_COLORS[signal.direction] || DIRECTION_COLORS.hold;
  const dirLabel = DIRECTION_LABELS[signal.direction] || signal.direction;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <div
          className="glass-card p-5 border border-surface-700 rounded-2xl shadow-2xl max-w-[800px] w-full max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{MARKET_ICONS[signal.market] || "📊"}</span>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-black text-surface-100">{signal.symbol}</span>
                  <span className="text-sm text-surface-400">{signal.name}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ color: marketColor, backgroundColor: `${marketColor}15` }}>{marketLabel}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${dirColor}`}>{dirLabel}</span>
                  <span className="text-xs text-surface-500">{signal.timeframe}</span>
                  {signal.decision_grade && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${GRADE_COLORS[signal.decision_grade] || GRADE_COLORS.B}`}>{signal.decision_grade}</span>
                  )}
                  {signal.decision_verdict && (
                    <span className={`text-[10px] font-bold ${VERDICT_COLORS[signal.decision_verdict] || "text-surface-500"}`}>
                      {signal.decision_verdict === "release" ? "تایید شده" : signal.decision_verdict === "watchlist" ? "دیده‌بان" : "رد شده"}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={onClose} className="text-surface-500 hover:text-surface-300 text-sm px-2 py-1 rounded hover:bg-surface-700/50 transition-colors">✕</button>
              <AddAlertButton
                symbol={signal.symbol}
                market={signal.market}
                timeframe={signal.timeframe}
                entry={signal.price}
                direction={signal.direction}
              />
            </div>
          </div>

          {/* Scores Row */}
          <div className="flex items-center gap-4 mb-4 p-3 glass-card">
            <div className="text-center">
              <div className="text-[10px] text-surface-500">امتیاز تکنیکال</div>
              <div className="text-lg font-black text-surface-200">{signal.rule_score.toFixed(0)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">امتیاز ML</div>
              <div className="text-lg font-black text-primary-300">{(signal.ml_score * 100).toFixed(0)}%</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">امتیاز ترکیبی</div>
              <div className="text-lg font-black text-accent-cyan">{signal.boosted_score.toFixed(0)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">نفوذ ML</div>
              <div className="text-lg font-black text-surface-300">{(signal.ml_influence_pct * 100).toFixed(0)}%</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">اطمینان</div>
              <div className="text-lg font-black text-accent-emerald">{(signal.confidence * 100).toFixed(0)}%</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">سطح اطمینان</div>
              <div className="text-sm font-bold text-surface-200">{CALIBRATION_LABELS[signal.calibration_level] || signal.calibration_level}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">قیمت</div>
              <div className="text-sm font-mono text-surface-200">{fmtPrice(signal.price)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-surface-500">تغییر</div>
              <div className={`text-sm font-mono font-bold ${signal.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{fmtPct(signal.change_pct)}</div>
            </div>
          </div>

          {/* 11 Columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">1. نقطه ورود</div>
              <div className="text-sm text-surface-200">{signal.entry_zone}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">2. حد ضرر</div>
              <div className="text-sm text-accent-rose">{signal.stop_loss}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">3. اهداف سود (دوگانه)</div>
              <div className="text-sm text-accent-emerald">{signal.targets}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">4. نسبت ریسک به ریوارد</div>
              <div className="text-sm text-primary-300 font-bold">{signal.risk_reward}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">5. حجم پیشنهادی</div>
              <div className="text-sm text-surface-300">{signal.position_sizing}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">6. شرط تأیید ورود</div>
              <div className="text-sm text-surface-300">{signal.confirmation_condition}</div>
            </div>
            <div className="p-3 glass-card md:col-span-2">
              <div className="text-[10px] text-surface-500 mb-1">7. علت و منطق</div>
              <div className="text-sm text-surface-200">{signal.reason}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">8. شرایط فسخ سیگنال</div>
              <div className="text-sm text-accent-amber">{signal.invalidation}</div>
            </div>
            <div className="p-3 glass-card">
              <div className="text-[10px] text-surface-500 mb-1">9. مدیریت پس از ورود</div>
              <div className="text-sm text-surface-300">{signal.trailing_stop}</div>
            </div>
          </div>

          {/* Gate Results */}
          {signal.gate_results && signal.gate_results.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold text-surface-400 mb-2">نتایج دروازه‌های تصمیم‌گیری</div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {signal.gate_results.map((gate, i) => (
                  <div key={i} className={`p-2 rounded-lg text-xs border ${
                    gate.verdict === "pass" ? "border-accent-emerald/30 bg-accent-emerald/5" :
                    gate.verdict === "warn" ? "border-accent-amber/30 bg-accent-amber/5" :
                    "border-accent-rose/30 bg-accent-rose/5"
                  }`}>
                    <div className="font-bold text-surface-300">{gate.gate}</div>
                    <div className={`mt-0.5 ${
                      gate.verdict === "pass" ? "text-accent-emerald" :
                      gate.verdict === "warn" ? "text-accent-amber" : "text-accent-rose"
                    }`}>
                      {gate.verdict === "pass" ? "✓ عبور" : gate.verdict === "warn" ? "⚠ هشدار" : "✕ مسدود"}
                    </div>
                    <div className="text-[10px] text-surface-500 mt-0.5">{gate.reason}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Confidence Factors */}
          {signal.confidence_factors && Object.keys(signal.confidence_factors).length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold text-surface-400 mb-2">عوامل اطمینان</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(signal.confidence_factors).map(([key, val]) => (
                  <div key={key} className="px-2 py-1 rounded-lg bg-surface-800/50 text-[10px]">
                    <span className="text-surface-500">{key}: </span>
                    <span className="text-surface-300 font-mono">{(val * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Vote Scores */}
          {signal.vote_direction_scores && Object.keys(signal.vote_direction_scores).length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold text-surface-400 mb-2">امتیازات رأی ({signal.vote_strategy})</div>
              <div className="flex gap-3">
                {Object.entries(signal.vote_direction_scores).map(([dir, score]) => (
                  <div key={dir} className="text-center">
                    <div className="text-[10px] text-surface-500">{DIRECTION_LABELS[dir] || dir}</div>
                    <div className="text-sm font-mono font-bold text-surface-200">{(score * 100).toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Confidence Notes */}
          {signal.confidence_notes && signal.confidence_notes.length > 0 && (
            <div>
              <div className="text-xs font-bold text-surface-400 mb-2">یادداشت‌های اطمینان</div>
              <ul className="text-xs text-surface-400 space-y-1">
                {signal.confidence_notes.map((note, i) => (
                  <li key={i}>• {note}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

const MARKET_ICONS: Record<string, string> = {
  stock: "📈", gold: "🪙", currency: "💵", crypto: "₿",
  option: "🎯", commodity: "🛢️", ime: "🏭",
};
