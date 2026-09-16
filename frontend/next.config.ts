import { withSentryConfig } from "@sentry/nextjs";
import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.resolve(__dirname, ".."),
  allowedDevOrigins: process.env.ALLOWED_DEV_ORIGINS?.split(",").map((s) => s.trim()).filter(Boolean) ?? ["127.0.0.1"],
  experimental: {
    optimizePackageImports: ["recharts", "@tanstack/react-query", "framer-motion", "lucide-react", "lightweight-charts"],
  },

  // ------ Server-Side Proxy ---------------------------------------------------------------------------------------
  // Client-side (browser) calls /api/v1/* → hits Next.js server →
  // proxy forwards to backend (resolves api:8000 in Docker network).
  // API_URL is NOT a NEXT_PUBLIC_* var, so it never leaks to the browser.
  async rewrites() {
    // Server-side only: API_URL must be used in production (Docker: http://api:8000). Fallback to localhost only in dev.
    const apiUrl = process.env.API_URL || (process.env.NODE_ENV === "production" ? "http://api:8000" : "http://127.0.0.1:8000");
    const apiPrefix = process.env.API_PREFIX || process.env.NEXT_PUBLIC_API_PREFIX || "/api/v1";
    // Standalone currency service (apps/currency_service) — must precede the
    // catch-all rule below since Next.js evaluates rewrites in order.
    const currencyUrl = process.env.CURRENCY_API_URL || (process.env.NODE_ENV === "production" ? "http://currency:8002" : "http://127.0.0.1:8002");

    if (process.env.NODE_ENV !== "production") {
      console.log(`[Next.js Rewrite] API → ${apiUrl}${apiPrefix}`);
      console.log(`[Next.js Rewrite] Currency → ${currencyUrl}${apiPrefix}/currency`);
    }

    return [
      {
        source: `${apiPrefix}/currency/:path*`,
        destination: `${currencyUrl}${apiPrefix}/currency/:path*`,
      },
      {
        source: `${apiPrefix}/:path*`,
        destination: `${apiUrl}${apiPrefix}/:path*`,
      },
    ];
  },
};

// Sentry webpack plugin wraps the config — disabled without an auth token
// (release creation / source-map upload only run in CI with SENTRY_AUTH_TOKEN).
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  // Keep local/dev builds silent and fast.
  silent: true,
  disableLogger: true,
  // Source maps upload only when a token is present (CI).
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
  },
  // Do not inject build-time teardown into every build.
  telemetry: false,
});
