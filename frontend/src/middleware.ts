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
 * Minimal edge-safe middleware.
 * Adds security headers to all responses and never blocks a request,
 * so it is safe to deploy alongside the existing auth (client-side).
 */
export function middleware(_request: NextRequest): NextResponse {
  const response = NextResponse.next();

  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value);
  }

  return response;
}

export const config = {
  matcher: [
    // Skip Next.js internals and static assets; everything else gets headers.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
