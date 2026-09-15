"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useState } from "react";
import { getTelegramStatus } from "@/lib/goldApi";
import { subscribeGoldWS } from "@/lib/goldApi";
import { ThemeProvider, ThemeToggle } from "@/components/gold/ThemeProvider";
import { LiveSignalBanner } from "@/components/gold/LiveSignalBanner";
import { PWAProvider } from "@/components/gold/PWAProvider";
import { NativeBridge } from "@/components/gold/NativeBridge";

const TABS = [
  { href: "/gold", label: "داشبورد", exact: true, icon: "📊" },
  { href: "/gold/futures", label: "آتی IME", exact: false, icon: "⚡" },
  { href: "/gold/etf", label: "صندوق ETF", exact: false, icon: "🏦" },
  { href: "/gold/physical", label: "فیزیکی", exact: false, icon: "🪙" },
  { href: "/gold/antigravity", label: "Antigravity", exact: false, icon: "🚀" },
  { href: "/gold/chat", label: "دستیار", exact: false, icon: "💬" },
  { href: "/gold/portfolio", label: "Portfolio", exact: false, icon: "💼" },
  { href: "/gold/analytics", label: "تحلیل", exact: false, icon: "📈" },
  { href: "/gold/alerts", label: "هشدارها", exact: false, icon: "🔔" },
  { href: "/gold/backtest", label: "بک‌تست", exact: false, icon: "🧪" },
  { href: "/gold/tokens", label: "API", exact: false, icon: "🔑" },
  { href: "/gold/settings", label: "تنظیمات", exact: false, icon: "⚙️" },
];

export default function GoldLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [wsActive, setWsActive] = useState(false);

  React.useEffect(() => {
    const unsub = subscribeGoldWS(
      () => setWsActive(true),
      () => setWsActive(false),
    );
    const t = setTimeout(() => setWsActive(false), 3000);
    return () => {
      unsub();
      clearTimeout(t);
    };
  }, []);

  const { data: tg } = useQuery({
    queryKey: ["gold", "telegram", "status"],
    queryFn: getTelegramStatus,
    staleTime: 5 * 60_000,
  });

  return (
    <ThemeProvider>
    <PWAProvider>
    <NativeBridge />
    <div className="min-h-screen text-zinc-100" dir="rtl" style={{ background: "var(--gd-bg)" }}>
      {/* Header — desktop + mobile topbar */}
      <header className="sticky top-0 z-30 backdrop-blur-xl border-b" style={{ background: "var(--gd-bg-2)", borderColor: "var(--gd-border)" }}>
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-3 md:py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {/* Hamburger — mobile only */}
            <button
              onClick={() => setDrawerOpen(true)}
              className="md:hidden p-2 -mr-2 text-zinc-300 hover:text-zinc-100"
              aria-label="منو"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <div className="text-xl md:text-2xl">🥇</div>
            <div>
              <h1 className="text-base md:text-lg font-bold text-zinc-100">GoldDesk</h1>
              <p className="text-[10px] text-zinc-500 hidden sm:block">تحلیل و پایش شخصی طلا</p>
            </div>
          </div>

          {/* Tabs — desktop only */}
          <nav className="hidden md:flex gap-1 bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-1">
            {TABS.map((t) => {
              const active = t.exact ? pathname === t.href : pathname.startsWith(t.href);
              return (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`px-3 lg:px-4 py-1.5 text-sm rounded-md transition ${
                    active
                      ? "bg-amber-500/20 text-amber-300 font-semibold"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {t.label}
                </Link>
              );
            })}
          </nav>

          {/* Status indicators */}
          <div className="flex items-center gap-2 md:gap-3 text-xs">
            <ThemeToggle />
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  wsActive ? "bg-emerald-400 ws-dot" : "bg-zinc-600"
                }`}
              />
              <span className="hidden sm:inline" style={{ color: "var(--gd-text-2)" }}>{wsActive ? "Live" : "Polling"}</span>
            </div>
            {tg?.data?.is_operational && (
              <span className="text-emerald-500 hidden sm:inline">📨 TG</span>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden" onClick={() => setDrawerOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="absolute right-0 top-0 bottom-0 w-72 border-l p-4 shadow-2xl"
            style={{ background: "var(--gd-bg)", borderColor: "var(--gd-border)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🥇</span>
                <span className="font-bold text-zinc-100">GoldDesk</span>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="p-2 text-zinc-400 hover:text-zinc-100"
                aria-label="بستن"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <nav className="space-y-1">
              {TABS.map((t) => {
                const active = t.exact ? pathname === t.href : pathname.startsWith(t.href);
                return (
                  <Link
                    key={t.href}
                    href={t.href}
                    onClick={() => setDrawerOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition ${
                      active
                        ? "bg-amber-500/20 text-amber-300 font-semibold"
                        : "text-zinc-300 hover:bg-zinc-800/60"
                    }`}
                  >
                    <span className="text-lg">{t.icon}</span>
                    {t.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-8 pb-24 md:pb-8">
        <LiveSignalBanner />
        {children}
      </main>

      {/* Bottom Nav — موبایل */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 md:hidden backdrop-blur-xl border-t" style={{ background: "var(--gd-bg-2)", borderColor: "var(--gd-border)" }}>
        <div className="grid grid-cols-5 px-2 py-2">
          {TABS.map((t) => {
            const active = t.exact ? pathname === t.href : pathname.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={`flex flex-col items-center gap-1 py-1.5 text-[10px] rounded-lg transition ${
                  active ? "text-amber-300" : "text-zinc-500"
                }`}
              >
                <span className="text-base">{t.icon}</span>
                <span className="truncate max-w-full">{t.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
    </PWAProvider>
    </ThemeProvider>
  );
}
