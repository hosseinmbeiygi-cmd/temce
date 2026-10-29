// ── Envelope contract for the Python API ────────────────────────────
//
// `schemas/common/responses.py::ApiResponse` wraps nearly every route in
// `{success, data, error, message, data_as_of, cache_hit}`. Three different
// situations look identical to a client that only reads `data`:
//
//   1. success + rows        → live data
//   2. success + empty array → genuinely nothing to show (market closed, …)
//   3. success:false         → the source failed; `data` is null/empty
//
// `extractArray()` collapses 2 and 3 into `[]`, and pages then render an
// "empty" state (or, worse, mock data) for a backend failure. This module is
// the single place that reads the envelope, so callers can tell the three
// apart: `apiRequest()` throws on (3), and `data_as_of`/`cache_hit` describe
// how old the payload is.
//
// Kept dependency-free (no imports) so it can be used from `api.ts`, hooks and
// page components without pulling the transport layer into a unit test.

/** آستانهٔ پیش‌فرض تازگی داده: ۵ دقیقه (هم‌راستا با `isDataFresh` داشبورد). */
export const DEFAULT_FRESHNESS_MS = 5 * 60 * 1000;

/** اختلاف ساعت سرور/مرورگر که هنوز «آینده» محسوب نمی‌شود. */
const FUTURE_SKEW_MS = 2 * 60 * 1000;

export interface ApiEnvelopeMeta {
  /** `success` پاکت؛ `null` یعنی پاسخ پاکت نداشت (مسیر برهنه یا آرایه). */
  success: boolean | null;
  /** زمان تولید داده (`data_as_of`) به‌صورت رشتهٔ خام. */
  dataAsOf: string | null;
  /** `true` یعنی پاسخ از کش aggregate سرو شده است، نه از کوئری تازه. */
  cacheHit: boolean;
  /** پیام خطای سرویس — فقط برای لاگ، نه برای رندر. */
  errorMessage: string | null;
  /** کد خطای ماشین‌خوان (`error.code`/`error.type`). */
  errorCode: string | null;
  /** بدنهٔ خام `error` برای لاگ/عیب‌یابی. */
  errorDetail: unknown;
}

/**
 * خطای «پاکت ناموفق»: HTTP 200 با `success:false`.
 *
 * پیام عمداً عمومی است — متن داخلی سرور (`error.message`) در `detail` می‌ماند
 * تا در UI لو نرود (همان قاعدهٔ C3 در `goldApi.ts`).
 */
export class ApiEnvelopeError extends Error {
  readonly code: string | null;
  readonly detail: unknown;
  readonly dataAsOf: string | null;

