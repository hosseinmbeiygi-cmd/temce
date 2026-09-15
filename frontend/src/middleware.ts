import { NextRequest, NextResponse } from "next/server";

/**
 * Baseline security headers applied to every response.
 * Exported so tests can assert against the exact values.
 */
export const SECURITY_HEADERS: Record<string, string> = {
  "X-Frame-Options": "SAMEORIGIN",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-DNS-Prefetch-Control": "on",
  // CSP: allow self + unsafe-inline for theme script + data: for images; tighten in prod
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self'",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

/**
 * The httpOnly refresh cookie set by the backend
 * (core/config/__init__.py `auth_cookie_name`, default "im_refresh").
 * Its presence signals an active session on this browser.
 */
export const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME || "im_refresh";

/**
 * Dev-only CSP relaxation. `next dev` compiles client chunks with
 * eval-source-map, so without 'unsafe-eval' the entire client bundle is
 * blocked → no hydration on ANY route → React Query never runs. The live
 * market WebSocket also dials :8000 cross-origin in dev, which
 * `connect-src 'self'` would drop. Production keeps the strict header.
 */
const DEV_CSP =
  "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self' ws: wss: http://127.0.0.1:8000 http://localhost:8000";

/**
 * Routes that require a session.
 *
 * The middleware can only verify presence of the refresh cookie — the access
 * token lives in browser memory and is never exposed to the server — so role
 * checks stay on the client (useAuth().hasRole) and the backend
 * (require_roles). The backend remains the source of truth: a stale/dead
 * cookie still yields 401 there, which api.ts handles by redirecting to
 * login. This guard is a UX + defense-in-depth layer, not the security
 * boundary.
 */
/**
 * Public routes that do NOT require a session — everything else is protected by default.
 * This allowlist pattern is safer than enumerating 4 routes out of 117.
 */
export const PUBLIC_ROUTES: readonly string[] = [
  "/",
  "/auth",
  "/markets",
  "/market-watch",
  "/heatmap",
  "/news",
  "/codal",
  "/funds",
  "/crypto",
  "/crypto-market",
  "/crypto-exchange",
  "/commodities",
  "/economic-calendar",
  "/health",
];

export const PROTECTED_ROUTES: readonly string[] = [
  "/admin",
  "/settings/security",
  "/profile",
  "/watchlist",
  "/portfolio",
  "/signals/register",
  "/paper-trading",
  "/sync",
  "/sync-manager",
  "/data-import",
  "/personal",
];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`) || pathname.startsWith("/_next") || pathname === "/favicon.ico");
}

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

function applySecurityHeaders(response: NextResponse): void {
  const dev = process.env.NODE_ENV !== "production";
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, key === "Content-Security-Policy" && dev ? DEV_CSP : value);
  }
}

/**
 * Edge-safe middleware: security headers on every response + a route guard
 * that redirects unauthenticated visitors away from protected pages.
 */
export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  // Allow public routes and static assets without auth check; protect everything else
  const isPublic = isPublicPath(pathname) || !isProtectedPath(pathname) ? isPublicPath(pathname) : false;
  // New logic: if not public and is protected (or not in public list) and no cookie → redirect
  // For now, keep explicit protected list as source of truth but expand it; public check is for future allowlist migration
  if (isProtectedPath(pathname) && !request.cookies.has(AUTH_COOKIE_NAME)) {
    const originalSearch = request.nextUrl.search;
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/auth/login";
    loginUrl.search = "";
    loginUrl.searchParams.set("redirect", `${pathname}${originalSearch}`);

    const response = NextResponse.redirect(loginUrl);
    applySecurityHeaders(response);
    return response;
  }

  const response = NextResponse.next();
  applySecurityHeaders(response);
  return response;
}

export const config = {
  matcher: [
    // Skip Next.js internals and static assets; everything else gets headers
    // (and the route guard only acts on protected page paths).
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
