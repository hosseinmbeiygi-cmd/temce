"use client";

import { useMemo, useEffect } from "react";
import { analyzeFund, Fund, FundAnalysis } from "@/lib/fund-analysis";

// ── Helpers ───────────────────────────────────────────────────────

function formatNum(v: number): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function scoreColor(s: number): string {
  if (s >= 75) return "text-accent-emerald";
  if (s >= 60) return "text-primary-300";
  if (s >= 40) return "text-accent-amber";
  return "text-accent-rose";
}

function recLabel(r: string): string {
  switch (r) {
    case "STRONG_BUY": return "خرید قوی";
    case "BUY": return "خرید";
    case "WATCHLIST": return "واچ‌لیست";
    case "HOLD": return "نگهداری";
    case "REDUCE": return "کاهش";
    case "SELL": return "فروش";
    case "AVOID": return "اجتناب";
    default: return "—";
  }
}

function recColor(r: string): string {
  switch (r) {
    case "STRONG_BUY": case "BUY": return "text-accent-emerald";
    case "WATCHLIST": return "text-primary-300";
    case "HOLD": return "text-accent-amber";
    case "REDUCE": case "SELL": case "AVOID": return "text-accent-rose";
    default: return "text-surface-400";
  }
}

// ── MiniScoreBar ──

function MiniScoreBar({ label, value, max }: { label: string; value: number; max?: number }) {
  const pct = max ? (value / max) * 100 : value;
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[8px]">
        <span className="text-surface-500">{label}</span>
        <span className={`font-mono font-bold ${scoreColor(value)}`}>{value}%</span>
      </div>
      <div className="h-1 bg-surface-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${Math.max(2, pct)}%`,
            backgroundColor: value >= 75 ? "#10b981" : value >= 60 ? "#6366f1" : value >= 40 ? "#f59e0b" : "#ef4444",
          }}
        />
      </div>
    </div>
  );
}

// ── Main Component ──

interface FundCompareModalProps {
  funds: Fund[];
  onClose: () => void;
  onRemove?: (symbol: string) => void;
}

export default function FundCompareModal({ funds, onClose, onRemove }: FundCompareModalProps) {
  const analyses = useMemo(() => funds.map(analyzeFund), [funds]);

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

  const entries: { label: string; render: (a: FundAnalysis, f: Fund) => React.ReactNode }[] = [
    {
      label: "امتیاز کل",
      render: (a) => <span className={`font-bold text-lg ${scoreColor(a.scores.total)}`}>{a.scores.total}%</span>,
    },
    {
      label: "توصیه",
      render: (a) => <span className={`font-bold text-sm ${recColor(a.recommendation)}`}>{recLabel(a.recommendation)}</span>,
    },
    {
      label: "سطح ریسک",
      render: (a) => (
        <span className={`text-xs font-bold ${a.riskLevel === "LOW" ? "text-accent-emerald" : a.riskLevel === "MEDIUM" ? "text-accent-amber" : "text-accent-rose"}`}>
          {a.riskLevel === "LOW" ? "کم" : a.riskLevel === "MEDIUM" ? "متوسط" : a.riskLevel === "HIGH" ? "زیاد" : "بحرانی"}
        </span>
      ),
    },
    {
      label: "NAV",
      render: (_, f) => <span className="font-mono text-sm text-surface-200">{f.nav.toLocaleString("fa-IR")}</span>,
    },
    {
      label: "تغییرات",
      render: (_, f) => (
        <span className={`font-mono text-sm ${f.nav_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
          {f.nav_change_pct >= 0 ? "+" : ""}{f.nav_change_pct?.toFixed(2)}%
        </span>
      ),
    },
    {
      label: "حجم",
      render: (_, f) => <span className="font-mono text-xs text-surface-400">{formatNum(f.trade_volume)}</span>,
    },
    {
      label: "ارزش بازار",
      render: (_, f) => <span className="font-mono text-xs text-primary-300">{formatNum(f.market_value)}</span>,
    },
    {
      label: "واحد",
      render: (_, f) => <span className="font-mono text-xs text-surface-400">{formatNum(f.shares_count)}</span>,
    },
  ];

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={handleBackdrop}
      dir="rtl"
    >
      <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-surface-700/50 bg-surface-900 shadow-2xl">
        {/* ── Header ── */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 bg-surface-900/95 backdrop-blur border-b border-surface-800 rounded-t-2xl">
          <div className="flex items-center gap-2">
            <span className="material-icons text-primary-400 text-lg">compare_arrows</span>
            <span className="text-sm font-bold text-surface-200">مقایسه صندوق‌ها</span>
            <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full">{funds.length} صندوق</span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-surface-500 hover:text-surface-200 hover:bg-surface-800 transition-all">
            <span className="material-icons text-sm">close</span>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="p-4 overflow-x-auto">
          <table className="w-full text-right" dir="rtl">
            <thead>
              <tr className="border-b border-surface-700/50">
                <th className="sticky right-0 bg-surface-900 px-3 py-2 text-[9px] font-medium text-surface-500 min-w-[80px]">معیار</th>
                {funds.map((f) => (
                  <th key={f.symbol} className="px-3 py-2 text-center min-w-[120px]">
                    <div className="flex items-center justify-center gap-1">
                      <span className="font-bold text-primary-300 text-xs">{f.symbol}</span>
                      {onRemove && (
                        <button
                          onClick={() => onRemove(f.symbol)}
                          className="p-0.5 rounded text-surface-600 hover:text-accent-rose transition-all"
                        >
                          <span className="material-icons text-[10px]">close</span>
                        </button>
                      )}
                    </div>
                    <p className="text-[8px] text-surface-500 truncate max-w-[100px]">{f.name || ""}</p>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.label} className="border-b border-surface-800/30">
                  <td className="sticky right-0 bg-surface-900 px-3 py-2.5 text-[9px] font-medium text-surface-500">{entry.label}</td>
                  {analyses.map((a, i) => (
                    <td key={funds[i]?.symbol ?? i} className="px-3 py-2.5 text-center">
                      {entry.render(a, funds[i])}
                    </td>
                  ))}
                </tr>
              ))}

              {/* ── Score bars ── */}
              {["total", "financial", "liquidity", "management", "risk", "cost", "transparency"].map((key) => (
                <tr key={key} className="border-b border-surface-800/20">
                  <td className="sticky right-0 bg-surface-900 px-3 py-2 text-[9px] text-surface-500">
                    {key === "total" ? "امتیاز کل" : key === "financial" ? "مالی" : key === "liquidity" ? "نقدشوندگی" : key === "management" ? "مدیریت" : key === "risk" ? "ریسک" : key === "cost" ? "هزینه" : "شفافیت"}
                  </td>
                  {analyses.map((a, i) => (
                    <td key={i} className="px-3 py-2">
                      <MiniScoreBar
                        label=""
                        value={(a.scores as unknown as Record<string, number>)[key] ?? 0}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ── Footer ── */}
        <div className="sticky bottom-0 px-4 py-2.5 bg-surface-900/95 backdrop-blur border-t border-surface-800 rounded-b-2xl flex items-center justify-between">
          <span className="text-[8px] text-surface-600">مقایسه هوشمند صندوق‌ها بر اساس ۶ بعد تحلیلی</span>
          <button onClick={onClose} className="text-[10px] px-3 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg transition-all">
            بستن
          </button>
        </div>
      </div>
    </div>
  );
}
