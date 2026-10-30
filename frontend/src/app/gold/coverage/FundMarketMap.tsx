"use client";

import Link from "next/link";

import type { FundMapCell, FundMapResponse, FundMapSummary } from "@/types/phase2";

import { MISSING, faNumber, faPercent } from "../terminal/format";
import { SourceNotice } from "./SectionFeedback";

const METRIC_LABEL: Record<FundMapResponse["size_metric"], string> = {
  trade_value: "ارزش معاملات",
  market_value: "ارزش بازار",
};

/**
 * رنگ سلول از بازده روزانه. مقیاس و قدرمطلق همیشه گارد می‌شوند تا
 * تقسیم بر صفر یا Infinity به style نرسد.
 */
export function heatColor(changePct: number | null | undefined, scalePct: number): string {
  if (
    changePct === null ||
    changePct === undefined ||
    !Number.isFinite(changePct) ||
    !Number.isFinite(scalePct) ||
    scalePct <= 0
  ) {
    return "rgba(63, 63, 70, 0.55)";
  }
  const ratio = Math.max(-1, Math.min(1, changePct / scalePct));
  const alpha = 0.16 + 0.58 * Math.abs(ratio);
  return ratio >= 0
    ? `rgba(16, 185, 129, ${alpha.toFixed(3)})`
    : `rgba(244, 63, 94, ${alpha.toFixed(3)})`;
}

/** سهم اندازه؛ مقادیر غیرمتناهی یا منفی هرگز به flex-grow نمی‌رسند. */
export function safeShare(sharePct: number | null | undefined): number {
  if (sharePct === null || sharePct === undefined || !Number.isFinite(sharePct) || sharePct <= 0) {
    return 1;
  }
  return Math.min(100, sharePct);
}

function safeBarWidth(sharePct: number | null | undefined): string {
  if (sharePct === null || sharePct === undefined || !Number.isFinite(sharePct)) return "0%";
  return `${Math.max(0, Math.min(100, sharePct))}%`;
}

function FundTile({ cell, scalePct }: { cell: FundMapCell; scalePct: number }) {
  return (
    <Link
      href={cell.href}
      data-testid={`fund-map-cell-${cell.symbol}`}
      data-share={cell.size_share_pct ?? ""}
      title={cell.data_gaps.length > 0 ? cell.data_gaps.join("؛ ") : cell.name}
      className="group flex min-h-[84px] min-w-[110px] flex-col justify-between rounded-lg border border-zinc-700/60 p-2.5 transition hover:border-amber-400/60"
      style={{
        flexGrow: safeShare(cell.size_share_pct),
        flexBasis: 0,
        background: heatColor(cell.change_pct, scalePct),
      }}
    >
      <div className="flex items-start justify-between gap-1">
        <span className="truncate text-[11px] font-semibold text-zinc-100">{cell.name}</span>
        <span className="shrink-0 text-[9px] text-zinc-300/80">{cell.symbol}</span>
      </div>
      <div className="mt-2">
        <div className="tabular-nums text-xs font-bold text-zinc-50">
          {cell.change_pct === null ? MISSING : faPercent(cell.change_pct)}
        </div>
        <div className="mt-0.5 text-[9px] text-zinc-200/80">
          سهم: {cell.size_share_pct === null ? MISSING : `${faNumber(cell.size_share_pct, 1)}٪`}
        </div>
      </div>
    </Link>
  );
}

