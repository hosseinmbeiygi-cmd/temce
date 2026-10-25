"use client";

import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import { decisionView } from "@/lib/gold-decision";
import type { Snapshot } from "@/types/gold";

const fmt = (value: number | null | undefined, digits = 0): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const fmtPct = (value: number | null | undefined, digits = 2): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}٪`;
};

interface SummarySectionProps {
  snapshot?: Snapshot;
  isLoading?: boolean;
}

export default function GoldSummarySection({ snapshot, isLoading }: SummarySectionProps) {
  if (isLoading && !snapshot) {
    return <SkeletonBlock visible className="h-48 w-full" />;
  }

  if (!snapshot) {
    return (
      <div className="rounded-lg border border-zinc-700/50 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
        اسنپ‌شات بازار در دسترس نیست.
      </div>
    );
  }

  const refs = snapshot.references;
  const gold18k = snapshot.gold?.gold_18k?.market_price ?? null;
  const melted = snapshot.gold?.gold_melted?.market_price ?? null;

  // F3/C1: decision ناشناخته یا NO_DATA هیچ‌وقت سبز/قرمز نمی‌شود.
  const view = decisionView(snapshot.score.decision);
  const coverage = snapshot.score.data_coverage_pct;

  const cards: Array<{ label: string; value: string; hint?: string }> = [
    { label: "اونس طلا (XAU/USD)", value: fmt(refs.xau_usd, 2), hint: "USD" },
    { label: "دلار آزاد", value: fmt(refs.usd_irt), hint: "ریال" },
    {
      label: "اختلاف درهم با پگ",
      value: fmtPct(refs.aed_gap_pct),
      hint: `AED/IRT ${fmt(refs.aed_irt)}`,
    },
    { label: "طلای ۱۸ عیار (گرم)", value: fmt(gold18k), hint: "ریال" },
    { label: "مثقال طلای آب‌شده", value: fmt(melted), hint: "ریال" },
  ];

  return (
    <section className="gold-summary space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-zinc-300">خلاصه بازار طلا</h2>
        <div className="flex flex-wrap items-center gap-2">
          {coverage !== null && coverage !== undefined && (
            <span
              className="rounded-full px-3 py-1 text-[11px] font-semibold ring-1 ring-zinc-700/40 bg-zinc-900/40 text-zinc-400"
              title="چه سهمی از وزان امتیاز واقعاً داده داشته است"
            >
              پوشش داده: {Math.round(coverage)}٪
            </span>
          )}
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${view.cls}`}
          >
            امتیاز {snapshot.score.total} — {view.label}
          </span>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {cards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl bg-zinc-900/40 p-3 ring-1 ring-zinc-700/50 backdrop-blur"
          >
            <div className="text-[11px] text-zinc-500">{card.label}</div>
            <div className="mt-1 font-mono text-lg text-zinc-100">{card.value}</div>
            {card.hint && <div className="text-[10px] text-zinc-600">{card.hint}</div>}
          </div>
        ))}
      </div>

      <div className="text-[11px] text-zinc-500">
        منبع مرجع: {refs.source} · کیفیت داده: {snapshot.quality_flag}
        {refs.age_seconds ? ` · سن داده: ${fmt(refs.age_seconds)} ثانیه` : ""}
      </div>

      {/* F3: هشدار ثابت و قابل‌دیدن — این ابزار توصیهٔ مالی نیست. */}
      <div className="text-[11px] leading-5 text-zinc-500">
        ابزار تحلیلی، نه توصیهٔ مالی. تصمیم خرید و فروش با خودِ کاربر است.
      </div>

      {view.neutral && (
        <div className="rounded-lg border border-zinc-700/50 bg-zinc-900/40 px-4 py-3 text-xs leading-5 text-zinc-400">
          داده برای داوری کافی نیست — پوشش امتیاز زیر آستانهٔ موتور است. این حالت نه
          سیگنال خرید است نه سیگنال فروش؛ تا تکمیل شدن داده‌ها صبر کنید.
        </div>
      )}

      {snapshot.score.hard_stop_active && (
        <div className="rounded-lg border border-rose-700/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">
          توقف اضطراری فعال است{snapshot.score.hard_stop_reason ? `: ${snapshot.score.hard_stop_reason}` : ""}
        </div>
      )}
    </section>
  );
}
