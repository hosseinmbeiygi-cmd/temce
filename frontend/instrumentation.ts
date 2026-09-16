// Next.js instrumentation — runs once per server process.
// Server-side Sentry init is env-guarded: without SENTRY_DSN nothing loads.
export async function register() {
  if (!process.env.SENTRY_DSN) return;

  const Sentry = await import("@sentry/nextjs");
  const { initSentryServer } = await import("./sentry.server.config");

  initSentryServer(Sentry);
}
