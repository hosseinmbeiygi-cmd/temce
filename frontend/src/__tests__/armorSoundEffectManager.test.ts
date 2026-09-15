import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { SoundEffectManager } from "@/lib/sound/SoundEffectManager";

// ── Minimal Web Audio doubles ──────────────────────────────────
class FakeAudioParam {
  value = 0;
  setValueAtTime = vi.fn();
  linearRampToValueAtTime = vi.fn();
  exponentialRampToValueAtTime = vi.fn();
}

class FakeOscillator {
  type = "sine";
  frequency = new FakeAudioParam();
  connect = vi.fn();
  start = vi.fn();
  stop = vi.fn();
}

class FakeGain {
  gain = new FakeAudioParam();
  connect = vi.fn();
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = [];
  state: AudioContextState = "running";
  currentTime = 0;
  destination = {};
  oscillators: FakeOscillator[] = [];
  createOscillator = vi.fn(() => {
    const osc = new FakeOscillator();
    this.oscillators.push(osc);
    return osc;
  });
  createGain = vi.fn(() => new FakeGain());
  resume = vi.fn(async () => {});
  close = vi.fn(async () => {});
  constructor() {
    FakeAudioContext.instances.push(this);
  }
}

const PRESET_LENGTHS: Record<string, number> = { shot: 2, finish: 3, chime: 2 };

const win = window as unknown as { AudioContext?: unknown };
const originalAudioContext = win.AudioContext;

let manager: InstanceType<typeof SoundEffectManager>;

describe("SoundEffectManager", () => {
  beforeEach(() => {
    localStorage.clear();
    FakeAudioContext.instances = [];
    win.AudioContext = FakeAudioContext;
    manager = new SoundEffectManager();
  });

  afterEach(() => {
    manager.destroy();
    win.AudioContext = originalAudioContext;
    localStorage.clear();
  });

  // ── defaults & persistence ───────────────────────────────────
  it("starts enabled, unmuted with the finish variant", () => {
    const state = manager.getState();
    expect(state.enabled).toBe(true);
    expect(state.muted).toBe(false);
    expect(state.variant).toBe("finish");
    expect(state.hasInteracted).toBe(false);
  });

  it("restores mute / variant / volume from localStorage", () => {
    localStorage.setItem("armor-sound-muted", "true");
    localStorage.setItem("armor-sound-variant", "shot");
    localStorage.setItem("armor-sound-volume", "0.8");

    const fresh = new SoundEffectManager();
    const state = fresh.getState();
    expect(state.muted).toBe(true);
    expect(state.variant).toBe("shot");
    expect(state.volume).toBeCloseTo(0.8);
    fresh.destroy();
  });

  it("persists mute toggles and notifies subscribers", () => {
    const listener = vi.fn();
    manager.subscribe(listener);

    manager.setMuted(true);
    expect(manager.getState().muted).toBe(true);
    expect(localStorage.getItem("armor-sound-muted")).toBe("true");
    expect(listener).toHaveBeenCalledTimes(1);

    manager.toggleMute();
    expect(manager.getState().muted).toBe(false);
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("only accepts known sound variants", () => {
    manager.setVariant("shot");
    expect(manager.getState().variant).toBe("shot");
    expect(localStorage.getItem("armor-sound-variant")).toBe("shot");

    manager.setVariant("explosion" as never);
    expect(manager.getState().variant).toBe("shot");
  });

  it("clamps volume into 0..1", () => {
    manager.setVolume(2);
    expect(manager.getState().volume).toBe(1);
    manager.setVolume(-1);
    expect(manager.getState().volume).toBe(0);
  });

  // ── autoplay policy gate ─────────────────────────────────────
  it("does not create an AudioContext before the first interaction", async () => {
    expect(manager.getState().hasInteracted).toBe(false);

    await manager.play("finish");

    expect(FakeAudioContext.instances).toHaveLength(0);
  });

  it("unlock() satisfies the autoplay gate", () => {
    manager.unlock();

    expect(manager.getState().hasInteracted).toBe(true);
    expect(FakeAudioContext.instances).toHaveLength(1);
  });

  // ── playback ─────────────────────────────────────────────────
  it("plays every tone of the selected preset", async () => {
    manager.unlock();
    const ctx = FakeAudioContext.instances[0];

    await manager.play("finish");

    expect(ctx.oscillators).toHaveLength(PRESET_LENGTHS.finish);
    expect(ctx.oscillators[0].start).toHaveBeenCalled();
    expect(ctx.oscillators[0].stop).toHaveBeenCalled();
  });

  it("stays silent while muted or disabled", async () => {
    manager.unlock();
    const ctx = FakeAudioContext.instances[0];

    manager.setMuted(true);
    await manager.play("shot");
    expect(ctx.oscillators).toHaveLength(0);

    manager.setMuted(false);
    manager.setEnabled(false);
    await manager.play("shot");
    expect(ctx.oscillators).toHaveLength(0);
  });

  it("PRECOMPUTATION_COMPLETED plays the configured variant", async () => {
    manager.unlock();
    manager.setVariant("shot");
    const ctx = FakeAudioContext.instances[0];

    manager.onPrecomputationCompleted();
    await Promise.resolve();

    expect(ctx.oscillators).toHaveLength(PRESET_LENGTHS.shot);
  });

  it("group A/B completion uses a soft chime while C uses the full variant", async () => {
    manager.unlock();
    const ctx = FakeAudioContext.instances[0];

    manager.onGroupCompleted("A");
    await Promise.resolve();
    expect(ctx.oscillators).toHaveLength(PRESET_LENGTHS.chime);

    const afterChime = ctx.oscillators.length;
    manager.onGroupCompleted("C");
    await Promise.resolve();
    expect(ctx.oscillators.length - afterChime).toBe(PRESET_LENGTHS[manager.getState().variant]);
  });

  it("preview() plays even when muted and restores the previous state", async () => {
    manager.unlock();
    manager.setMuted(true);
    const ctx = FakeAudioContext.instances[0];

    await manager.preview("chime");

    expect(ctx.oscillators).toHaveLength(PRESET_LENGTHS.chime);
    expect(manager.getState().muted).toBe(true);
  });

  // ── metadata ─────────────────────────────────────────────────
  it("exposes available variants with Persian labels", () => {
    expect(manager.getAvailableVariants().sort()).toEqual(["chime", "finish", "shot"]);
    expect(manager.getVariantLabel("shot")).toBe("شلیک");
    expect(manager.getVariantLabel("finish")).toBe("پایان");
    expect(manager.getVariantLabel("chime")).toBe("زنگ");
  });

  it("destroy() closes the AudioContext", () => {
    manager.unlock();
    const ctx = FakeAudioContext.instances[0];

    manager.destroy();

    expect(ctx.close).toHaveBeenCalled();
  });
});
