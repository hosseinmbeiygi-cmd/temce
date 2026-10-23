"use client";

/**
 * Macro posture for gold — real yield (10Y TIPS), broad dollar index and the
 * gold trend, evaluated by ``GET /gold/analytics/macro/live``.
 *
 * The API only exposes the *latest* stored observation per indicator. There is
 * no historical-series endpoint for TIPS, DXY or CFTC COT yet, so this section
 * deliberately renders point values (and marks DXY percentile as unavailable)
 * instead of inventing a chart from a single point.
 */

import { useQuery } from "@tanstack/react-query";
import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import { getMacroPosture } from "@/lib/goldApi";
import { cn } from "@/lib/cn";
import type { MacroLiveResponse } from "@/types/gold";

const MISSING_LABELS: Record<string, string> = {
  tips_yield: "بازده واقعی ۱۰ ساله (TIPS)",
  tips_yield_stale: "بازده واقعی TIPS کهنه است",
  dxy_index: "شاخص دلار (DXY)",
  dxy_index_stale: "شاخص دلار کهنه است",
  gold_trend: "روند طلا",
  posture_computation_failed: "مدل وضعیت کلان",
};

const SIGNAL_LABELS: Record<string, string> = {
  ACCOMMODATIVE: "انبساطی — محرک صعودی",
  RESTRICTIVE: "انقباضی — فشار نزولی",
  NEUTRAL: "خنثی",
  WEAK: "ضعیف — مساعد طلا",
  STRONG: "قوی — فشار نزولی",
};

const POSTURE_STYLE: Record<string, string> = {
  BULLISH: "bg-emerald-950/40 text-emerald-300 ring-emerald-700/40",
  BEARISH: "bg-rose-950/40 text-rose-300 ring-rose-700/40",
  NEUTRAL: "bg-amber-950/40 text-amber-300 ring-amber-700/40",
};

const POSTURE_LABEL: Record<string, string> = {
  BULLISH: "صعودی",
  BEARISH: "نزولی",
  NEUTRAL: "خنثی",
};

const TREND_LABEL: Record<string, string> = {
  up: "صعودی",
  down: "نزولی",
  sideways: "خنثی",
};

const fmt = (value: number | null | undefined, digits = 2): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

function ageLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  if (seconds < 3_600) return `${fmt(seconds / 60, 0)} دقیقه پیش`;
  if (seconds < 86_400) return `${fmt(seconds / 3_600, 1)} ساعت پیش`;
  return `${fmt(seconds / 86_400, 1)} روز پیش`;
}

function isServiceUnavailable(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /\b503\b/.test(message);
}

function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border p-3" style={{ borderColor: "var(--gd-border)" }}>
      <div className="text-[11px] text-zinc-500">{label}</div>
      <div className={cn("mt-1 font-mono text-lg text-zinc-100", tone)}>{value}</div>
      {hint && <div className="mt-1 text-[10px] leading-4 text-zinc-500">{hint}</div>}
    </div>
  );
}

function PostureContent({ data }: { data: MacroLiveResponse }) {
  const posture = data.posture;
  if (!data.available || !posture) {
    return (
      <div className="space-y-2 rounded-xl border border-amber-800/40 bg-amber-950/20 p-4 text-xs text-amber-200">
        <p className="font-semibold">وضعیت کلان فعلاً قابل محاسبه نیست.</p>
        <p className="text-amber-200/80">
          ورودی‌های غایب یا کهنه:{" "}
          {data.missing.length > 0
            ? data.missing.map((key) => MISSING_LABELS[key] ?? key).join(" · ")
            : "نامشخص"}
        </p>
        {data.error && <p className="text-amber-200/70">خطای مدل: {data.error}</p>}
        <p className="text-[11px] text-amber-200/60">
          هیچ عدد جایگزینی ساخته نمی‌شود؛ تا زمانی که فید FRED مقدار تازه نداشته باشد
          وضعیت خنثی نمایش داده نمی‌شود.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs font-semibold ring-1",
            POSTURE_STYLE[posture.posture] ?? "bg-zinc-900/40 text-zinc-300 ring-zinc-700/40",
          )}
        >
          وضعیت: {POSTURE_LABEL[posture.posture] ?? posture.posture}
        </span>
        <span className="text-[11px] text-zinc-500">
          امتیاز مرکب: {fmt(posture.composite_score, 0)}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="بازده واقعی ۱۰ ساله (TIPS)"
          value={`${fmt(posture.tips_yield)}٪`}
          hint={SIGNAL_LABELS[posture.real_yield_signal] ?? posture.real_yield_signal}
        />
        <StatCard
          label="شاخص دلار (DXY)"
          value={fmt(posture.dxy_index)}
          hint={SIGNAL_LABELS[posture.dxy_signal] ?? posture.dxy_signal}
        />
        <StatCard
          label="روند طلا"
          value={TREND_LABEL[posture.gold_trend] ?? posture.gold_trend}
          hint={`امتیاز ${fmt(posture.trend_score, 0)}`}
        />
        <StatCard
          label="درصدک DXY"
          value="—"
          hint="نیازمند سری تاریخی است؛ اندپوینت سری زمانی DXY وجود ندارد."
        />
      </div>

      <ul className="space-y-1 text-xs text-zinc-400">
        {posture.reasons.map((reason) => (
          <li key={reason}>• {reason}</li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-3 text-[11px] text-zinc-500">
        <span>TIPS: {ageLabel(data.tips_staleness_seconds)}</span>
        <span>DXY: {ageLabel(data.dxy_staleness_seconds)}</span>
        <span>روند: {ageLabel(data.trend_staleness_seconds)}</span>
        {data.high_vol_window && (
          <span className="text-rose-300">پنجرهٔ پرنوسان (CPI/NFP/FOMC) فعال است</span>
        )}
        {posture.divergence && (
          <span className="text-amber-300">واگرایی روند طلا با بازده واقعی</span>
        )}
      </div>

      <p className="text-[11px] leading-5 text-zinc-500">
        موقعیت‌های هفتگی CFTC (COT) و نمودار تاریخی بازده واقعی ذخیره می‌شوند، اما
        اندپوینت خواندنی برای آن‌ها وجود ندارد؛ بنابراین در این صفحه نمودار رسم
        نمی‌شود تا سری ساختگی تولید نشود.
      </p>
    </div>
  );
}

export default function MacroPostureSection() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "macro", "posture"],
    queryFn: getMacroPosture,
    refetchInterval: 5 * 60_000,
    retry: 1,
  });

  return (
    <section className="space-y-3" data-testid="macro-posture">
      <h2 className="text-sm font-semibold text-zinc-300">وضعیت کلان طلا</h2>

      {isLoading && <SkeletonBlock visible className="h-40 w-full" />}

      {isError &&
        (isServiceUnavailable(error) ? (
          <div
            data-testid="macro-posture-503"
            className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-xs text-rose-300"
          >
            سرویس تحلیل کلان موقتاً در دسترس نیست (۵۰۳). مقدار جایگزین نمایش داده
            نمی‌شود؛ چند دقیقه بعد دوباره تلاش کنید.
          </div>
        ) : (
          <div className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-xs text-rose-300">
            دریافت وضعیت کلان ناموفق بود. اتصال API را بررسی کنید.
          </div>
        ))}

      {data && <PostureContent data={data} />}
    </section>
  );
}
