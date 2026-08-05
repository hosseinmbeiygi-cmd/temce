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
};

/**
 * The httpOnly refresh cookie set by the backend
 * (core/config/__init__.py `auth_cookie_name`, default "im_refresh").
 * Its presence signals an active session on this browser.
 */
export const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME || "im_refresh";

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
export const PROTECTED_ROUTES: readonly string[] = [
  "/admin",
  "/settings/security",
  "/profile",
  "/watchlist",
];

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

function applySecurityHeaders(response: NextResponse): void {
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value);
  }
}

/**
 * Edge-safe middleware: security headers on every response + a route guard
 * that redirects unauthenticated visitors away from protected pages.
 */
export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  // Route guard: no refresh cookie → send the visitor to the login page,
  // remembering where they were headed so we can return after login.
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
