"use client";

import { DataTrustBadge, normalizeQuality } from "@/components/gold/DataTrustBadge";
import { GoldDisclaimer } from "@/components/gold/GoldDisclaimer";
import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import { decisionView } from "@/lib/gold-decision";
import type { AssetBlock, PriceQuality, ReferenceBlock, Snapshot } from "@/types/gold";

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

const UNIT_LABELS: Record<string, string> = {
  toman: "تومان",
  rial: "ریال",
  ounce: "اونس",
};

interface CardTrust {
  quality: PriceQuality;
  source: string;
  asOf: string | null;
  ageSeconds: number | null;
}

interface SummaryCard {
  label: string;
  value: string;
  hint?: string;
  trust?: CardTrust;
}

function trustFromReference(refs: ReferenceBlock): CardTrust {
  return {
    quality: normalizeQuality(refs.quality),
    source: refs.source,
    asOf: refs.asOf ?? null,
    ageSeconds: refs.age_seconds ?? null,
  };
}

function trustFromAsset(asset?: AssetBlock): CardTrust | undefined {
  if (!asset) return undefined;
  return {
    quality: normalizeQuality(asset.quality),
    source: asset.source,
    asOf: asset.asOf ?? null,
    ageSeconds: null,
  };
}

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
  const gold18k = snapshot.gold?.gold_18k;
  const melted = snapshot.gold?.gold_melted;

  // F3/C1: decision ناشناخته یا NO_DATA هیچ‌وقت سبز/قرمز نمی‌شود.
  const view = decisionView(snapshot.score.decision);
  const coverage = snapshot.score.data_coverage_pct;
  const refTrust = trustFromReference(refs);

  const cards: SummaryCard[] = [
    { label: "اونس طلا (XAU/USD)", value: fmt(refs.xau_usd, 2), hint: "دلار", trust: refTrust },
    {
      label: "دلار آزاد",
      value: fmt(refs.usd_irt),
      hint: UNIT_LABELS[refs.unit ?? "toman"] ?? "تومان",
      trust: refTrust,
    },
    {
      label: "اختلاف درهم با پگ",
      value: fmtPct(refs.aed_gap_pct),
      hint: `AED/IRT ${fmt(refs.aed_irt)}`,
      trust: refTrust,
    },
    {
      label: "طلای ۱۸ عیار (گرم)",
      value: gold18k ? fmt(gold18k.market_price) : "—",
      hint: gold18k ? UNIT_LABELS[gold18k.unit] ?? "تومان" : "داده‌ای نیست",
      trust: trustFromAsset(gold18k),
    },
    {
      label: "مثقال طلای آب‌شده",
      value: melted ? fmt(melted.market_price) : "—",
      hint: melted ? UNIT_LABELS[melted.unit] ?? "تومان" : "داده‌ای نیست",
      trust: trustFromAsset(melted),
    },
    {
      label: "شاخص دلار (DXY)",
      value: refs.dxy_index !== null && refs.dxy_index !== undefined ? fmt(refs.dxy_index, 2) : "—",
      hint: "شاخص",
      trust: refTrust,
    },
  ];

  // هر عددی که کیفیت SAMPLE/EDUCATIONAL دارد باید به‌وضوح «زنده نیست» اعلام شود.
  const hasSimulated = cards.some(
    (card) => card.trust?.quality === "SAMPLE" || card.trust?.quality === "EDUCATIONAL",
  );

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

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] text-zinc-500">کیفیت مراجع بازار:</span>
        <DataTrustBadge
          quality={refs.quality}
          source={refs.source}
          asOf={refs.asOf ?? null}
          ageSeconds={refs.age_seconds ?? null}
        />
      </div>

      {hasSimulated && (
        <div
          role="alert"
          className="rounded-lg border border-rose-500/60 bg-rose-950/40 px-4 py-3 text-xs font-semibold leading-5 text-rose-200"
        >
          بخشی از اعداد این صفحه دادهٔ نمونه یا آموزشی است و قیمت زنده نیست.
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        {cards.map((card) => {
          const simulated =
            card.trust?.quality === "SAMPLE" || card.trust?.quality === "EDUCATIONAL";
          return (
            <div
              key={card.label}
              className={`rounded-xl bg-zinc-900/40 p-3 ring-1 backdrop-blur ${
                simulated ? "ring-2 ring-rose-500/60" : "ring-zinc-700/50"
              }`}
            >
              <div className="text-[11px] text-zinc-500">{card.label}</div>
              <div className="mt-1 font-mono text-lg text-zinc-100">{card.value}</div>
              {card.hint && <div className="text-[10px] text-zinc-600">{card.hint}</div>}
              {card.trust && (
                <DataTrustBadge
                  quality={card.trust.quality}
                  source={card.trust.source}
                  asOf={card.trust.asOf}
                  ageSeconds={card.trust.ageSeconds}
                  className="mt-2"
                />
              )}
            </div>
          );
        })}
      </div>

      <GoldDisclaimer className="mt-2" />

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
