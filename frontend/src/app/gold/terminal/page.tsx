"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { DataTrustBadge, formatAsOf } from "@/components/gold/DataTrustBadge";
import { GoldDisclaimer } from "@/components/gold/GoldDisclaimer";
import { getGoldTerminal, isServiceUnavailable, postGoldWhatIf } from "@/lib/goldApi";
import type { TerminalReferences } from "@/types/phase1";

import { CertificateTable } from "./CertificateTable";
import { GoldFundsTable } from "./GoldFundsTable";
import { Phase1Ticker } from "./Phase1Ticker";
import { PhysicalParityTable } from "./PhysicalParityTable";
import { WhatIfCalculator } from "./WhatIfCalculator";
import { faNumber, gapTitle, sourceTime } from "./format";

/**
 * Phase 1 — میز دادهٔ طلا (parity surface).
 *
 * همهٔ اعداد از `/gold/terminal` می‌آید و با منبع/زمان/کیفیت برچسب می‌خورند.
 * ماشین‌حساب سناریو فقط پیش‌نمایش است و هیچ سفارشی ثبت نمی‌کند.
 */
export default function GoldTerminalPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "terminal"],
    queryFn: getGoldTerminal,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
  });

  const whatIf = useMutation({ mutationFn: postGoldWhatIf });

  const whatIfError = whatIf.isError
    ? isServiceUnavailable(whatIf.error)
      ? "سرویس محاسبهٔ طلا موقتاً در دسترس نیست (۵۰۳)؛ چند لحظه دیگر دوباره تلاش کنید."
      : "محاسبهٔ پیش‌نمایش ناموفق بود."
    : null;

  return (
    <div className="space-y-6" dir="rtl" data-testid="phase1-terminal-page">
      <header className="space-y-2">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">میز داده و برابری طلا</h1>
            <p className="mt-1 text-xs text-zinc-500">
              تیکر بازار، جدول طلا و سکه، صندوق‌ها و گواهی‌ها — همه با ارزش ذاتی موتور
              فاز ۰ و برچسب منبع/زمان/کیفیت.
            </p>
          </div>
          {data && (
            <p className="text-[10px] text-zinc-500" data-testid="terminal-generated-at">
              تولید: {formatAsOf(data.generated_at) ?? "نامشخص"}
            </p>
          )}
        </div>
      </header>

      {isError && (
        <div
          role="alert"
          data-testid="terminal-error"
          className="rounded-lg border px-4 py-3 text-sm"
          style={{
            borderColor: "var(--gd-danger)",
            background: "var(--gd-bg-2)",
            color: "var(--gd-danger)",
          }}
        >
          {isServiceUnavailable(error)
            ? "سرویس دادهٔ طلا موقتاً در دسترس نیست (۵۰۳)؛ چند لحظه دیگر دوباره تلاش کنید."
            : "دریافت میز داده ناموفق بود."}
        </div>
      )}

      {isLoading && (
        <div
          data-testid="terminal-loading"
          className="rounded-xl p-6 text-center text-sm"
          style={{ background: "var(--gd-bg-2)", color: "var(--gd-text-2)" }}
        >
          در حال دریافت داده‌های طلا...
        </div>
      )}

      {data && (
        <>
          <ReferenceStrip references={data.references} />
          <Phase1Ticker items={data.ticker} />
          <WhatIfCalculator
            references={data.references}
            result={whatIf.data ?? null}
            pending={whatIf.isPending}
            error={whatIfError}
            onSubmit={(input) => whatIf.mutate(input)}
          />
          <PhysicalParityTable rows={data.physical} />
          <GoldFundsTable funds={data.funds} />
          <CertificateTable rows={data.certificates} />
          <p
            data-testid="capability-note"
            className="rounded-lg border border-zinc-800/70 bg-zinc-900/40 px-4 py-2 text-[11px] text-zinc-400"
          >
            این میز فقط داده، تحلیل و پیش‌نمایش است؛ سفارش:{" "}
            {data.capabilities.orders ? "فعال" : "غیرفعال"} · کیف پول:{" "}
            {data.capabilities.wallet ? "فعال" : "غیرفعال"} · تحویل:{" "}
            {data.capabilities.delivery ? "فعال" : "غیرفعال"} · پیش‌نمایش محاسبات:{" "}
            {data.capabilities.preview_only ? "فعال" : "غیرفعال"}
          </p>
          <GoldDisclaimer variant="inline" />
        </>
      )}
    </div>
  );
}

function ReferenceStrip({ references }: { references: TerminalReferences }) {
  return (
    <section
      aria-label="مراجع محاسبه"
      data-testid="reference-strip"
      className="rounded-xl border border-zinc-800/70 bg-zinc-900/40 px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
        <span className="text-zinc-400">
          XAU/USD:{" "}
          <span className="font-bold tabular-nums text-zinc-100">
            {faNumber(references.xau_usd, 2)}
          </span>{" "}
          <span className="text-[10px] text-zinc-500">دلار / اونس</span>
        </span>
        <span className="text-zinc-400">
          دلار آزاد:{" "}
          <span className="font-bold tabular-nums text-zinc-100">
            {faNumber(references.usd_irt_rial)}
          </span>{" "}
          <span className="text-[10px] text-zinc-500">ریال</span>
          {references.usd_irt_rial !== null && (
            <span className="text-[10px] text-zinc-500">
              {" "}
              (معادل {faNumber(references.usd_irt_rial / 10)} تومان)
            </span>
          )}
        </span>
        <span className="text-zinc-400">
          زمان مرجع:{" "}
          <span className="tabular-nums text-zinc-200">
            {sourceTime(references.as_of) ?? "نامشخص"}
          </span>
        </span>
        <DataTrustBadge
          quality={references.quality}
          source={references.source}
          asOf={references.as_of}
          showMeta={false}
        />
      </div>
      {references.data_gaps.length > 0 && (
        <p className="mt-2 text-[10px] leading-5 text-amber-300/80" title={gapTitle(references.data_gaps)}>
          کمبود داده: {references.data_gaps.join("؛ ")}
        </p>
      )}
    </section>
  );
}
