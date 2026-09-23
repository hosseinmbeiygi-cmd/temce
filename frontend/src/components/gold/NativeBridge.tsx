"use client";

import { useEffect } from "react";

// Capacitor is an optional mobile-only integration. Keep imports opaque to
// Next's server/web bundler so the regular web build does not require the
// native plugin packages to be installed.
const loadOptional = <T,>(specifier: string): Promise<T> =>
  Function("s", "return import(s)")(specifier) as Promise<T>;

type CapacitorCore = {
  Capacitor: { isNativePlatform(): boolean; getPlatform(): string };
};
type StatusBarModule = {
  StatusBar: { setStyle(options: unknown): Promise<void>; setBackgroundColor(options: unknown): Promise<void> };
  Style: { Dark: unknown };
};
type SplashScreenModule = { SplashScreen: { hide(): Promise<void> } };
type KeyboardModule = { Keyboard: { setAccessoryBarVisible(options: unknown): Promise<void> } };
type HapticsModule = {
  Haptics: { impact(options: unknown): Promise<void> };
  ImpactStyle: { Light: unknown; Medium: unknown; Heavy: unknown };
};
type AppModule = { App: { getInfo(): Promise<{ version: string }> } };

/**
 * Bridge بین PWA و native Capacitor.
 * - در Web: noop
 * - در native: تنظیم status bar + haptics + splash screen + keyboard
 */
export function NativeBridge() {
  useEffect(() => {
    // فقط در سمت کلاینت اجرا شود
    if (typeof window === "undefined") return;

    const initNative = async () => {
      try {
        const { Capacitor } = await loadOptional<CapacitorCore>("@capacitor/core");
        const isNative = Capacitor.isNativePlatform();

        if (!isNative) return;

        // Status bar
        try {
          const { StatusBar, Style } = await loadOptional<StatusBarModule>("@capacitor/status-bar");
          await StatusBar.setStyle({ style: Style.Dark });
          await StatusBar.setBackgroundColor({ color: "#09090b" });
        } catch {
          /* noop */
        }

        // Splash screen
        try {
          const { SplashScreen } = await loadOptional<SplashScreenModule>("@capacitor/splash-screen");
          await SplashScreen.hide();
        } catch {
          /* noop */
        }

        // Keyboard
        try {
          const { Keyboard } = await loadOptional<KeyboardModule>("@capacitor/keyboard");
          await Keyboard.setAccessoryBarVisible({ isVisible: false });
        } catch {
          /* noop */
        }
      } catch (err) {
        // Capacitor not available (web)
      }
    };

    initNative();
  }, []);

  return null;
}

/**
 * Haptic feedback (فقط native).
 */
export async function hapticImpact(style: "light" | "medium" | "heavy" = "medium"): Promise<void> {
  if (typeof window === "undefined") return;
  try {
    const { Capacitor } = await loadOptional<CapacitorCore>("@capacitor/core");
    if (!Capacitor.isNativePlatform()) return;
    const { Haptics, ImpactStyle } = await loadOptional<HapticsModule>("@capacitor/haptics");
    const map = { light: ImpactStyle.Light, medium: ImpactStyle.Medium, heavy: ImpactStyle.Heavy };
    await Haptics.impact({ style: map[style] });
  } catch {
    /* noop */
  }
}

/**
 * App info.
 */
export async function getAppInfo(): Promise<{ version: string; platform: string } | null> {
  if (typeof window === "undefined") return null;
  try {
    const { Capacitor } = await loadOptional<CapacitorCore>("@capacitor/core");
    const info = await loadOptional<AppModule>("@capacitor/app").then((m) => m.App.getInfo());
    return { version: info.version, platform: Capacitor.getPlatform() };
  } catch {
    return null;
  }
}