  constructor(
    message: string,
    options: { code?: string | null; detail?: unknown; dataAsOf?: string | null } = {},
  ) {
    super(message);
    this.name = "ApiEnvelopeError";
    this.code = options.code ?? null;
    this.detail = options.detail ?? null;
    this.dataAsOf = options.dataAsOf ?? null;
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function readErrorFields(detail: unknown): { message: string | null; code: string | null } {
  if (typeof detail === "string") return { message: detail, code: null };
  const obj = asRecord(detail);
  if (!obj) return { message: null, code: null };
  const message =
    typeof obj.message === "string"
      ? obj.message
      : typeof obj.detail === "string"
        ? obj.detail
        : null;
  const code =
    typeof obj.code === "string" ? obj.code : typeof obj.type === "string" ? obj.type : null;
  return { message, code };
}

/**
 * خواندن متادیتای پاکت. برای پاسخ برهنه (آرایه یا شیء بدون `success`) مقدار
 * `success: null` برمی‌گردد — یعنی «پاکتی وجود ندارد»، نه «موفق».
 */
export function readEnvelopeMeta(response: unknown): ApiEnvelopeMeta {
  const empty: ApiEnvelopeMeta = {
    success: null,
    dataAsOf: null,
    cacheHit: false,
    errorMessage: null,
    errorCode: null,
    errorDetail: null,
  };
  const obj = asRecord(response);
  if (!obj) return empty;

  const success = typeof obj.success === "boolean" ? obj.success : null;
  // `data_as_of` معمولاً در ریشه است؛ بعضی مسیرها آن را داخل `data` می‌گذارند.
  const dataObj = asRecord(obj.data);
  const rawAsOf = obj.data_as_of ?? dataObj?.data_as_of;
  const dataAsOf = typeof rawAsOf === "string" && rawAsOf.trim() !== "" ? rawAsOf : null;
  const cacheHit = obj.cache_hit === true || dataObj?.cache_hit === true;
  const error = readErrorFields(obj.error);

  return {
    success,
    dataAsOf,
    cacheHit,
    errorMessage: error.message,
    errorCode: error.code,
    errorDetail: obj.error ?? null,
  };
}

/** `data_as_of` پاکت (یا `null` وقتی پاسخ تازگی ندارد). */
export function getDataAsOf(response: unknown): string | null {
  return readEnvelopeMeta(response).dataAsOf;
}

/** آیا پاسخ از کش aggregate سرو شده است؟ */
export function isCacheHit(response: unknown): boolean {
  return readEnvelopeMeta(response).cacheHit;
}

/**
 * اگر پاکت `success:false` باشد خطا می‌اندازد.
 *
 * عمداً فقط `success === false` را رد می‌کند: پاسخ برهنه (`{items: [...]}`)
 * همچنان دادهٔ معتبر است و نباید شکسته شود.
 */
export function assertSuccessEnvelope(response: unknown, endpoint = ""): void {
  const meta = readEnvelopeMeta(response);
  if (meta.success !== false) return;
  const label = endpoint || "API";
  // متن داخلی فقط به کنسول می‌رود (قاعدهٔ C3) — نه به پیام خطای کاربر.
  if (typeof console !== "undefined") {
    console.warn(`[api] ${label}: پاسخ success=false`, meta.errorCode ?? meta.errorDetail ?? meta.errorMessage);
  }
  const codeSuffix = meta.errorCode ? ` (${meta.errorCode})` : "";
  throw new ApiEnvelopeError(`${label}: داده در دسترس نیست${codeSuffix}`, {
    code: meta.errorCode,
    detail: meta.errorDetail,
    dataAsOf: meta.dataAsOf,
  });
}

/** ISO-8601 با جداکنندهٔ `T` یا فاصله، کسر ثانیه و منطقهٔ زمانی اختیاری. */
const ISO_INSTANT_RE =
  /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:?\d{2})?$/;

/**
 * تبدیل `data_as_of` به epoch ms؛ ورودی نامعتبر ⇒ `null`.
 *
 * عمداً سخت‌گیر است: `Date.parse("12")` عدد برمی‌گرداند و آن‌وقت کهنگی با یک
 * زمان جعلی حساب می‌شود. رشتهٔ بدون منطقهٔ زمانی UTC فرض می‌شود (بک‌اند زمان
 * سرور را naive ذخیره می‌کند) تا اختلاف ۳:۳۰ باعث «کهنه» دیده‌شدن دادهٔ تازه نشود.
 */
export function parseIsoInstant(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = ISO_INSTANT_RE.exec(value.trim());
  if (!match) return null;
  const [, year, month, day, hour, minute, second, fraction, zone] = match;
  const y = Number(year);
  const mo = Number(month);
  const d = Number(day);
  const h = Number(hour);
  const mi = Number(minute);
  const s = second ? Number(second) : 0;
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59 || s > 59) return null;

  const base = Date.UTC(
    y,
    mo - 1,
    d,
    h,
    mi,
    s,
    fraction ? Math.round(Number(`0.${fraction}`) * 1000) : 0,
  );
  if (!zone || zone === "Z") return base;
  const sign = zone.startsWith("-") ? -1 : 1;
  const digits = zone.slice(1).replace(":", "");
  const offsetMinutes = Number(digits.slice(0, 2)) * 60 + Number(digits.slice(2));
  return base - sign * offsetMinutes * 60_000;
}

/**
 * آیا `data_as_of` داخل آستانهٔ تازگی است؟
 *
 * `false` برای: مقدار غایب/نامعتبر، زمان آینده (با احتساب ۲ دقیقه اسکیو)، و
 * دادهٔ قدیمی‌تر از آستانه. زمان آینده رد می‌شود چون `now - t` منفی می‌شود و
 * مقایسهٔ سادهٔ `<=` دادهٔ آینده را «تازه» اعلام می‌کند.
 */
export function isDataAsOfFresh(
  value: unknown,
  options: { now?: number; thresholdMs?: number } = {},
): boolean {
  const instant = parseIsoInstant(value);
  if (instant === null) return false;
  const now = options.now ?? Date.now();
  if (instant > now + FUTURE_SKEW_MS) return false;
  return now - instant <= (options.thresholdMs ?? DEFAULT_FRESHNESS_MS);
}
