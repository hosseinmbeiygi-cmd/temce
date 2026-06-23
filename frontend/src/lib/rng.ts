// ── Seeded PRNG (deterministic across server & client) ──
// Used by mock data generators to avoid React hydration mismatches.
// Math.random() produces different values on server vs client;
// a seeded LCG produces identical output on both sides.

export function createRng(seed: number) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// Fixed "now" timestamp for module-level generators (avoids Date.now() drift)
export const FIXED_NOW = new Date("2026-06-21T00:00:00+03:30");
