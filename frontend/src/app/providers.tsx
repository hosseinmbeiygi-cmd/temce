"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useEffect, useState } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { AUTH_STATE_CLEARED_EVENT } from "@/lib/api";

/** Register the service worker after hydration (replaces the old inline script). */
function useServiceWorker() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      const onLoad = () => {
        navigator.serviceWorker
          .register("/sw.js")
          .then((registration) => {
            console.log("SW registered:", registration.scope);
          })
          .catch((error) => {
            console.log("SW registration failed:", error);
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
  const [queryClient] = useState(() => new QueryClient());
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
