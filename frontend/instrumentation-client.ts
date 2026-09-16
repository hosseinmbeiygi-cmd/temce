// Sentry client-side initialization (browser).
// Loaded from instrumentation.ts — runs only when NEXT_PUBLIC_SENTRY_DSN is
// set, keeping local/offline development 100% Sentry-free.
import * as Sentry from "@sentry/nextjs";

// Required by @sentry/nextjs to instrument App Router navigations.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;

export function registerErrorObserver() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
    integrations: [
      // Session replay off by default — enable deliberately via env.
      ...(process.env.NEXT_PUBLIC_SENTRY_REPLAY === "true" ? [Sentry.replayIntegration()] : []),
    ],
    tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0.1),
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: process.env.NEXT_PUBLIC_SENTRY_REPLAY === "true" ? 1.0 : 0,
    // Never attach cookies/localStorage — auth tokens live there.
    sendDefaultPii: false,
  });
}
