import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import {
  middleware,
  SECURITY_HEADERS,
  AUTH_COOKIE_NAME,
  PROTECTED_ROUTES,
  config,
} from "@/middleware";

/**
 * Production CSP uses a per-request nonce (`{NONCE}` template filled by
 * middleware()); dev CSP is intentionally relaxed ('unsafe-eval' for
 * next dev source maps + local websocket). Branch the assertions so each
 * mode is checked against its own contract.
 */
function expectSecurityHeaders(res: Response): void {
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    if (key === "Content-Security-Policy") {
      expect(value).toContain("{NONCE}");
      expect(value).toContain("strict-dynamic");
      expect(value).toContain("object-src 'none'");

      const actual = res.headers.get(key) ?? "";
      const isDevCsp = actual.includes("unsafe-eval");
      if (isDevCsp) {
        expect(actual).toContain("connect-src 'self' ws: wss:");
      } else {
        expect(actual).not.toContain("{NONCE}");
        expect(actual).not.toContain("script-src 'self' 'unsafe-inline'");
        expect(actual).toContain("nonce-");
        expect(actual).toContain("strict-dynamic");
      }
    } else {
      expect(res.headers.get(key)).toBe(value);
    }
  }
}

describe("middleware", () => {
  it("returns a NextResponse with all security headers", () => {
    const req = new NextRequest("http://localhost:3000/dashboard");
    const res = middleware(req);

    // NextResponse.next() is a Response subclass
    expect(res).toBeInstanceOf(Response);
    expectSecurityHeaders(res);
  });

  it("never blocks a public request (pass-through)", () => {
    const req = new NextRequest("http://localhost:3000/symbol/فولاد");
    const res = middleware(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("X-Frame-Options")).toBe("SAMEORIGIN");
  });

  it("applies headers on API paths too", () => {
    const req = new NextRequest("http://localhost:3000/api/v1/market");
    const res = middleware(req);

    expect(res.headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(res.headers.get("Referrer-Policy")).toBe(
      "strict-origin-when-cross-origin",
    );
  });

  it("exposes a matcher config that skips static assets", () => {
    // Config is a non-empty array of matcher regex strings.
    expect(Array.isArray(config.matcher)).toBe(true);
    expect(config.matcher.length).toBeGreaterThan(0);

    const matcher = config.matcher[0];
    expect(typeof matcher).toBe("string");
    expect(matcher).toContain("_next/static");
  });

  // ══════════════════════════════════════════════════════════════
  // Route guard
  // ══════════════════════════════════════════════════════════════

  describe("route guard", () => {
    it("covers every protected route in the list", () => {
      expect(PROTECTED_ROUTES).toEqual(
        expect.arrayContaining([
          "/admin",
          "/settings/security",
          "/profile",
          "/watchlist",
        ]),
      );
    });

    it.each(PROTECTED_ROUTES)(
      "redirects unauthenticated visitors away from %s",
      (route) => {
        const req = new NextRequest(`http://localhost:3000${route}`);
        const res = middleware(req);

        expect(res.status).toBe(307);
        const location = res.headers.get("location") || "";
        expect(location).toContain("/auth/login");
        expect(location).toContain(`redirect=${encodeURIComponent(route)}`);
      },
    );

    it("redirects on protected sub-paths too (e.g. /admin/users)", () => {
      const req = new NextRequest("http://localhost:3000/admin/users");
      const res = middleware(req);

      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toContain(
        "redirect=%2Fadmin%2Fusers",
      );
    });

    it("lets authenticated visitors through (refresh cookie present)", () => {
      const req = new NextRequest("http://localhost:3000/admin", {
        headers: { cookie: `${AUTH_COOKIE_NAME}=valid-refresh` },
      });
      const res = middleware(req);

      expect(res.status).toBe(200);
      expect(res.headers.get("X-Frame-Options")).toBe("SAMEORIGIN");
    });

    it("preserves the original query string in the redirect target", () => {
      const req = new NextRequest("http://localhost:3000/watchlist?page=2&q=خودرو");
      const res = middleware(req);

      expect(res.status).toBe(307);
      const location = res.headers.get("location") || "";
      // The full target (path + query) is carried in the redirect param.
      expect(location).toContain("redirect=%2Fwatchlist%3Fpage%3D2%26q%3D");
    });

    it("does not redirect the login page itself", () => {
      const req = new NextRequest("http://localhost:3000/auth/login?redirect=%2Fadmin");
      const res = middleware(req);

      expect(res.status).toBe(200);
      expect(res.headers.get("X-Frame-Options")).toBe("SAMEORIGIN");
    });

    it("does not redirect public sections (dashboard, market, codal…)", () => {
      for (const path of ["/", "/market", "/codal", "/options", "/smart-money"]) {
        const res = middleware(new NextRequest(`http://localhost:3000${path}`));
        expect(res.status).toBe(200);
      }
    });

    it("adds security headers to the redirect response", () => {
      const req = new NextRequest("http://localhost:3000/profile");
      const res = middleware(req);

      expect(res.status).toBe(307);
      expectSecurityHeaders(res);
    });

    it("generates a fresh nonce per request (prod CSP)", () => {
      // Next.js types NODE_ENV as read-only; the runtime value is a normal
      // property, so route around the type via a scoped mock of the module env.
      const env = process.env as { NODE_ENV?: string };
      const original = env.NODE_ENV;
      env.NODE_ENV = "production";
      try {
        const a = middleware(new NextRequest("http://localhost:3000/"));
        const b = middleware(new NextRequest("http://localhost:3000/"));
        const cspA = a.headers.get("Content-Security-Policy") ?? "";
        const cspB = b.headers.get("Content-Security-Policy") ?? "";

        expect(cspA).toContain("script-src 'self' 'nonce-");
        expect(cspA).toContain("strict-dynamic");
        expect(cspA).not.toBe(cspB);
      } finally {
        env.NODE_ENV = original;
      }
    });
  });
});
