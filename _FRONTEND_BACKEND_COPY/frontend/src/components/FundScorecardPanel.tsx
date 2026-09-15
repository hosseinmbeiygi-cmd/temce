"use client";

/**
 * FundScorecardPanel — کارت امتیازدهی ۵ لایه (پرامپت ماژول ۲).
 * شامل: گیج ۰-۱۰۰ (رنگ داینامیک + برچسب ۵ سطحی)، رادار ۶ بعدی،
 * Reason Vector فارسی (rule-based روی داده واقعی — بدون اختراع LLM)
 * و نوار ریسک ابطال/نقدشوندگی.
 */

import { useMemo } from "react";
import FundScoreRadar from "@/components/FundScoreRadar";
import { Card } from "@/components/ui/Card";
import { calcBubble } from "@/lib/fund-categories";
import type { Fund, FundIssue, FundScore } from "@/lib/fund-analysis";

interface FundScorecardPanelProps {
  fund: Fund;
  scores: FundScore;
  issues: FundIssue[];
}

// ── گیج ──────────────────────────────────────────────────────────────────────

const LEVELS: { min: number; label: string; color: string }[] = [
  { min: 75, label: "خرید قوی", color: "#10b981" },
  { min: 60, label: "خرید", color: "#06b6d4" },
  { min: 45, label: "نگهداری", color: "#f59e0b" },
  { min: 30, label: "احتیاط", color: "#f43f5e" },
  { min: 0, label: "اجتناب", color: "#9f1239" },
];

function levelOf(score: number) {
  return LEVELS.find((l) => score >= l.min) ?? LEVELS[LEVELS.length - 1];
}

