"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useEffect, useState } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { AUTH_STATE_CLEARED_EVENT } from "@/lib/api";

/** Register the service worker after hydration (replaces the old inline script). */
function useServiceWorker() {
  useEffect(() => {
    // Never let a stale service worker interfere with Next.js HMR/dev pages.
    // The PWA worker is only useful in the production build.
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
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
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 60_000,
            gcTime: 300_000,
            refetchOnWindowFocus: false,
            refetchIntervalInBackground: false,
          },
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
      <QueryClientProvider client={queryClient}>
        <Toaster position="top-right" richColors />
        {children}
      </QueryClientProvider>
    </AuthProvider>
  );
}
