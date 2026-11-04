"use client";

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import { useEffect, useState } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { PersonaProvider } from "@/lib/persona-context";
import { AUTH_STATE_CLEARED_EVENT } from "@/lib/api";
import { apiErrorUserMessage, isRetryableApiError, isTimeoutError } from "@/lib/api-errors";

// A timeout affects every widget fed by the same backend; one toast is enough.
// (Cancelled requests and 401s are handled elsewhere and never toasted.)
const TIMEOUT_TOAST_WINDOW_MS = 15_000;
let lastTimeoutToast = { message: "", at: 0 };

function notifyTimeout(error: unknown) {
  if (!isTimeoutError(error)) return;
  const message = apiErrorUserMessage(error);
  const now = Date.now();
  if (lastTimeoutToast.message === message && now - lastTimeoutToast.at < TIMEOUT_TOAST_WINDOW_MS) {
    return;
  }
  lastTimeoutToast = { message, at: now };
  toast.error(message, { id: "api-timeout" });
}

/** Register the service worker after hydration (replaces the old inline script). */
function useServiceWorker() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      const onLoad = () => {
        navigator.serviceWorker
          .register("/sw.js")
          .then((registration) => {
            if (process.env.NODE_ENV !== "production") console.log("SW registered:", registration.scope);
          })
          .catch((error) => {
            if (process.env.NODE_ENV !== "production") console.log("SW registration failed:", error);
          });
      };
      if (document.readyState === "complete") {
        onLoad();
      } else {
        window.addEventListener("load", onLoad);
      }
      return () => window.removeEventListener("load", onLoad);
    }
  }, []);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: notifyTimeout }),
        defaultOptions: {
          queries: {
            // Never retry cancellations, timeouts, or auth failures; retry the
            // transient network/5xx classes once (the previous blanket retry:1
            // re-sent aborted and 401 requests pointlessly).
            retry: (failureCount, error) => failureCount < 1 && isRetryableApiError(error),
            staleTime: 60_000,
            gcTime: 300_000,
            refetchOnWindowFocus: false,
            refetchIntervalInBackground: false,
          },
          mutations: { retry: false },
        },
      }),
  );
  useServiceWorker();

  useEffect(() => {
    const clearUserScopedQueries = () => queryClient.clear();
    window.addEventListener(AUTH_STATE_CLEARED_EVENT, clearUserScopedQueries);
    return () => window.removeEventListener(AUTH_STATE_CLEARED_EVENT, clearUserScopedQueries);
  }, [queryClient]);

  return (
    <AuthProvider>
      <PersonaProvider>
        <QueryClientProvider client={queryClient}>
          <Toaster position="top-right" richColors />
          {children}
        </QueryClientProvider>
      </PersonaProvider>
    </AuthProvider>
  );
}
