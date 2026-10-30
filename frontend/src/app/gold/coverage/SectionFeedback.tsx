"use client";

import { isServiceUnavailable } from "@/lib/goldApi";

/** بلوک بارگذاری یک بخش — خطای یک endpoint بقیهٔ صفحه را نمی‌خواباند. */
export function SectionLoading({ label }: { label: string }) {
  return (
    <div
      className="rounded-xl border border-zinc-800/70 bg-zinc-950/40 px-4 py-6 text-center text-xs text-zinc-500"
      data-testid="coverage-loading"
    >
      در حال دریافت {label}...
    </div>
  );
}

export function SectionError({
  error,
  label,
  testId,
}: {
  error: unknown;
  label: string;
  testId: string;
}) {
  return (
    <div
      role="alert"
      data-testid={testId}
      className="rounded-xl border px-4 py-3 text-xs leading-6"
      style={{
        borderColor: "var(--gd-danger)",
        background: "var(--gd-bg-2)",
        color: "var(--gd-danger)",
      }}
    >
      {isServiceUnavailable(error)
        ? `${label} موقتاً در دسترس نیست (۵۰۳)؛ چند لحظه دیگر دوباره تلاش کنید.`
        : `دریافت ${label} ناموفق بود.`}
    </div>
  );
}

/** یادداشت خنثی برای وضعیت منبع (بدون قیمت جعلی). */
export function SourceNotice({
  children,
  tone = "neutral",
  testId,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "warn";
  testId?: string;
}) {
  return (
    <p
      data-testid={testId}
      className={`rounded-lg border px-3 py-2 text-[11px] leading-6 ${
        tone === "warn"
          ? "border-amber-500/30 bg-amber-500/5 text-amber-200/90"
          : "border-zinc-800/70 bg-zinc-900/40 text-zinc-400"
      }`}
    >
      {children}
    </p>
  );
}
