import type { PriceQuality } from "@/types/gold";

// SAMPLE/EDUCATIONAL باید از LIVE کاملاً متمایز باشد: پس‌زمینهٔ توپر + حلقهٔ
// روشن، نه فقط یک رنگ ملایم که با سبزِ LIVE اشتباه گرفته شود.
const QUALITY_STYLES: Record<PriceQuality, string> = {
  LIVE: "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/50",
  DELAYED: "bg-amber-500/15 text-amber-200 ring-1 ring-amber-400/50",
  SAMPLE: "bg-rose-600 text-white ring-2 ring-rose-300",
  EDUCATIONAL: "bg-violet-600 text-white ring-2 ring-violet-300",
};

const QUALITY_HINTS: Record<PriceQuality, string> = {
  LIVE: "داده‌ی تازه از منبع اصلی",
  DELAYED: "داده‌ی کهنه یا از منبع ثانویه",
  SAMPLE: "داده‌ی نمونه — قیمت زنده نیست",
  EDUCATIONAL: "داده‌ی آموزشی — قیمت زنده نیست",
};

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

function faDigits(value: string): string {
  return value.replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

/**
 * هر مقدار ناشناخته fail-closed به DELAYED نگاشت می‌شود: UI اجازه ندارد بدون
 * اثباتِ تازگی، چیزی را LIVE خطاب کند.
 */
export function normalizeQuality(value: unknown): PriceQuality {
  return value === "LIVE" || value === "DELAYED" || value === "SAMPLE" || value === "EDUCATIONAL"
    ? value
    : "DELAYED";
}

/**
 * زمان به‌صورت دستی و قطعی (UTC+03:30) قالب می‌شود تا رندر سرور و کلاینت
 * دقیقاً یکسان باشد؛ ایران از ۲۰۲۲ ساعت تابستانی ندارد.
 */
export function formatAsOf(asOf?: string | null): string | null {
  if (!asOf) return null;
  const ms = Date.parse(asOf);
  if (!Number.isFinite(ms)) return null;
  const tehran = new Date(ms + 3.5 * 60 * 60 * 1000);
  const pad = (part: number) => String(part).padStart(2, "0");
  return faDigits(
    `${tehran.getUTCFullYear()}/${pad(tehran.getUTCMonth() + 1)}/${pad(tehran.getUTCDate())} ` +
      `${pad(tehran.getUTCHours())}:${pad(tehran.getUTCMinutes())}`,
  );
}

export function formatAge(ageSeconds?: number | null): string | null {
  if (ageSeconds === null || ageSeconds === undefined || !Number.isFinite(ageSeconds)) {
    return null;
  }
  const seconds = Math.max(0, Math.round(ageSeconds));
  if (seconds === 0) return "همین حالا";
  return `${faDigits(seconds.toLocaleString("en-US"))} ثانیه پیش`;
}

interface DataTrustBadgeProps {
  quality?: PriceQuality | string | null;
  source?: string | null;
  asOf?: string | null;
  ageSeconds?: number | null;
  showMeta?: boolean;
  className?: string;
}

/** برچسب اجباری کیفیت + منبع + زمان آخرین به‌روزرسانی برای هر قیمت. */
export function DataTrustBadge({
  quality,
  source,
  asOf,
  ageSeconds,
  showMeta = true,
  className = "",
}: DataTrustBadgeProps) {
  const resolved = normalizeQuality(quality);
  const stamp = formatAsOf(asOf);
  const age = formatAge(ageSeconds);
  const timeLabel = stamp ?? age ?? "زمان: نامشخص";

  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 ${className}`}>
      <span
        data-testid="quality-badge"
        data-quality={resolved}
        className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide ${QUALITY_STYLES[resolved]}`}
        title={QUALITY_HINTS[resolved]}
      >
        {resolved}
        <span className="sr-only"> — {QUALITY_HINTS[resolved]}</span>
      </span>
      {showMeta && (
        <>
          <span className="text-[10px] text-zinc-500">
            منبع: {source || "نامشخص"}
          </span>
          <span className="text-[10px] text-zinc-500">
            {stamp ? (
              <>
                آخرین به‌روزرسانی: <time dateTime={asOf ?? undefined}>{stamp}</time>
              </>
            ) : (
              timeLabel
            )}
          </span>
          {stamp && age && <span className="text-[10px] text-zinc-500">· {age}</span>}
        </>
      )}
    </span>
  );
}
