"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface UseNotificationSoundOptions {
  /** localStorage key for persisting mute preference. Default: "notification-sound-muted" */
  storageKey?: string;
}

interface PlayChimeOptions {
  /** If true, skips playback when document.visibilityState === "visible" (user is actively viewing the tab). Default: false */
  skipWhenVisible?: boolean;
}

/**
 * Shared hook for playing Web Audio API notification chimes.
 *
 * Manages a single AudioContext across the component lifecycle,
 * provides a mute toggle persisted in localStorage, and exposes
 * a `playChime` function to play a sequence of sine-wave tones.
 */
export function useNotificationSound(options: UseNotificationSoundOptions = {}) {
  const { storageKey = "notification-sound-muted" } = options;

  // ── Mute state (persisted across sessions) ──
  const [muted, setMuted] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(storageKey) === "true";
  });

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      localStorage.setItem(storageKey, String(next));
      return next;
    });
  }, [storageKey]);

  // ── Shared AudioContext ──
  const audioCtxRef = useRef<AudioContext | null>(null);

  const getAudioCtx = useCallback((): AudioContext | null => {
    if (audioCtxRef.current) return audioCtxRef.current;
    try {
      const AudioCtor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtor) return null;
      audioCtxRef.current = new AudioCtor();
      return audioCtxRef.current;
    } catch {
      return null;
    }
  }, []);

  // Close AudioContext on unmount
  useEffect(() => {
    return () => {
      audioCtxRef.current?.close().catch(() => {});
      audioCtxRef.current = null;
    };
  }, []);

  // ── Play chime ──
  const playChime = useCallback(
    (tones: number[], playOptions: PlayChimeOptions = {}) => {
      if (muted) return;

      // Optionally skip when user is actively viewing the tab
      if (playOptions.skipWhenVisible && document.visibilityState === "visible") {
        return;
      }

      const ctx = getAudioCtx();
      if (!ctx) return;

      // IIFE so we can use async for ctx.resume()
      (async () => {
        try {
          if (ctx.state === "suspended") await ctx.resume();
          const now = ctx.currentTime;
          tones.forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0, now + i * 0.15);
            gain.gain.linearRampToValueAtTime(0.3, now + i * 0.15 + 0.05);
            gain.gain.exponentialRampToValueAtTime(
              0.001,
              now + i * 0.15 + 0.35
            );
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + i * 0.15);
            osc.stop(now + i * 0.15 + 0.4);
          });
        } catch {
          // Audio not available — silently skip
        }
      })();
    },
    [muted, getAudioCtx]
  );

  return { muted, toggleMute, playChime };
}
