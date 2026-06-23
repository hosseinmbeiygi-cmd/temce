"use client";

import { useState, useEffect, useCallback } from "react";

type Theme = "dark" | "light";

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    if (saved === "light" || saved === "dark") {
      setThemeState(saved);
      document.body.classList.toggle("dark-theme", saved === "dark");
      document.documentElement.setAttribute("data-theme", saved);
    } else {
      document.body.classList.add("dark-theme");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  }, []);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    localStorage.setItem("theme", t);
    document.body.classList.toggle("dark-theme", t === "dark");
    document.documentElement.setAttribute("data-theme", t);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return { theme, setTheme, toggleTheme, isDark: theme === "dark" };
}
