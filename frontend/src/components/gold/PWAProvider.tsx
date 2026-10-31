"use client";

import { useEffect, useRef, useState } from "react";

export function PWAProvider({ children }: { children: React.ReactNode }) {
  const [online, setOnline] = useState(true);
  // F9: بنر باید تفاوت «آفلاین ولی دادهٔ تازه در کش هست» با «آفلاین و دادهٔ
  // کهنه رد شد» را بگوید. نسخهٔ قبلی همیشه وعدهٔ «داده‌های cache نمایش داده
  // می‌شود» را می‌داد، درحالی‌که SW جدید پاسخ مالی کهنه را سرو نمی‌کند.
  const [staleRefused, setStaleRefused] = useState(false);
  const [installPrompt, setInstallPrompt] = useState<{ prompt: () => Promise<unknown>; userChoice: Promise<{ outcome: string }> } | null>(null);
  const [showInstall, setShowInstall] = useState(false);
  const swRegisteredRef = useRef(false);

  useEffect(() => {
    // ── Online/Offline status ──
    setOnline(navigator.onLine);
    const onOnline = () => {
      setOnline(true);
      setStaleRefused(false);
    };
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);

    // ── پیام‌های service worker (golddesk-sw.js) ──
    const onSWMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string } | null;
      if (!data || typeof data.type !== "string") return;
      if (data.type === "golddesk:stale-refused") setStaleRefused(true);
      if (data.type === "golddesk:online") setStaleRefused(false);
    };
    navigator.serviceWorker?.addEventListener("message", onSWMessage);

    // ── Service Worker registration ──
    if ("serviceWorker" in navigator && !swRegisteredRef.current) {
      swRegisteredRef.current = true;
      navigator.serviceWorker
        .register("/golddesk-sw.js", { scope: "/gold" })
        .then(() => {
          /* SW registered */
        })
        .catch(() => {
          /* SW registration failed */
        });
    }

    // ── Install prompt ──
    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      // The browser fires a BeforeInstallPromptEvent here; its shape is
      // an extended Promise, but TS only sees the base Event.
      setInstallPrompt(e as unknown as Parameters<typeof setInstallPrompt>[0]);
      setShowInstall(true);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);

    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      navigator.serviceWorker?.removeEventListener("message", onSWMessage);
    };
  }, []);

  const onInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    if (choice.outcome === "accepted") {
      setShowInstall(false);
    }
    setInstallPrompt(null);
  };

  return (
    <>
      {children}

      {/* Offline indicator */}
      {(!online || staleRefused) && (
        <div
          role="status"
          className="fixed bottom-20 md:bottom-4 left-1/2 -translate-x-1/2 z-40 px-4 py-2 rounded-full bg-amber-600 text-white text-sm shadow-lg"
        >
          {!online && !staleRefused && "📵 آفلاین — اگر دادهٔ تازه در کش باشد نمایش داده می‌شود"}
          {staleRefused && "⚠️ دادهٔ کش‌شده کهنه‌تر از حد مجاز بود — برای اعداد فعلی متصل شوید"}
        </div>
      )}

      {/* Install prompt */}
      {showInstall && (
        <div className="fixed bottom-4 right-4 z-50 max-w-sm rounded-xl p-4 shadow-2xl" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
          <div className="flex items-start gap-3">
            <div className="text-3xl">🥇</div>
            <div className="flex-1">
              <div className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
                GoldDesk را نصب کنید
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--gd-text-2)" }}>
                دسترسی سریع، آفلاین، بدون نیاز به نصب اپ
              </div>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={onInstall}
                  className="text-xs bg-amber-500 hover:bg-amber-400 text-zinc-900 rounded px-3 py-1.5 font-semibold"
                >
                  نصب
                </button>
                <button
                  onClick={() => setShowInstall(false)}
                  className="text-xs px-3 py-1.5 rounded"
                  style={{ background: "var(--gd-bg-3)", color: "var(--gd-text-2)" }}
                >
                  بعداً
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
