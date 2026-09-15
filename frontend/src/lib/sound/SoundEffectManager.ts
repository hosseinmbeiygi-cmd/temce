"use client";

/**
 * SoundEffectManager — Armor Dashboard
 * =====================================
 * Web Audio API based sound system compatible with browser Autoplay Policy.
 * - Requires a user interaction (click/touch/keydown) before any sound can play.
 * - Persisted mute + variant preference in localStorage.
 * - Triggered by PRECOMPUTATION_COMPLETED event (and optionally group completed).
 *
 * Decoupled from any other module — only depends on contracts/events.md payloads.
 * Reuses patterns from frontend/src/hooks/useNotificationSound.ts
 */

export type SoundVariant = "shot" | "finish" | "chime";
export type SoundTrigger = "PRECOMPUTATION_COMPLETED" | "PRECOMPUTATION_GROUP_COMPLETED" | "manual";

const STORAGE_KEY_MUTED = "armor-sound-muted";
const STORAGE_KEY_VARIANT = "armor-sound-variant";
const STORAGE_KEY_ENABLED = "armor-sound-enabled";
const STORAGE_KEY_VOLUME = "armor-sound-volume";

// ── Tone presets — pure Web Audio, no external files ─────────────
const PRESETS: Record<SoundVariant, number[]> = {
  // shot: sharp percussive double-tap (like armor lock)
  shot: [880, 1320],
  // finish: triumphant 3-note fanfare
  finish: [523.25, 659.25, 783.99],
  // chime: soft notification
  chime: [659.25, 830.61],
};

const PRESET_LABEL: Record<SoundVariant, string> = {
  shot: "شلیک",
  finish: "پایان",
  chime: "زنگ",
};

export interface SoundManagerState {
  enabled: boolean;
  muted: boolean;
  variant: SoundVariant;
  volume: number; // 0..1
  hasInteracted: boolean;
}

type Listener = (state: SoundManagerState) => void;

