// Server (Node runtime) Sentry config — imported lazily from instrumentation.ts
// so the SDK never loads when SENTRY_DSN is unset.
import type * as SentryModule from "@sentry/nextjs";

export function initSentryServer(Sentry: typeof SentryModule) {
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? 0.1),
    attachStacktrace: true,
    sendDefaultPii: false,
  });
}