function Gauge({ score }: { score: number }) {
  const lvl = levelOf(score);
  const RADIUS = 62;
  const CIRC = Math.PI * RADIUS; // نیم‌دایره (۱۸۰°)
  const filled = (Math.max(0, Math.min(100, score)) / 100) * CIRC;
  const needle = -90 + (Math.max(0, Math.min(100, score)) / 100) * 180;

  return (
    <div className="relative w-[180px] h-[110px] mx-auto" dir="ltr">
      <svg viewBox="0 0 140 90" className="w-full">
        <path
          d="M 10 80 A 60 60 0 0 1 130 80"
          fill="none"
          stroke="rgba(100,116,139,0.2)"
          strokeWidth="11"
          strokeLinecap="round"
        />
        <path
          d="M 10 80 A 60 60 0 0 1 130 80"
          fill="none"
          stroke={lvl.color}
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${CIRC}`}
          style={{ transition: "stroke-dasharray 0.8s ease, stroke 0.4s ease" }}
        />
        {/* needle */}
        <line
          x1="70"
          y1="80"
          x2={70 + 45 * Math.cos(((needle - 90) * Math.PI) / 180)}
          y2={80 + 45 * Math.sin(((needle - 90) * Math.PI) / 180)}
          stroke="#e2e8f0"
          strokeWidth="2"
          strokeLinecap="round"
          style={{ transition: "all 0.8s ease" }}
        />
        <circle cx="70" cy="80" r="4" fill="#e2e8f0" />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <span className="font-mono text-[28px] font-black leading-none" style={{ color: lvl.color }}>
          {score}
        </span>
        <span className="block text-[9px] font-bold mt-0.5" style={{ color: lvl.color }}>
          {lvl.label}
        </span>
      </div>
    </div>
  );
}

// ── Reason Vector (rule-based روی داده واقعی) ───────────────────────────────

interface Reason {
  text: string;
  badges: string[]; // [P/NAV: -1.8%] [Liquidity: 92]
  tone: "pos" | "neg" | "warn";
}

function fmt(v: number): string {
  return v.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

export default function FundScorecardPanel({ fund, scores, issues }: FundScorecardPanelProps) {
  const bubble = calcBubble(fund.price_last, fund.nav);
  const bubbleFlag = bubble !== null ? (bubble > 3 ? "hot" : bubble < -2 ? "cold" : "flat") : "none";

  const reasons = useMemo<Reason[]>(() => {
    const out: Reason[] = [];

    // ۱. حباب P/NAV (override اولویت‌دار)
    if (bubble !== null) {
      if (bubble > 3) {
        out.push({
          text: `قیمت بازار ${bubble.toFixed(2)}٪ بالاتر از NAV است؛ طبق قاعده «حباب > +۳٪» سقف سیگنال «اجتناب از خرید» اعمال می‌شود.`,
          badges: [`P/NAV: ${bubble > 0 ? "+" : ""}${bubble.toFixed(1)}٪`],
          tone: "warn",
        });
      } else if (bubble < -2) {
        out.push({
          text: `صندوق با تخفیف ${bubble.toFixed(2)}٪ نسبت به NAV معامله می‌شود — کاندید ورود در صورت سلامت سایر ابعاد.`,
          badges: [`P/NAV: ${bubble.toFixed(1)}٪`],
          tone: "pos",
        });
      }
    }

    // ۲. ابعاد امتیاز — بالا و پایین
    const dims: { key: keyof Omit<FundScore, "total">; label: string; neg: string; pos: string }[] = [
      { key: "financial", label: "مالی", neg: "بازدهی تعدیل‌نشده ضعیف است", pos: "عملکرد مالی مناسب" },
      { key: "liquidity", label: "نقدشوندگی", neg: "نقدشوندگی پایین — خروج سخت", pos: "نقدشوندگی خوب" },
      { key: "management", label: "مدیریت", neg: "امتیاز مدیریت پایین", pos: "مدیریت پایدار" },
      { key: "risk", label: "ریسک", neg: "ریسک بالا (نوسان/افت)", pos: "ریسک کنترل‌شده" },
      { key: "cost", label: "هزینه", neg: "هزینه‌ها (کارمزد/صرف) بالاست", pos: "هزینه رقابتی" },
      { key: "transparency", label: "شفافیت", neg: "شفافیت گزارش‌دهی پایین", pos: "شفافیت خوب" },
    ];
    for (const d of dims) {
      const v = scores[d.key];
      if (v >= 70) {
        out.push({ text: `${d.pos} — امتیاز ${d.label} بالای آستانه ۷۰.`, badges: [`${d.label}: ${v}`], tone: "pos" });
      } else if (v < 40) {
        out.push({ text: `${d.neg} — امتیاز ${d.label} زیر آستانه ۴۰.`, badges: [`${d.label}: ${v}`], tone: "neg" });
      }
    }

    // ۳. فشار ابطال / جریان نقدینگی
    const totalReal = fund.buy_real_volume + fund.sell_real_volume;
    if (totalReal > 0) {
      const sellRatio = fund.sell_real_volume / totalReal;
      if (sellRatio > 0.6) {
        out.push({
          text: `سهم فروش حقیقی‌ها ${(sellRatio * 100).toFixed(0)}٪ از کل جریان است — فشار ابطال/فروش محسوس.`,
          badges: [`فروش حقیقی: ${fmt(fund.sell_real_volume)}`, `خرید حقیقی: ${fmt(fund.buy_real_volume)}`],
          tone: "warn",
        });
      } else if (sellRatio < 0.4) {
        out.push({
          text: `سهم خرید حقیقی‌ها ${((1 - sellRatio) * 100).toFixed(0)}٪ است — جریان ورود پول مثبت.`,
          badges: [`خرید حقیقی: ${fmt(fund.buy_real_volume)}`],
          tone: "pos",
        });
      }
    }

    // ۴. حجم معاملات
    if (fund.trade_value > 0 && fund.trade_value < 1_000_000_000) {
      out.push({
        text: `ارزش معاملات روزانه ${fmt(fund.trade_value / 1_000_000)} میلیون ریال — نقدشوندگی در مقیاس ورود/خروج بزرگ کافی نیست.`,
        badges: [`حجم: ${fmt(fund.trade_value)}`],
        tone: "warn",
      });
    }

    // ۵. معیارهای NAV
    if (fund.nav_source !== "nav_record") {
      out.push({
        text: "NAV تقریبی (جانشین قیمت) است — صرف/کسر و حباب دقیق نیستند؛ قبل از تصمیم به NAV رسمی فیپیران رجوع کنید.",
        badges: ["NAV: تقریبی"],
        tone: "warn",
      });
    }

    // ۶. مسائل اولویت‌دار
    const a1 = issues.filter((i) => i.priority === "A1").slice(0, 2);
    for (const i of a1) {
      out.push({ text: `${i.title} — ${i.description}`, badges: [`اولویت ${i.priority}`], tone: "warn" });
    }

    return out.slice(0, 5);
  }, [fund, scores, issues, bubble]);

  // نوار فشار ابطال
  const totalReal = fund.buy_real_volume + fund.sell_real_volume;
  const sellPct = totalReal > 0 ? (fund.sell_real_volume / totalReal) * 100 : 50;
  const pressureTone = sellPct > 60 ? "warn" : sellPct < 40 ? "pos" : "flat";

  return (
    <Card title="کارت امتیازدهی صندوق" subtitle="موتور امتیازدهی ۶ بعدی + بردار دلایل">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* گیج */}
        <div className="flex flex-col items-center justify-center">
          <Gauge score={scores.total} />
          <div className="flex items-center gap-1 mt-2 flex-wrap justify-center">
            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold text-accent-emerald bg-accent-emerald/15">
              {bubbleFlag === "hot" ? "حالت هشدار حباب" : bubbleFlag === "cold" ? "تخفیف نسبت به NAV" : bubbleFlag === "flat" ? "P/NAV متعادل" : "P/NAV نامعلوم"}
            </span>
            {fund.nav_source !== "nav_record" && (
              <span className="px-2 py-0.5 rounded-full text-[9px] font-bold text-accent-amber bg-accent-amber/15">NAV تقریبی</span>
            )}
          </div>
        </div>

        {/* رادار */}
        <div className="flex items-center justify-center">
          <FundScoreRadar scores={scores} size={240} />
        </div>

        {/* Reason Vector */}
        <div className="flex flex-col">
          <p className="text-[10px] font-black text-ink mb-2 flex items-center gap-1.5">
            <span className="material-icons text-sm text-primary-400">psychology_alt</span>
            بردار دلایل هوش مصنوعی
          </p>
          <div className="space-y-2">
            {reasons.map((r, i) => (
              <div
                key={i}
                className={`rounded-xl px-3 py-2 border text-[10px] leading-relaxed ${
                  r.tone === "pos"
                    ? "bg-accent-emerald/10 border-accent-emerald/20 text-emerald-200"
                    : r.tone === "warn"
                    ? "bg-accent-amber/10 border-accent-amber/20 text-amber-200"
                    : "bg-rose-500/10 border-rose-500/20 text-rose-200"
                }`}
              >
                <div className="flex flex-wrap gap-1 mb-1">
                  {r.badges.map((b, j) => (
                    <span key={j} className="text-[8px] font-mono font-bold px-1.5 py-0.5 rounded bg-black/30" dir="ltr">
                      {b}
                    </span>
                  ))}
                </div>
                <span className="text-ink-2">{r.text}</span>
              </div>
            ))}
          </div>

          {/* نوار فشار ابطال */}
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] text-ink-3">فشار ابطال / فروش حقیقی</span>
              <span className={`text-[9px] font-mono font-bold ${
                pressureTone === "warn" ? "text-amber-300" : pressureTone === "pos" ? "text-emerald-300" : "text-ink-2"
              }`}>
                {totalReal > 0 ? `${sellPct.toFixed(0)}٪` : "—"}
              </span>
            </div>
            <div className="h-1.5 bg-soft rounded-full overflow-hidden" dir="ltr">
              <div
                className={`h-full rounded-full transition-all duration-700 ${
                  pressureTone === "warn" ? "bg-amber-500" : pressureTone === "pos" ? "bg-emerald-500" : "bg-zinc-600"
                }`}
                style={{ width: `${totalReal > 0 ? sellPct : 50}%` }}
              />
            </div>
            <p className="text-[8px] text-ink-3 mt-1">
              {totalReal > 0
                ? pressureTone === "warn"
                  ? "هشدار: خروج پول حقیقی غالب است — ریسک نقدشوندگی"
                  : pressureTone === "pos"
                  ? "جریان ورود پول حقیقی غالب است"
                  : "جریان خرید/فروش حقیقی متعادل"
                : "داده جریان حقیقی/حقوقی در دسترس نیست"}
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}