class SoundEffectManagerImpl {
  private audioCtx: AudioContext | null = null;
  private state: SoundManagerState = {
    enabled: true,
    muted: false,
    variant: "finish",
    volume: 0.35,
    hasInteracted: false,
  };
  private listeners = new Set<Listener>();
  private boundInteraction: (() => void) | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.hydrate();
      this.bindInteractionGate();
    }
  }

  // ── Persistence ──────────────────────────────────────────────
  private hydrate() {
    try {
      const muted = localStorage.getItem(STORAGE_KEY_MUTED);
      const variant = localStorage.getItem(STORAGE_KEY_VARIANT) as SoundVariant | null;
      const enabled = localStorage.getItem(STORAGE_KEY_ENABLED);
      const vol = localStorage.getItem(STORAGE_KEY_VOLUME);
      if (muted !== null) this.state.muted = muted === "true";
      if (variant && PRESETS[variant]) this.state.variant = variant;
      if (enabled !== null) this.state.enabled = enabled === "true";
      if (vol !== null) {
        const v = parseFloat(vol);
        if (!isNaN(v)) this.state.volume = Math.min(1, Math.max(0, v));
      }
      // interaction flag does NOT persist across sessions — must re-interact each load
    } catch {
      // ignore storage errors (private mode, SSR)
    }
  }

  private persist() {
    try {
      localStorage.setItem(STORAGE_KEY_MUTED, String(this.state.muted));
      localStorage.setItem(STORAGE_KEY_VARIANT, this.state.variant);
      localStorage.setItem(STORAGE_KEY_ENABLED, String(this.state.enabled));
      localStorage.setItem(STORAGE_KEY_VOLUME, String(this.state.volume));
    } catch {
      // ignore
    }
  }

  // ── Autoplay Policy gate ─────────────────────────────────────
  private bindInteractionGate() {
    if (typeof window === "undefined" || this.boundInteraction) return;
    const handler = () => {
      this.state.hasInteracted = true;
      this.notify();
      // Lazily create/resume AudioContext on first interaction
      this.ensureAudioContext();
      this.unbindInteractionGate();
    };
    this.boundInteraction = handler;
    // Capture-phase to catch any click/touch/keydown in the app
    window.addEventListener("click", handler, { once: true, capture: true });
    window.addEventListener("keydown", handler, { once: true, capture: true });
    window.addEventListener("touchstart", handler, { once: true, capture: true, passive: true });
  }

  private unbindInteractionGate() {
    if (!this.boundInteraction || typeof window === "undefined") return;
    window.removeEventListener("click", this.boundInteraction, { capture: true } as unknown as EventListenerOptions);
    window.removeEventListener("keydown", this.boundInteraction, { capture: true } as unknown as EventListenerOptions);
    window.removeEventListener("touchstart", this.boundInteraction, { capture: true } as unknown as EventListenerOptions);
    this.boundInteraction = null;
  }

  /** Call manually (e.g. from a button) to unlock audio without waiting for global gate. */
  unlock(): void {
    this.state.hasInteracted = true;
    this.ensureAudioContext();
    this.notify();
    this.unbindInteractionGate();
  }

  // ── AudioContext ─────────────────────────────────────────────
  private ensureAudioContext(): AudioContext | null {
    if (this.audioCtx) return this.audioCtx;
    if (typeof window === "undefined") return null;
    try {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return null;
      this.audioCtx = new Ctor();
      return this.audioCtx;
    } catch {
      return null;
    }
  }

  // ── Public state API ─────────────────────────────────────────
  getState(): SoundManagerState {
    return { ...this.state };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    const snap = this.getState();
    for (const l of this.listeners) {
      try {
        l(snap);
      } catch {
        // ignore
      }
    }
  }

  setEnabled(enabled: boolean) {
    this.state.enabled = enabled;
    this.persist();
    this.notify();
  }

  setMuted(muted: boolean) {
    this.state.muted = muted;
    this.persist();
    this.notify();
  }

  toggleMute() {
    this.setMuted(!this.state.muted);
  }

  setVariant(variant: SoundVariant) {
    if (!PRESETS[variant]) return;
    this.state.variant = variant;
    this.persist();
    this.notify();
  }

  setVolume(volume: number) {
    this.state.volume = Math.min(1, Math.max(0, volume));
    this.persist();
    this.notify();
  }

  // ── Playback ─────────────────────────────────────────────────
  /**
   * Play a sound. Respects muted/enabled/hasInteracted gates.
   * @param variant override preset, defaults to current variant
   * @param trigger for logging / analytics
   */
  async play(variant?: SoundVariant, _trigger: SoundTrigger = "manual"): Promise<void> {
    if (!this.state.enabled || this.state.muted) return;
    if (!this.state.hasInteracted) {
      // Autoplay policy — silently skip (will play after first interaction)
      // We do NOT queue — next eligible event will play.
      if (typeof window !== "undefined") {
        console.debug("[SoundEffectManager] blocked by Autoplay Policy — waiting for user interaction");
      }
      return;
    }

    const preset = PRESETS[variant ?? this.state.variant];
    if (!preset) return;

    const ctx = this.ensureAudioContext();
    if (!ctx) return;

    try {
      if (ctx.state === "suspended") await ctx.resume();
      const now = ctx.currentTime;
      const vol = this.state.volume;

      preset.forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const isLast = i === preset.length - 1;

        osc.type = i === 0 ? "sine" : isLast ? "triangle" : "sine";
        osc.frequency.value = freq;

        // Envelope: quick attack, exponential decay
        const t0 = now + i * 0.14;
        gain.gain.setValueAtTime(0, t0);
        gain.gain.linearRampToValueAtTime(vol, t0 + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.38);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t0);
        osc.stop(t0 + 0.4);
      });
    } catch {
      // Audio unavailable — silently ignore
    }
  }

  /** One-shot test play (used by settings UI). Bypasses muted check but still needs interaction. */
  async preview(variant: SoundVariant = this.state.variant): Promise<void> {
    const prevMuted = this.state.muted;
    const prevEnabled = this.state.enabled;
    // Temporarily force enabled/unmuted for preview
    this.state.muted = false;
    this.state.enabled = true;
    if (!this.state.hasInteracted) {
      this.unlock();
    }
    await this.play(variant, "manual");
    this.state.muted = prevMuted;
    this.state.enabled = prevEnabled;
  }

  /** Handle PRECOMPUTATION_COMPLETED event payload. */
  onPrecomputationCompleted(): void {
    void this.play(this.state.variant, "PRECOMPUTATION_COMPLETED");
  }

  /** Handle PRECOMPUTATION_GROUP_COMPLETED — optional subtle chime. */
  onGroupCompleted(group: string): void {
    // Only play a soft chime for group, not the full fanfare
    // Respect variant but use less intrusive volume via preset
    if (group === "C") {
      // C completion is effectively full completion — use finish sound
      void this.play(this.state.variant, "PRECOMPUTATION_GROUP_COMPLETED");
    } else {
      void this.play("chime", "PRECOMPUTATION_GROUP_COMPLETED");
    }
  }

  getVariantLabel(variant: SoundVariant): string {
    return PRESET_LABEL[variant] ?? variant;
  }

  getAvailableVariants(): SoundVariant[] {
    return Object.keys(PRESETS) as SoundVariant[];
  }

  // Cleanup on app teardown (not usually needed, but for HMR/tests)
  destroy() {
    this.unbindInteractionGate();
    if (this.audioCtx) {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }
    this.listeners.clear();
  }
}

// Singleton — shared across the app (Zustand-like pattern but vanilla)
let _singleton: SoundEffectManagerImpl | null = null;

export function getSoundManager(): SoundEffectManagerImpl {
  if (!_singleton) _singleton = new SoundEffectManagerImpl();
  return _singleton;
}

// Default export is the singleton getter + class for testing
export const SoundEffectManager = SoundEffectManagerImpl;
export default getSoundManager;
