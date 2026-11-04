import { DataTrustBadge } from "@/components/gold/DataTrustBadge";
import type { Phase1Quality } from "@/types/phase1";

import { MISSING, gapTitle, sourceTime } from "./format";

/** «—» با tooltip دلیل؛ مقدار ناموجود هرگز صفر نمایش داده نمی‌شود. */
export function MissingValue({
  reason,
  testId = "missing-value",
}: {
  reason?: string;
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      title={reason}
      className="text-zinc-500"
      aria-label={reason ? `ناموجود: ${reason}` : "ناموجود"}
    >
      {MISSING}
    </span>
  );
}

/** منبع + زمان مشاهده، درست زیر خودِ سلول قیمت. */
export function SourceStamp({
  source,
  asOf,
  gaps,
}: {
  source: string;
  asOf: string | null;
  gaps?: string[];
}) {
  const stamp = sourceTime(asOf);
  return (
    <div
      className="mt-0.5 text-[9px] leading-4 text-zinc-500"
      title={gapTitle(gaps)}
      data-testid="source-stamp"
    >
      {source} · {stamp ?? "زمان: نامشخص"}
    </div>
  );
}

export function QualityCell({
  quality,
  source,
  asOf,
  gaps,
}: {
  quality: Phase1Quality;
  source: string;
  asOf: string | null;
  gaps?: string[];
}) {
  return (
    <div title={gapTitle(gaps)}>
      <DataTrustBadge quality={quality} source={source} asOf={asOf} />
    </div>
  );
}
