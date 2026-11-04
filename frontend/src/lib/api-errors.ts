// Typed transport errors + Persian user-facing copy.
//
// Three failure classes used to collapse into one generic `Error`:
//   * request cancelled by the caller (React Query symbol switch / unmount)
//   * request timed out inside `fetchWithTimeout`
//   * request rejected by auth (401) and the session was terminated
//
// Keeping them distinct lets React Query skip retries, lets the UI stay silent
// on cancellation, and lets every surface show the same clear message.

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, options: { status?: number | null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? null;
  }
}

export class ApiTimeoutError extends ApiError {
  readonly timeoutMs: number;
  readonly endpoint: string;

  constructor(endpoint: string, timeoutMs: number) {
    super(`Request timeout after ${timeoutMs}ms: ${endpoint}`);
    this.name = "TimeoutError";
    this.timeoutMs = timeoutMs;
    this.endpoint = endpoint;
  }
}

export class ApiUnauthorizedError extends ApiError {
  constructor(message: string) {
    super(message, { status: 401 });
    this.name = "UnauthorizedError";
  }
}

function errorName(error: unknown): string | null {
  if (!error || typeof error !== "object") return null;
  const name = (error as { name?: unknown }).name;
  return typeof name === "string" ? name : null;
}

/** Cancellation is not a failure: callers should ignore it, never render it. */
export function isAbortError(error: unknown): boolean {
  const name = errorName(error);
  return name === "AbortError" || name === "CanceledError";
}

export function isTimeoutError(error: unknown): boolean {
  return error instanceof ApiTimeoutError || errorName(error) === "TimeoutError";
}

export function isUnauthorizedError(error: unknown): boolean {
  if (error instanceof ApiUnauthorizedError) return true;
  if (errorName(error) === "UnauthorizedError") return true;
  return getApiErrorStatus(error) === 401;
}

export function getApiErrorStatus(error: unknown): number | null {
  if (!error || typeof error !== "object") return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

/** `fetch` reports DNS/offline failures as TypeError. */
export function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError;
}

export const API_ERROR_MESSAGES = {
  timeout: "پاسخی از سرور دریافت نشد (اتمام زمان انتظار). اتصال شبکه را بررسی کنید و دوباره تلاش کنید.",
  unauthorized: "نشست شما منقضی شده است — لطفاً دوباره وارد شوید.",
  forbidden: "دسترسی به این بخش برای حساب شما مجاز نیست.",
  rateLimited: "تعداد درخواست‌ها بیش از حد مجاز است — کمی بعد دوباره تلاش کنید.",
  server: "سرور در دسترس نیست یا خطای داخلی دارد — کمی بعد دوباره تلاش کنید.",
  network: "ارتباط با سرور برقرار نشد — اتصال شبکه را بررسی کنید.",
  unknown: "دریافت داده از سرور ناموفق بود.",
} as const;

/**
 * Persian message for a transport error. Returns `""` for cancellations —
 * an aborted request is not something the user should ever be told about.
 */
export function apiErrorUserMessage(error: unknown, fallback: string = API_ERROR_MESSAGES.unknown): string {
  if (isAbortError(error)) return "";
  if (isTimeoutError(error)) return API_ERROR_MESSAGES.timeout;
  if (isUnauthorizedError(error)) return API_ERROR_MESSAGES.unauthorized;
  if (isNetworkError(error)) return API_ERROR_MESSAGES.network;

  const status = getApiErrorStatus(error);
  if (status === 403) return API_ERROR_MESSAGES.forbidden;
  if (status === 429) return API_ERROR_MESSAGES.rateLimited;
  if (status != null && status >= 500) return API_ERROR_MESSAGES.server;
  return fallback;
}

/**
 * Retry policy for React Query. Cancellations and timeouts are not retried
 * (the timeout already waited the full budget), auth failures are terminal,
 * and other 4xx answers will not change on a second identical request.
 */
export function isRetryableApiError(error: unknown): boolean {
  if (isAbortError(error) || isTimeoutError(error) || isUnauthorizedError(error)) return false;
  if (isNetworkError(error)) return true;
  const status = getApiErrorStatus(error);
  if (status == null) return true;
  if (status === 408 || status === 429) return true;
  return status >= 500;
}

/**
 * Message for a user-visible surface (form error, banner).
 *
 * Transport classes get the friendly Persian copy; a 4xx validation message
 * from the backend is passed through because it tells the user what to fix.
 * Returns `""` for cancellations, which callers must not render.
 */
export function describeApiError(error: unknown, fallback: string = API_ERROR_MESSAGES.unknown): string {
  const friendly = apiErrorUserMessage(error, "");
  if (friendly) return friendly;
  if (isAbortError(error)) return "";
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