function SummaryBar({
  label,
  value,
  sharePct,
  testId,
  tone,
}: {
  label: string;
  value: number;
  sharePct: number | null;
  testId: string;
  tone: string;
}) {
  return (
    <li data-testid={testId} className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-[11px]">
        <span className="truncate text-zinc-300">{label}</span>
        <span className="shrink-0 tabular-nums text-zinc-400">
          {faNumber(value)} <span className="text-[9px]">ریال</span>
          {" · "}
          {sharePct === null ? MISSING : `${faNumber(sharePct, 1)}٪`}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${tone}`}
          style={{ width: safeBarWidth(sharePct) }}
        />
      </div>
    </li>
  );
}

function FundValueSummary({ summary }: { summary: FundMapSummary }) {
  const bars = summary.items.length + (summary.other_value > 0 ? 1 : 0);
  return (
    <div
      data-testid="fund-summary"
      className="rounded-xl border border-zinc-800/70 bg-zinc-950/40 p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-200">
          جمع {METRIC_LABEL[summary.size_metric]}
        </h3>
        <p className="tabular-nums text-sm font-bold text-zinc-100" data-testid="fund-map-total">
          {faNumber(summary.total_value)} <span className="text-[10px] text-zinc-500">ریال</span>
        </p>
      </div>
      <p className="mt-1 text-[10px] text-zinc-500">
        {faNumber(summary.cells_count)} صندوق در نقشه · {faNumber(bars)} سهم در نمودار
      </p>

      {summary.total_value <= 0 || bars === 0 ? (
        <p className="mt-3 text-xs text-zinc-500">
          منبع IME برای این معیار عدد مثبتی برنگردانده است؛ نمودار ساخته نمی‌شود.
        </p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {summary.items.map((item, index) => (
            <SummaryBar
              key={item.symbol ?? `${item.label}-${index}`}
              label={item.label || item.symbol || MISSING}
              value={item.value}
              sharePct={item.share_pct}
              testId={`fund-summary-bar-${item.symbol ?? index}`}
              tone={index === 0 ? "bg-amber-400" : "bg-zinc-500"}
            />
          ))}
          {summary.other_value > 0 && (
            <SummaryBar
              label="سایر"
              value={summary.other_value}
              sharePct={summary.other_share_pct}
              testId="fund-summary-bar-other"
              tone="bg-zinc-600"
            />
          )}
        </ul>
      )}
    </div>
  );
}

/**
 * نقشهٔ بازار صندوق‌ها (heatmap) + جمع ارزش.
 *
 * اندازهٔ کاشی = سهم ارزش معاملات/بازار، رنگ = بازده روزانه روی مقیاس ±٪۴.
 * کلیک روی هر صندوق به ردیف همان صندوق در جدول فاز ۱ می‌رود و آن را هایلایت می‌کند.
 */
export function FundMarketMap({
  data,
  sizeMetric,
  onSizeMetricChange,
  pending,
}: {
  data: FundMapResponse;
  sizeMetric: FundMapResponse["size_metric"];
  onSizeMetricChange: (value: FundMapResponse["size_metric"]) => void;
  pending?: boolean;
}) {
  const scalePct =
    Number.isFinite(data.color_scale_pct) && data.color_scale_pct > 0 ? data.color_scale_pct : 4;

  return (
    <section aria-labelledby="fund-map-heading" className="space-y-3" data-testid="fund-map-section">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="fund-map-heading" className="text-base font-semibold text-zinc-100">
            نقشهٔ بازار صندوق‌های طلا
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            اندازه = {METRIC_LABEL[data.size_metric]} · رنگ = بازده روزانه روی مقیاس ±
            {faNumber(scalePct, 1)}٪. کلیک روی هر کاشی ردیف همان صندوق را در «میز داده»
            نشان می‌دهد.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-zinc-800/70 bg-zinc-900/60 p-1">
          {(["trade_value", "market_value"] as const).map((metric) => (
            <button
              key={metric}
              type="button"
              aria-pressed={sizeMetric === metric}
              data-testid={`size-metric-${metric}`}
              onClick={() => onSizeMetricChange(metric)}
              className={`rounded-md px-3 py-1 text-xs transition ${
                sizeMetric === metric
                  ? "bg-amber-500/20 font-semibold text-amber-300"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {METRIC_LABEL[metric]}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[10px] text-zinc-400" data-testid="fund-map-legend">
        <span>−{faNumber(scalePct, 1)}٪</span>
        {[-scalePct, -scalePct / 2, 0, scalePct / 2, scalePct].map((value) => (
          <span
            key={value}
            aria-hidden="true"
            className="h-3 w-8 rounded-sm border border-zinc-700/60"
            style={{ background: heatColor(value, scalePct) }}
          />
        ))}
        <span>+{faNumber(scalePct, 1)}٪</span>
        <span className="mr-2">· خاکستری = بازده ناموجود</span>
      </div>

      {data.cells.length === 0 ? (
        <SourceNotice tone="warn" testId="fund-map-empty">
          هیچ صندوقی با ارزش معاملات/بازار مثبت از فید IME نیامده است؛ نقشه رسم نمی‌شود.
        </SourceNotice>
      ) : (
        <div
          className={`flex flex-wrap gap-1.5 ${pending ? "opacity-60" : ""}`}
          data-testid="fund-map"
        >
          {data.cells.map((cell) => (
            <FundTile key={cell.symbol || cell.name} cell={cell} scalePct={scalePct} />
          ))}
        </div>
      )}

      <FundValueSummary summary={data.summary} />
    </section>
  );
}
