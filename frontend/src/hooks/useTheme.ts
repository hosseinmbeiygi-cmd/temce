import { useEffect, useState } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'theme';

// Module-level listener set so every mounted instance (header toggle,
// settings page, …) stays in sync with the same underlying theme choice.
const listeners = new Set<() => void>();

function prefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

function getStoredMode(): ThemeMode {
  if (typeof window === 'undefined') return 'system';
  const t = localStorage.getItem(STORAGE_KEY);
  return t === 'light' || t === 'dark' || t === 'system' ? t : 'system';
}

function resolve(mode: ThemeMode): ResolvedTheme {
  return mode === 'system' ? (prefersDark() ? 'dark' : 'light') : mode;
}

/**
 * Theme already painted by the inline <head> script (before hydration).
 * Preferring it on first mount guarantees the hook never contradicts what
 * is already on screen, so the page does not flip light↔dark on load.
 */
function paintedTheme(): ResolvedTheme | null {
  if (typeof document === 'undefined') return null;
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'light' || t === 'dark' ? t : null;
}

function applyTheme(theme: ResolvedTheme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.setAttribute('data-theme', theme);
  root.classList.toggle('dark', theme === 'dark');

  const body = document.body;
  if (body) {
    body.classList.toggle('dark-theme', theme === 'dark');
    body.classList.toggle('light-theme', theme === 'light');
  }
}

function notifyListeners() {
  listeners.forEach((l) => l());
}

export function useTheme() {
  // ── SSR-safe initial state ──────────────────────────────────────
  // The server cannot read localStorage / matchMedia / the <head> paint,
  // so initializing state from them at render time produces different HTML
  // than the client → hydration mismatch → React regenerates the whole
  // tree on every load (the page visibly blinks off/on).
  // Instead, start from deterministic defaults (same on server & client)
  // and adopt the real preference after mount.
  const [mode, setMode] = useState<ThemeMode>('system');
  const [theme, setTheme] = useState<ResolvedTheme>('light');
  // True once we've adopted the stored/painted preference; the applyTheme
  // effect stays inert until then so it never overrides what the <head>
  // script already painted (no flash on load).
  const [ready, setReady] = useState(false);

  // Adopt the stored choice + whatever the <head> script painted before
  // hydration. Runs once after mount.
  useEffect(() => {
    const stored = getStoredMode();
    const resolved = paintedTheme() ?? resolve(stored);
    setMode(stored);
    setTheme(resolved);
    setReady(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the DOM in sync once the real theme is known (no-op on first
  // paint because the <head> script already applied it).
  useEffect(() => {
    if (!ready) return;
    applyTheme(theme);
  }, [theme, ready]);

  useEffect(() => {
    // Keep every mounted instance in sync (e.g. header toggle + settings).
    const refresh = () => {
      setMode(getStoredMode());
      setTheme(resolve(getStoredMode()));
    };
    listeners.add(refresh);

    // Keep tabs in sync when the theme is changed in another tab.
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) refresh();
    };
    window.addEventListener('storage', onStorage);

    return () => {
      listeners.delete(refresh);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  const toggleTheme = () => {
    setThemeMode(theme === 'dark' ? 'light' : 'dark');
  };

  const setThemeMode = (next: ThemeMode) => {
    const resolved = resolve(next);
    setMode(next);
    setTheme(resolved);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(resolved);
    notifyListeners();
  };

  const isDark = theme === 'dark';

  return { theme, mode, toggleTheme, setThemeMode, isDark };
}
