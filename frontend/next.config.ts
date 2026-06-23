import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(process.cwd(), ".."),
  experimental: {
    optimizePackageImports: ["recharts", "@tanstack/react-query"],
  },

  // ── Server-Side Proxy ─────────────────────────────
  // Client-side (browser) calls /api/v1/* → hits Next.js server →
  // proxy forwards to backend (resolves api:8000 in Docker network).
  // API_URL is NOT a NEXT_PUBLIC_* var, so it never leaks to the browser.
  async rewrites() {
    const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const apiPrefix = process.env.API_PREFIX || process.env.NEXT_PUBLIC_API_PREFIX || "/api/v1";

    if (process.env.NODE_ENV !== "production") {
      console.log(`[Next.js Rewrite] API → ${apiUrl}${apiPrefix}`);
    }

    return [
      {
        source: `${apiPrefix}/:path*`,
        destination: `${apiUrl}${apiPrefix}/:path*`,
      },
    ];
  },
};

export default nextConfig;
