import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import { middleware, SECURITY_HEADERS, config } from "@/middleware";

describe("middleware", () => {
  it("returns a NextResponse with all security headers", () => {
    const req = new NextRequest("http://localhost:3000/dashboard");
    const res = middleware(req);

    // NextResponse.next() is a Response subclass
    expect(res).toBeInstanceOf(Response);
    for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
      expect(res.headers.get(key)).toBe(value);
    }
  });

  it("never blocks a request (pass-through)", () => {
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
});
