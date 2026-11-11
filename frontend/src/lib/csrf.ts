// Double-submit CSRF token.
//
// The backend sets a JS-readable `im_csrf` cookie alongside the httpOnly
// refresh cookie and rejects any unsafe request from a cookie session that
// does not echo the value in `X-CSRF-Token`. A cross-site page cannot read the
// cookie (different origin) nor set a custom header without a CORS preflight,
// so echoing the cookie proves same-origin intent.

const CSRF_COOKIE = process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME || "im_csrf";
const CSRF_HEADER = process.env.NEXT_PUBLIC_CSRF_HEADER_NAME || "X-CSRF-Token";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function getCsrfToken(): string {
  if (typeof document === "undefined") return "";
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    if (trimmed.slice(0, eq) === CSRF_COOKIE) {
      return decodeURIComponent(trimmed.slice(eq + 1));
    }
  }
  return "";
}

/** Return `headers` with the CSRF header added for unsafe methods. */
export function withCsrf(headers: HeadersInit | undefined, method: string = "GET"): HeadersInit {
  if (SAFE_METHODS.has(method.toUpperCase())) return headers ?? {};
  const token = getCsrfToken();
  if (!token) return headers ?? {};
  if (headers instanceof Headers) {
    const next = new Headers(headers);
    next.set(CSRF_HEADER, token);
    return next;
  }
  if (Array.isArray(headers)) {
    return [...headers.filter(([k]) => k.toLowerCase() !== CSRF_HEADER.toLowerCase()), [CSRF_HEADER, token]];
  }
  return { ...(headers ?? {}), [CSRF_HEADER]: token };
}
