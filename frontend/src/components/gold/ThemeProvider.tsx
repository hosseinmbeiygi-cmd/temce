"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "dark" | "light" | "gold";

interface ThemeCtx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  cycle: () => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

const STORAGE_KEY = "golddesk-theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const saved = (typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null) as Theme | null;
    if (saved === "dark" || saved === "light" || saved === "gold") {
      setThemeState(saved);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // ignore
    }
  }, [theme, hydrated]);

  const setTheme = (t: Theme) => setThemeState(t);
  const cycle = () => {
    setThemeState((prev) => (prev === "dark" ? "light" : prev === "light" ? "gold" : "dark"));
  };

  return <Ctx.Provider value={{ theme, setTheme, cycle }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const c = useContext(Ctx);
  if (!c) {
    // SSR fallback
    return { theme: "dark" as Theme, setTheme: () => {}, cycle: () => {} };
  }
  return c;
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, cycle } = useTheme();
  const icons: Record<Theme, string> = { dark: "🌙", light: "☀️", gold: "✨" };
  const labels: Record<Theme, string> = { dark: "تاریک", light: "روشن", gold: "طلایی" };
  return (
    <button
      onClick={cycle}
      title={`تم فعلی: ${labels[theme]}`}
      className={`text-xs bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 rounded-lg px-3 py-1.5 transition flex items-center gap-1.5 ${className}`}
    >
      <span>{icons[theme]}</span>
      <span className="hidden sm:inline">{labels[theme]}</span>
    </button>
  );
}
